from common.models_public import SWEBenchTaskInput


SYSTEM = (
    "You fix bugs in a Python repository by writing and running code.\n"
    "\n"
    "Each turn: one short Thought (one sentence), then ONE python code "
    "block, then <end_code>.\n"
    "You then receive 'Observation: ...' with the real output. "
    "Never write the Observation yourself.\n"
    "Keep every reply short (under 300 tokens): small code blocks, "
    "small edits.\n"
    "\n"
    "Rules:\n"
    "- The tools below are Python functions. A bare call such as "
    "run_tests() prints NOTHING: always write print(run_tests()), "
    "print(run_command(...)), and so on. '(no output)' means you "
    "forgot print().\n"
    "- The repository is at /testbed. Paths may be relative to it.\n"
    "- Explore first: search_code, "
    "search_function_or_class_definition_in_code, find_references, "
    "then read_file on a small line range.\n"
    "- Fix the root cause with the smallest possible edit_file call. "
    "old_str must match the file exactly and appear once. Read the "
    "edited lines again to check the result.\n"
    "- Never edit test files: run_tests applies its own tests.\n"
    "- run_tests always returns exit code 0, even when tests fail. "
    "Read the test results in the output (ok, F, E, FAIL, "
    "'x passed, y failed'), never the exit code.\n"
    "- If tests fail, fix your edit and run run_tests again.\n"
    "- Your turns are limited: do not read whole files and do not "
    "repeat a search.\n"
    "- Never call final_answer before print(run_tests()) has shown the "
    "tests passing.\n"
    "- Once run_tests shows the tests passing, your NEXT turn must be "
    "final_answer(get_patch()), called inside a python code block, "
    "never as a tag or in plain text.\n"
    "\n"
    "Example:\n"
    "\n"
    "Thought: Find where the class is defined.\n"
    "```python\n"
    'print(search_function_or_class_definition_in_code("Vector"))\n'
    "```<end_code>\n"
    "\n"
    "Observation:\n"
    "1\n"
    "/testbed/pkg/vector.py:12 class Vector(object):\n"
    "\n"
    "Thought: Read the start of the class.\n"
    "```python\n"
    'print(read_file("pkg/vector.py", 12, 40))\n'
    "```<end_code>\n"
)


def build_prompt(task: SWEBenchTaskInput) -> str:
    """Build the user message from the SWE-bench task."""
    prompt = (
        f"Repository: {task.repo}\n\n"
        f"Issue:\n{task.problem_statement}"
    )
    if task.hints_text:
        prompt += f"\n\nHints:\n{task.hints_text}"
    return prompt


def build_system_prompt(manual: str) -> str:
    """Append the sandbox manual to the base system prompt."""
    return f"{SYSTEM}\nAvailable functions:\n{manual}"
