"""Pydantic model describing the result of one sandbox execution."""
from pydantic import BaseModel, Field


class Results(BaseModel):
    """Outcome of one sandboxed code execution.

    Attributes:
        output: Everything the code printed to stdout.
        error: Traceback, timeout or crash message, empty if none.
        final_ans: Value passed to final_answer(), or None.
        timed_out: True if execution hit the time limit.
        truncated: True if output was cut (not used yet).
        state_reset: True if the worker was restarted and the
            namespace lost.
    """

    output: str = Field(default="")
    error: str = Field(default="")
    final_ans: str | None = Field(default=None)
    timed_out: bool = Field(default=False)
    truncated: bool = Field(default=False)
    state_reset: bool = Field(default=False)
