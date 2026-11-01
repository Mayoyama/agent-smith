"""Extract code from an LLM answer, whatever its output format.

Non-Python formats (XML, Hermes JSON, ReAct) are converted to an
equivalent Python call, so the sandbox only ever runs Python.
"""

import json
import re
from typing import Any


Match = tuple[int, int, str]  # (start, end, python_code)

CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)
XML_INVOKE = re.compile(r'<invoke name="(\w+)">(.*?)</invoke>', re.DOTALL)
XML_PARAM = re.compile(
    r'<parameter name="(\w+)">(.*?)</parameter>', re.DOTALL)
HERMES = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
REACT = re.compile(r"Action:\s*(\w+)\s*\nAction Input:")


def to_python_call(name: str, args: dict[str, Any]) -> str:
    """Build `result = name(k=v, ...)` followed by `print(result)`."""
    params = ", ".join(f"{key}={value!r}" for key, value in args.items())
    return f"result = {name}({params})\nprint(result)"


def parse_python(text: str) -> Match | None:
    """Find the first fenced Python block."""
    match = CODE_BLOCK.search(text)
    if match is None:
        return None
    return match.start(), match.end(), match.group(1).strip()


def parse_value(raw: str) -> Any:
    """Decode a JSON value (number, list...), else keep the raw string."""
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def parse_xml(text: str) -> Match | None:
    """Find the first <invoke> call and convert it."""
    match = XML_INVOKE.search(text)
    if match is None:
        return None
    args = {k: parse_value(v.strip()) for k, v in XML_PARAM.findall(
        match.group(2))}
    return match.start(), match.end(), to_python_call(match.group(1), args)


def parse_hermes(text: str) -> Match | None:
    """Find the first <tool_call>{json}</tool_call> and convert it."""
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
    """Find the first Action / Action Input pair and convert it."""
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
    """Return the earliest match among all formats, or None."""
    matches = [m for m in (parse(text) for parse in PARSERS) if m]
    return min(matches, default=None)


def extract_code(text: str) -> str | None:
    """Return the Python code of the first call/block, or None."""
    match = first_match(text)
    return match[2] if match else None


def cut_after_first_block(text: str) -> str:
    """Drop everything after the first call/block."""
    match = first_match(text)
    return text[: match[1]] if match else text
