"""Entry point for the SWE bench agent."""

import signal
import sys

from argparse import ArgumentParser
from types import FrameType

from agent_swebench.mcp_setup import connect_swebench_tools
from common.models_public import SWEBenchTaskInput
from common import json_loader, setup_agent_parser
from sandbox.config import get_default_config
from sandbox.sandbox import Sandbox


MAX_ITERATIONS = 30
MAX_INPUT_TOKENS = 300000
MAX_OUTPUT_TOKENS = 10000
MAX_TIME_SECONDS = 900


if __name__ == "__main__":
    parser: ArgumentParser = setup_agent_parser()
    args = parser.parse_args()

    task = json_loader(args.task_file, SWEBenchTaskInput)
    if task is None:
        print("Could not load task file", file=sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))

    sandbox = Sandbox(get_default_config())
    client = connect_swebench_tools(sandbox, args.task_file)
    if client is None:
        sandbox.shutdown()
        sys.exit(1)

    try:
        print(sandbox.get_manual(client))
    finally:
        sandbox.shutdown()
        client.close()
