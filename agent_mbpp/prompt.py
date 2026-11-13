"""System prompt and user message for the MBPP agent."""

from common.models_public import MBPPTaskInput


SYSTEM = (
    "You solve Python tasks by writing and running code.\n"
    "\n"
    "Each turn: one short Thought (one sentence, never compute by hand), "
    "then ONE python code block, then <end_code>.\n"
    "You then receive 'Observation: ...' with the real output. "
    "Never write the Observation yourself.\n"
    "\n"
    "Rules:\n"
    "- Turn 1: store the full function source in a triple-quoted string "
    "`code = \"\"\"...\"\"\"`, store the given assertions in a list "
    "`tests`, then run result = run_tests(code, tests), print(result), "
    "and submit in the same block when every test passes: "
    "if '\"success\": true' in result: final_answer(code)\n"
    "- run_tests runs every assertion separately and returns JSON with "
    "\"success\" and one PASS, FAIL or TIMEOUT line per assertion. "
    "Use it to test; do not write your own print tests.\n"
    "- `code` must be self-contained: put every import it needs at the "
    "top, including modules only the tests use (e.g. `import math` when a "
    "test calls math.isclose), even if the task does not show the import. "
    "`tests` holds the given assertions as strings, copied exactly.\n"
    "- Wait for the Observation. Never say tests pass before you have "
    "seen their output.\n"
    "- If a test fails, fix `code` and run the same block again: it "
    "submits by itself once every test passes.\n"
    "- Variables persist between turns.\n"
    "- Keep code short: no comments, no docstrings, and when fixing, change "
    "only what failed. Print only what you need.\n"
    "- Call final_answer only inside a python code block, never as a tag "
    "or in plain text.\n"
    "\n"
    "Example:\n"
    "\n"
    "Thought: Write the function, test it and submit it if it passes.\n"
    "```python\n"
    'code = """def add(a, b):\n    return a + b"""\n'
    'tests = ["assert add(1, 2) == 3"]\n'
    "result = run_tests(code, tests)\n"
    "print(result)\n"
    "if '\"success\": true' in result:\n"
    "    final_answer(code)\n"
    "```<end_code>\n"
)


def build_prompt(task: MBPPTaskInput) -> str:
    """Build the user message from the MBPP task.

    Args:
        task: The MBPP task to solve.

    Returns:
        The task description, the function signature and the visible test
        assertions, one per line, followed by the test imports if any.
    """

    tests = "\n".join(task.test_list)
    prompt: str = (
        f"{task.task_definition}\n\n"
        f"Signature:\n{task.function_definition}\n\n"
        f"Tests:\n{tests}"
    )
    if task.test_imports:
        prompt += "\n\nTest imports:\n" + "\n".join(task.test_imports)
    return prompt


def build_system_prompt(manual: str) -> str:
    """Append the sandbox manual to the base system prompt.

    Args:
        manual: Description of the sandbox functions, from
            Sandbox.get_manual().

    Returns:
        SYSTEM followed by the manual under an "Available functions:" heading.
    """

    return f"{SYSTEM}\nAvailable functions:\n{manual}"
