from multiprocessing.connection import Connection
from common import Output
import io


class OutputStreamer(io.TextIOBase):
    def __init__(self, conn: Connection) -> None:
        super().__init__()

        self.conn = conn
        self.text_buffer = ""

    def write(self, text: str) -> int:
        self.text_buffer += text
        text_len = len(self.text_buffer)

        if '\n' in self.text_buffer or text_len >= 200:
            self.conn.send(Output(self.text_buffer))
            self.text_buffer = ""

        return len(text)

    def send_remaining(self) -> None:
        if len(self.text_buffer):
            self.conn.send(Output(self.text_buffer))
            self.text_buffer = ""


class OutputCollector():
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.first_qtr_size = limit // 4
        self.remainder_size = self.limit - self.first_qtr_size

        self.start_buffer = ""
        self.end_buffer = ""
        self.char_count = 0

    def _calculate_missing_chars(self) -> int:
        return self.char_count - len(self.start_buffer) - len(self.end_buffer)

    def add_to_buffer(self, text: str) -> None:
        self.char_count += len(text)

        remaining_start_space = self.first_qtr_size - len(self.start_buffer)

        self.start_buffer += text[:remaining_start_space]
        self.end_buffer += text[remaining_start_space:]

        if len(self.end_buffer) > self.remainder_size:
            over = len(self.end_buffer) - self.remainder_size
            self.end_buffer = self.end_buffer[over:]

    def get_final_text(self) -> tuple[str, bool]:
        missing = self._calculate_missing_chars()

        if missing:
            return ((f"{self.start_buffer}\n[{missing} characters truncated "
                     f"(limit {self.limit}), print less, e.g. a slice or"
                     f" a summary]\n{self.end_buffer}"), True)

        return (self.start_buffer + self.end_buffer, False)
