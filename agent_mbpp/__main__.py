"""Entry point for the MBPP agent."""


import sys

from argparse import ArgumentParser

from agent.loop import make_generate, run_agent
from agent_mbpp.prompt import SYSTEM, build_prompt
from common.models_public import MBPPTaskInput
from common import json_loader, setup_agent_parser
from sandbox.config import get_default_config
from sandbox.sandbox import Sandbox

MAX_ITERATIONS = 10
MAX_INPUT_TOKENS = 6000
MAX_OUTPUT_TOKENS = 1500
MAX_TIME_SECONDS = 120


if __name__ == "__main__":
    parser: ArgumentParser = setup_agent_parser()
    args = parser.parse_args()

    task = json_loader(args.task_file, MBPPTaskInput)
    if task is None:
        print("Could not load task file", file=sys.stderr)
        sys.exit(1)

    generate = make_generate(args.model_name, args.provider_url)
    sandbox = Sandbox(get_default_config())

    try:
        assert task is not None
        answer = run_agent(
            task=build_prompt(task),
            system_prompt=SYSTEM,
            generate=generate,
            sandbox=sandbox,
            max_iterations=MAX_ITERATIONS,
            max_input_tokens=MAX_INPUT_TOKENS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            max_time_sec=MAX_TIME_SECONDS,
            exec_timeout=sandbox.config.max_execution_time_seconds,
            api_url=args.provider_url,
            model_name=args.model_name
        )
    finally:
        sandbox.shutdown()

    print(answer)
