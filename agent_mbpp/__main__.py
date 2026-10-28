"""Entry point for the MBPP agent."""

from common.models_public import MBPPTaskInput
from common import json_loader, setup_agent_parser
from argparse import ArgumentParser


if __name__ == "__main__":
    parser: ArgumentParser = setup_agent_parser()
    args = parser.parse_args()

    task = json_loader(args.task_file, MBPPTaskInput)

    if task is None:
        pass  # Need to decide what will happen if data fails to load
