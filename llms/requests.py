

from .models import LLMModelData, RequestData
from typing import Any
import requests
import time


def send_request(
    model_data: LLMModelData,
    api_key: str,
    msgs: list[dict[str, str]],
    timeout_limit: int,
    stop: list[str] | None = None,
    max_tokens: int | None = None
) -> RequestData:
    url = model_data.base_url.rstrip('/') + '/chat/completions'
    headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
    body: dict[str, Any] = {"model": model_data.model_name, "messages": msgs}

    if stop:
        body["stop"] = stop
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    start: float = time.perf_counter()
    reply = requests.post(
        url=url, headers=headers, json=body, timeout=timeout_limit
    )
    end: float = time.perf_counter()

    request_time_in_ms: float = (end - start) * 1000
    reply_code = reply.status_code

    if reply.status_code == 200:
        json_data = reply.json()
        reply_text = json_data["choices"][0]["message"]["content"] or ""
        input_tokens = json_data["usage"]["prompt_tokens"]
        output_tokens = json_data["usage"]["completion_tokens"]

        reply_data = RequestData(
            text=reply_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_time_in_ms=request_time_in_ms,
            reply_code=reply_code,
        )

    else:
        print("DEBUG", reply.status_code, reply.text)
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
    stop: list[str] | None = None,
    max_tokens: int | None = None
) -> tuple[RequestData, int]:

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

                if 500 <= data.reply_code < 600:
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
