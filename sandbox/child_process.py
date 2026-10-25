"""Child process that executes sandboxed code sent over a pipe."""

from multiprocessing import connection
from multiprocessing.connection import Connection
from contextlib import redirect_stdout
from typing import Any, Callable
from common import (SandboxConfig, ToolCall, ToolResult,
                    ResourceRequest, PromptRequest)
from .final_answer import FinalAnswer, send_final_answer
from .results import Results
from .security import Security
from .output_stream import OutputStreamer
import traceback
import resource
import signal


def child_process(conn: connection.Connection, config: SandboxConfig,
                  tool_names: list[str], supports_resources: bool,
                  supports_prompts: bool) -> None:
    """Run received code in a persistent namespace until told to stop.

    Gives the namespace restricted builtins, adds final_answer, one wrapper per
    tool and, if the server supports them, the resource and prompt functions,
    sets the memory and file size limits, blocks network access and ignores
    Ctrl+C. Each message is checked with the AST check and executed, with
    printed output streamed to the parent, then answered with a Results. A None
    message ends the loop.

    Args:
        conn: Child end of the pipe to the parent.
        config: Sandbox config, used for the import and directory allowlists
            and the memory limit.
        tool_names: Names of the MCP tools to expose as functions.
        supports_resources: Add the read_resource_uri function.
        supports_prompts: Add the read_prompt_info function.
    """

    process_protections = Security(config)
    builtins_dict = process_protections.build_builtins_whitelist()

    namespace: dict[str, Any] = {}
    namespace["__builtins__"] = builtins_dict
    namespace["final_answer"] = send_final_answer
    namespace["__name__"] = "sandbox"

    for tool in tool_names:
        namespace[tool] = make_tool_function(conn, tool)

    if supports_resources:
        namespace["read_resource_uri"] = make_resource_function(conn)

    if supports_prompts:
        namespace["read_prompt_info"] = make_prompt_function(conn)

    bytes_limit = config.max_memory_mb * 1024 * 1024
    max_file_bytes = 100 * 1024 * 1024

    resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))
    resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_bytes, max_file_bytes))

    process_protections.replace_socket()

    signal.signal(signal.SIGINT, signal.SIG_IGN)

    while True:
        msg = conn.recv()

        if msg is None:
            break

        buffer = OutputStreamer(conn)
        err = ""
        final_answer = None

        try:
            with redirect_stdout(buffer):
                process_protections.ast_parse(msg)
                exec(msg, namespace)

        except FinalAnswer as fa:
            final_answer = str(fa.value)

        except Exception:
            err = traceback.format_exc(chain=True)

        finally:
            buffer.send_remaining()

        conn.send(Results(
            output="",
            error=err,
            final_ans=final_answer,
        ))

    conn.close()


def make_resource_function(conn: Connection) -> Callable[[str], str]:
    """Build the read_resource_uri function for the sandbox namespace.

    Args:
        conn: Child end of the pipe to the parent.

    Returns:
        A function that sends a ResourceRequest to the parent and returns the
        text of the ToolResult.
    """

    def read_resource(uri: str) -> str:
        """Ask the parent to read a resource and wait for the result.

        Args:
            uri: URI of the resource, as listed in the manual.

        Returns:
            The resource's contents as text.

        Raises:
            RuntimeError: If reading failed or the reply was unexpected.
        """

        conn.send(ResourceRequest(uri))

        reply = conn.recv()

        if not isinstance(reply, ToolResult):
            raise RuntimeError("unexpected reply from sandbox")

        if reply.is_error:
            raise RuntimeError(reply.text)

        return reply.text

    return read_resource


def make_prompt_function(conn: Connection) -> Callable[[str], str]:
    """Build the read_prompt_info function for the sandbox namespace.

    Args:
        conn: Child end of the pipe to the parent.

    Returns:
        A function that sends a PromptRequest to the parent and returns the
        text of the ToolResult.
    """

    def read_prompt(name: str, args: dict[str, str] | None = None) -> str:
        """Ask the parent to get a prompt and wait for the result.

        Args:
            name: Name of the prompt, as listed in the manual.
            args: Prompt arguments as strings, or None.

        Returns:
            The prompt's messages as text, one "role: text" line each.

        Raises:
            RuntimeError: If getting the prompt failed or the reply was
                unexpected.
        """

        conn.send(PromptRequest(name, args))

        reply = conn.recv()

        if not isinstance(reply, ToolResult):
            raise RuntimeError("unexpected reply from sandbox")

        if reply.is_error:
            raise RuntimeError(reply.text)

        return reply.text

    return read_prompt


def make_tool_function(conn: Connection, tool_name: str) -> Callable[..., str]:
    """Wrap one MCP tool as a function that asks the parent to call it.

    Args:
        conn: Child end of the pipe to the parent.
        tool_name: Name of the tool to wrap.

    Returns:
        A function that sends its positional and keyword arguments to the
        parent as a ToolCall and returns the text of the ToolResult.
    """

    def toolCall_function(*args: Any, **kwargs: Any) -> str:
        """Send a tool request to the parent and wait for the result.

        Args:
            *args: Positional arguments, mapped to parameter names by the
                parent.
            **kwargs: Keyword arguments for the tool.

        Returns:
            The tool's result as text.

        Raises:
            RuntimeError: If the parent rejected the arguments, the tool call
                failed, or the reply was unexpected.
        """

        conn.send(ToolCall(tool_name, kwargs, args))

        reply = conn.recv()

        if not isinstance(reply, ToolResult):
            raise RuntimeError("unexpected reply from sandbox")

        if reply.is_error:
            raise RuntimeError(reply.text)

        return reply.text

    return toolCall_function
