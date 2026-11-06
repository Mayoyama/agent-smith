"""Write the solution.json of an agent run."""

import time

from pathlib import Path
from typing import Literal

from agent.loop import RunResult
from common import SolutionOutput


def write_solution(
    task_id: str,
    benchmark: Literal["mbpp", "swebench"],
    answer: str,
    result: RunResult,
    start: float,
    system_prompt: str,
    output: str,
) -> None:
    """Build the solution of a run and write it to a file.

    The parent folders of the file are created if needed.

    Args:
        task_id: ID of the task.
        benchmark: Benchmark the task comes from.
        answer: Solution to submit: the code or the patch.
        result: Outcome of the run.
        start: time.monotonic() timestamp of the start of the run.
        system_prompt: System prompt of the run.
        output: Path of the file to write.
    """

    steps = result.steps
    solution = SolutionOutput(
        task_id=task_id,
        benchmark=benchmark,
        success=result.answer is not None,
        solution=answer,
        iterations=len(steps),
        total_requests=(sum(1 + s.retries for s in steps)
                        + result.failed_requests),
        total_input_tokens=sum(s.input_tokens for s in steps),
        total_output_tokens=sum(s.output_tokens for s in steps),
        total_time_seconds=time.monotonic() - start,
        steps=steps,
        system_prompt=system_prompt,
        error=result.error,
    )
    output_path: Path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(solution.model_dump_json(indent=2))
