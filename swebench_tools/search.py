"""Code search tools for the SWE-bench MCP server."""

from .tool_workspace import WorkspaceBase, RunResults


def search_code(workspace: WorkspaceBase,
                pattern: str,
                file_pattern: str,
                timeout: int,
                ) -> tuple[str, int]:
    """Search the repository with grep for lines matching a regex.

    Args:
        workspace: Workspace the search runs in; its root is searched.
        pattern: Extended regex (grep -E) to search for.
        file_pattern: Shell-style pattern for which files to search.
        timeout: Seconds before the search is stopped.

    Returns:
        A tuple of the result text and a code. The text is the number of
        matches followed by one "path:<line_number> <line_content>" line per
        match, with code 0; or a no-match message, with code 1.

    Raises:
        ValueError: If grep fails, e.g. for an invalid regex.
        RuntimeError: If grep can't be started.
    """

    result: RunResults = workspace.execute_command(
        ["grep", "-rnIE", "--include=" + file_pattern,
         pattern, workspace.root_path],
        workspace.root_path,
        timeout,
    )

    if result.exit_code == 2:
        raise ValueError(result.std_err)

    if result.exit_code == 1:
        return f"no lines matched '{pattern}'", 1

    lines = result.std_out.splitlines()
    res_string = f"{len(lines)} matches\n"

    for res in lines:
        parts = res.split(':', 2)
        res_string += f"{parts[0]}:{parts[1]} {parts[2]}\n"

    return res_string, 0


def search_function_or_class_definition_in_code(workspace: WorkspaceBase,
                                                name: str,
                                                timeout: int,
                                                ) -> str:
    """Find the lines where a function or class is defined.

    Uses search_code on .py files with a regex for def, async def or class
    followed by the name.

    Args:
        workspace: Workspace the search runs in.
        name: Function or class name.
        timeout: Seconds before the search is stopped.

    Returns:
        The search_code result text, or a message if no definition was found.

    Raises:
        ValueError: If name is not a valid identifier, or grep fails.
        RuntimeError: If grep can't be started.
    """

    if not name.isidentifier():
        raise ValueError(f"'{name}' is not a valid identifier")

    reg = rf"^[[:space:]]*(async[[:space:]]+)?(def|class)[[:space:]]+{name}\b"

    res, code = search_code(workspace, reg, "*.py", timeout)

    if code == 1:
        return f"no function or class found for '{name}'"

    return res


def find_references(workspace: WorkspaceBase,
                    name: str,
                    filepath: str,
                    line: int,
                    timeout: int,
                    ) -> str:
    """Find every line in the .py files that uses a name as a whole word.

    Results at filepath:line are left out, so the definition itself is not
    listed.

    Args:
        workspace: Workspace the search runs in.
        name: Function or class name.
        filepath: Absolute path of the file with the definition.
        line: Line number of the definition.
        timeout: Seconds before the search is stopped.

    Returns:
        The number of matches, then one "path:<line_number> <line_content>"
        line per use, or a message if none was found.

    Raises:
        ValueError: If name is not a valid identifier, or grep fails.
        RuntimeError: If grep can't be started.
    """

    if not name.isidentifier():
        raise ValueError(f"'{name}' is not a valid identifier")

    reg = rf"\b{name}\b"

    result, code = search_code(workspace, reg, "*.py", timeout)

    if code == 1:
        return f"no references found for '{name}'"

    res_string = ""

    for res in result.splitlines()[1:]:
        if res.startswith(f"{filepath}:{line} "):
            continue

        res_string += res + '\n'

    return f"{len(res_string.splitlines())} matches\n" + res_string
