"""MCP server with the SWE-bench tools.

Relative file paths are resolved from TESTBED_PATH (/testbed if it is unset).
Runs over stdio by default, or over streamable HTTP with --http
(http://127.0.0.1:PORT/mcp, port 8000 unless --port is given).
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from common.models_public import SWEBenchTaskInput
from common import parse_tool_args, OutputCollector, loader
import swebench_tools
import os


SEARCH_TIMEOUT_LIMIT: int = 20
EXEC_TIMEOUT_LIMIT: int = 30
TEST_TIMEOUT_LIMIT: int = 280
OUTPUT_LIMIT: int = 10000
TESTBED_PATH: str = os.environ.get("TESTBED_PATH", "/testbed")
MCP_SERVER: MCPServer = MCPServer()
WORKSPACE: swebench_tools.WorkspaceBase = \
    swebench_tools.LocalWorkspace(TESTBED_PATH)


def get_absolute_path(filepath: str) -> str:
    """Resolve a path against the repository root.

    Args:
        filepath: Path from the LLM, absolute or relative to TESTBED_PATH.

    Returns:
        The normalised absolute path.
    """

    if not os.path.isabs(filepath):
        filepath = os.path.join(WORKSPACE.root_path, filepath)

    return os.path.normpath(filepath)


def get_truncated_text(text: str) -> str:
    """Cut text to OUTPUT_LIMIT characters, keeping its start and end.

    Args:
        text: Tool output.

    Returns:
        The text, with a marker saying how much was cut if it was too long.
    """

    collector = OutputCollector(OUTPUT_LIMIT)
    collector.add_to_buffer(text)

    final, _ = collector.get_final_text()

    return final


@MCP_SERVER.tool()
def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read a range of lines from a file, numbered like cat -n.

    Args:
        filepath: Path to the file, absolute or relative to the repository
            root.
        start_line: First line to read, starting at 1.
        end_line: Last line to read. If it is past the end of the file, the
            file is read to the end and a note gives its line count.

    Returns:
        One "<line_number>: <line_content>" line per line read. Long output
        keeps its start and end, with a marker saying how much was cut.

    Raises:
        ToolError: If the line range is invalid or the file can't be read.
    """

    abs_path = get_absolute_path(filepath)

    try:
        res = swebench_tools.read_file(
            WORKSPACE,
            abs_path,
            start_line,
            end_line
        )

    except (OSError, ValueError) as e:
        raise ToolError(str(e)) from e

    return get_truncated_text(res)


@MCP_SERVER.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Replace one exact, unique string in a file.

    old_str must appear exactly once in the file, so include enough surrounding
    lines to make it unique. After a .py file is edited, a warning is added if
    it no longer compiles.

    Args:
        filepath: Path to the file, absolute or relative to the repository
            root.
        old_str: Exact text to replace, whitespace and indentation included.
        new_str: Replacement text.

    Returns:
        A success message with the line of the edit, plus a warning if a .py
        file now has a syntax error.

    Raises:
        ToolError: If old_str is not found or not unique, or the file can't be
            read or written.
    """

    abs_path = get_absolute_path(filepath)

    try:
        res_line, new_content = swebench_tools.edit_file(
            WORKSPACE, abs_path, old_str, new_str)

    except (OSError, ValueError) as e:
        raise ToolError(str(e)) from e

    if filepath.endswith(".py"):
        try:
            compile(new_content, abs_path, "exec")

        except SyntaxError as e:
            res_line += (f"\nWARNING: file now has syntax error at line "
                         f"{e.lineno}: {e.msg}")

        except ValueError as e:
            res_line += f"\nWARNING: file is not valid python source: {e}"

    return res_line


@MCP_SERVER.tool()
def list_files(directory: str, pattern: str) -> str:
    """List files in a directory and its subdirectories by name pattern.

    Args:
        directory: Directory to search, absolute or relative to the repository
            root.
        pattern: Shell-style pattern matched against file names only, e.g.
            "*.py".

    Returns:
        The number of files found, then one absolute file path per line (.git
        is skipped), or a message if nothing matched. Long output keeps its
        start and end, with a marker saying how much was cut.

    Raises:
        ToolError: If the directory doesn't exist or the search fails.
    """

    abs_path = get_absolute_path(directory)

    try:
        res = swebench_tools.list_files(
            WORKSPACE,
            abs_path,
            pattern,
            SEARCH_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    return get_truncated_text(res)


@MCP_SERVER.tool()
def search_code(pattern: str, file_pattern: str) -> str:
    """Search the repository's files for lines matching a regex.

    The pattern uses extended regex syntax (grep -E). Binary files are skipped.

    Args:
        pattern: Regex to search for, e.g. "def validate_\\w+".
        file_pattern: Shell-style pattern for which files to search, e.g.
            "*.py".

    Returns:
        The number of matches, then one "/absolute/path:<line_number>
        <line_content>" line per match, or a message if nothing matched. Long
        output keeps its start and end, with a marker saying how much was cut.

    Raises:
        ToolError: If the regex is invalid or the search fails.
    """

    try:
        res, _ = swebench_tools.search_code(
            WORKSPACE,
            pattern,
            file_pattern,
            SEARCH_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    return get_truncated_text(res)


@MCP_SERVER.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """Find where a function or class is defined.

    Searches .py files for lines that define the name with def, async def or
    class.

    Args:
        name: Exact function or class name, without arguments or dots.

    Returns:
        The number of matches, then one "/absolute/path:<line_number>
        <line_content>" line per definition, or a message if none was found.
        Long output keeps its start and end, with a marker saying how much was
        cut.

    Raises:
        ToolError: If name is not a valid Python identifier or the search
            fails.
    """

    try:
        res = swebench_tools.search_function_or_class_definition_in_code(
            WORKSPACE,
            name,
            SEARCH_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    return get_truncated_text(res)


@MCP_SERVER.tool()
def find_references(name: str, filepath: str, line: int) -> str:
    """Find all uses of a function or class name in the .py files.

    Matches the name as a whole word, so mentions in comments and strings are
    included too. The line at filepath:line, usually the definition, is left
    out.

    Args:
        name: Exact function or class name.
        filepath: File of the definition, absolute or relative to the
            repository root.
        line: Line number of the definition in that file.

    Returns:
        The number of matches, then one "/absolute/path:<line_number>
        <line_content>" line per use, or a message if none was found. Long
        output keeps its start and end, with a marker saying how much was cut.

    Raises:
        ToolError: If name is not a valid Python identifier or the search
            fails.
    """

    abs_path = get_absolute_path(filepath)

    try:
        res = swebench_tools.find_references(
            WORKSPACE,
            name,
            abs_path,
            line,
            SEARCH_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    return get_truncated_text(res)


@MCP_SERVER.tool()
def run_command(command: str, workdir: str) -> str:
    """Run a shell command in a directory.

    A command that runs past the time limit is stopped and reported with exit
    code -1.

    Args:
        command: Shell command to run.
        workdir: Directory to run it in, absolute or relative to the repository
            root.

    Returns:
        The exit code, stdout and stderr, each under its own heading. Long
        output keeps its start and end, with a marker saying how much was cut.

    Raises:
        ToolError: If workdir doesn't exist or the command can't be started.
    """

    abs_path = get_absolute_path(workdir)

    try:
        res = swebench_tools.run_command(
            WORKSPACE,
            command,
            abs_path,
            EXEC_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    res_str = (f"exit code:\n{res.exit_code}\nstdout:\n"
               f"{res.std_out}\nstderr:\n{res.std_err}")

    return get_truncated_text(res_str)


@MCP_SERVER.tool()
def run_tests() -> str:
    """Run the task's evaluation script and return its results.

    The script installs the repository, applies the task's tests and runs them.
    A script that runs past the time limit is stopped and reported with exit
    code -1.

    Returns:
        The exit code, stdout and stderr, each under its own heading. Long
        output keeps its start and end, with a marker saying how much was cut.

    Raises:
        ToolError: If SWE_TASK_FILE is not set, the task file can't be loaded,
            or the script can't be started.
    """

    swe_task_file = os.environ.get("SWE_TASK_FILE", None)

    if not swe_task_file:
        raise ToolError("no task given: set SWE_TASK_FILE to the task JSON")

    task = loader(swe_task_file, SWEBenchTaskInput)

    if not task:
        raise ToolError("task file could not be loaded")

    try:
        res = swebench_tools.run_tests(
            WORKSPACE,
            task.eval_script,
            TEST_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    res_string = (f"exit code:\n{res.exit_code}\nstdout:\n"
                  f"{res.std_out}\nstderr:\n{res.std_err}")

    return get_truncated_text(res_string)


@MCP_SERVER.tool()
def get_patch() -> str:
    """Return the unified git diff of all changes made to the repository.

    New files are included. Submit it with final_answer(get_patch()).

    Returns:
        The diff from git -c core.fileMode=false diff, never cut, or a message
        if nothing has changed yet.

    Raises:
        ToolError: If git fails, e.g. because the root is not a git repository.
    """

    try:
        res = swebench_tools.get_patch(
            WORKSPACE,
            EXEC_TIMEOUT_LIMIT,
        )

    except (OSError, ValueError, RuntimeError) as e:
        raise ToolError(str(e)) from e

    return res


if __name__ == "__main__":
    args = parse_tool_args("swebench")

    if args.http:
        MCP_SERVER.run(transport="streamable-http", port=args.port)

    else:
        MCP_SERVER.run()
