"""Interactive command-line REPL for testing the sandbox and MCP tools."""

from argparse import ArgumentParser
import sys
from .sandbox import Sandbox
from .results import Results
from .mcp_client import MCPClient
from .config import load_config_or_defaults


def repl() -> None:
    """Run an interactive sandbox session, optionally with MCP tools.

    Connects to an MCP server if --mcp-stdio or --mcp-server is given, prints
    the manual, then executes each input line until exit, EOF or
    final_answer(). Ctrl+C at the prompt is ignored; during a run it restarts
    the child, so the namespace is lost.
    """

    parser = ArgumentParser(description="repl command-line argument parser")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--mcp-stdio",
        type=str,
        required=False,
        help="starts MCP server, connected via stdio",
    )

    group.add_argument(
        "--mcp-server",
        type=str,
        required=False,
        help="URL of running server, connected via streamable http",
    )

    parser.add_argument(
        "config",
        type=str,
        nargs="?",
        default=None,
        help="path to JSON sandbox config file; defaults used if omitted",
    )

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

    except KeyboardInterrupt:
        print("Program terminated", file=sys.stderr)

        if mcp_client:
            mcp_client.close()

        sandbox.shutdown()

        sys.exit(130)

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

            try:
                res: Results = sandbox.run_exec(line)

            except KeyboardInterrupt:
                print("interrupted, sandbox state reset")
                sandbox.restart_child_process()

                continue

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
