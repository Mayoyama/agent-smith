"""Execution tools for the SWE-bench MCP server."""

from .tool_workspace import WorkspaceBase, RunResults
import re


def run_command(
    workspace: WorkspaceBase,
    command: str,
    workdir: str,
    timeout: int,
) -> RunResults:
    """Run a shell command in a directory through the workspace.

    Args:
        workspace: Workspace the command runs in.
        command: Shell command to run.
        workdir: Directory to run it in.
        timeout: Seconds before the command is stopped.

    Returns:
        The command's stdout, stderr and exit code. A timeout gives exit code
        -1 and a message in std_err.

    Raises:
        ValueError: If workdir doesn't exist or isn't a directory.
        RuntimeError: If the command can't be started.
    """

    workdir_check = workspace.execute_command(
        ["test", "-d", workdir],
        workspace.root_path,
        timeout,
    )

    if workdir_check.exit_code != 0:
        raise ValueError(f"{workdir} does not exist or is not a directory")

    return workspace.execute_command(command, workdir, timeout)


def run_tests(
    workspace: WorkspaceBase,
    eval_script: str,
    timeout: int,
) -> RunResults:
    """Run an evaluation script with bash in the repository root.

    Args:
        workspace: Workspace the script runs in.
        eval_script: Bash script from the task's eval_script field.
        timeout: Seconds before the script is stopped.

    Returns:
        The script's stdout, stderr and exit code. A timeout gives exit code -1
        and a message in std_err.

    Raises:
        RuntimeError: If bash can't be started.
    """

    return workspace.execute_command(
        ["bash", "-c", eval_script],
        workspace.root_path,
        timeout,
    )


def tests_passed(output: str) -> bool:
    """Tell whether a test run's output shows every test passing.

    Recognises three common test summary formats: "tests finished: N
    passed, in Xs" (bin/test, e.g. sympy), "Ran N tests ... OK" (unittest,
    e.g. Django) and "N passed in Xs" (pytest). Anything else counts as not
    passed, so the model reads the output itself.

    Args:
        output: Stdout of the evaluation script.

    Returns:
        True only if a known summary reports passing tests and no failure.
    """

    bin_test_summary = re.search(
        r"tests finished: \d+ passed"
        r"(, \d+ (skipped|expected to fail))*, in",
        output
    )

    if bin_test_summary:
        return True

    unittest_summary = re.search(r"Ran \d+ tests? in [\d.]+s\s*\n\s*OK\b",
                                 output)

    if unittest_summary:
        return True

    pytest_summary = re.search(r"=+ ([^=\n]*\bpassed\b[^=\n]*) =+",
                               output)

    if pytest_summary:
        summary_text = pytest_summary.group(1)

        if not re.search(r"failed|error|exception", summary_text):
            return True

    return False


def get_patch(workspace: WorkspaceBase, timeout: int) -> str:
    """Return the git diff of all changes in the repository.

    New, untracked files are first marked with git add -N so that they appear
    in the diff.

    Args:
        workspace: Workspace the git commands run in.
        timeout: Seconds before each command is stopped.

    Returns:
        The output of git -c core.fileMode=false diff, or a message if it is
        empty.

    Raises:
        ValueError: If a git command fails.
        RuntimeError: If git can't be started.
    """

    result = workspace.execute_command(
        ["git", "add", "-N", "."],
        workspace.root_path,
        timeout,
    )

    if result.exit_code != 0:
        raise ValueError(result.std_err)

    result = workspace.execute_command(
        ["git", "-c", "core.filemode=false", "diff"],
        workspace.root_path,
        timeout,
    )

    if result.exit_code != 0:
        raise ValueError(result.std_err)

    if not result.std_out:
        return "no changes made yet (empty diff)"

    return result.std_out
