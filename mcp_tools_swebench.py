"""MCP server with the SWE-bench tools.

Relative file paths are resolved from TESTBED_PATH (/testbed if it is unset).
Runs over stdio by default, or over streamable HTTP with --http
(http://127.0.0.1:PORT/mcp, port 8000 unless --port is given).
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import swebench_tools
from common import parse_tool_args, OutputCollector
import os


LIST_TIMEOUT_LIMIT: int = 20
EXEC_TIMEOUT_LIMIT: int = 30
OUTPUT_LIMIT: int = 10000
TESTBED_PATH = os.environ.get("TESTBED_PATH", "/testbed")
MCP_SERVER = MCPServer()
LOCAL_WORKSPACE = swebench_tools.LocalWorkspace(TESTBED_PATH)


def get_absolute_path(filepath: str) -> str:
    if not os.path.isabs(filepath):
        filepath = os.path.join(TESTBED_PATH, filepath)

    return os.path.normpath(filepath)


def get_truncated_text(text: str) -> str:
    collector = OutputCollector(OUTPUT_LIMIT)
    collector.add_to_buffer(text)

    final, _ = collector.get_final_text()

    return final


@MCP_SERVER.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read a range of lines from a file, numbered like cat -n.

    Args:
        filepath: Path to the file, absolute or relative to the repository
            root.
        start_line: First line to read, starting at 1.
        end_line: Last line to read. If it is past the end of the file, the
            file is read to the end and a note gives its line count.

    Returns:
        One "<line_number>: <line_content>" line per line read. Long output
        keeps its start and end, with a marker saying how much was cut.

    Raises:
        ToolError: If the line range is invalid or the file can't be read.
    """

    abs_path = get_absolute_path(filepath)

    try:
        res = swebench_tools.read_file(
            LOCAL_WORKSPACE,
            abs_path,
            start_line,
            end_line
        )

    except (OSError, ValueError) as e:
        raise ToolError(str(e)) from e

    return get_truncated_text(res)


@MCP_SERVER.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    abs_path = get_absolute_path(filepath)

    try:
        res_line, new_content = swebench_tools.edit_file(
            LOCAL_WORKSPACE, abs_path, old_str, new_str)

    except (OSError, ValueError) as e:
        raise ToolError(str(e)) from e

    if filepath.endswith(".py"):
        try:
            compile(new_content, abs_path, "exec")

        except SyntaxError as e:
            res_line += (f"\nWARNING: file now has syntax error at line "
                         f"{e.lineno}: {e.msg}")

        except ValueError as e:
            res_line += f"\nWARNING: file is not valid python source: {e}"

    return res_line


@MCP_SERVER.tool()
def list_files(directory: str, pattern: str) -> str:
    abs_path = get_absolute_path(directory)

    try:
        res = swebench_tools.list_files(
            LOCAL_WORKSPACE,
            abs_path,
            pattern,
            LIST_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    return get_truncated_text(res)


@MCP_SERVER.tool()
def run_command(command: str, workdir: str) -> str:
    abs_path = get_absolute_path(workdir)

    try:
        res = swebench_tools.run_command(
            LOCAL_WORKSPACE,
            command,
            abs_path,
            EXEC_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    res_str = (f"exit code:\n{res.exit_code}\nstdout:\n"
               f"{res.std_out}\nstderr:\n{res.std_err}")

    return get_truncated_text(res_str)


if __name__ == "__main__":
    args = parse_tool_args("swebench")

    if args.http:
        MCP_SERVER.run(transport="streamable-http", port=args.port)

    else:
        MCP_SERVER.run()
