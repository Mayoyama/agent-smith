"""Interactive command-line REPL for testing the sandbox and MCP tools."""
from argparse import ArgumentParser
import sys
from .sandbox import Sandbox
from .results import Results
from .mcp_client import MCPClient
from .config import load_config_or_defaults


def repl() -> None:
    """Run an interactive sandbox session, optionally with MCP tools.

    Connects to an MCP server if --mcp-stdio or --mcp-server is given,
    prints the manual, then executes each input line until exit,
    EOF or final_answer().
    """

    parser = ArgumentParser(description="repl command-line argument parser")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--mcp-stdio", type=str, required=False)
    group.add_argument("--mcp-server", type=str, required=False)
    parser.add_argument("config", nargs="?", default=None)
    args = parser.parse_args()

    config = load_config_or_defaults(args.config)
    sandbox = Sandbox(config)
    mcp_client: MCPClient | None = None

    try:
        if args.mcp_stdio:
            mcp_client = MCPClient()
            mcp_client.connect_stdio(args.mcp_stdio)
            sandbox.add_tools(mcp_client)

        if args.mcp_server:
            mcp_client = MCPClient()
            mcp_client.connect_http(args.mcp_server)
            sandbox.add_tools(mcp_client)

    except (TimeoutError, RuntimeError) as e:
        print(f"Could not connect to mcp server: {e}", file=sys.stderr)

        if mcp_client:
            mcp_client.close()

        sandbox.shutdown()

        sys.exit(1)

    print(sandbox.get_manual(mcp_client))

    try:
        while True:
            try:
                line = input(">>> ")

            except EOFError:
                print()

                break

            except KeyboardInterrupt:
                print()
                continue

            if line.strip() == "exit":
                break

            res: Results = sandbox.run_exec(line)

            if res.final_ans is not None:
                print(res.final_ans)

                break

            if res.output:
                print(res.output, end="")

            if res.error:
                print(res.error)

    finally:
        if mcp_client:
            mcp_client.close()

        sandbox.shutdown()
