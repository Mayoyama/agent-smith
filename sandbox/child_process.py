"""Worker process that executes sandboxed code sent over a pipe."""
from multiprocessing import connection
from multiprocessing.connection import Connection
from contextlib import redirect_stdout
from typing import Any, Callable
from common import SandboxConfig, ToolCall, ToolResult
from .final_answer import FinalAnswer, send_final_answer
from .results import Results
from .security import Security
import traceback
import resource
import signal

import io


def child_process(conn: connection.Connection, config: SandboxConfig,
                  tool_names: list[str]) -> None:
    """Run received code in a persistent namespace until told to stop.

    Gives the namespace builtins with a restricted __import__, adds
    final_answer and one wrapper per tool, sets the memory limit and
    ignores Ctrl+C, then executes each message and sends back a
    Results. A None message ends the loop.

    Args:
        conn: Child end of the pipe to the parent.
        config: Sandbox config, used for the import allowlist and the
            memory limit.
        tool_names: Names of the MCP tools to expose as functions.
    """

    process_protections = Security(config)
    builtins_dict = process_protections.build_builtins_whitelist()

    namespace: dict[str, Any] = {}
    namespace["__builtins__"] = builtins_dict
    namespace["final_answer"] = send_final_answer
    namespace["__name__"] = "sandbox"
    for tool in tool_names:
        namespace[tool] = make_tool_function(conn, tool)

    bytes_limit = config.max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))

    process_protections.replace_socket()

    signal.signal(signal.SIGINT, signal.SIG_IGN)

    while True:
        msg = conn.recv()

        if msg is None:
            break

        buffer = io.StringIO()
        err = ""
        final_answer = None

        try:
            with redirect_stdout(buffer):
                exec(msg, namespace)

        except FinalAnswer as fa:
            final_answer = str(fa.value)

        except Exception:
            err = traceback.format_exc(chain=True)

        conn.send(Results(
            output=buffer.getvalue(),
            error=err,
            final_ans=final_answer,
        ))

    conn.close()


def make_tool_function(conn: Connection, tool_name: str) -> Callable[..., str]:
    """Wrap one MCP tool as a function that asks the parent to call it.

    Args:
        conn: Child end of the pipe to the parent.
        tool_name: Name of the tool to wrap.

    Returns:
        A function that sends its keyword arguments to the parent as
        a ToolCall and returns the text of the ToolResult.
    """

    def toolCall_function(**kwargs: Any) -> str:
        """Send a tool request to the parent and wait for the result.

        Args:
            **kwargs: Arguments passed straight to the tool.

        Returns:
            The tool's result as text.

        Raises:
            RuntimeError: If the tool call failed.
        """

        conn.send(ToolCall(tool_name, kwargs))

        reply = conn.recv()

        if not isinstance(reply, ToolResult):
            raise RuntimeError("unexpected reply from sandbox")

        if reply.is_error:
            raise RuntimeError(reply.text)

        return reply.text

    return toolCall_function
