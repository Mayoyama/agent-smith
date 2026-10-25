"""MCP server with the MBPP tools (run_tests)."""
from mcp.server.mcpserver import MCPServer
from common import OutputCollector
import subprocess
import json
import sys


MCP_SERVER = MCPServer()
TIMEOUT_LIMIT = 5
ERROR_LENGTH_LIMIT = 300


@MCP_SERVER.tool()
def run_tests(code: str, test_list: list[str]) -> str:
    """Run a candidate solution against MBPP test assertions.

    Each assertion runs separately in a fresh Python process together
    with the code, so one failing or hanging test does not hide the
    others. The code must be self-contained: include every import the
    tests need (e.g. import math) at the top of it.

    Args:
        code: Full Python source of the solution, imports included.
        test_list: Assertions to check, e.g.
            "assert add(1, 2) == 3".

    Returns:
        A JSON string with "success" (true only if every assertion
        passed) and "output" (one PASS, FAIL or TIMEOUT line per
        assertion; long error messages are truncated with a marker).
    """

    if not test_list or not [line for line in test_list if line.strip()]:
        return json.dumps({"success": False, "output": "No tests to run"})

    test_results: list[str] = []
    all_passed = True

    for test in test_list:
        result_text = ""
        assert_text = f"{code}\n{test}"

        try:
            res = subprocess.run(
                [sys.executable, "-c", assert_text],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_LIMIT,
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
    MCP_SERVER.run()
