from contextlib import redirect_stdout
from typing import Any
from .results import Results
from .final_answer import FinalAnswer, send_final_answer
import traceback
import io


class Sandbox:
    def __init__(self) -> None:
        self.namespace: dict[str, Any] = {}
        self.namespace["final_answer"] = send_final_answer

    def run_exec(self, code: str) -> Results:
        buffer = io.StringIO()
        err = ""
        final_answer = None

        try:
            with redirect_stdout(buffer):
                exec(code, self.namespace)

        except FinalAnswer as fa:
            final_answer = str(fa.value)
        except Exception:
            err = traceback.format_exc(chain=True)

        return Results(
            output=buffer.getvalue(),
            error=err,
            final_ans=final_answer,
        )
