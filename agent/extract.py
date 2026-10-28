"""Extract code from LLM answer."""


import re


CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str | None:
    """Return the code of the first fenced block, or None if absent.

    Args:
        text: Raw LLM answer that may contain fenced code blocks.

    Returns:
        The stripped content of the first block, or None if no block.
    """
    match = CODE_BLOCK.search(text)
    return match.group(1).strip() if match else None


def cut_after_first_block(text: str) -> str:
    """Drop everything after the first block (hallucinated observations).

    Args:
        text: Raw LLM answer that may contain fenced code blocks.

    Returns:
        The text up to and including the closing fence of the first
        block, or the unchanged text if no block is found.
    """
    match = CODE_BLOCK.search(text)
    return text[: match.end()] if match else text
