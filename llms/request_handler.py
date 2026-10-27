"""Send chat completion requests, with retries and API key rotation."""

from .models import LLMModelData, RequestData
from typing import Any
import requests
import time


def send_request(
    model_data: LLMModelData,
    api_key: str,
    msgs: list[dict[str, str]],
    timeout_limit: int,
    stop: tuple[str, ...] = ("<end_code>", "Observation:"),
    max_tokens: int | None = None
) -> RequestData:
    """Send one chat completion request and return the result.

    Posts the messages to <base_url>/chat/completions with the given key and
    times the request. A failed request is returned, not raised: the result
    then has an empty text, zero tokens and the HTTP status code.

    Args:
        model_data: Base URL and model name to use.
        api_key: API key for this request.
        msgs: The conversation, as dicts with "role" and "content".
        timeout_limit: Seconds to wait for the response.
        stop: Sequences at which the model stops generating.
        max_tokens: Maximum tokens the model may generate or None for no limit.

    Returns:
        The reply text, token counts, request time and status code.

    Raises:
        requests.Timeout: If no response arrives within timeout_limit.
        requests.ConnectionError: If the API can't be reached.
    """

    url = model_data.base_url.rstrip('/') + '/chat/completions'
    headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
    body: dict[str, Any] = {
        "model": model_data.model_name,
        "messages": msgs,
        "stop": list(stop),
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    start: float = time.perf_counter()
    reply = requests.post(url=url, headers=headers,
                          json=body, timeout=timeout_limit)
    end: float = time.perf_counter()

    request_time_in_ms: float = (end - start) * 1000
    reply_code = reply.status_code

    if reply.status_code == 200:
        json_data = reply.json()
        reply_text = json_data["choices"][0]["message"]["content"]
        input_tokens = json_data["usage"]["prompt_tokens"]
        output_tokens = json_data["usage"]["completion_tokens"]

        if reply_text is None:
            reply_text = ""

        reply_data = RequestData(
            text=reply_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_time_in_ms=request_time_in_ms,
            reply_code=reply_code,
        )

    else:
        reply_data = RequestData(
            text="",
            input_tokens=0,
            output_tokens=0,
            response_time_in_ms=request_time_in_ms,
            reply_code=reply_code
        )

    return reply_data


def handle_request(
    model_data: LLMModelData,
    msgs: list[dict[str, str]],
    timeout_limit: int,
    stop: tuple[str, ...] = ("<end_code>",),
    max_tokens: int | None = None
) -> tuple[RequestData, int]:
    """Send a request, retrying and switching API keys as needed.

    The keys are tried in order. A 401 or 429 moves on to the next key. A 5xx,
    timeout or connection error is retried on the same key up to 3 times, 2 s
    apart, before moving on. Every attempt after the first counts as a retry.

    Args:
        model_data: Base URL, model name and API keys to use.
        msgs: The conversation, as dicts with "role" and "content".
        timeout_limit: Seconds to wait for each response.
        stop: Sequences at which the model stops generating.
        max_tokens: Maximum tokens the model may generate or None for no limit.

    Returns:
        The successful result and the total number of retries.

    Raises:
        RuntimeError: If the API answers with any other error code, or if every
            key failed.
    """

    total_retries: int = 0

    for key in model_data.api_keys:
        retry_count: int = 0

        while True:
            try:
                data = send_request(
                    model_data, key, msgs, timeout_limit, stop, max_tokens
                )

                if data.reply_code == 200:
                    return (data, total_retries)

                if data.reply_code == 401 or data.reply_code == 429:
                    total_retries += 1

                    break

                if data.reply_code >= 500 and data.reply_code < 600:
                    retry_count += 1
                    total_retries += 1

                    if retry_count <= 3:
                        time.sleep(2)

                        continue

                    else:
                        break

                else:
                    raise RuntimeError(
                        f"handle request error: {data.reply_code}"
                    )

            except (requests.Timeout, requests.ConnectionError):
                retry_count += 1
                total_retries += 1

                if retry_count <= 3:
                    time.sleep(2)

                    continue

                else:
                    break

    raise RuntimeError("all keys failed")
