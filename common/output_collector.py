"""Size-limited text collection that keeps the start and end."""


class OutputCollector():
    """Collects text up to a limit, keeping its start and end.

    The first quarter of the limit holds the start of the text and the
    rest holds the most recent text, so memory stays bounded however
    much is added. Used by the sandbox parent for the child's output
    and by the MCP tool servers for long tool output.

    Attributes:
        limit: Maximum number of characters kept.
        first_qtr_size: Characters kept from the start.
        remainder_size: Characters kept from the end.
        start_buffer: Kept text from the start.
        end_buffer: Kept text from the end.
        char_count: Total number of characters received.
        hint: Advice for the LLM added to the truncation marker, or
            an empty string.
    """

    def __init__(self, limit: int, use_hint: bool = False) -> None:
        """Set the part sizes and start with empty buffers.

        Args:
            limit: Maximum number of characters kept.
            use_hint: Add the "print less" hint to the truncation
                marker (for sandbox output).
        """

        self.limit = limit
        self.first_qtr_size = limit // 4
        self.remainder_size = self.limit - self.first_qtr_size

        self.start_buffer = ""
        self.end_buffer = ""
        self.char_count = 0
        hint = ", print less, e.g. a slice or a summary"
        self.hint = hint if use_hint else ""

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
        characters, the limit and, if enabled, the hint sits between
        start and end.

        Returns:
            The final text and True if it was truncated.
        """

        missing = self._calculate_missing_chars()

        if missing:
            return ((f"{self.start_buffer}\n[{missing} characters truncated "
                     f"(limit {self.limit}){self.hint}"
                     f"]\n{self.end_buffer}"), True)

        return (self.start_buffer + self.end_buffer, False)
