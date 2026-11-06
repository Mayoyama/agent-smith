"""Entry point for the MBPP agent.

Loads the task, connects the MBPP tool server to the sandbox, runs the agent
loop within the MBPP limits and writes solution.json to --output. No request
is sent after DEADLINE_SECONDS, and code runs end SHUTDOWN_MARGIN_SECONDS
before MAX_TIME_SECONDS, both counted from start-up. Without an answer, the
sandbox's `code` variable is submitted if it holds a compilable function.
Exits with code 1 on a setup error or SIGTERM, and 130 on Ctrl+C.
"""

import sys
import time
import signal

from argparse import ArgumentParser

from agent.loop import RunResult, make_generate, run_agent
from agent.solution import write_solution
from agent_mbpp.mcp_setup import connect_mbpp_tools
from agent_mbpp.prompt import build_prompt, build_system_prompt
from common.models_public import MBPPTaskInput
from common import json_loader, setup_agent_parser, StepMetrics
from sandbox.config import get_default_config
from sandbox.sandbox import Sandbox


MAX_ITERATIONS = 10
MAX_INPUT_TOKENS = 6000
MAX_OUTPUT_TOKENS = 1500
MAX_TIME_SECONDS = 120
DEADLINE_SECONDS = 100
SHUTDOWN_MARGIN_SECONDS = 10


def fetch_code(sandbox: Sandbox) -> str:
    """Get the `code` variable of the sandbox as a fallback answer.

    Args:
        sandbox: Sandbox of the finished run.

    Returns:
        The source in `code` if it compiles and defines a function, else "".
    """

    res = sandbox.run_exec("print(code)")
    text: str = res.output.strip()
    if res.error or res.truncated or "def " not in text:
        return ""
    try:
        compile(text, "<fallback>", "exec")
    except (SyntaxError, ValueError):
        return ""
    return text


def check_answer(answer: str) -> str | None:
    """Refuse a final answer that is not the source of a function.

    Args:
        answer: Value the model passed to final_answer.

    Returns:
        A message for the model if the answer is refused, else None.
    """

    try:
        compile(answer, "<answer>", "exec")
    except (SyntaxError, ValueError):
        return ("final_answer was not accepted: it is not valid Python "
                "source. Pass the full code as a string, e.g. "
                "final_answer(code).")
    if "def " not in answer:
        return ("final_answer was not accepted: it defines no function. "
                "Pass the full code as a string, e.g. final_answer(code).")
    return None


if __name__ == "__main__":
    now: float = time.monotonic()
    deadline: float = now + DEADLINE_SECONDS
    end_time: float = now + MAX_TIME_SECONDS - SHUTDOWN_MARGIN_SECONDS
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))

    parser: ArgumentParser = setup_agent_parser()
    args = parser.parse_args()

    task = json_loader(args.task_file, MBPPTaskInput)
    if task is None:
        print("Could not load task file", file=sys.stderr)
        sys.exit(1)

    try:
        generate = make_generate(args.model_name, args.provider_url, deadline)
    except (ValueError, RuntimeError) as e:
        print(f"LLM setup error: {e}", file=sys.stderr)
        sys.exit(1)

    sandbox = Sandbox(get_default_config())
    client = connect_mbpp_tools(sandbox)
    if client is None:
        sandbox.shutdown()
        sys.exit(1)

    try:
        system_prompt: str = build_system_prompt(sandbox.get_manual(client))
        start: float = now
        steps: list[StepMetrics] = []
        try:
            result: RunResult = run_agent(
                task=build_prompt(task),
                system_prompt=system_prompt,
                generate=generate,
                sandbox=sandbox,
                max_iterations=MAX_ITERATIONS,
                max_input_tokens=MAX_INPUT_TOKENS,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                max_time_sec=MAX_TIME_SECONDS,
                end_time=end_time,
                exec_timeout=sandbox.config.max_execution_time_seconds,
                api_url=args.provider_url,
                model_name=args.model_name,
                steps=steps,
                check_answer=check_answer,
            )
        except Exception as e:
            result = RunResult(None, steps, f"crash: {e}")
        answer: str = result.answer or fetch_code(sandbox)
        write_solution(
            str(task.task_id),
            "mbpp",
            answer,
            result,
            start,
            system_prompt,
            args.output
        )
    finally:
        sandbox.shutdown()
        client.close()
