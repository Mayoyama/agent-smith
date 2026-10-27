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


MCP_SERVER = MCPServer()
TESTBED_PATH = os.environ.get("TESTBED_PATH", "/testbed")
OUTPUT_LIMIT = 10000


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

    if not os.path.isabs(filepath):
        filepath = os.path.join(TESTBED_PATH, filepath)

    try:
        res = swebench_tools.read_file(filepath, start_line, end_line)

    except (OSError, ValueError) as e:
        raise ToolError(str(e)) from e

    collector = OutputCollector(OUTPUT_LIMIT)
    collector.add_to_buffer(res)

    final, _ = collector.get_final_text()

    return final


if __name__ == "__main__":
    args = parse_tool_args("swebench")

    if args.http:
        MCP_SERVER.run(transport="streamable-http", port=args.port)

    else:
        MCP_SERVER.run()
