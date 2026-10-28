"""Interface for where the SWE-bench tools read, write and run commands."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import os


@dataclass
class RunResults:
    """Result of a command run through a workspace.

    Attributes:
        std_out: What the command printed to stdout.
        std_err: What it printed to stderr, or the timeout message.
        exit_code: The command's exit code, or -1 if it timed out.
    """

    std_out: str = ""
    std_err: str = ""
    exit_code: int = 0


class WorkspaceBase(ABC):
    """Base class for the places the SWE-bench tools access the repository.

    Subclasses implement reading, writing and running commands, e.g. on a local
    folder or inside a Docker container.

    Attributes:
        root_path: Root directory of the repository.
    """

    def __init__(self, root_path: str):
        """Store the repository root.

        Args:
            root_path: Root directory of the repository.
        """

        self.root_path = os.path.abspath(root_path)

    @abstractmethod
    def read_from_file(self, filepath: str) -> str:
        """Return the full text of a file.

        Args:
            filepath: Path to the file.

        Returns:
            The file's content.

        Raises:
            OSError: If the file can't be read.
            ValueError: If the file is not valid UTF-8.
        """

        pass

    @abstractmethod
    def write_to_file(self, filepath: str, content: str) -> None:
        """Replace the content of a file.

        Args:
            filepath: Path to the file.
            content: New text of the file.

        Raises:
            OSError: If the file can't be written.
        """

        pass

    @abstractmethod
    def execute_command(self,
                        command: str | list[str],
                        directory: str,
                        timeout: int
                        ) -> RunResults:
        """Run a command and return its output.

        Args:
            command: A list of arguments, run without a shell, or a string, run
                through the shell.
            directory: Directory to run it in.
            timeout: Seconds before the command is stopped.

        Returns:
            Its stdout, stderr and exit code. A timeout gives exit code -1 and
            a message in std_err.

        Raises:
            TypeError: If command is not a str or a list of str.
            RuntimeError: If the command can't be started.
        """

        pass
