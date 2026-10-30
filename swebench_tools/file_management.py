"""File system tools for the SWE-bench MCP server."""

from .tool_workspace import WorkspaceBase, RunResults
import io


def read_file(workspace: WorkspaceBase,
              filepath: str,
              start_line: int,
              end_line: int
              ) -> str:
    """Read a range of lines from a file, numbered from 1.

    Args:
        workspace: Workspace the file is read through.
        filepath: Path to the file.
        start_line: First line to read, at least 1.
        end_line: Last line to read, not less than start_line. If it is past
            the end of the file, the file is read to the end and a note with
            its line count is added.

    Returns:
        One "<line_number>: <line_content>" line per line read.

    Raises:
        ValueError: If start_line is less than 1, end_line is less than
            start_line, start_line is past the end of the file, or the file is
            not valid UTF-8.
        OSError: If the file can't be opened or read.
        RuntimeError: If the workspace fails to run the read, e.g. Docker.
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


def edit_file(workspace: WorkspaceBase,
              filepath: str,
              old_str: str,
              new_str: str
              ) -> tuple[str, str]:
    """Replace one exact, unique string in a file.

    Args:
        workspace: Workspace the file is read and written through.
        filepath: Path to the file.
        old_str: Text to replace; it must occur exactly once.
        new_str: Replacement text.

    Returns:
        A success message with the line of the edit, and the new file content
        for the caller's syntax check.

    Raises:
        ValueError: If old_str is not found, occurs more than once, or the file
            is not valid UTF-8.
        OSError: If the file can't be read or written.
        RuntimeError: If the workspace fails to run the read or write, e.g.
            Docker.
    """

    content = workspace.read_from_file(filepath)
    occurrences = content.count(old_str)

    if occurrences == 0:
        msg = f"old_str not found in {filepath}"
        first_line = (old_str.strip().splitlines()[0].strip()
                      if old_str.strip()
                      else "")

        if first_line:
            found_pos = []

            for i, line in enumerate(content.splitlines(), start=1):
                if first_line in line:
                    found_pos.append(str(i))

            if found_pos:
                msg += (f"; its first line appears at line(s) "
                        f"{', '.join(found_pos[:5])}")

                if len(found_pos) > 5:
                    msg += f" (and {len(found_pos) - 5} more)"

                msg += ": read_file those lines and copy them exactly"

        raise ValueError(msg)

    if occurrences > 1:
        raise ValueError(f"old_str found {occurrences} times in "
                         f"{filepath}; Unique string required")

    found = content.count('\n', 0, content.find(old_str)) + 1
    new_content = content.replace(old_str, new_str, 1)

    workspace.write_to_file(filepath, new_content)

    return f"Successfully replaced old_str at line {found}", new_content


def list_files(workspace: WorkspaceBase,
               directory: str,
               pattern: str,
               timeout: int
               ) -> str:
    """List files below a directory whose names match a pattern.

    Runs find through the workspace, so subdirectories are searched too and
    .git is skipped.

    Args:
        workspace: Workspace the commands run in.
        directory: Directory to search.
        pattern: Shell-style pattern matched against file names.
        timeout: Seconds before each command is stopped.

    Returns:
        The number of files found, then one path per line, or a message if
        nothing matched.

    Raises:
        ValueError: If the directory doesn't exist or find fails.
        RuntimeError: If a command can't be started.
    """

    workdir_check: RunResults = workspace.execute_command(
        ["test", "-d", directory],
        workspace.root_path,
        timeout,
    )

    if workdir_check.exit_code != 0:
        raise ValueError(f"{directory} does not exist or is not a directory")

    res: RunResults = workspace.execute_command(
        ["find", directory, "-type", "f", "-name", pattern,
         "-not", "-path", "*/.git/*"],
        workspace.root_path,
        timeout,
    )

    if res.exit_code != 0:
        raise ValueError(f"{res.std_err}")

    if not res.std_out:
        return f"no files in the directory matched '{pattern}'"

    count = len(res.std_out.splitlines())

    return f"{count} files\n" + res.std_out
