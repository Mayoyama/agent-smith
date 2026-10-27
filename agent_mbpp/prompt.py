from common.models_public import MBPPTaskInput


SYSTEM = """You solve Python tasks by writing and running code.

Each turn: one short Thought (one sentence, never compute by hand), then ONE python code block, then <end_code>.
You then receive 'Observation: ...' with the real output. Never write the Observation yourself.

Rules:
- Write the function, then test it with print(...) on the given tests.
- Never say tests pass before you have seen their output.
- Variables persist between turns.
- Keep code short. Print only what you need.
- When all tests pass, call final_answer(code) with the function source as a string.

Example:
Thought: Write the function and test it.
```python
def add(a, b):
    return a + b
print(add(1, 2))
```<end_code>
"""


def build_prompt(task: MBPPTaskInput) -> str:
    """Build the user message from the MBPP task."""
    tests = "\n".join(task.test_list)
    return f"{task.task_definition}\n\nSignature:\n{task.function_definition}\n\nTests:\n{tests}"
