from common.models_public import MBPPTaskInput


SYSTEM = r"""You solve Python tasks by writing and running code.

Each turn: one short Thought (one sentence, never compute by hand), then ONE python code block, then <end_code>.
You then receive 'Observation: ...' with the real output. Never write the Observation yourself.

Rules:
- Turn 1: write the function and test it with print(...) on the given tests.
- Wait for the Observation. Never say tests pass before you have seen their output.
- If a test fails or an error appears, fix the code and test again.
- Variables persist between turns.
- Keep code short. Print only what you need.
- Once the Observation shows every test passing, your NEXT turn must be a call to final_answer with the function source as a string. Do not repeat the function without calling it.
- final_answer is a Python function: call it inside a ```python block. Never write it as a tag or in plain text.

Example:

Thought: Write the function and test it.
```python
def add(a, b):
    return a + b
print(add(1, 2) == 3)
```<end_code>

Observation:
True

Thought: Test passes, submit the code.
```python
final_answer("def add(a, b):\n    return a + b")
```<end_code>
"""


def build_prompt(task: MBPPTaskInput) -> str:
    """Build the user message from the MBPP task."""
    tests = "\n".join(task.test_list)
    return f"{task.task_definition}\n\nSignature:\n{task.function_definition}\n\nTests:\n{tests}"


def build_system_prompt(manual: str) -> str:
    """Append the sandbox manual to the base system prompt."""
    return f"{SYSTEM}\nAvailable functions:\n{manual}"
