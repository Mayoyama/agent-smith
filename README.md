*This project has been created as part of the 42 curriculum by .*

<a id="top"></a>

# Agent Smith

## Table of Contents

- [Description](#description)
- [Instructions](#instructions)
- [System Architecture](#system-architecture)
- [Agent Loop](#agent-loop)
- [Sandbox Design](#sandbox-design)
- [Tool Implementation](#tool-implementation)
- [Benchmark Results and Analysis](#benchmark-results-and-analysis)
- [Resources](#resources)

## Description

Agent Smith is a code agent that solves programming tasks autonomously. It runs a Thought → Code → Observation loop: the LLM writes Python code, the code runs in a restricted sandbox, and the output is fed back to the LLM until it submits an answer with `final_answer()`. Tools are provided by MCP servers and are called from the generated code as ordinary Python functions.

The agent is evaluated on two benchmarks: MBPP (short algorithmic Python problems) and SWE-bench Verified (real bug fixes in open-source repositories, inside Docker).

[↑ Back to top](#top)

## Instructions

Install dependencies with `uv sync`. Use `make lint` to run flake8 and mypy, and `make clean` to remove caches and compiled files.

The interactive sandbox is started with `uv run sandbox`, optionally followed by a JSON config file (e.g. `sandbox_template.json`). Without one, the defaults from the subject are used. An MCP server is connected with `--mcp-stdio "<command>"` (the sandbox starts the server itself) or `--mcp-server <URL>` (an already running server over streamable HTTP). Type `exit` or press Ctrl+D to quit.

The MBPP tool server runs over stdio by default. Start it with `python mcp_tools_mbpp.py --http [--port N]` to serve it over streamable HTTP instead, at `http://127.0.0.1:N/mcp` (port 8000 by default).

[↑ Back to top](#top)

## System Architecture

- `sandbox/`: the sandbox (`sandbox.py`), its child process (`child_process.py`), security restrictions (`security.py`), output streaming (`output_stream.py`), config loading (`config.py`), `final_answer` (`final_answer.py`), the MCP client (`mcp_client.py`) and the REPL (`repl.py`).
- `common/`: code shared between the sandbox, agents and tool servers: the moulinette models (`models_public.py`), task loading and the agent CLI parser (`task_loader.py`), pipe messages (`messages.py`), size-limited output collection (`output_collector.py`) and the tool server CLI parser (`tool_arg_parser.py`).
- `mcp_tools_mbpp.py`: MCP server with the MBPP tools.
- `agent_mbpp/`, `agent_swebench/`: agent entry points.

[↑ Back to top](#top)

## Agent Loop

[↑ Back to top](#top)

## Sandbox Design

Sandboxed code runs in a separate child process, connected to the parent by a `multiprocessing` pipe. The child keeps one namespace between runs, so variables persist across steps. If the child crashes, times out or sends something unexpected, it is restarted and the result reports that the state was reset.

Restrictions, configured through `SandboxConfig` (JSON file or defaults):

- **Imports:** `__import__` is replaced by an allowlist check; an entry ending in `.*` also allows that module's submodules. Attributes of allowed modules that lead to non-allowed modules (e.g. `random._os`) are found at startup and blocked.
- **Filesystem:** `open()` resolves the path with `os.path.realpath` and only opens files inside `allowed_directories`.
- **Builtins:** only an allowlist of builtins is available.
- **Network:** `socket.socket` and `socket.getaddrinfo` are replaced in the child.
- **AST check:** code accessing dunder names or frame/traceback attributes is rejected before it runs.
- **Timeout:** enforced by the parent; the child is killed when the time runs out. Time spent in MCP tool calls doesn't count.
- **Memory:** `RLIMIT_AS` in the child, plus a 100 MB per-file size limit.

Printed output is streamed to the parent while the code runs, so partial output survives a timeout. Output and errors are truncated to a limit (10,000 characters by default), keeping the first quarter and the last three quarters with a marker stating how much was cut.

`final_answer()` is always in the namespace and is not an MCP tool: it raises a `BaseException` subclass that ends the run, so `except Exception` in generated code can't swallow it.

MCP tools are injected into the namespace as wrapper functions. A call is sent from the child to the parent, which checks and maps the arguments (positional arguments are matched to the tool's schema parameters) and calls the server. If the server provides resources or prompts, `read_resource_uri(uri)` and `read_prompt_info(name, args)` are added the same way. The manual given to the LLM is generated from the connected server's tool, resource and prompt listings.

[↑ Back to top](#top)

## Tool Implementation

### MBPP Tools

`run_tests(code, test_list)` runs each assertion in its own Python subprocess together with the candidate code, with a 5-second timeout per assertion, so one failing or hanging test doesn't hide the others. It returns a JSON string with `success` (true only if every assertion passed) and `output` (one PASS, FAIL or TIMEOUT line per assertion, with the last line of the error for failures). Error messages are cut to 300 characters with a marker. An empty test list returns `success: false`. Imports needed by the tests must be included in `code`.

The server supports stdio and streamable HTTP (see Instructions).

### SWE-bench Tools

[↑ Back to top](#top)

## Benchmark Results and Analysis

[↑ Back to top](#top)

## Resources

- https://www.geeksforgeeks.org/python/exec-in-python/
- https://docs.python.org/3/library/traceback.html
- https://docs.python.org/3/library/shlex.html
- https://docs.python.org/3/library/multiprocessing.html
- https://github.com/python/typeshed/blob/main/stdlib/builtins.pyi
- Asyncio: https://www.youtube.com/watch?v=K56nNuBEd0c
- Asyncio: https://www.youtube.com/watch?v=Qb9s3UiMSTA

### AI Usage

[↑ Back to top](#top)
