"""Agent loop: Thought -> Code -> Observation."""


import time

from typing import Callable

from agent.extract import cut_after_first_block, extract_code
from agent.observation import format_observation, no_code_observation
from llms.model_loader import validate_llm_providers
from llms.models import RequestData
from llms.request_handler import handle_request
from sandbox.sandbox import Sandbox


Messages = list[dict[str, str]]


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
    exec_timeout: int
) -> str | None:
    """Run the loop. Return the final answer, or None if never submitted."""
    messages: Messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    total_in = 0
    total_out = 0
    last_in = 0
    start = time.monotonic()
    for step in range(1, max_iterations + 1):
        if (
            time.monotonic() - start > max_time_sec
            or total_out >= max_output_tokens
            or total_in + last_in > max_input_tokens
        ):
            break
        print("DEBUG step", step, "in/out", total_in, total_out)
        data, retries = generate(messages, max_output_tokens - total_out)
        reply = cut_after_first_block(data.text)
        total_in += data.input_tokens
        total_out += data.output_tokens
        last_in = data.input_tokens
        print("DEBUG tokens", data.input_tokens, data.output_tokens)
        print("DEBUG text", repr(data.text[:300]))
        messages.append({"role": "assistant", "content": reply})

        code = extract_code(reply)
        if code is None:
            observation = no_code_observation()
        else:
            res = sandbox.run_exec(code)
            if res.final_ans is not None:
                return res.final_ans
            observation = format_observation(res, exec_timeout)

        messages.append(
            {"role": "user", "content": "Observation:\n" + observation}
        )
    return None
