"""Command-line parsers for the agents and the MCP tool servers."""

from argparse import ArgumentParser, Namespace


def setup_agent_parser() -> ArgumentParser:
    """Build the command-line parser shared by both agents.

    Returns:
        A parser with the required options --task-file, --output, --model-name
        and --provider-url.
    """

    parser = ArgumentParser(description="argument parser")
    parser.add_argument(
        "--task-file",
        type=str,
        required=True,
        help="path to the task JSON",
    )

    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="path where solution.json gets written",
    )

    parser.add_argument(
        "--model-name",
        type=str,
        required=True,
        help="model/name",
    )

    parser.add_argument(
        "--provider-url",
        type=str,
        required=True,
        help="URL for the api",
    )

    return parser


def parse_tool_args(server: str = "mbpp") -> Namespace:
    """Parse the command line of an MCP tool server.

    Both servers get --http (serve over streamable HTTP instead of stdio) and
    --port; the server name is only checked.

    Args:
        server: Which server is starting, "mbpp" or "swebench".

    Returns:
        The parsed arguments.

    Raises:
        ValueError: If server is not a known server name.
    """

    if server not in ("mbpp", "swebench"):
        raise ValueError(f"invalid server value: {server}")

    tools_parser = ArgumentParser()

    tools_parser.add_argument(
        "--http",
        action="store_true",
        required=False,
        help="set to run server via streamable http rather than stdio",
    )

    tools_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        required=False,
        help="set port for http connection (http://127.0.0.1:PORT/mcp)",
    )

    return tools_parser.parse_args()
