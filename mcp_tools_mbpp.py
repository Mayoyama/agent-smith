"""MCP server with the MBPP tools (run_tests).

Runs over stdio by default, or over streamable HTTP with --http
(http://127.0.0.1:PORT/mcp, port 8000 unless --port is given).
"""

from mcp.server.fastmcp import FastMCP
from common import OutputCollector, parse_tool_args
import subprocess
import asyncio
import json
import ast
import sys
import os


MCP_SERVER = FastMCP()
TIMEOUT_LIMIT = 5
ERROR_LENGTH_LIMIT = 300


def adjust_assert(test: str) -> str:
    """Rewrite an "assert a == b" test so a failure shows the value of a.

    Args:
        test: One assertion from test_list.

    Returns:
        Two lines that store a in a variable and assert it equals b, with
        "got <repr>" as the failure message, or test unchanged if it is not a
        single assert with one == comparison and no message.
    """

    try:
        parsed = ast.parse(test)

    except SyntaxError:
        return test

    if len(parsed.body) != 1:
        return test

    node = parsed.body[0]
    if not isinstance(node, ast.Assert) or node.msg is not None:
        return test

    compare = node.test
    if not isinstance(compare, ast.Compare):
        return test

    if len(compare.ops) != 1 or not isinstance(compare.ops[0], ast.Eq):
        return test

    left = ast.unparse(compare.left)
    right = ast.unparse(compare.comparators[0])

    return (
        f"__run_tests_got = {left}\n"
        f"assert __run_tests_got == {right}, "
        "'got ' + repr(__run_tests_got)"
    )


@MCP_SERVER.tool()
def run_tests(code: str, test_list: list[str]) -> str:
    """Run a candidate solution against MBPP test assertions.

    Each assertion runs separately in a fresh Python process together with the
    code, so one failing or hanging test does not hide the others. The code
    must be self-contained: include every import the tests need (e.g. import
    math) at the top of it.

    Args:
        code: Full Python source of the solution, imports included.
        test_list: Assertions to check, e.g. "assert add(1, 2) == 3".

    Returns:
        A JSON string with "success" (true only if every assertion passed) and
        "output" (one PASS, FAIL or TIMEOUT line per assertion; a failed ==
        assertion shows the value it got, and long error messages are
        truncated with a marker).
    """

    existing_tests = [line for line in test_list if line.strip()]

    if not existing_tests:
        return json.dumps({"success": False, "output": "No tests to run"})

    test_results: list[str] = []
    all_passed = True

    for test in existing_tests:
        result_text = ""
        assert_text = f"{code}\n{adjust_assert(test)}"

        try:
            res = subprocess.run(
                [sys.executable, "-c", assert_text],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_LIMIT,
                env={"PATH": os.environ.get("PATH", "")},
            )

        except subprocess.TimeoutExpired:
            timed_out = f"TIMEOUT: {test} (exceeded {TIMEOUT_LIMIT} s)"
            test_results.append(timed_out)
            all_passed = False

            continue

        except (OSError, ValueError) as e:
            error = f"FAIL: could not run test {test} -> {e}"
            test_results.append(error)
            all_passed = False

            continue

        if res.returncode != 0:
            if not res.stderr.strip():
                err = f"exit code {res.returncode} used, reason unknown"

            else:
                collector = OutputCollector(ERROR_LENGTH_LIMIT)

                errors = [line for line in res.stderr.splitlines()
                          if line.strip()][-1]

                collector.add_to_buffer(errors)

                err, _ = collector.get_final_text()

            result_text = f"FAIL: {test} -> {err}"
            all_passed = False

        else:
            result_text = f"PASS: {test}"

        test_results.append(result_text)

    output = "\n".join(test_results)

    return json.dumps({"success": all_passed, "output": output})


if __name__ == "__main__":
    args = parse_tool_args()

    try:
        if args.http:
            MCP_SERVER.settings.port = args.port
            MCP_SERVER.run(transport="streamable-http")

        else:
            MCP_SERVER.run()

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("Program terminated", file=sys.stderr)
        os._exit(130)

    except Exception:
        print("Program terminated", file=sys.stderr)
        os._exit(1)
