*This project has been created as part of the 42 curriculum by speterse, jpik.*

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

The SWE-bench tool server (`mcp_tools_swebench.py`) takes the same options. With `TESTBED_PATH` set, it works on that local folder. Otherwise it starts the Docker container of the task JSON at `SWE_TASK_FILE` and works on `/testbed` inside it; Docker must be running. `run_tests` reads the eval script from `SWE_TASK_FILE` in both modes.

Run an agent with `uv run python -m agent_mbpp --task-file <task.json> --output <solution.json> --model-name <model> --provider-url <url>` (`agent_swebench` takes the same options). The provider is found in `models_config.json` by matching `--provider-url`, and its API keys are read from `.env` as `<key_prefix>_1`, `<key_prefix>_2`, and so on. The agent prints nothing on success: it writes a `SolutionOutput` JSON to `--output`. For SWE-bench, Docker must be running, and pulling the task's image beforehand (`docker pull <docker_image>`) avoids a slow first run.
 
The moulinette (`moulinette_eval`) needs Python 3.12 while the agents run on Python 3.10, so its steps are run one by one with `uv run --python 3.12` (`quickstart.sh` calls a plain `uv run` and fails on Python 3.10). For example, for MBPP (replace `mbpp` with `swebench` for SWE-bench, and add `--task-id <id>` to the dump to pick a task):
 
```
cd moulinette
PYTHONPATH="$PWD" uv run --python 3.12 moulinette_eval dump mbpp --output ../cache/mbpp_task.json
cd ..
uv run python -m agent_mbpp --task-file cache/mbpp_task.json --output cache/mbpp_solution.json --model-name <model> --provider-url <url>
cd moulinette
PYTHONPATH="$PWD" uv run --python 3.12 moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

[↑ Back to top](#top)

## System Architecture

- `sandbox/`: the sandbox (`sandbox.py`), its child process (`child_process.py`), security restrictions (`security.py`), output streaming (`output_stream.py`), config loading (`config.py`), `final_answer` (`final_answer.py`), the MCP client (`mcp_client.py`) and the REPL (`repl.py`).
- `common/`: code shared between the sandbox, agents and tool servers: the moulinette models (`models_public.py`), JSON loading into Pydantic models (`json_loader.py`), the agent and tool server CLI parsers (`arg_parsers.py`), pipe messages (`messages.py`) and size-limited output collection (`output_collector.py`).
- `mcp_tools_mbpp.py`: MCP server with the MBPP tools.
- `mcp_tools_swebench.py`: MCP server with the SWE-bench tools; `swebench_tools/` holds their implementations (`file_management.py`, `search.py`, `execution.py`) and the workspace classes (`tool_workspace.py`, `local_workspace.py`, `docker_workspace.py`).
- `agent_mbpp/`, `agent_swebench/`: agent entry points.

[↑ Back to top](#top)

## Agent Loop

The loop is in `agent/loop.py` (`run_agent`). It starts from a system prompt and the task as the first user message, then repeats up to `max_iterations` times:
 
1. The limits are checked before each request: wall-clock time, cumulative output tokens, and cumulative input tokens (the next request is assumed to be as large as the last one). If one is exceeded, the loop stops and `error` names it (`max_time`, `max_output_tokens`, `max_input_tokens`, or `max_iterations` when the steps run out).
2. The LLM is called. Its reply is cut after the first fenced code block, which removes any `Observation:` the model wrote itself, and the first `python` block is extracted.
3. The code runs in the sandbox. Its output becomes the next user message, `Observation: ...`. A reply without a code block gets a reminder asking for a Thought and exactly one block instead.
4. If the code calls `final_answer()`, the loop ends and the answer is returned.
Each step is recorded as a `StepMetrics` (tokens, request time, raw LLM output, sandbox input and output, retries, API URL and model), and the agent entry points build the `SolutionOutput` from them. Observations (`agent/observation.py`) contain the printed output, the last three lines of an error, and a note when the run timed out, the sandbox restarted (variables lost) or the output was truncated.
 
The LLM layer is in `llms/`. `make_generate` binds the loop to one model and one provider: the provider is chosen from `models_config.json` by its `base_url`, and its keys are read from `.env` (`<key_prefix>_1`, `<key_prefix>_2`, ...). Requests go to `<base_url>/chat/completions` with a 60-second timeout, the stop sequence `<end_code>`, and a cap of 400 output tokens per generation. `handle_request` tries the keys in order: a 401 or 429 moves to the next key, a 5xx, timeout or connection error is retried up to 3 times on the same key (2 seconds apart) before moving on, and any other error code stops the run. When every key has failed, the run ends with the error `all keys failed`. There is no fallback between providers: a run uses one.
 
### MBPP Agent
 
`agent_mbpp/` runs the loop with a short budget: 10 iterations, 6,000 input tokens, 1,500 output tokens, 120 seconds. `mcp_setup.py` starts `mcp_tools_mbpp.py` over stdio and adds its tools to the sandbox, and the sandbox manual is appended to the system prompt (`prompt.py`). The prompt tells the model to put its function in a string `code` and the given assertions in a list `tests`, check them with `run_tests(code, tests)`, fix and repeat until `success` is true, then call `final_answer(code)`. The answer is the function source; the output has `benchmark="mbpp"`. If the MCP connection fails, the agent prints a clear error and exits with code 1. The sandbox and the MCP client are always closed in a `finally`.
 
### SWE-bench Agent
 
`agent_swebench/` runs the same loop with the SWE-bench limits: 30 iterations, 300,000 input tokens, 10,000 output tokens, 900 seconds. The time budget counts from the start of the process, so the container start-up is included.
 
- **Connection:** `mcp_setup.py` sets `SWE_TASK_FILE` to the absolute path of the task JSON, removes `TESTBED_PATH` from the environment (otherwise the server would work on a local folder instead of Docker), and starts `mcp_tools_swebench.py` over stdio. The server starts the task's container and removes it when it exits. The agent never manages Docker itself.
- **Prompt:** `prompt.py` builds the first message from the repository, the issue and the hints (if any). The system prompt asks the model to explore with the search tools, read small line ranges, make the smallest `edit_file` change, never edit test files, and read the test results in the `run_tests` output rather than its exit code (the eval script always exits with 0). Once the tests pass, the model submits `final_answer(get_patch())`.
- **Output:** `benchmark="swebench"`, `task_id` is the instance id, and `solution` is the git patch.
- **Cleanup:** the sandbox and the MCP client are closed in a `finally`, so the container is removed after a normal run or an error. A SIGTERM handler turns the signal into `sys.exit(1)`, so the same cleanup runs when the moulinette kills a timed-out agent. A container that outlives a SIGKILL stops by itself after 20 minutes.

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

Each tool is registered in `mcp_tools_swebench.py` as a thin wrapper that resolves paths, turns errors into `ToolError` messages the LLM can read, and truncates long output. The implementations in `swebench_tools/` never touch the repository directly: they read, write and run commands through a workspace (`WorkspaceBase`). `LocalWorkspace` works on a local folder, `DockerWorkspace` inside the task's container through `docker exec`.

The subject leaves several details of the tools open (V.4, V.5). The choices made, and why:

- **Return values:** the subject describes some outputs only as "output", and doesn't say what `run_tests()` returns. The return value is the only thing the LLM gets back, so every tool returns its result as text; `run_tests()` returns the eval script's exit code, stdout and stderr.
- **Paths:** relative paths are resolved from the repository root: `TESTBED_PATH` locally, `/testbed` in the container.
- **Docker (V.4):** the sandbox runs on the host and the tools reach into the container (option b). The tool server owns the container: it is removed when the server exits or gets SIGTERM, and stops by itself after 20 minutes if the server is killed with SIGKILL. Shell commands run through `bash -lc` so the task's conda environment is active, and every command is stopped by `timeout` inside the container.
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
- [Tech With Tim - Build Your Own Agentic Harness in Python](https://www.youtube.com/watch?v=H5o1P8RMiMw)
- [Agentic Loops AI - Agentic AI Engineering](https://github.com/agenticloops-ai/agentic-ai-engineering)
- [Hugging Face - Agents Course](https://huggingface.co/learn/agents-course/en/unit0/introduction)

### AI Usage

[↑ Back to top](#top)
