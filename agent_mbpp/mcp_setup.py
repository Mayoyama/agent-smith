import shlex
import sys

from pathlib import Path

from sandbox.mcp_client import MCPClient
from sandbox.sandbox import Sandbox


MCP_SERVER_SCRIPT: Path = (
    Path(__file__).resolve().parent.parent / "mcp_tools_mbpp.py"
)


def connect_mbpp_tools(sandbox: Sandbox) -> MCPClient | None:
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
