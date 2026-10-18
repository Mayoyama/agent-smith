from pydantic import BaseModel, Field


class Results(BaseModel):
    output: str = Field(default="")
    error: str = Field(default="")
    final_ans: str | None = Field(default=None)
    timed_out: bool = Field(default=False)
    truncated: bool = Field(default=False)
    state_reset: bool = Field(default=False)
