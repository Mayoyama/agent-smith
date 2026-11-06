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
from llms.request_handler import RequestFailed, handle_request
from sandbox.sandbox import Sandbox

INPUT_TOKEN_RESERVE: int = 100
CONFIG_PATH: str = str(
    Path(__file__).resolve().parent.parent / "models_config.json"
)
Messages = list[dict[str, str]]
OLD_OBSERVATION_LIMIT: int = 600
NO_CODE_REPLY_LIMIT: int = 150


def compact_history(messages: Messages) -> None:
    """Shorten every observation of the history except the last message.

    Args:
        messages: Conversation history, changed in place.
    """

    for msg in messages[2:-1]:
        content: str = msg["content"]
        if (msg["role"] == "user" and content.startswith("Observation:")
                and len(content) > OLD_OBSERVATION_LIMIT):
            msg["content"] = (content[:OLD_OBSERVATION_LIMIT]
                              + "\n[old observation cut]")


@dataclass
class RunResult:
    """Outcome of an agent run.

    Attributes:
        answer: Final answer produced by the agent, or None if it failed.
        steps: Metrics recorded for each executed step.
        error: Reason the run stopped without an answer, or None.
        failed_requests: Requests sent by a step that failed, so that no step
            was recorded for them.
    """

    answer: str | None
    steps: list[StepMetrics]
    error: str | None
    failed_requests: int = 0


def make_generate(
    model_name: str,
    provider_url: str,
    deadline: float | None = None,
    reply_tokens: int = 400,
    request_timeout: float = 60,
) -> Callable[[Messages, int], tuple[RequestData, int]]:
    """Return generate(messages, max_tokens) bound to one model/provider.

    Args:
        model_name: Name of the model, as declared in models_config.json.
        provider_url: URL of the provider serving the model.
        deadline: A time.monotonic() timestamp after which no request is
            sent, or None for no deadline.
        reply_tokens: Maximum tokens of each reply.
        request_timeout: Seconds to wait for each response.

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
        """Send messages to the LLM, capping the output at reply_tokens.

        Args:
            messages: Conversation history sent to the model.
            max_tokens: Requested output budget (capped at reply_tokens).

        Returns:
            The response data and the number of retries needed.

        Raises:
            RequestFailed: If the deadline passed, if every API key fails or
                if the provider returns an unexpected error.
        """

        return handle_request(
            model_data, messages, request_timeout,
            max_tokens=min(max_tokens, reply_tokens), deadline=deadline)
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
    check_answer: Callable[[str], str | None] | None = None,
) -> RunResult:
    """Run the Thought -> Code -> Observation loop until an answer or a limit.

    Each reply is cut after its first code block or tool call, its code is
    run in the sandbox and the observation is sent back as the next user
    message. A reply without code is kept in the history cut to
    NO_CODE_REPLY_LIMIT characters, so that it does not use the input budget
    at every later step. The loop stops on final_answer, on a request error
    or when a limit is reached. Before each step, the next input size is
    estimated from the last input, the last reply and the last observation,
    and the loop stops if the total would come within INPUT_TOKEN_RESERVE
    tokens of max_input_tokens. With end_time, each code run gets at most the
    time left before it, and at least 1 second.

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
        check_answer: Called on each final answer; it returns a message when
            the answer must be refused, else None. A refused answer is sent
            back to the model as the observation and the loop goes on. None
            accepts every answer.

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
    failed_requests = 0
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
        compact_history(messages)
        try:
            data, retries = generate(messages, max_output_tokens - total_out)
        except RequestFailed as e:
            error = str(e)
            failed_requests = e.retries
            break
        except Exception as e:
            error = str(e)
            break
        reply = cut_after_first_block(data.text)
        total_in += data.input_tokens
        total_out += data.output_tokens
        messages.append({"role": "assistant", "content": reply})

        code = extract_code(reply)
        note = get_conversion_note(reply)
        out_tokens = data.output_tokens
        if code is None and len(reply) > NO_CODE_REPLY_LIMIT:
            reply = reply[:NO_CODE_REPLY_LIMIT] + "\n[reply cut]"
            messages[-1]["content"] = reply
            out_tokens = len(reply) // 3
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
                problem: str | None = None
                if check_answer is not None:
                    problem = check_answer(res.final_ans)
                if problem is None:
                    final = res.final_ans
                    observation = res.final_ans
                else:
                    observation = problem
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
        next_in = (data.input_tokens + out_tokens
                   + len(observation) // 3 + 50)
    return RunResult(None, steps, error, failed_requests)
