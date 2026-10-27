from sandbox.results import Results


def format_observation(res: Results, timeout: int) -> str:
    """Turn a sandbox Results into a message for the LLM."""
    parts: list[str] = []

    if res.output:
        parts.append(res.output)

    if res.error:
        last_lines = res.error.strip().splitlines()[-3:]
        parts.append("Error:\n" + "\n".join(last_lines))

    if res.timed_out:
        parts.append(
            f"Execution timed out after {timeout}s. "
            "Output above is partial. Your variables were reset."
        )
    elif res.state_reset:
        parts.append("The sandbox restarted. Your variables are lost.")

    if res.truncated:
        parts.append("(output truncated: print less or read fewer lines)")

    return "\n".join(parts) or "(no output)"


def no_code_observation() -> str:
    """Message sent when the LLM reply contains no code block."""
    return (
        "No ```python block found in your reply. "
        "Reply with a Thought, then exactly one ```python block."
    )
