"""Entry point for the SWE-bench agent.

Loads the task, connects the SWE-bench tool server (which starts the task's
Docker container) to the sandbox, runs the agent loop with
TIME_MARGIN_SECONDS kept in reserve and writes solution.json to --output. If
the model's answer is not a diff, the repository diff is submitted instead.
Exits with code 1 on a setup error or SIGTERM, and 130 on Ctrl+C.
"""

import signal
import sys
import time

from argparse import ArgumentParser

from agent.loop import RunResult, make_generate, run_agent
from agent.solution import write_solution
from agent_swebench.mcp_setup import connect_swebench_tools
from agent_swebench.prompt import build_prompt, build_system_prompt
from common.models_public import SWEBenchTaskInput
from common import json_loader, setup_agent_parser, StepMetrics
from sandbox.config import get_default_config
from sandbox.mcp_client import MCPClient
from sandbox.sandbox import Sandbox


MAX_ITERATIONS = 30
MAX_INPUT_TOKENS = 300000
MAX_OUTPUT_TOKENS = 10000
MAX_TIME_SECONDS = 900
TIME_MARGIN_SECONDS = 360


def fetch_patch(client: MCPClient) -> str:
    """Get the repository diff from the get_patch tool.

    Args:
        client: Connected client of the SWE-bench tool server.

    Returns:
        The diff, or "" if the tool call fails or its result does not start
        with "diff".
    """

    try:
        patch: str = client.call_tool("get_patch", {})
    except Exception:
        return ""
    return patch if patch.startswith("diff") else ""


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(130))

    start: float = time.monotonic()
    parser: ArgumentParser = setup_agent_parser()
    args = parser.parse_args()

    task = json_loader(args.task_file, SWEBenchTaskInput)
    if task is None:
        print("Could not load task file", file=sys.stderr)
        sys.exit(1)

    try:
        generate = make_generate(args.model_name, args.provider_url)
    except (ValueError, RuntimeError) as e:
        print(f"LLM setup error: {e}", file=sys.stderr)
        sys.exit(1)

    sandbox = Sandbox(get_default_config())
    client = connect_swebench_tools(sandbox, args.task_file)
    if client is None:
        sandbox.shutdown()
        sys.exit(1)

    try:
        system_prompt: str = build_system_prompt(sandbox.get_manual(client))
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
                max_time_sec=(MAX_TIME_SECONDS - TIME_MARGIN_SECONDS
                              - int(time.monotonic() - start)),
                exec_timeout=sandbox.config.max_execution_time_seconds,
                api_url=args.provider_url,
                model_name=args.model_name,
                steps=steps
            )
        except Exception as e:
            result = RunResult(None, steps, f"crash: {e}")
        answer: str = ""
        if result.answer and result.answer.startswith("diff"):
            answer = result.answer
        else:
            answer = fetch_patch(client)
        write_solution(
            task.instance_id,
            "swebench",
            answer,
            result,
            start,
            system_prompt,
            args.output
        )
    finally:
        sandbox.shutdown()
        client.close()
