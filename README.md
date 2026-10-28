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

The SWE-bench tool server (`mcp_tools_swebench.py`) takes the same options. It works on the repository at `TESTBED_PATH` (`/testbed` if unset). `run_tests` also needs `SWE_TASK_FILE`, the path to the task JSON, to read the eval script.

[↑ Back to top](#top)

## System Architecture

- `sandbox/`: the sandbox (`sandbox.py`), its child process (`child_process.py`), security restrictions (`security.py`), output streaming (`output_stream.py`), config loading (`config.py`), `final_answer` (`final_answer.py`), the MCP client (`mcp_client.py`) and the REPL (`repl.py`).
- `common/`: code shared between the sandbox, agents and tool servers: the moulinette models (`models_public.py`), JSON loading into Pydantic models (`json_loader.py`), the agent and tool server CLI parsers (`arg_parsers.py`), pipe messages (`messages.py`) and size-limited output collection (`output_collector.py`).
- `mcp_tools_mbpp.py`: MCP server with the MBPP tools.
- `mcp_tools_swebench.py`: MCP server with the SWE-bench tools; `swebench_tools/` holds their implementations (`file_management.py`, `search.py`, `execution.py`) and the workspace classes (`tool_workspace.py`, `local_workspace.py`).
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

Each tool is registered in `mcp_tools_swebench.py` as a thin wrapper that resolves paths, turns errors into `ToolError` messages the LLM can read, and truncates long output. The implementations in `swebench_tools/` never touch the repository directly: they read, write and run commands through a workspace (`WorkspaceBase`). `LocalWorkspace` works on a local folder; a Docker workspace can be added later without changing the tools.

The subject leaves several details of the tools open (V.4, V.5). The choices made, and why:

- **Return values:** the subject describes some outputs only as "output", and doesn't say what `run_tests()` returns. The return value is the only thing the LLM gets back, so every tool returns its result as text; `run_tests()` returns the eval script's exit code, stdout and stderr.
- **Paths:** relative paths are resolved from the repository root, `TESTBED_PATH`. If it isn't set, `/testbed` is used, the repository's location in the SWE-bench containers.
- **`read_file`:** lines are numbered from 1, like `cat -n`. An `end_line` past the end of the file returns the rest of the file with a note giving its line count, instead of an error.
- **`edit_file`:** `old_str` must occur exactly once; otherwise nothing is changed and the error says how often it was found. This avoids editing the wrong place silently. After a `.py` file is edited, a warning is added if it no longer compiles (required by V.1).
- **`list_files`:** `pattern` is a shell-style file name pattern (e.g. `*.py`). Subdirectories are searched, `.git` is skipped, and only files are listed.
- **`search_code`:** `pattern` is an extended regex (`grep -E`), `file_pattern` a shell-style pattern for which files to search, and the whole repository is searched.
- **`search_function_or_class_definition_in_code`:** finds lines that define the name with `def`, `async def` or `class`.
- **`find_references`:** the subject doesn't say what `filepath` and `line` are for. They are used to leave the definition itself out of the results.
- **`get_patch`:** new, untracked files are included in the diff (`git add -N`), so a fix that adds a file is complete. An empty diff returns a message instead of an empty string.
- **Long output:** tool results longer than 10,000 characters keep their start and end with a marker saying how much was cut, so the LLM knows output is missing (V.1). `get_patch` is never cut, since a cut patch would be broken.

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
