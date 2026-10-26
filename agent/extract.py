"""Extract code from LLM answer."""


import re


CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str | None:
    """Return the code of the first fenced block, or None if absent."""
    match = CODE_BLOCK.search(text)
    return match.group(1).strip() if match else None


def cut_after_first_block(text: str) -> str:
    """Drop everything after the first block (hallucinated observations)."""
    match = CODE_BLOCK.search(text)
    return text[: match.end()] if match else text
