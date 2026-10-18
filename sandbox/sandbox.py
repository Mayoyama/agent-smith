from contextlib import redirect_stdout
from typing import Any, Callable
from .results import Results
from .mcp_client import MCPClient
from .final_answer import FinalAnswer, send_final_answer
import traceback
import signal
import io


class ExecTimeout(BaseException):
    """Raised when sandboxed code runs too long."""


def _on_alarm(signum: int, frame: Any) -> None:
    raise ExecTimeout


class Sandbox:
    def __init__(self) -> None:
        self.namespace: dict[str, Any] = {}
        self.namespace["final_answer"] = send_final_answer
        self.alarm_seconds = 30

    def run_exec(self, code: str) -> Results:
        signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(self.alarm_seconds)
        buffer = io.StringIO()
        err = ""
        final_answer = None
        timed_out = False

        try:
            with redirect_stdout(buffer):
                exec(code, self.namespace)

        except ExecTimeout:
            err = f"Execution timed out after {self.alarm_seconds} seconds"
            timed_out = True

        except FinalAnswer as fa:
            final_answer = str(fa.value)
        except Exception:
            err = traceback.format_exc(chain=True)

        finally:
            signal.alarm(0)

        return Results(
            output=buffer.getvalue(),
            error=err,
            final_ans=final_answer,
            timed_out=timed_out,
        )

    def _make_tool_function(self, client: MCPClient, tool_name: str
                            ) -> Callable[..., str]:
        def tool_function(**kwargs: Any) -> str:
            return client.call_tool(tool_name, kwargs)

        return tool_function

    def add_tools(self, client: MCPClient) -> None:
        for tool in client.tools_list:
            if tool.name == "final_answer":
                continue

            self.namespace[tool.name] = self._make_tool_function(
                client, tool.name)

    def get_manual(self, client: MCPClient | None = None) -> str:
        manual_string = "final_answer(answer: str): submit your final answer and end the task.\n"

        if client is not None:
            for tool in client.tools_list:
                if tool.name == "final_answer":

                    continue

                properties = tool.input_schema.get('properties', {})
                param_strings: list[str] = []

                for param_name, param_info in properties.items():
                    param_strings.append(f"{param_name}: {param_info.get('type', 'any')}")

                desc = tool.description if tool.description is not None else ''

                tool_string = f"{tool.name}({', '.join(param_strings)}): {desc}"

                manual_string += f"{tool_string}\n"

        return manual_string
