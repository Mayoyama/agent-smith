"""Interactive command-line REPL for testing the sandbox and MCP tools."""

from argparse import ArgumentParser
import codeop
import sys
from .sandbox import Sandbox
from .results import Results
from .mcp_client import MCPClient
from .config import load_config_or_defaults


def repl() -> None:
    """Run an interactive sandbox session, optionally with MCP tools.

    Connects to an MCP server if --mcp-stdio or --mcp-server is given and
    prints the manual. Piped input (not a terminal) is run once, as a single
    entry. Typed lines are collected until codeop finds the entry complete or
    invalid (a block ends with an empty line), then run; this repeats until
    exit, EOF or final_answer(). Ctrl+C at the prompt drops the unfinished
    entry; during a run it restarts the child, so the namespace is lost.
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
        if not sys.stdin.isatty():
            read_line = sys.stdin.read()

            try:
                res: Results = sandbox.run_exec(read_line)

            except KeyboardInterrupt:
                print("interrupted, sandbox state reset")
                sandbox.restart_child_process()

                return

            if res.output:
                print(res.output, end="")

            if res.final_ans is not None:
                print(res.final_ans)

                return

            if res.error:
                print(res.error)

            return

        collected_lines: list[str] = []
        prompt_prefix = ">>> "

        while True:
            try:
                if not collected_lines:
                    prompt_prefix = ">>> "

                else:
                    prompt_prefix = "... "

                line = input(prompt_prefix)

            except EOFError:
                print()

                break

            except KeyboardInterrupt:
                print()
                collected_lines = []

                continue

            if not collected_lines and line.strip() == "exit":
                break

            collected_lines.append(line)
            source = "\n".join(collected_lines)

            try:
                ready = codeop.compile_command(source) is not None

            except SyntaxError:
                ready = True

            if not ready:
                continue

            try:
                res = sandbox.run_exec(source)

            except KeyboardInterrupt:
                print("interrupted, sandbox state reset")
                sandbox.restart_child_process()
                collected_lines = []

                continue

            collected_lines = []

            if res.output:
                print(res.output, end="")

            if res.final_ans is not None:
                print(res.final_ans)

                break

            if res.error:
                print(res.error)

    finally:
        if mcp_client:
            mcp_client.close()

        sandbox.shutdown()
