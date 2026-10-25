"""Command-line options shared by the MCP tool servers."""

from argparse import ArgumentParser, Namespace


def parse_tool_args(server: str = "mbpp") -> Namespace:
    """Parse the command line of an MCP tool server.

    Every server gets --http (serve over streamable HTTP instead of stdio) and
    --port. Options only one server needs are added based on the server name.

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
