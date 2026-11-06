"""Send chat completion requests, with retries and API key rotation."""

from .models import LLMModelData, RequestData
from typing import Any
import requests
import time


DEFAULT_WAIT: float = 60
MAX_WAIT: float = 60
MAX_RETRIES: int = 3


def get_retry_after_value(reply: requests.Response) -> float | None:
    """Get how long a rate-limited provider asks the client to wait.

    Reads the retry-after header in seconds (Groq), or else the retryDelay of
    the RetryInfo entry in the JSON error body (Gemini, e.g. "44s").

    Args:
        reply: Response of a failed request.

    Returns:
        The wait in seconds, or None if the response gives none.
    """

    val: float | None

    retry_after = reply.headers.get("retry-after")

    if isinstance(retry_after, str):
        try:
            val = float(retry_after)

            return val

        except ValueError:
            pass

    try:
        reply_data = reply.json()

        if isinstance(reply_data, list):
            if not reply_data:
                return None

            reply_data = reply_data[0]

        if not isinstance(reply_data, dict):
            return None

        err = reply_data.get("error")

        if not isinstance(err, dict):
            return None

        details = err.get("details")

        if not isinstance(details, list):
            return None

        for item in details:
            if not isinstance(item, dict):
                continue

            delay = item.get("retryDelay")

            if isinstance(delay, str) and delay:
                try:
                    ans = float(delay.rstrip("s"))

                    return ans

                except ValueError:
                    pass

    except ValueError:
        return None

    return None


def time_left(deadline: float | None) -> float:
    """Get the seconds left before a deadline.

    Args:
        deadline: A time.monotonic() timestamp, or None for no deadline.

    Returns:
        The seconds left (negative once passed), or infinity without deadline.
    """

    if deadline is None:
        return float("inf")

    return deadline - time.monotonic()


def sleep_until(seconds: float, deadline: float | None) -> None:
    """Sleep, but never past the deadline.

    Args:
        seconds: Wanted sleep time in seconds.
        deadline: A time.monotonic() timestamp, or None for no deadline.
    """

    time.sleep(max(0.0, min(seconds, time_left(deadline))))


def send_request(
    model_data: LLMModelData,
    api_key: str,
    msgs: list[dict[str, str]],
    timeout_limit: float,
    stop: tuple[str, ...] = ("<end_code>", "Observation:"),
    max_tokens: int | None = None,
) -> RequestData:
    """Send one chat completion request and return the result.

    Posts the messages to <base_url>/chat/completions with the given key and
    times the request. Reply content sent as a list of parts is joined from
    its text parts. A failed request is returned, not raised: the result then
    has an empty text, zero tokens, the HTTP status code and the wait the
    provider asks for, if any. A 200 reply that can't be parsed is returned
    with code 502, so it is retried like a server error.

    Args:
        model_data: Base URL and model name to use.
        api_key: API key for this request.
        msgs: The conversation, as dicts with "role" and "content".
        timeout_limit: Seconds to wait for the response.
        stop: Sequences at which the model stops generating.
        max_tokens: Maximum tokens the model may generate or None for no limit.

    Returns:
        The reply text, token counts, request time, status code and, for a
        failed request, the requested wait.

    Raises:
        requests.RequestException: If the request can't be completed, e.g.
            no response within timeout_limit or the API can't be reached.
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
        try:
            json_data = reply.json()
            reply_text = json_data["choices"][0]["message"].get("content")
            input_tokens = json_data["usage"]["prompt_tokens"]
            output_tokens = json_data["usage"]["completion_tokens"]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return RequestData(
                text="",
                input_tokens=0,
                output_tokens=0,
                response_time_in_ms=request_time_in_ms,
                reply_code=502,
            )

        if isinstance(reply_text, list):
            reply_text = "".join(
                part.get("text", "") for part in reply_text
                if part.get("type") == "text"
            )

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
        val: float | None = get_retry_after_value(reply)

        reply_data = RequestData(
            text="",
            input_tokens=0,
            output_tokens=0,
            response_time_in_ms=request_time_in_ms,
            reply_code=reply_code,
            retry_after=val,
        )

    return reply_data


def handle_request(
    model_data: LLMModelData,
    msgs: list[dict[str, str]],
    timeout_limit: float,
    stop: tuple[str, ...] = ("<end_code>", "Observation:"),
    max_tokens: int | None = None,
    deadline: float | None = None,
) -> tuple[RequestData, int]:
    """Send a request, retrying and switching API keys as needed.

    The keys are tried in order. A 401, 402 or 403 drops the key. A 429 moves
    on to the next key at once. When every key has been tried, the keys that
    were rate limited are retried after the shortest wait the providers gave
    (DEFAULT_WAIT if none, at most MAX_WAIT), for at most MAX_RETRIES waits. A
    5xx (including an unreadable 200 reply) or any request error, such as a
    timeout, is retried on the same key up to 3 times, 2 s apart, before
    moving on. Every attempt after the first counts as a retry.
    Timeouts and waits never go past the deadline.

    Args:
        model_data: Base URL, model name and API keys to use.
        msgs: The conversation, as dicts with "role" and "content".
        timeout_limit: Seconds to wait for each response.
        stop: Sequences at which the model stops generating.
        max_tokens: Maximum tokens the model may generate or None for no limit.
        deadline: A time.monotonic() timestamp after which no request is
            sent, or None for no deadline.

    Returns:
        The successful result and the total number of retries.

    Raises:
        RuntimeError: If the deadline passed ("max_time"), if the API answers
            with any other error code, or if every key failed.
    """

    total_retries: int = 0
    pending: list[str] = list(model_data.api_keys)

    for attempt in range(MAX_RETRIES + 1):
        limited: list[str] = []
        waits: list[float] = []

        for key in pending:
            retry_count: int = 0

            while True:
                left: float = time_left(deadline)

                if left <= 0:
                    raise RuntimeError("max_time")

                try:
                    data = send_request(
                        model_data, key, msgs, min(timeout_limit, left),
                        stop, max_tokens
                    )

                    if data.reply_code == 200:
                        return (data, total_retries)

                    if data.reply_code in (401, 402, 403):
                        total_retries += 1

                        break

                    if data.reply_code == 429:
                        total_retries += 1
                        limited.append(key)

                        if data.retry_after is not None:
                            waits.append(data.retry_after)

                        else:
                            waits.append(DEFAULT_WAIT)

                        break

                    if data.reply_code >= 500 and data.reply_code < 600:
                        retry_count += 1
                        total_retries += 1

                        if retry_count <= 3:
                            sleep_until(2, deadline)

                            continue

                        else:
                            break

                    else:
                        raise RuntimeError(
                            f"handle request error: {data.reply_code}"
                        )

                except requests.RequestException:
                    retry_count += 1
                    total_retries += 1

                    if retry_count <= 3:
                        sleep_until(2, deadline)

                        continue

                    else:
                        break

        if not limited or attempt == MAX_RETRIES:
            break

        pending = limited
        sleep_until(min(min(waits), MAX_WAIT), deadline)

    raise RuntimeError("all keys failed")
