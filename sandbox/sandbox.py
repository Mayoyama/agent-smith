"""Sandbox running code in a child process with time and memory limits."""

from common import (SandboxConfig, ToolCall, ToolResult,
                    Output, OutputCollector, ResourceRequest, PromptRequest)
from .results import Results
from .mcp_client import MCPClient
from .child_process import child_process
from multiprocessing.connection import Connection
from typing import Any
import multiprocessing
import time


class Sandbox:
    """Runs code in a child process whose namespace persists between runs.

    Attributes:
        config: Sandbox limits and allowlists.
        buffer_limit: Maximum characters of output and error kept per run.
        client: Connected MCP client, or None.
        support_resources: True if the connected server supports resources and
            lists at least one.
        support_prompts: True if the connected server supports prompts and
            lists at least one.
        tool_names: MCP tool names exposed in the child.
        tool_param_names: Each tool's parameter names in schema order, used to
            map positional arguments.
        conn: Parent end of the pipe to the child.
        process: The child process.
    """

    def __init__(self, config: SandboxConfig, buff_limit: int = 10000) -> None:
        """Store the config and start the child process.

        Args:
            config: Sandbox limits and allowlists.
            buff_limit: Maximum characters of output and error kept per run;
                longer text keeps its start and end.
        """

        self.buffer_limit = buff_limit
        self.config = config

        self.client: MCPClient | None = None
        self.support_resources: bool = False
        self.support_prompts: bool = False

        self.tool_names: list[str] = []
        self.tool_param_names: dict[str, list[str]] = {}
        self.conn, self.process = self._start_new_process()

    def _start_new_process(self) -> tuple[Connection, multiprocessing.Process]:
        """Start a child process connected by a new pipe.

        Returns:
            The parent end of the pipe and the started process.
        """

        parent_conn, child_conn = multiprocessing.Pipe()
        process = multiprocessing.Process(
            target=child_process,
            args=(
                child_conn,
                self.config,
                self.tool_names,
                self.support_resources,
                self.support_prompts,
            ),
            daemon=True
        )

        process.start()

        child_conn.close()

        return parent_conn, process

    def restart_child_process(self) -> None:
        """Stop the current child process and start a fresh one.

        The child's namespace is lost.
        """

        self.process.terminate()
        self.process.join()
        self.conn.close()

        self.conn, self.process = self._start_new_process()

    def run_exec(self, code: str) -> Results:
        """Run code in the child and return its result.

        If the child times out or dies, it is restarted and the result reports
        that the state was reset.

        Args:
            code: Python source to execute.

        Returns:
            Output, error, final answer, and timeout/truncation/reset flags.
        """

        try:
            self.conn.send(code)

        except BrokenPipeError as e:
            error_msg = f"Sandbox process crashed({e}), state was reset"
            self.restart_child_process()

            return Results(
                error=error_msg,
                state_reset=True,
            )

        return self._wait_for_result()

    def _run_request(
            self,
            msg: ToolCall | ResourceRequest | PromptRequest
            ) -> str:
        """Run one request from the child on the MCP client.

        Resource and prompt requests have their arguments checked first; tool
        calls are checked and mapped with handle_tool_args.

        Args:
            msg: Tool call, resource request or prompt request from the child.

        Returns:
            The result as text.

        Raises:
            RuntimeError: If no MCP server is connected or the client call
                fails.
            ValueError: If the request's arguments are invalid.
        """

        if self.client is None:
            raise RuntimeError("no MCP server connected")

        if isinstance(msg, ResourceRequest):
            if not isinstance(msg.uri, str):
                raise ValueError("uri must be a string")

            return self.client.read_resource_uri(msg.uri)

        if isinstance(msg, PromptRequest):
            if not isinstance(msg.name, str):
                raise ValueError("prompt name must be a string")

            if msg.args is not None:
                if not isinstance(msg.args, dict):
                    raise ValueError("prompt arguments must be a dict")

                for k, val in msg.args.items():
                    if not isinstance(k, str) or not isinstance(val, str):
                        raise ValueError(
                            "prompt argument names and values must be strings"
                        )

            return self.client.read_prompt_info(msg.name, msg.args)

        kwargs = self.handle_tool_args(msg)

        return self.client.call_tool(msg.tool_name, kwargs)

    def _wait_for_result(self) -> Results:
        """Wait for the child's result while serving its messages.

        Collects streamed output, runs each tool call, resource request and
        prompt request for the child with _run_request and returns when the
        Results arrive. A rejected or failed request is sent back as an error
        ToolResult. Only time spent waiting on the child counts toward the
        timeout. On a timeout, crash or unexpected message the child is
        restarted. Output and error are cut to buffer_limit.

        Returns:
            The run's result, including any partial output.
        """

        time_left: float = self.config.max_execution_time_seconds
        output_collector = OutputCollector(self.buffer_limit, True)

        while True:
            before = time.monotonic()
            got_res = self.conn.poll(time_left)
            after = time.monotonic()

            time_left -= (after - before)

            if not got_res:
                self.restart_child_process()

                error_msg = (
                    "Execution timed out after "
                    f"{self.config.max_execution_time_seconds} seconds "
                    "and output is partial"
                )

                output, truncated = output_collector.get_final_text()

                return Results(
                    output=output,
                    error=error_msg,
                    timed_out=True,
                    state_reset=True,
                    truncated=truncated,
                )

            try:
                msg = self.conn.recv()

            except EOFError:
                error_msg = "Sandbox process crashed, state was reset"
                self.restart_child_process()

                output, truncated = output_collector.get_final_text()

                return Results(
                    output=output,
                    error=error_msg,
                    state_reset=True,
                    truncated=truncated,
                )

            if isinstance(msg, Output):
                output_collector.add_to_buffer(msg.output)
                continue

            if isinstance(msg, Results):
                err_collector = OutputCollector(self.buffer_limit, True)

                err_collector.add_to_buffer(msg.error)

                err_output, err_truncated = err_collector.get_final_text()

                output, truncated = output_collector.get_final_text()

                msg.output = output
                msg.error = err_output
                msg.truncated = True if truncated or err_truncated else False

                return msg

            if isinstance(msg, (ToolCall, ResourceRequest, PromptRequest)):
                if self.client is None:
                    tool_result = ToolResult(
                        text="no MCP server connected",
                        is_error=True,
                    )

                else:
                    try:
                        res = self._run_request(msg)
                        tool_result = ToolResult(
                            text=res,
                            is_error=False,
                        )

                    except Exception as e:
                        tool_result = ToolResult(
                            text=str(e),
                            is_error=True,
                        )

                try:
                    self.conn.send(tool_result)

                except BrokenPipeError:
                    error_msg = "Sandbox process crashed, state was reset."
                    self.restart_child_process()

                    output, truncated = output_collector.get_final_text()

                    return Results(
                        output=output,
                        error=error_msg,
                        state_reset=True,
                        truncated=truncated,
                    )

                continue

            error_msg = (
                "Unexpected message from sandbox process, state "
                "was reset"
            )

            self.restart_child_process()

            output, truncated = output_collector.get_final_text()

            return Results(
                output=output,
                error=error_msg,
                state_reset=True,
                truncated=truncated,
            )

    def add_tools(self, client: MCPClient) -> None:
        """Store the client, its resource and prompt support, tool names and
        parameter names, then restart the child.

        The new child starts with one function per tool. Server tools named
        final_answer, read_resource_uri or read_prompt_info are skipped so they
        cannot replace the built-in functions.

        Args:
            client: Connected MCP client.
        """

        self.client = client

        self.support_resources = (client.support_resources
                                  and len(client.resource_list) > 0)
        self.support_prompts = (client.support_prompts
                                and len(client.prompt_list) > 0)

        for tool in client.tools_list:
            if tool.name in ("final_answer",
                             "read_resource_uri",
                             "read_prompt_info"):
                continue

            self.tool_names.append(tool.name)
            properties = tool.input_schema.get("properties", {})
            self.tool_param_names[tool.name] = list(properties.keys())

        self.restart_child_process()

    def get_manual(self, client: MCPClient | None = None) -> str:
        """List the functions, resources and prompts for sandboxed code.

        Resources and prompts are listed only if the server supports them and
        has at least one, each section followed by how to read or get one.

        Args:
            client: Connected MCP client, or None for built-ins only.

        Returns:
            One line per function, resource and prompt, with headers for the
            resource and prompt sections.
        """

        manual_string = ("final_answer(answer: str): submit your final answer "
                         "and end the task.\n")

        if client is not None:
            for tool in client.tools_list:
                if tool.name in (
                    "final_answer",
                    "read_resource_uri",
                    "read_prompt_info",
                ):

                    continue

                properties = tool.input_schema.get('properties', {})
                param_strings: list[str] = []

                for param_name, param_info in properties.items():
                    param_strings.append(
                        f"{param_name}: {param_info.get('type', 'any')}")

                desc = tool.description if tool.description is not None else ''

                tool_string = (f"{tool.name}({', '.join(param_strings)}): "
                               f"{desc}")

                manual_string += f"{tool_string}\n"

            if client.support_resources and len(client.resource_list):
                resource_string = "**Resources**:\n"

                for item in client.resource_list:
                    resource_string += f"name: {item.name}, uri: {item.uri}"

                    if not item.description:
                        resource_string += '\n'

                    else:
                        desc = f", description: {item.description}\n"
                        resource_string += desc

                resource_string += ("Read one with: "
                                    "read_resource_uri(uri: str) -> str\n")
                manual_string += resource_string

            if client.support_prompts and len(client.prompt_list):
                prompt_string = "**Prompts**:\n"

                for item in client.prompt_list:
                    prompt_string += f"name: {item.name}"

                    if item.description:
                        prompt_string += f", description: {item.description}"

                    if item.arguments:
                        arg_names = []

                        for arg in item.arguments:
                            if arg.required:
                                arg_names.append(f"{arg.name} (required)")

                            else:
                                arg_names.append(f"{arg.name}")

                        prompt_string += f", args: {', '.join(arg_names)}"

                    prompt_string += '\n'

                prompt_string += ("Get one with: read_prompt_info(name: str, "
                                  "args: dict[str, str] | None = None) -> str "
                                  "(argument values must be strings)\n")
                manual_string += prompt_string

        return manual_string

    def handle_tool_args(self, tool_call: ToolCall) -> dict[str, Any]:
        """Check a tool call and turn its arguments into keyword arguments.

        Positional arguments are matched to the tool's parameter names in
        schema order, then the keyword arguments are added.

        Args:
            tool_call: Tool request received from the child.

        Returns:
            All arguments by parameter name, ready for call_tool.

        Raises:
            ValueError: If the tool is unknown, too many positional arguments
                are given, an argument is given both positionally and by
                keyword, or a keyword is not a parameter of the tool.
        """

        if tool_call.tool_name not in self.tool_names:
            raise ValueError(f"unknown tool '{tool_call.tool_name}'")

        param_names = self.tool_param_names[tool_call.tool_name]

        positional = tool_call.positional_args

        if len(positional) > len(param_names):
            raise ValueError(
                f"{tool_call.tool_name} takes {len(param_names)} arguments "
                f"but {len(positional)} were provided")

        mapped: dict[str, Any] = {}

        for i, val in enumerate(positional):
            mapped[param_names[i]] = val

        for name, val in tool_call.args.items():
            if name in mapped:
                raise ValueError(
                    f"{name} given both as positional argument and by keyword")

            if name not in param_names:
                raise ValueError(
                    f"unknown argument '{name}' for {tool_call.tool_name}")

            mapped[name] = val

        return mapped

    def shutdown(self) -> None:
        """Stop the child, terminating it if it doesn't exit in time."""

        try:
            self.conn.send(None)
        except BrokenPipeError:
            pass

        self.process.join(timeout=5)

        if self.process.is_alive():
            self.process.terminate()

        self.conn.close()
