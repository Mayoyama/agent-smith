"""Entry point for the SWE bench agent."""

import signal
import sys
import time

from argparse import ArgumentParser
from pathlib import Path

from agent.loop import make_generate, run_agent
from agent_swebench.mcp_setup import connect_swebench_tools
from agent_swebench.prompt import build_prompt, build_system_prompt
from common.models_public import SWEBenchTaskInput
from common import json_loader, setup_agent_parser
from common import SolutionOutput
from sandbox.config import get_default_config
from sandbox.sandbox import Sandbox


MAX_ITERATIONS = 30
MAX_INPUT_TOKENS = 300000
MAX_OUTPUT_TOKENS = 10000
MAX_TIME_SECONDS = 900


if __name__ == "__main__":
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

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))

    sandbox = Sandbox(get_default_config())
    client = connect_swebench_tools(sandbox, args.task_file)
    if client is None:
        sandbox.shutdown()
        sys.exit(1)

    try:
        system_prompt: str = build_system_prompt(sandbox.get_manual(client))
        result = run_agent(
            task=build_prompt(task),
            system_prompt=system_prompt,
            generate=generate,
            sandbox=sandbox,
            max_iterations=MAX_ITERATIONS,
            max_input_tokens=MAX_INPUT_TOKENS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            max_time_sec=MAX_TIME_SECONDS - int(time.monotonic() - start),
            exec_timeout=sandbox.config.max_execution_time_seconds,
            api_url=args.provider_url,
            model_name=args.model_name,
        )
        steps = result.steps
        solution = SolutionOutput(
            task_id=task.instance_id,
            benchmark="swebench",
            success=result.answer is not None,
            solution=result.answer or "",
            iterations=len(steps),
            total_requests=sum(1 + s.retries for s in steps),
            total_input_tokens=sum(s.input_tokens for s in steps),
            total_output_tokens=sum(s.output_tokens for s in steps),
            total_time_seconds=time.monotonic() - start,
            steps=steps,
            system_prompt=system_prompt,
            error=result.error,
        )
        Path(args.output).write_text(solution.model_dump_json(indent=2))
    finally:
        sandbox.shutdown()
        client.close()
