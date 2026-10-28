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
    "- Turn 1: store the full function source in a string variable "
    "`code`, store the given assertions in a list `tests`, then check "
    "them with print(run_tests(code, tests)).\n"
    "- run_tests runs every assertion separately and returns JSON with "
    "\"success\" and one PASS, FAIL or TIMEOUT line per assertion. "
    "Use it to test; do not write your own print tests.\n"
    "- `code` must be self-contained: put every import it needs at the "
    "top. `tests` holds the given assertions as strings, copied exactly.\n"
    "- Wait for the Observation. Never say tests pass before you have "
    "seen their output.\n"
    "- If \"success\" is false or an error appears, fix `code` and run "
    "run_tests again.\n"
    "- Variables persist between turns.\n"
    "- Keep code short. Print only what you need.\n"
    "- Once the Observation shows \"success\": true, your NEXT turn must "
    "be final_answer(code), called inside a python code block, never as "
    "a tag or in plain text. Do not repeat the function without calling "
    "it.\n"
    "\n"
    "Example:\n"
    "\n"
    "Thought: Write the function and test it with run_tests.\n"
    "```python\n"
    r'code = "def add(a, b):\n    return a + b"' "\n"
    'tests = ["assert add(1, 2) == 3"]\n'
    "print(run_tests(code, tests))\n"
    "```<end_code>\n"
    "\n"
    "Observation:\n"
    '{"success": true, "output": "PASS: assert add(1, 2) == 3"}\n'
    "\n"
    "Thought: Every test passes, submit the code.\n"
    "```python\n"
    "final_answer(code)\n"
    "```<end_code>\n"
)


def build_prompt(task: MBPPTaskInput) -> str:
    """Build the user message from the MBPP task."""
    tests = "\n".join(task.test_list)
    return (
        f"{task.task_definition}\n\n"
        f"Signature:\n{task.function_definition}\n\n"
        f"Tests:\n{tests}"
    )


def build_system_prompt(manual: str) -> str:
    """Append the sandbox manual to the base system prompt."""
    return f"{SYSTEM}\nAvailable functions:\n{manual}"
