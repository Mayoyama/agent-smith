"""Entry point for the SWE bench agent."""

from common.models_public import SWEBenchTaskInput
from common.task_loader import loader, setup_parser
from argparse import ArgumentParser


if __name__ == "__main__":
    parser: ArgumentParser = setup_parser()
    args = parser.parse_args()

    task = loader(args.task_file, SWEBenchTaskInput)

    if task is None:
        pass  # Need to decide what will happen if data fails to load
