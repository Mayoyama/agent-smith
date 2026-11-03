"""Connect the MBPP MCP tool server to the sandbox."""

import shlex
import sys

from pathlib import Path

from sandbox.mcp_client import MCPClient
from sandbox.sandbox import Sandbox


MCP_SERVER_SCRIPT: Path = (
    Path(__file__).resolve().parent.parent / "mcp_tools_mbpp.py"
)


def connect_mbpp_tools(sandbox: Sandbox) -> MCPClient | None:
    """Start the MBPP tool server and add its tools to the sandbox.

    Runs mcp_tools_mbpp.py over stdio with the current Python interpreter. On a
    connection error, the error is printed to stderr and the client is closed.

    Args:
        sandbox: Sandbox that receives the server's tools.

    Returns:
        The connected client, or None if the connection failed.
    """

    client: MCPClient = MCPClient()
    command: str = shlex.join([sys.executable, str(MCP_SERVER_SCRIPT)])

    try:
        client.connect_stdio(command)
    except (TimeoutError, RuntimeError) as e:
        print(f"MCP connection error: {e}", file=sys.stderr)
        client.close()
        return None

    sandbox.add_tools(client)
    return client
