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
    answer: str | None
    steps: list[StepMetrics]
    error: str | None


def make_generate(
        model_name: str, provider_url: str
) -> Callable[[Messages, int], tuple[RequestData, int]]:
    """Return generate(messages, max_tokens) bound to one model/provider."""
    model_data = validate_llm_providers(
        "models_config.json", model_name, provider_url
    )

    def generate(
            messages: Messages, max_tokens: int
    ) -> tuple[RequestData, int]:
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
    """Run the loop. Return the answer, the steps and the error if any."""
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
