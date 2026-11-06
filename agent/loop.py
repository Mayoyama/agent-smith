"""Agent loop: Thought -> Code -> Observation."""

import time
from typing import Callable
from dataclasses import dataclass
from pathlib import Path

from agent.extract import (
    cut_after_first_block,
    extract_code,
    get_conversion_note,
    has_unclosed_block
)
from agent.observation import (
    format_observation, no_code_observation, cut_off_observation
)
from common import StepMetrics
from llms.model_loader import validate_llm_providers
from llms.models import RequestData
from llms.request_handler import handle_request
from sandbox.sandbox import Sandbox

INPUT_TOKEN_RESERVE: int = 100
CONFIG_PATH: str = str(
    Path(__file__).resolve().parent.parent / "models_config.json"
)
Messages = list[dict[str, str]]


@dataclass
class RunResult:
    """Outcome of an agent run.

    Attributes:
        answer: Final answer produced by the agent, or None if it failed.
        steps: Metrics recorded for each executed step.
        error: Reason the run stopped without an answer, or None.
    """

    answer: str | None
    steps: list[StepMetrics]
    error: str | None


def make_generate(
    model_name: str, provider_url: str, deadline: float | None = None
) -> Callable[[Messages, int], tuple[RequestData, int]]:
    """Return generate(messages, max_tokens) bound to one model/provider.

    Args:
        model_name: Name of the model, as declared in models_config.json.
        provider_url: URL of the provider serving the model.
        deadline: A time.monotonic() timestamp after which no request is
            sent, or None for no deadline.

    Returns:
        A function returning the LLM response data and the retry count.

    Raises:
        ValueError: If the provider URL is unknown or no API key is set.
        RuntimeError: If models_config.json can't be loaded.
    """

    model_data = validate_llm_providers(CONFIG_PATH, model_name, provider_url)

    def generate(
        messages: Messages, max_tokens: int
    ) -> tuple[RequestData, int]:
        """Send messages to the LLM, capping the output at 400 tokens.

        Args:
            messages: Conversation history sent to the model.
            max_tokens: Requested output budget (capped at 400).

        Returns:
            The response data and the number of retries needed.

        Raises:
            RuntimeError: If the deadline passed, if every API key fails or
                if the provider returns an unexpected error.
        """

        return handle_request(
            model_data, messages, 60, max_tokens=min(max_tokens, 400),
            deadline=deadline)
    return generate


def run_agent(
    task: str,
    system_prompt: str,
    generate: Callable[[Messages, int], tuple[RequestData, int]],
    sandbox: Sandbox,
    max_iterations: int,
    max_input_tokens: int,
    max_output_tokens: int,
    max_time_sec: int,
    exec_timeout: int,
    api_url: str,
    model_name: str,
    end_time: float | None = None,
    steps: list[StepMetrics] | None = None,
) -> RunResult:
    """Run the Thought -> Code -> Observation loop until an answer or a limit.

    Each reply is cut after its first code block or tool call, its code is
    run in the sandbox and the observation is sent back as the next user
    message. The loop stops on final_answer, on a request error or when a
    limit is reached. Before each step, the next input size is estimated
    from the last input, the last reply and the last observation, and the
    loop stops if the total would come within INPUT_TOKEN_RESERVE tokens of
    max_input_tokens. With end_time, each code run gets at most the time left
    before it, and at least 1 second.

    Args:
        task: Task given to the agent as the first user message.
        system_prompt: System prompt describing the expected behavior.
        generate: LLM call function, as returned by make_generate.
        sandbox: Sandbox used to execute the generated code.
        max_iterations: Maximum number of steps.
        max_input_tokens: Cumulative input token budget.
        max_output_tokens: Cumulative output token budget.
        max_time_sec: Wall-clock time budget in seconds.
        exec_timeout: Sandbox execution timeout, used to format
            observations.
        api_url: API URL recorded in each step's metrics.
        model_name: Model name recorded in each step's metrics.
        end_time: A time.monotonic() timestamp that caps each code run, or
            None to use only the sandbox's own timeout.
        steps: List that receives each step as it is recorded, so the caller
            keeps the steps if this function raises. A new list is used if
            None.

    Returns:
        A RunResult with the answer and the steps. Without an answer, error is
        the reason the loop stopped: max_iterations, max_time,
        max_output_tokens, max_input_tokens or the request error.
    """

    messages: Messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    if steps is None:
        steps = []
    error: str | None = "max_iterations"
    total_in = 0
    total_out = 0
    next_in = 0
    start = time.monotonic()
    for step in range(1, max_iterations + 1):
        if time.monotonic() - start > max_time_sec:
            error = "max_time"
            break
        if total_out >= max_output_tokens:
            error = "max_output_tokens"
            break
        if total_in + next_in > max_input_tokens - INPUT_TOKEN_RESERVE:
            error = "max_input_tokens"
            break
        try:
            data, retries = generate(messages, max_output_tokens - total_out)
        except Exception as e:
            error = str(e)
            break
        reply = cut_after_first_block(data.text)
        total_in += data.input_tokens
        total_out += data.output_tokens
        messages.append({"role": "assistant", "content": reply})

        code = extract_code(reply)
        note = get_conversion_note(reply)
        final: str | None = None
        if code is None:
            if has_unclosed_block(reply):
                observation = cut_off_observation()
            else:
                observation = no_code_observation()
        else:
            exec_limit: float | None = None
            if end_time is not None:
                exec_limit = max(1.0, end_time - time.monotonic())
            res = sandbox.run_exec(code, exec_limit)
            if res.final_ans is not None:
                final = res.final_ans
                observation = res.final_ans
            else:
                observation = format_observation(res, exec_timeout)

                if note is not None:
                    observation = note + '\n' + observation

        steps.append(StepMetrics(
            step=step,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            request_time_ms=data.response_time_in_ms,
            llm_output=data.text,
            sandbox_input=code or "",
            sandbox_output="" if code is None else observation,
            retries=retries,
            api_url=api_url,
            model_name=model_name
        ))
        if final is not None:
            return RunResult(final, steps, None)

        messages.append(
            {"role": "user", "content": "Observation:\n" + observation}
        )
        next_in = (data.input_tokens + data.output_tokens
                   + len(observation) // 3 + 50)
    return RunResult(None, steps, error)
