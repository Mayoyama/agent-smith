"""Connect the SWE-bench MCP tool server to the sandbox."""

import os
import shlex
import sys

from pathlib import Path

from sandbox.mcp_client import MCPClient
from sandbox.sandbox import Sandbox


MCP_SERVER_SCRIPT: Path = (
    Path(__file__).resolve().parent.parent / "mcp_tools_swebench.py"
)
MCP_CONNECT_TIMEOUT: int = 300


def connect_swebench_tools(
    sandbox: Sandbox,
    task_file: str,
) -> MCPClient | None:
    """Start the SWE-bench tool server and add its tools to the sandbox.

    Sets SWE_TASK_FILE to the task file's absolute path and unsets
    TESTBED_PATH, so the server works in the task's Docker container. Runs
    mcp_tools_swebench.py over stdio with the current Python interpreter. On a
    connection error, the error is printed to stderr and the client is closed.

    Args:
        sandbox: Sandbox that receives the server's tools.
        task_file: Path to the task JSON, passed to the server through
            SWE_TASK_FILE.

    Returns:
        The connected client, or None if the connection failed.
    """

    os.environ["SWE_TASK_FILE"] = str(Path(task_file).resolve())
    os.environ.pop("TESTBED_PATH", None)

    client: MCPClient = MCPClient()
    command: str = shlex.join([sys.executable, str(MCP_SERVER_SCRIPT)])

    try:
        client.connect_stdio(command, timeout=MCP_CONNECT_TIMEOUT)
    except (TimeoutError, RuntimeError) as e:
        print(f"MCP connection error: {e}", file=sys.stderr)
        client.close()
        return None

    sandbox.add_tools(client)
    return client
