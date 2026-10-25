"""Sync MCP client running its async session in a background thread."""

from concurrent.futures import Future
from typing import Any
import os
import sys
import shlex
import asyncio
import threading

try:
    from mcp import ClientSession, StdioServerParameters, InitializeResult
    from mcp.types import TextResourceContents
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

except ImportError as e:
    print(e)
    sys.exit(1)


class MCPClient:
    """Synchronous wrapper around an async MCP client session.

    The session runs on an event loop in a background daemon thread, so sandbox
    code can call tools, read resources and get prompts without using asyncio.

    Attributes:
        session: The active MCP ClientSession, or None.
        support_resources: True if the server supports resources.
        support_prompts: True if the server supports prompts.
        tools_list: Tools reported by the server after connecting.
        resource_list: Resources reported by the server, empty if unsupported.
        prompt_list: Prompts reported by the server, empty if unsupported.
    """

    def __init__(self) -> None:
        """Create the event loop, thread and connection signals."""

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)

        self.session: ClientSession | None = None

        self.support_resources: bool = False
        self.support_prompts: bool = False

        self.tools_list: list[Any] = []
        self.resource_list: list[Any] = []
        self.prompt_list: list[Any] = []

        self._thread_holder: Future | None = None
        self._ready_signal = threading.Event()
        self._stop_signal: asyncio.Event | None = None
        self._error: BaseException | None = None

    def _run_loop(self) -> None:
        """Run the event loop forever in the background thread."""

        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def connect_stdio(self, command: str) -> None:
        """Start an MCP server as a subprocess and connect over stdio.

        Args:
            command: Shell command that launches the server.

        Raises:
            TimeoutError: If the connection is not ready within 30 s.
            RuntimeError: If connecting or initialising fails.
        """

        parts = shlex.split(command)
        params = StdioServerParameters(
            command=parts[0],
            args=parts[1:],
            env=dict(os.environ),
        )

        self._thread.start()
        self._thread_holder = asyncio.run_coroutine_threadsafe(
            self._hold_connection(params), self._loop)

        if not self._ready_signal.wait(timeout=30):
            raise TimeoutError("MCP server did not start in time")

        if self._error is not None:
            raise RuntimeError(f"MCP connection failure: {self._error}")

    async def _hold_connection(self, params: StdioServerParameters) -> None:
        """Open a stdio session, list tools, then wait for close().

        Resources and prompts are also listed if the server supports them.

        Args:
            params: How to launch the server process.
        """

        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    init_res = await session.initialize()

                    await self.handle_resources_prompts(init_res, session)

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
        """Connect to an MCP server over streamable HTTP.

        Args:
            url: Server endpoint URL.

        Raises:
            TimeoutError: If the connection is not ready within 30 s.
            RuntimeError: If connecting or initialising fails.
        """

        self._thread.start()
        self._thread_holder = asyncio.run_coroutine_threadsafe(
            self._hold_http(url), self._loop)

        if not self._ready_signal.wait(timeout=30):
            raise TimeoutError("MCP server did not start in time")

        if self._error is not None:
            raise RuntimeError(f"MCP connection failure: {self._error}")

    async def _hold_http(self, url: str) -> None:
        """Open an HTTP session, list tools, then wait for close().

        Resources and prompts are also listed if the server supports them.

        Args:
            url: Server endpoint URL.
        """

        try:
            async with streamable_http_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    init_res = await session.initialize()

                    await self.handle_resources_prompts(init_res, session)

                    tool_list = await session.list_tools()
                    self.tools_list = tool_list.tools
                    self.session = session

                    self._stop_signal = asyncio.Event()
                    self._ready_signal.set()

                    await self._stop_signal.wait()

        except Exception as e:
            self._error = e
            self._ready_signal.set()

    async def handle_resources_prompts(
            self,
            init_result: InitializeResult,
            session: ClientSession
            ) -> None:
        """Record resource and prompt support and list the supported ones.

        Args:
            init_result: Result of session.initialize(), with the server's
                capabilities.
            session: The initialised session used to list them.
        """

        self.support_resources = init_result.capabilities.resources is not None

        self.support_prompts = init_result.capabilities.prompts is not None

        if self.support_resources:
            resource_list = await session.list_resources()
            self.resource_list = resource_list.resources

        if self.support_prompts:
            prompt_list = await session.list_prompts()
            self.prompt_list = prompt_list.prompts

    def read_resource_uri(self, uri: str) -> str:
        """Read a resource from the server and return its contents as text.

        Args:
            uri: URI of the resource.

        Returns:
            The text contents, one per line; binary contents are replaced by a
            "[Binary content (type=...)]" placeholder.

        Raises:
            RuntimeError: If the session is not connected or the server does
                not support resources.
        """

        if self.session is None:
            raise RuntimeError("session not connected")

        if not self.support_resources:
            raise RuntimeError("resources not supported")

        coroutine = self.session.read_resource(uri)
        pend_result = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        result = pend_result.result(timeout=300)

        resources = ""

        for resource in result.contents:
            if isinstance(resource, TextResourceContents):
                resources += (f"Text content: {resource.text}\n")

            else:
                mtype = (resource.mime_type
                         if resource.mime_type is not None
                         else "unknown")

                resources += (f"[Binary content (type={mtype})]\n")

        return resources

    def read_prompt_info(self, name: str, args: dict[str, str] | None) -> str:
        """Get a prompt from the server and return its messages as text.

        Args:
            name: Name of the prompt.
            args: Prompt arguments as strings, or None.

        Returns:
            One "role: text" line per message; non-text content is replaced by
            a "[Non-text content (type=...)]" placeholder.

        Raises:
            RuntimeError: If the session is not connected or the server does
                not support prompts.
        """

        if self.session is None:
            raise RuntimeError("session not connected")

        if not self.support_prompts:
            raise RuntimeError("prompts not supported")

        coroutine = self.session.get_prompt(name, args)
        pend_result = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        result = pend_result.result(timeout=300)

        prompts = ""

        for prompt in result.messages:
            if prompt.content.type == "text":
                prompts += (
                    f"{prompt.role}: {prompt.content.text}\n"
                )

            else:
                mtype = prompt.content.type
                prompts += (
                    f"{prompt.role}: [Non-text content (type={mtype})]\n")

        return prompts

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the server and return its result as text.

        Args:
            name: Tool name.
            arguments: Keyword arguments for the tool.

        Returns:
            The text content joined together.

        Raises:
            RuntimeError: If the session is not connected or the server flagged
                the call as an error.
        """

        if self.session is None:
            raise RuntimeError("session not connected")

        coroutine = self.session.call_tool(name, arguments)
        pend_result = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        result = pend_result.result(timeout=300)

        parts: list[str] = []

        for item in result.content:
            if item.type == "text":
                parts.append(item.text)

            else:
                parts.append(f"[{item.type} content]")

        text = "\n".join(parts)

        if result.is_error:
            raise RuntimeError(f"Tool error: {text}")

        return text

    def close(self) -> None:
        """Signal the session to close, then stop the loop and thread."""

        if self._stop_signal is not None:
            try:
                self._loop.call_soon_threadsafe(self._stop_signal.set)

                if self._thread_holder is not None:
                    self._thread_holder.result(timeout=5)

            except Exception as e:
                print(e)

        self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread.is_alive():
            self._thread.join(timeout=5)
