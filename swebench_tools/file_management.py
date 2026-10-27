"""File system tools for the SWE-bench MCP server."""


def read_file(filepath: str, start_line: int, end_line: int) -> str:
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

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

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

    except OSError as e:
        raise OSError(f"error reading from file: {e}")

    return line_strings
