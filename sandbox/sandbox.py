"""Sandbox running code in a worker process with time and memory limits."""
from typing import Any, Callable
from common import SandboxConfig
from .results import Results
from .mcp_client import MCPClient
from .child_process import child_process
from multiprocessing.connection import Connection
import multiprocessing


class Sandbox:
    """Runs code in a worker process whose namespace persists between runs.

    Attributes:
        config: Sandbox limits and allowlists.
        conn: Parent end of the pipe to the worker.
        process: The worker process.
    """

    def __init__(self, config: SandboxConfig) -> None:
        """Store the config and start the worker process.

        Args:
            config: Sandbox limits and allowlists.
        """

        self.config = config
        self.conn, self.process = self._start_new_process()

    def _start_new_process(self) -> tuple[Connection, multiprocessing.Process]:
        """Start a worker process connected by a new pipe.

        Returns:
            The parent end of the pipe and the started process.
        """

        parent_conn, child_conn = multiprocessing.Pipe()
        process = multiprocessing.Process(
            target=child_process, args=(child_conn,self.config), daemon=True)
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

            
        ok = self.conn.poll(self.config.max_execution_time_seconds)

        if not ok:
            self.restart_child_process()

            error_msg = ("Execution timed out after "
                         f"{self.config.max_execution_time_seconds} seconds")

            return Results(
                error=error_msg,
                timed_out=True,
                state_reset=True,
            )

        try:
            received = self.conn.recv()

        except EOFError:
            error_msg = f"Sandbox process crashed, state was reset"
            self.restart_child_process()
            
            return Results(
                error=error_msg,
                state_reset=True,
            )

        return received

    def _make_tool_function(self, client: MCPClient, tool_name: str
                            ) -> Callable[..., str]:
        """Wrap one MCP tool as a plain function.

        Args:
            client: Connected MCP client.
            tool_name: Name of the tool to wrap.

        Returns:
            A function that forwards keyword arguments to the tool.
        """

        def tool_function(**kwargs: Any) -> str:
            """Call the wrapped MCP tool.

            Args:
                **kwargs: Arguments passed straight to the tool.

            Returns:
                The tool's result as text.
            """

            return client.call_tool(tool_name, kwargs)

        return tool_function

    #def add_tools(self, client: MCPClient) -> None:
    #    """Inject every server tool into the namespace as a function.

    #    A server tool named final_answer is skipped so it cannot
    #    replace the built-in one.

    #    Args:
    #        client: Connected MCP client.
    #    """

    #    for tool in client.tools_list:
    #        if tool.name == "final_answer":
    #            continue

    #        self.namespace[tool.name] = self._make_tool_function(
    #            client, tool.name)

    def get_manual(self, client: MCPClient | None = None) -> str:
        """List the functions available to sandboxed code.

        Args:
            client: Connected MCP client, or None for built-ins only.

        Returns:
            One line per function: name, parameters and description.
        """

        manual_string = "final_answer(answer: str): submit your final answer and end the task.\n"

        if client is not None:
            for tool in client.tools_list:
                if tool.name == "final_answer":

                    continue

                properties = tool.input_schema.get('properties', {})
                param_strings: list[str] = []

                for param_name, param_info in properties.items():
                    param_strings.append(f"{param_name}: {param_info.get('type', 'any')}")

                desc = tool.description if tool.description is not None else ''

                tool_string = f"{tool.name}({', '.join(param_strings)}): {desc}"

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
