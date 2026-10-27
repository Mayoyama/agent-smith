from .tool_workspace import BackendBase, RunResults
import subprocess


class LocalWorkspace(BackendBase):
    def __init__(self, root_path: str):
        super().__init__(root_path)

    def read_from_file(self, filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="UTF-8") as f:
                content = f.read()

        except OSError as e:
            raise OSError(f"error reading file: {e}")

        except UnicodeDecodeError as e:
            raise ValueError("Invalid UTF-8 text in filepath "
                             f"'{filepath}': {e}") from e

        return content

    def write_to_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, "w", encoding="UTF-8") as f:
                f.write(content)

        except OSError as e:
            raise OSError(f"error writing to file: {e}")

    def execute_command(self,
                        command: str | list[str],
                        directory: str,
                        timeout: int) -> RunResults:
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
