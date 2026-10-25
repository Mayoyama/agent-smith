"""Messages sent over the pipe between the sandbox and its child process."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool call, sent from the parent to the child.

    Attributes:
        text: The tool's output, or the error message.
        is_error: True if the tool call failed.
    """

    text: str
    is_error: bool


@dataclass(frozen=True)
class ToolCall:
    """Tool request, sent from the child to the parent.

    Attributes:
        tool_name: Name of the MCP tool to call.
        args: Keyword arguments for the tool.
        positional_args: Positional arguments for the tool, mapped to parameter
            names by the parent.
    """

    tool_name: str
    args: dict[str, Any]
    positional_args: tuple[Any, ...]


@dataclass(frozen=True)
class Output:
    """Piece of printed output, sent from the child to the parent.

    Attributes:
        output: Text the sandboxed code printed since the last piece.
    """

    output: str


@dataclass(frozen=True)
class ResourceRequest:
    """Resource read request, sent from the child to the parent.

    Attributes:
        uri: URI of the resource to read.
    """

    uri: str


@dataclass(frozen=True)
class PromptRequest:
    """Prompt request, sent from the child to the parent.

    Attributes:
        name: Name of the prompt.
        args: Prompt arguments, or None.
    """

    name: str
    args: dict[str, str] | None
