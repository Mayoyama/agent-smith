"""File system tools for the SWE-bench MCP server."""

from .tool_workspace import BackendBase
import io


def read_file(workspace: BackendBase,
              filepath: str,
              start_line: int,
              end_line: int
              ) -> str:
    """Read a range of lines from a file, numbered from 1.

    Args:
        filepath: Path to the file.
        start_line: First line to read, at least 1.
        end_line: Last line to read, not less than start_line. If it is past
            the end of the file, the file is read to the end and a note with
            its line count is added.

    Returns:
        One "<line_number>: <line_content>" line per line read.

    Raises:
        ValueError: If start_line is less than 1, end_line is less than
            start_line, or start_line is past the end of the file.
        OSError: If the file can't be opened or read.
    """

    if start_line < 1:
        raise ValueError("start_line must be at least 1")

    if end_line < start_line:
        raise ValueError("end_line must not be less than start_line")

    line_strings = ""

    content = workspace.read_from_file(filepath)
    lines = io.StringIO(content).readlines()

    if start_line > len(lines):
        raise ValueError("start_line is beyond end of text")

    for i, line in enumerate(lines, start=1):
        if i < start_line:
            continue

        if i > end_line:
            break

        no_newline = line.rstrip('\n')
        line_strings += f"{i}: {no_newline}\n"

    if end_line > len(lines):
        line_strings += (f"[end_line={end_line} requested, "
                         f"but file has {len(lines)} lines]")

    return line_strings


def edit_file(workspace: BackendBase,
              filepath: str,
              old_str: str,
              new_str: str
              ) -> tuple[str, str]:
    content = workspace.read_from_file(filepath)
    occurrences = content.count(old_str)

    if occurrences == 0:
        raise ValueError(f"old_str not found in {filepath}")

    if occurrences > 1:
        raise ValueError(f"old_str found {occurrences} times in "
                         f"{filepath}; Unique string required")

    found = content.count('\n', 0, content.find(old_str)) + 1
    new_content = content.replace(old_str, new_str, 1)

    workspace.write_to_file(filepath, new_content)

    return f"Successfully replaced old_str at line {found}", new_content


def list_files(workspace: BackendBase,
               directory: str,
               pattern: str,
               timeout: int
               ) -> str:
    workdir_check = workspace.execute_command(
        ["test", "-d", directory],
        workspace.root_path,
        timeout,
    )

    if workdir_check.exit_code != 0:
        raise ValueError(f"{directory} does not exist or is not a directory")

    res = workspace.execute_command(
        ["find", directory, "-type", "f", "-name", pattern,
         "-not", "-path", "*/.git/*"],
        workspace.root_path,
        timeout,
    )

    if res.exit_code != 0:
        raise ValueError(f"{res.std_err}")

    if not res.std_out:
        return f"no files in the directory matched '{pattern}'"

    return res.std_out
