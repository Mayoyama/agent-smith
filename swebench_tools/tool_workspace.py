from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RunResults:
    std_out: str = ""
    std_err: str = ""
    exit_code: int = 0


class BackendBase(ABC):
    def __init__(self, root_path: str):
        self.root_path = root_path

    @abstractmethod
    def read_from_file(self, filepath: str) -> str:
        pass

    @abstractmethod
    def write_to_file(self, filepath: str, content: str) -> None:
        pass

    @abstractmethod
    def execute_command(self,
                        command: str | list[str],
                        directory: str,
                        timeout: int
                        ) -> RunResults:
        pass
