"""Entry point for the SWE bench agent."""

from common.models_public import SWEBenchTaskInput
from common import json_loader, setup_agent_parser
from argparse import ArgumentParser


MAX_ITERATIONS = 30
MAX_INPUT_TOKENS = 300000
MAX_OUTPUT_TOKENS = 10000
MAX_TIME_SECONDS = 900


if __name__ == "__main__":
    parser: ArgumentParser = setup_agent_parser()
    args = parser.parse_args()

    task = json_loader(args.task_file, SWEBenchTaskInput)

    if task is None:
        pass  # Need to decide what will happen if data fails to load
