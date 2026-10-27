from .tool_workspace import BackendBase, RunResults


def run_command(workspace: BackendBase,
                command: str,
                workdir: str,
                timeout: int
                ) -> RunResults:
    workdir_check = workspace.execute_command(
        ["test", "-d", workdir],
        workspace.root_path,
        timeout,
    )

    if workdir_check.exit_code != 0:
        raise ValueError(f"{workdir} does not exist or is not a directory")

    return workspace.execute_command(command, workdir, timeout)
