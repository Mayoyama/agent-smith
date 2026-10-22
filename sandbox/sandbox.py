"""Sandbox running code in a worker process with time and memory limits."""

from common import SandboxConfig, ToolCall, ToolResult
from .results import Results
from .mcp_client import MCPClient
from .child_process import child_process
from multiprocessing.connection import Connection
import multiprocessing
import time


class Sandbox:
    """Runs code in a worker process whose namespace persists between runs.

    Attributes:
        config: Sandbox limits and allowlists.
        client: Connected MCP client, or None.
        tool_names: MCP tool names exposed in the worker.
        conn: Parent end of the pipe to the worker.
        process: The worker process.
    """

    def __init__(self, config: SandboxConfig) -> None:
        """Store the config and start the worker process.

        Args:
            config: Sandbox limits and allowlists.
        """

        self.config = config
        self.client: MCPClient | None = None
        self.tool_names: list[str] = []
        self.conn, self.process = self._start_new_process()

    def _start_new_process(self) -> tuple[Connection, multiprocessing.Process]:
        """Start a worker process connected by a new pipe.

        Returns:
            The parent end of the pipe and the started process.
        """

        parent_conn, child_conn = multiprocessing.Pipe()
        process = multiprocessing.Process(
            target=child_process,
            args=(child_conn, self.config, self.tool_names),
            daemon=True
        )

        process.start()

        child_conn.close()

        return parent_conn, process

    def restart_child_process(self) -> None:
        """Kill the current worker and start a fresh one.

        The worker's namespace is lost.
        """

        self.process.terminate()
        self.process.join()
        self.conn.close()

        self.conn, self.process = self._start_new_process()

    def run_exec(self, code: str) -> Results:
        """Run code in the worker and return its result.

        If the worker times out or dies, it is restarted and the
        result reports that the state was reset.

        Args:
            code: Python source to execute.

        Returns:
            Output, error, final answer, and timeout/reset flags.
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

    def _wait_for_result(self) -> Results:
        time_left: float = self.config.max_execution_time_seconds

        while True:
            before = time.monotonic()
            got_res = self.conn.poll(time_left)
            after = time.monotonic()

            time_left -= (after - before)

            if not got_res:
                self.restart_child_process()

                error_msg = (
                    "Execution timed out after "
                    f"{self.config.max_execution_time_seconds} seconds"
                )

                return Results(
                    error=error_msg,
                    timed_out=True,
                    state_reset=True,
                )

            try:
                msg = self.conn.recv()

            except EOFError:
                error_msg = "Sandbox process crashed, state was reset"
                self.restart_child_process()

                return Results(
                    error=error_msg,
                    state_reset=True,
                )

            if isinstance(msg, Results):
                return msg

            if isinstance(msg, ToolCall):
                if self.client is None:
                    tool_result = ToolResult(
                        text="no MCP server connected",
                        is_error=True,
                    )

                else:
                    try:
                        res = self.client.call_tool(msg.tool_name, msg.args)
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

                    return Results(
                        error=error_msg,
                        state_reset=True,
                    )

                continue

            error_msg = (
                "Unexpected message from sandbox process, state "
                "was reset"
            )

            self.restart_child_process()

            return Results(
                error=error_msg,
                state_reset=True,
            )

    def add_tools(self, client: MCPClient) -> None:
        """Store the client and tool names, then restart the worker.

        The new worker starts with one function per tool. A server
        tool named final_answer is skipped so it cannot replace the
        built-in one.

        Args:
            client: Connected MCP client.
        """

        self.client = client

        for tool in client.tools_list:
            if tool.name == "final_answer":
                continue

            self.tool_names.append(tool.name)

        self.restart_child_process()

    def get_manual(self, client: MCPClient | None = None) -> str:
        """List the functions available to sandboxed code.

        Args:
            client: Connected MCP client, or None for built-ins only.

        Returns:
            One line per function: name, parameters and description.
        """

        manual_string = ("final_answer(answer: str): submit your final answer "
                         "and end the task.\n")

        if client is not None:
            for tool in client.tools_list:
                if tool.name == "final_answer":

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

        return manual_string

    def shutdown(self) -> None:
        """Stop the worker, terminating it if it doesn't exit in time."""

        try:
            self.conn.send(None)
        except BrokenPipeError:
            pass

        self.process.join(timeout=5)

        if self.process.is_alive():
            self.process.terminate()

        self.conn.close()
