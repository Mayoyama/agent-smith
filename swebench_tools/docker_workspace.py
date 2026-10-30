"""Workspace that works inside a SWE-bench task's Docker container."""

from .tool_workspace import WorkspaceBase, RunResults
import subprocess


CONTAINER_LIFESPAN: int = 1200


class DockerWorkspace(WorkspaceBase):
    """Workspace for the repository at /testbed inside a Docker container.

    The container is started with docker_run and removed with docker_remove.
    Reads, writes and commands run in it through docker exec and are stopped by
    timeout inside the container. The container stops by itself after
    CONTAINER_LIFESPAN seconds, and --rm then removes it, in case cleanup never
    runs.

    Attributes:
        root_path: Root directory of the repository, /testbed.
        container_id: ID of the running container, or "" if none is running.
        read_write_timeout: Seconds before a read or write is stopped.
    """

    def __init__(self, read_write_timeout: int = 20):
        """Set up the workspace, without starting a container.

        Args:
            read_write_timeout: Seconds before a read or write is stopped.

        Raises:
            ValueError: If read_write_timeout is not greater than 0.
        """

        self.root_path = "/testbed"
        self.container_id = ""

        if read_write_timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        self.read_write_timeout = read_write_timeout

    def docker_run(self, image: str, timeout: int) -> None:
        """Start a detached container from an image and store its ID.

        Args:
            image: Docker image to start, e.g. the task's docker_image.
            timeout: Seconds to wait for docker run, image pull included.

        Raises:
            ValueError: If timeout is not greater than 0.
            RuntimeError: If docker can't be started, times out or fails.
        """

        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        docker_cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            image,
            "sleep",
            str(CONTAINER_LIFESPAN),
        ]

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        except (subprocess.TimeoutExpired, OSError) as e:
            raise RuntimeError(f"error starting docker: {e}") from e

        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()

            raise RuntimeError(f"error starting docker: {err}")

        self.container_id = res.stdout.strip()

    def docker_remove(self, timeout: int = 10) -> None:
        """Remove the running container, if there is one, and clear its ID.

        Args:
            timeout: Seconds to wait for docker rm.

        Raises:
            ValueError: If timeout is not greater than 0.
            RuntimeError: If docker can't be started, times out or fails.
        """

        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        if not self.container_id:
            return

        try:
            res = subprocess.run(
                ["docker", "rm", "-f", self.container_id],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        except (subprocess.TimeoutExpired, OSError) as e:
            raise RuntimeError(f"Error removing docker: {e}") from e

        if res.returncode != 0:
            raise RuntimeError(f"Error removing docker: {res.stderr}")

        self.container_id = ""

    def read_from_file(self, filepath: str) -> str:
        """Read a file in the container as UTF-8 text, with cat.

        Args:
            filepath: Path to the file in the container.

        Returns:
            The file's content.

        Raises:
            OSError: If the file can't be read.
            ValueError: If the file is not valid UTF-8.
            RuntimeError: If no container is running, or docker fails or times
                out.
        """

        if not self.container_id:
            raise RuntimeError("docker container not running: "
                               "call docker_run() first")

        docker_cmd = [
            "docker",
            "exec",
            self.container_id,
            "timeout",
            str(self.read_write_timeout),
            "cat",
            filepath,
        ]

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=self.read_write_timeout + 5,
            )

        except subprocess.TimeoutExpired as e:
            raise RuntimeError("TIMEOUT: read from file (exceeded "
                               f"{self.read_write_timeout} s)") from e

        except (OSError, ValueError) as e:
            raise RuntimeError(f"error reading file: {e}") from e

        if res.returncode == 124:
            raise RuntimeError("TIMEOUT: read from file (exceeded "
                               f"{self.read_write_timeout} s)")

        if res.returncode != 0:
            err = res.stderr.decode("UTF-8", errors="replace")
            raise OSError(f"error reading file: {err}")

        try:
            res_string = res.stdout.decode("UTF-8")
        except UnicodeDecodeError as e:
            raise ValueError("Invalid UTF-8 text in filepath "
                             f"'{filepath}': {e}") from e

        return res_string

    def write_to_file(self, filepath: str, content: str) -> None:
        """Write text to a file in the container as UTF-8, with tee.

        Replaces the file's content.

        Args:
            filepath: Path to the file in the container.
            content: New text of the file.

        Raises:
            OSError: If the file can't be written.
            RuntimeError: If no container is running, or docker fails or times
                out.
        """

        if not self.container_id:
            raise RuntimeError("docker container not running: "
                               "call docker_run() first")

        docker_cmd = [
            "docker",
            "exec", "-i",
            self.container_id,
            "timeout",
            str(self.read_write_timeout),
            "tee",
            filepath,
        ]

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                timeout=self.read_write_timeout + 5,
                input=content.encode("UTF-8"),
            )

        except subprocess.TimeoutExpired as e:
            raise RuntimeError("TIMEOUT: write to file (exceeded "
                               f"{self.read_write_timeout} s)") from e

        except (OSError, ValueError) as e:
            raise RuntimeError(f"error writing to file: {e}") from e

        if res.returncode == 124:
            raise RuntimeError("TIMEOUT: write to file (exceeded "
                               f"{self.read_write_timeout} s)")

        if res.returncode != 0:
            err = res.stderr.decode("UTF-8", errors="replace")
            raise OSError(f"error writing to file: {err}")

    def execute_command(
        self,
        command: str | list[str],
        directory: str,
        timeout: int,
    ) -> RunResults:
        """Run a command in the container with docker exec.

        A string is run through a login shell (bash -lc), so the task's conda
        environment is active; a list is run directly. Both are stopped by
        timeout inside the container.

        Args:
            command: The command, as a string or a list of arguments.
            directory: Directory in the container to run it in.
            timeout: Seconds before the command is stopped.

        Returns:
            Its stdout, stderr and exit code. A timeout gives exit code -1 and
            a message in std_err.

        Raises:
            TypeError: If command is not a str or a list of str.
            ValueError: If timeout is not greater than 0.
            RuntimeError: If no container is running, or docker can't be
                started.
        """

        if not isinstance(command, (str, list)):
            raise TypeError("command must be str or list[str]")

        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        if not self.container_id:
            raise RuntimeError("docker container not running: "
                               "call docker_run() first")

        docker_cmd = ["docker", "exec", "-w", directory, self.container_id]

        if isinstance(command, str):
            shell_cmd = ["timeout", str(timeout), "bash", "-lc", command]
            docker_cmd.extend(shell_cmd)

        elif isinstance(command, list):
            for cmd in command:
                if not isinstance(cmd, str):
                    raise TypeError("command must be str or list[str]")

            docker_cmd.extend(["timeout", str(timeout)] + command)

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5,
            )

        except subprocess.TimeoutExpired:
            return RunResults(
                std_err=f"TIMEOUT: {command} (exceeded {timeout} s)",
                exit_code=-1,
            )

        except (OSError, ValueError) as e:
            raise RuntimeError(f"FAIL: could not run command {command} -> "
                               f"{e}") from e

        if res.returncode == 124:
            return RunResults(
                std_err=f"TIMEOUT: {command} (exceeded {timeout} s)",
                exit_code=-1,
            )

        return RunResults(
            std_out=res.stdout,
            std_err=res.stderr,
            exit_code=res.returncode,
        )
