"""Exception-based signal for submitting a final answer from sandboxed code."""


class FinalAnswer(BaseException):
    """Signal raised to end execution with a final answer.

    Inherits from BaseException so `except Exception` in model code cannot
    swallow it.

    Attributes:
        value: The submitted answer.
    """

    def __init__(self, value: object) -> None:
        """Store the submitted answer.

        Args:
            value: The answer passed to final_answer().
        """

        super().__init__(value)
        self.value = value


def send_final_answer(value: object) -> None:
    """Submit a final answer from sandboxed code.

    Args:
        value: The answer to submit.

    Raises:
        FinalAnswer: Always, carrying the value.
    """

    raise FinalAnswer(value)
