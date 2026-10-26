

from mcp.server.mcpserver import MCPServer
from common import parse_tool_args
import os


MCP_SERVER = MCPServer()


if __name__ == "__main__":
    testbed_path = os.environ.get("TESTBED_PATH", "")
    
    args = parse_tool_args("swebench")

    if args.http:
        MCP_SERVER.run(transport="streamable-http", port=args.port)

    else:
        MCP_SERVER.run()

    
