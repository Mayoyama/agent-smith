"""Messages sent over the pipe between the sandbox and its worker."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool call, sent from the parent to the worker.

    Attributes:
        text: The tool's output, or the error message.
        is_error: True if the tool call failed.
    """

    text: str
    is_error: bool


@dataclass(frozen=True)
class ToolCall:
    """Tool request, sent from the worker to the parent.

    Attributes:
        tool_name: Name of the MCP tool to call.
        args: Keyword arguments for the tool.
    """

    tool_name: str
    args: dict[str, Any]
