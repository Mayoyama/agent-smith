"""Streaming of printed output from the child and size-limited
collection in the parent."""
from multiprocessing.connection import Connection
from common import Output
import io


class OutputStreamer(io.TextIOBase):
    """Stdout replacement in the child that streams output to the parent.

    Text is sent as Output messages whenever a newline arrives or 200
    characters have built up, so the parent keeps what was printed
    even if the child is killed.

    Attributes:
        conn: Child end of the pipe to the parent.
        text_buffer: Text not sent yet.
    """

    def __init__(self, conn: Connection) -> None:
        """Store the pipe and start with an empty buffer.

        Args:
            conn: Child end of the pipe to the parent.
        """

        super().__init__()

        self.conn = conn
        self.text_buffer = ""

    def write(self, text: str) -> int:
        """Buffer text and send it once a line or 200 characters are ready.

        Args:
            text: Text written by print or sys.stdout.write.

        Returns:
            The number of characters written.
        """

        self.text_buffer += text
        text_len = len(self.text_buffer)

        if '\n' in self.text_buffer or text_len >= 200:
            self.conn.send(Output(self.text_buffer))
            self.text_buffer = ""

        return len(text)

    def send_remaining(self) -> None:
        """Send any buffered text that has not been sent yet."""

        if len(self.text_buffer):
            self.conn.send(Output(self.text_buffer))
            self.text_buffer = ""


class OutputCollector():
    """Collects output in the parent, keeping its start and end.

    The first quarter of the limit holds the start of the text and the
    rest holds the most recent text, so memory stays bounded however
    much is printed.

    Attributes:
        limit: Maximum number of characters kept.
        first_qtr_size: Characters kept from the start.
        remainder_size: Characters kept from the end.
        start_buffer: Kept text from the start.
        end_buffer: Kept text from the end.
        char_count: Total number of characters received.
    """

    def __init__(self, limit: int) -> None:
        """Set the part sizes and start with empty buffers.

        Args:
            limit: Maximum number of characters kept.
        """

        self.limit = limit
        self.first_qtr_size = limit // 4
        self.remainder_size = self.limit - self.first_qtr_size

        self.start_buffer = ""
        self.end_buffer = ""
        self.char_count = 0

    def _calculate_missing_chars(self) -> int:
        """Return how many received characters were dropped."""

        return self.char_count - len(self.start_buffer) - len(self.end_buffer)

    def add_to_buffer(self, text: str) -> None:
        """Add text, filling the start first and trimming the end.

        Args:
            text: Piece of output to add.
        """

        self.char_count += len(text)

        remaining_start_space = self.first_qtr_size - len(self.start_buffer)

        self.start_buffer += text[:remaining_start_space]
        self.end_buffer += text[remaining_start_space:]

        if len(self.end_buffer) > self.remainder_size:
            over = len(self.end_buffer) - self.remainder_size
            self.end_buffer = self.end_buffer[over:]

    def get_final_text(self) -> tuple[str, bool]:
        """Return the kept text and whether anything was dropped.

        When text was dropped, a marker with the number of missing
        characters and a hint for the LLM sits between start and end.

        Returns:
            The final text and True if it was truncated.
        """

        missing = self._calculate_missing_chars()

        if missing:
            return ((f"{self.start_buffer}\n[{missing} characters truncated "
                     f"(limit {self.limit}), print less, e.g. a slice or"
                     f" a summary]\n{self.end_buffer}"), True)

        return (self.start_buffer + self.end_buffer, False)
