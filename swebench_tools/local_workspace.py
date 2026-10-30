"""Workspace that works directly on a local folder."""

from .tool_workspace import WorkspaceBase, RunResults
import subprocess


class LocalWorkspace(WorkspaceBase):
    """Workspace for a repository in a local folder, e.g. TESTBED_PATH."""

    def __init__(self, root_path: str):
        """Store the repository root.

        Args:
            root_path: Root directory of the repository.
        """

        super().__init__(root_path)

    def read_from_file(self, filepath: str) -> str:
        """Read a local file as UTF-8 text.

        Args:
            filepath: Path to the file.

        Returns:
            The file's content.

        Raises:
            OSError: If the file can't be read.
            ValueError: If the file is not valid UTF-8.
        """

        try:
            with open(filepath, "r", encoding="UTF-8") as f:
                content = f.read()

        except OSError as e:
            raise OSError(f"error reading file: {e}") from e

        except UnicodeDecodeError as e:
            raise ValueError("Invalid UTF-8 text in filepath "
                             f"'{filepath}': {e}") from e

        return content

    def write_to_file(self, filepath: str, content: str) -> None:
        """Write text to a local file as UTF-8, replacing its content.

        Args:
            filepath: Path to the file.
            content: New text of the file.

        Raises:
            OSError: If the file can't be written.
        """

        try:
            with open(filepath, "w", encoding="UTF-8") as f:
                f.write(content)

        except OSError as e:
            raise OSError(f"error writing to file: {e}") from e

    def execute_command(
        self,
        command: str | list[str],
        directory: str,
        timeout: int,
    ) -> RunResults:
        """Run a command with subprocess in a local directory.

        A string is run through the shell; a list is run directly, without a
        shell.

        Args:
            command: The command, as a string or a list of arguments.
            directory: Directory to run it in.
            timeout: Seconds before the command is stopped.

        Returns:
            Its stdout, stderr and exit code. A timeout gives exit code -1 and
            a message in std_err.

        Raises:
            TypeError: If command is not a str or a list of str.
            ValueError: If timeout is not greater than 0.
            RuntimeError: If the command can't be started.
        """

        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        if not isinstance(command, (str, list)):
            raise TypeError("command must be str or list[str]")

        use_shell = False

        if isinstance(command, str):
            use_shell = True

        elif isinstance(command, list):
            for cmd in command:
                if not isinstance(cmd, str):
                    raise TypeError("command must be str or list[str]")

        try:
            res = subprocess.run(
                command,
                shell=use_shell,
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        except subprocess.TimeoutExpired:
            return RunResults(
                std_err=f"TIMEOUT: {command} (exceeded {timeout} s)",
                exit_code=-1,
            )

        except (OSError, ValueError) as e:
            raise RuntimeError(f"FAIL: could not run command {command} -> "
                               f"{e}") from e

        return RunResults(
            std_out=res.stdout,
            std_err=res.stderr,
            exit_code=res.returncode,
        )
