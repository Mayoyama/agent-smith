"""Worker process that executes sandboxed code sent over a pipe."""
from multiprocessing import connection
from contextlib import redirect_stdout
from typing import Any
from common import SandboxConfig
from .final_answer import FinalAnswer, send_final_answer
from .results import Results
import traceback
import resource
import signal
import io


def child_process(conn: connection.Connection, config: SandboxConfig) -> None:
    """Run received code in a persistent namespace until told to stop.

    Sets the memory limit and ignores Ctrl+C, then executes each
    message and sends back a Results. A None message ends the loop.

    Args:
        conn: Child end of the pipe to the parent.
        config: Sandbox config, used for the memory limit.
    """

    namespace: dict[str, Any] = {}
    namespace["final_answer"] = send_final_answer

    bytes_limit = config.max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))

    signal.signal(signal.SIGINT, signal.SIG_IGN)

    while True:
        msg = conn.recv()

        if msg is None:
            break

        buffer = io.StringIO()
        err = ""
        final_answer = None

        try:
            with redirect_stdout(buffer):
                exec(msg, namespace)

        except FinalAnswer as fa:
            final_answer = str(fa.value)

        except Exception:
            err = traceback.format_exc(chain=True)

        conn.send(Results(
            output=buffer.getvalue(),
            error=err,
            final_ans=final_answer,
        ))

    conn.close()
