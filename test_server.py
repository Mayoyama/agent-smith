from mcp.server.mcpserver import MCPServer

server = MCPServer("test-server")

@server.tool()
def add(a: int, b: int) -> int:
    return a + b

@server.tool()
def greet(name: str) -> str:
    return f"Greetings, {name}!"

@server.tool()
def multiply(a: float, b: float) -> float:
    return a * b

if __name__ == "__main__":
    server.run()