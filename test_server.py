"""Minimal MCP server with dummy tools for testing the sandbox."""
from mcp.server.mcpserver import MCPServer


server = MCPServer("test-server")


@server.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""

    return a + b


@server.tool()
def greet(name: str) -> str:
    """Return a greeting for the given name."""

    return f"Greetings, {name}!"


@server.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""

    return a * b


if __name__ == "__main__":
    server.run()
