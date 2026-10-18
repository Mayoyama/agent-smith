from concurrent.futures import Future
from typing import Any
import os
import sys
import shlex
import asyncio
import threading

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

except ImportError as e:
    print(e)
    sys.exit(1)


class MCPClient:
    """Keeps one MCP connection open in a background event loop."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.session: ClientSession | None = None
        self.tools_list: list[Any] = []
        self._thread_holder: Future | None = None
        self._ready_signal = threading.Event()
        self._stop_signal: asyncio.Event | None = None
        self._error: BaseException | None = None

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def connect_stdio(self, command: str) -> None:
        parts = shlex.split(command)
        params = StdioServerParameters(
            command=parts[0],
            args=parts[1:],
            env=dict(os.environ),
        )

        self.thread.start()
        self._thread_holder = asyncio.run_coroutine_threadsafe(
            self._hold_connection(params), self.loop)

        if not self._ready_signal.wait(timeout=30):
            raise TimeoutError("MCP server did not start in time")

        if self._error is not None:
            raise RuntimeError(f"MCP connection failure: {self._error}")

    async def _hold_connection(self, params: StdioServerParameters) -> None:
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tool_list = await session.list_tools()
                    self.tools_list = tool_list.tools
                    self.session = session

                    self._stop_signal = asyncio.Event()
                    self._ready_signal.set()

                    await self._stop_signal.wait()  # keeps connection open

        except Exception as e:
            self._error = e
            self._ready_signal.set()

    def connect_http(self, url: str) -> None:
        self.thread.start()
        self._thread_holder = asyncio.run_coroutine_threadsafe(
            self._hold_http(url), self.loop)

        if not self._ready_signal.wait(timeout=30):
            raise TimeoutError("MCP server did not start in time")

        if self._error is not None:
            raise RuntimeError(f"MCP connection failure: {self._error}")

    async def _hold_http(self, url: str) -> None:
        try:
            async with streamable_http_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tool_list = await session.list_tools()
                    self.tools_list = tool_list.tools
                    self.session = session

                    self._stop_signal = asyncio.Event()
                    self._ready_signal.set()

                    await self._stop_signal.wait()

        except Exception as e:
            self._error = e
            self._ready_signal.set()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if self.session is None:
            raise RuntimeError("Session not connected")

        coroutine = self.session.call_tool(name, arguments)
        pending_result = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        result = pending_result.result(timeout=300)

        parts: list[str] = []

        for item in result.content:
            if item.type == "text":
                parts.append(item.text)

            else:
                parts.append(f"[{item.type} content]")

        text = "\n".join(parts)

        if result.is_error:
            return f"Tool error: {text}"

        return text

    def close(self) -> None:
        if self._stop_signal is not None:
            try:
                self.loop.call_soon_threadsafe(self._stop_signal.set)

                if self._thread_holder is not None:
                    self._thread_holder.result(timeout=5)

            except Exception as e:
                print(e)

        self.loop.call_soon_threadsafe(self.loop.stop)

        if self.thread.is_alive():
            self.thread.join(timeout=5)
