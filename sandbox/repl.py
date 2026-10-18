from .sandbox import Sandbox
from .results import Results


def repl() -> None:
    sandbox = Sandbox()

    while True:
        try:
            line = input(">>> ")

        except EOFError:
            print()

            break

        except KeyboardInterrupt:
            print()
            continue

        if line.strip() == "exit":
            break

        res: Results = sandbox.run_exec(line)

        if res.final_ans is not None:
            print(res.final_ans)

            break

        if res.output:
            print(res.output, end="")

        if res.error:
            print(res.error)
