"""Pydantic model describing the result of one sandbox execution."""

from pydantic import BaseModel, Field


class Results(BaseModel):
    """Outcome of one sandboxed code execution.

    Attributes:
        output: What the code printed to stdout, cut to the size limit if
            needed.
        error: Traceback, timeout or crash message, empty if none.
        final_ans: Value passed to final_answer(), or None.
        timed_out: True if execution hit the time limit.
        truncated: True if output or error was cut to the size limit.
        state_reset: True if the child was restarted and the namespace lost.
    """

    output: str = Field(default="")
    error: str = Field(default="")
    final_ans: str | None = Field(default=None)
    timed_out: bool = Field(default=False)
    truncated: bool = Field(default=False)
    state_reset: bool = Field(default=False)
