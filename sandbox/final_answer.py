"""Storage for the answer that sandboxed code submits with final_answer()."""

from dataclasses import dataclass


@dataclass
class FinalAnswer:
    """Holds the answer submitted with final_answer() during one run.

    The child process puts the bound submit method in the namespace as
    final_answer, clears value before each run and sends it back with the
    run's Results. final_answer() returns normally, so the rest of the code
    still runs; the agent loop takes the answer once the run is over.

    Attributes:
        value: The submitted answer, or None if none was submitted yet.
    """

    value: str | None = None

    def submit(self, answer: object) -> str:
        """Store the answer; the run goes on, and the last call wins.

        Args:
            answer: The answer passed to final_answer().

        Returns:
            The stored answer.
        """

        self.value = str(answer)

        return self.value
