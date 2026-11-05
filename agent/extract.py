"""Extract code from an LLM answer, whatever its output format.

Non-Python formats (XML, Hermes JSON, ReAct) are converted to an
equivalent Python call, so the sandbox only ever runs Python.
"""

import json
import re
from typing import Any


Match = tuple[int, int, str]  # (start, end, python_code)

CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.I)
OPEN_BLOCK = re.compile(r"```(python|py)?\s*\n", re.I)
XML_INVOKE = re.compile(r'<invoke name="(\w+)">(.*?)</invoke>', re.DOTALL)
XML_PARAM = re.compile(
    r'<parameter name="(\w+)">(.*?)</parameter>', re.DOTALL)
HERMES = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
REACT = re.compile(r"Action:\s*(\w+)\s*\nAction Input:")


def to_python_call(name: str, args: dict[str, Any]) -> str:
    """Build Python code that calls a tool and prints the result.

    Args:
        name: Name of the tool function.
        args: Keyword arguments for the call.

    Returns:
        The code result = name(key=value, ...) followed by print(result), with
        each value written as its repr.
    """

    params = ", ".join(f"{key}={value!r}" for key, value in args.items())
    return f"result = {name}({params})\nprint(result)"


def parse_python(text: str) -> Match | None:
    """Find the first fenced code block tagged python, py or nothing.

    The tag is matched in any case, e.g. ```Python.

    Args:
        text: Raw LLM answer.

    Returns:
        The block's start and end positions in text and its stripped code, or
        None if there is no block.
    """

    match = CODE_BLOCK.search(text)
    if match is None:
        return None
    return match.start(), match.end(), match.group(1).strip()


def parse_value(raw: str) -> Any:
    """Decode a parameter value as JSON, e.g. a number or a list.

    Args:
        raw: The value as written in the answer.

    Returns:
        The decoded value, or raw unchanged if it is not valid JSON.
    """

    try:
        return json.loads(raw)
    except ValueError:
        return raw


def parse_xml(text: str) -> Match | None:
    """Find the first XML <invoke> call and convert it to Python.

    Its <parameter> values are decoded with parse_value.

    Args:
        text: Raw LLM answer.

    Returns:
        The call's start and end positions in text and the equivalent Python
        code, or None if there is no call.
    """

    match = XML_INVOKE.search(text)
    if match is None:
        return None
    args = {k: parse_value(v.strip()) for k, v in XML_PARAM.findall(
        match.group(2))}
    return match.start(), match.end(), to_python_call(match.group(1), args)


def parse_hermes(text: str) -> Match | None:
    """Find the first Hermes <tool_call> and convert it to Python.

    The tag holds JSON with "name" and "arguments"; the arguments may also be
    a JSON string.

    Args:
        text: Raw LLM answer.

    Returns:
        The call's start and end positions in text and the equivalent Python
        code, or None if there is no call or its JSON is invalid.
    """

    match = HERMES.search(text)
    if match is None:
        return None
    try:
        call = json.loads(match.group(1))
        args = call.get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args)
        code = to_python_call(call["name"], args)
    except (ValueError, KeyError, AttributeError, TypeError):
        return None
    return match.start(), match.end(), code


def parse_react(text: str) -> Match | None:
    """Find the first ReAct Action / Action Input and convert it to Python.

    Action Input must be a JSON object; parsing stops at the end of it.

    Args:
        text: Raw LLM answer.

    Returns:
        The pair's start and end positions in text, the end including the JSON
        input, and the equivalent Python code, or None if there is no pair or
        its input is not a valid JSON object.
    """

    match = REACT.search(text)
    if match is None:
        return None
    rest = text[match.end():]
    start = len(rest) - len(rest.lstrip())
    try:
        args, end = json.JSONDecoder().raw_decode(rest, start)
        code = to_python_call(match.group(1), args)
    except (ValueError, AttributeError):
        return None
    return match.start(), match.end() + end, code


PARSERS = (parse_python, parse_xml, parse_hermes, parse_react)


def first_match(text: str) -> Match | None:
    """Find the earliest code block or tool call, whatever its format.

    Args:
        text: Raw LLM answer.

    Returns:
        The match that starts first, as (start, end, Python code), or None if
        no format matches.
    """

    matches = [m for m in (parse(text) for parse in PARSERS) if m]
    return min(matches, default=None)


def extract_code(text: str) -> str | None:
    """Return the Python code of the first code block or tool call.

    Args:
        text: Raw LLM answer.

    Returns:
        The code, converted to Python for the other formats, or None if
        nothing matches.
    """

    match = first_match(text)
    return match[2] if match else None


def cut_after_first_block(text: str) -> str:
    """Drop everything after the first code block or tool call.

    Removes observations the model wrote itself after its code.

    Args:
        text: Raw LLM answer.

    Returns:
        The text up to the end of the first match, or text unchanged if
        nothing matches.
    """

    match = first_match(text)
    return text[: match[1]] if match else text


def get_conversion_note(text: str) -> str | None:
    """Describe how a reply was converted or tolerated.

    Args:
        text: Raw LLM answer.

    Returns:
        For a non-Python format, a note naming the format and giving the
        Python code that was run. For a python block whose tag is not
        lowercase, a note asking for the lowercase tag. None if the reply has
        no match or is a correct python block.
    """

    match = first_match(text)

    if match is None:
        return None

    if match == parse_python(text):
        opening = OPEN_BLOCK.search(text)
        tag: str | None = opening.group(1) if opening else None
        if tag is None or tag in ("python", "py"):
            return None
        return (f"Note: your code block was tagged '{tag}' and was run "
                "anyway. Write the tag as 'python', in lowercase.")

    format_name = "a non-Python format"
    for parse in PARSERS:
        if parse(text) == match:
            format_name = parse.__name__.removeprefix("parse_") + " format"

    return (
        f"Note: your reply used the {format_name}. It was run as this "
        f"Python code:\n{match[2]}"
    )


def has_unclosed_block(text: str) -> bool:
    """Check whether a reply opens a python code block without closing it.

    Args:
        text: Raw LLM answer.

    Returns:
        True if an opening fence is found but no complete code block, e.g.
        when the reply was cut off by the token limit.
    """

    if CODE_BLOCK.search(text) is not None:
        return False

    return OPEN_BLOCK.search(text) is not None
