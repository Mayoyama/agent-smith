"""Agent loop: Thought -> Code -> Observation."""


import time
from typing import Callable
from dataclasses import dataclass

from agent.extract import cut_after_first_block, extract_code
from agent.observation import format_observation, no_code_observation
from common import StepMetrics
from llms.model_loader import validate_llm_providers
from llms.models import RequestData
from llms.request_handler import handle_request
from sandbox.sandbox import Sandbox


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
        model_name: str, provider_url: str
) -> Callable[[Messages, int], tuple[RequestData, int]]:
    """Return generate(messages, max_tokens) bound to one model/provider.

    Args:
        model_name: Name of the model, as declared in models_config.json.
        provider_url: URL of the provider serving the model.

    Returns:
        A function returning the LLM response data and the retry count.
    """
    model_data = validate_llm_providers(
        "models_config.json", model_name, provider_url
    )

    def generate(
            messages: Messages, max_tokens: int
    ) -> tuple[RequestData, int]:
        """Send messages to the LLM, capping the output at 400 tokens.

        Args:
            messages: Conversation history sent to the model.
            max_tokens: Requested output budget (capped at 400).

        Returns:
            The response data and the number of retries needed.
        """
        return handle_request(
            model_data, messages, 60, max_tokens=min(max_tokens, 400))
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
) -> RunResult:
    """Run the loop. Return the answer, the steps and the error if any.

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

    Returns:
        A RunResult with the answer, the steps and the error if any.
    """
    messages: Messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    steps: list[StepMetrics] = []
    error: str | None = "max_iterations"
    total_in = 0
    total_out = 0
    last_in = 0
    start = time.monotonic()
    for step in range(1, max_iterations + 1):
        if time.monotonic() - start > max_time_sec:
            error = "max_time"
            break
        if total_out >= max_output_tokens:
            error = "max_output_tokens"
            break
        if total_in + last_in > max_input_tokens:
            error = "max_input_tokens"
            break
        try:
            data, retries = generate(messages, max_output_tokens - total_out)
        except RuntimeError as e:
            error = str(e)
            break
        reply = cut_after_first_block(data.text)
        total_in += data.input_tokens
        total_out += data.output_tokens
        last_in = data.input_tokens
        messages.append({"role": "assistant", "content": reply})

        code = extract_code(reply)
        final: str | None = None
        if code is None:
            observation = no_code_observation()
        else:
            res = sandbox.run_exec(code)
            if res.final_ans is not None:
                final = res.final_ans
                observation = res.final_ans
            else:
                observation = format_observation(res, exec_timeout)

        steps.append(StepMetrics(
            step=step,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            request_time_ms=data.response_time_in_ms,
            llm_output=data.text,
            sandbox_input=code or "",
            sandbox_output=observation,
            retries=retries,
            api_url=api_url,
            model_name=model_name
        ))
        if final is not None:
            return RunResult(final, steps, None)

        messages.append(
            {"role": "user", "content": "Observation:\n" + observation}
        )
    return RunResult(None, steps, error)
