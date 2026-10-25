"""Streaming of printed output from the child to the parent."""
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
