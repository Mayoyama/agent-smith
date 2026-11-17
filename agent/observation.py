"""Format sandbox results into messages for the LLM."""

from sandbox.results import Results
import re


def format_observation(res: Results, timeout: int, code: str = "") -> str:
    """Turn a sandbox Results into a message for the LLM.

    Keeps the output, the last 3 lines of the error (except after a timeout,
    which has its own note), a note when the run timed out or the sandbox
    restarted, and a hint when the output was truncated.

    Args:
        res: Result of the sandbox execution.
        timeout: Time limit of the run in seconds, shown if it was hit.
        code: Code that was run, used to name a tool call that was not
            printed.

    Returns:
        The observation text, or a reminder to use print() if there is nothing
        to report.
    """

    parts: list[str] = []

    if res.output:
        parts.append(res.output)

    if res.error and not res.timed_out:
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

    if parts:
        return "\n".join(parts)

    call = re.match(r"\s*([A-Za-z_]\w*)\(", code)

    if call is not None and call.group(1) != "print":
        name = call.group(1)

        return (f"(no output: {name}(...) is not printed. To see what it "
                f"returns, write print({name}(...)))")

    return "(no output: use print() to see results)"


def no_code_observation(extra_hint: str = "") -> str:
    """Message sent when the LLM reply contains no code block.

    Args:
        extra_hint: Sentence placed between the two sentences of the
            message, for advice that fits one agent only. Empty by default.

    Returns:
        A reminder asking for a Thought and exactly one python block.
    """

    message = "No ```python block found in your reply. "

    if extra_hint:
        message += extra_hint + " "

    message += ("Reply with a one-sentence Thought, then exactly "
                "one ```python block.")

    return message


def cut_off_observation() -> str:
    """Message sent when the reply's code block was never closed.

    Returns:
        A reminder that the block was cut off and to write shorter code.
    """

    return (
        "Your ```python block was cut off before its closing ``` "
        "(the reply ended early), so none of it was run and "
        "none of its variables exist. Send the whole block again, shorter:"
        " a one-sentence Thought, no comments."
    )
