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

### Folder layout

The repository is used next to the moulinette and the exam scripts, as in the evaluation:

```
eval_root/
├── student/      # this repository
├── moulinette/   # unzipped moulinette.zip
├── exams/        # unzipped exams.zip
└── .env          # API keys, see .env.example
```

Every `make` command below runs from `student/`, and every moulinette rule uses `../moulinette` (pass `MOULINETTE_DIR=<path>` for another location).

API keys are never in the code. They are read from the environment, after a `.env` file is loaded: for each provider in `models_config.json`, `<key_prefix>` (e.g. `GEMINI_API_KEY`), then `<key_prefix>_1`, `<key_prefix>_2`, and so on. Both agents use `gemini-3.1-flash-lite` through Google AI Studio unless `--model-name` and `--provider-url` say otherwise, so a `GEMINI_API_KEY` (or `GEMINI_API_KEY_1`) is enough to run everything.

### Setup

```bash
cd student
make setup          # uv sync in student/ and in ../moulinette
make pull-images    # pulls python:3.11-slim and the 6 exam-pool images (a few minutes)
```

`make pull-images` is optional but recommended: a SWE-bench run that has to download its image spends part of its 900-second budget on it. Docker must be running.

On 42 computers, everything that validates a SWE-bench solution (the moulinette's `validate swebench`, `make validate-swebench`) must run inside `rootlesskit bash`, otherwise Docker fails with `failed to Lchown "/tmp/patch.diff"`. Start it first, then run the command inside it.

### Tool servers and agents

The interactive sandbox is started with `uv run sandbox`, optionally followed by a JSON config file (e.g. `sandbox_template.json`). Without one, the defaults from the subject are used. An MCP server is connected with `--mcp-stdio "<command>"` (the sandbox starts the server itself) or `--mcp-server <URL>` (an already running server over streamable HTTP; while the connection is refused, e.g. because the server is still starting, it is tried again every 0.5 seconds for up to 30 seconds). A block such as a `def` or a `for` loop is typed over several lines at a `... ` prompt and ends with an empty line. Input piped into the sandbox (e.g. `cat test.py | uv run sandbox`) runs as one entry. Type `exit` or press Ctrl+D to quit.

The MBPP tool server runs over stdio by default. Start it with `python mcp_tools_mbpp.py --http [--port N]` to serve it over streamable HTTP instead, at `http://127.0.0.1:N/mcp` (port 8000 by default).

The SWE-bench tool server (`mcp_tools_swebench.py`) takes the same options. With `TESTBED_PATH` set, it works on that local folder. Otherwise, with `SWE_TASK_FILE` set to a task JSON, it starts that task's Docker container and works on `/testbed` inside it; Docker must be running. With neither, it works on a local `/testbed` folder. A path starting with `/testbed` is mapped to the repository root, so the same paths work in all three cases. `run_tests` reads the eval script from `SWE_TASK_FILE`.

An agent is run with `uv run python -m agent_mbpp --task-file <task.json> --output <solution.json> [--model-name <model> --provider-url <url>]` (`agent_swebench` takes the same options). The provider is found in `models_config.json` by matching `--provider-url`. The agent prints nothing on success: it writes a `SolutionOutput` JSON to `--output`.

### Single tasks during development

The moulinette needs Python 3.12 while the agents run on Python 3.10, so the `make` rules call it with `uv run --python 3.12` (its `quickstart.sh` calls a plain `uv run` and fails on Python 3.10).

```bash
# MBPP
make dump-mbpp ID=11                  # without ID: a random task; SEED=42 repeats a random pick
make run-mbpp                         # MODEL=qwen/qwen3.8-27b URL=https://api.groq.com/openai/v1 for Groq
make validate-mbpp
make display

# SWE-bench (validation inside rootlesskit bash on 42 computers)
make dump-swebench ID=sympy__sympy-14711
make run-swebench
make validate-swebench
make display SOLUTION=cache/swebench_solution.json
```

The tool server starts and removes the task's Docker container by itself; `docker ps | grep sweb.eval` in another terminal shows it while the agent runs. For batches, `scripts/eval_mbpp.sh` and `scripts/eval_swebench.sh` dump, run and validate several tasks in a row (see System Architecture); with the folder layout above, run them as `MOUL_DIR=../moulinette bash scripts/eval_mbpp.sh 5`.

[↑ Back to top](#top)

## System Architecture

- `agent/`: the agent loop shared by both agents: the loop (`loop.py`: `run_agent`, `make_generate`, history compaction), code extraction from the reply in any format (`extract.py`), formatting of sandbox results and feedback messages for the LLM (`observation.py`) and writing of `solution.json` (`solution.py`).
- `llms/`: the LLM layer: provider config and API keys (`model_loader.py`), requests with retries and key rotation (`request_handler.py`) and the Pydantic models (`models.py`).
- `sandbox/`: the sandbox (`sandbox.py`), its child process (`child_process.py`), security restrictions (`security.py`), output streaming (`output_stream.py`), config loading (`config.py`), `final_answer` (`final_answer.py`), the MCP client (`mcp_client.py`) and the REPL (`repl.py`).
- `common/`: code shared between the sandbox, agents and tool servers: the moulinette models (`models_public.py`), JSON loading into Pydantic models (`json_loader.py`), the agent and tool server CLI parsers (`arg_parsers.py`), pipe messages (`messages.py`) and size-limited output collection (`output_collector.py`).
- `mcp_tools_mbpp.py`: MCP server with the MBPP tools.
- `mcp_tools_swebench.py`: MCP server with the SWE-bench tools; `swebench_tools/` holds their implementations (`file_management.py`, `search.py`, `execution.py`) and the workspace classes (`tool_workspace.py`, `local_workspace.py`, `docker_workspace.py`).
- `agent_mbpp/`, `agent_swebench/`: the two agent entry points. Each has its `__main__.py` (limits, setup, fallback answer), its `prompt.py` (system prompt and first message) and its `mcp_setup.py` (connection to its tool server).
- `models_config.json`: the LLM providers (base URL and API key variable prefix). `sandbox_template.json`: an example sandbox config. `pyproject.toml` and `Makefile`: dependencies, and the `make` rules listed in Instructions (setup, sandbox modes, single-task runs, `make lint`, `make clean`).
- `bench/`: the `solution.json` files behind `BENCHMARK_REPORT.md`. `scripts/eval_mbpp.sh`: runs N MBPP tasks through the moulinette, the given IDs first and the rest random (`bash scripts/eval_mbpp.sh N [ID...]`). `scripts/eval_swebench.sh`: dumps, runs (under the 900-second `run-agent` limit) and validates the given SWE-bench tasks, all 6 exam-pool tasks by default, and checks that no container is left (`bash scripts/eval_swebench.sh [ID...]`; on the school computers, inside `rootlesskit bash`). Both scripts run from the repo root and read three optional environment variables: `MODEL` and `URL` (defaults: qwen on Groq for MBPP, Gemini for SWE-bench) and `MOUL_DIR`, the moulinette folder (default: `moulinette/` in the repo; `MOUL_DIR=../moulinette` with the folder layout in Instructions).

[↑ Back to top](#top)

## Agent Loop

The loop is in `agent/loop.py` (`run_agent`). It starts from a system prompt and the task as the first user message, then repeats up to `max_iterations` times:

1. The limits are checked before each request: wall-clock time, cumulative output tokens, and cumulative input tokens (the next request is estimated from the last request's input and output tokens plus the last observation, at about 3 characters per token). The input check keeps 100 tokens (`INPUT_TOKEN_RESERVE`) in reserve below the limit, since the estimate can be a little low. If one is exceeded, the loop stops and `error` names it (`max_time`, `max_output_tokens`, `max_input_tokens`, or `max_iterations` when the steps run out).
2. The LLM is called. Before each request, every observation of the history except the last message is cut to 600 characters (`OLD_OBSERVATION_LIMIT`) with the marker `[old observation cut]`, so old tool output doesn't use the input budget at every later step. The reply is cut after the first code block or tool call, which removes any `Observation:` the model wrote itself. An empty reply is replaced by `(empty reply)`, so that no empty assistant message is sent. The code comes from a fenced `python` block or, for models that answer in another format, from an XML `<invoke>` call, a Hermes `<tool_call>` or a ReAct `Action` / `Action Input` pair, which `agent/extract.py` converts to an equivalent Python call (`result = tool(...)` followed by `print(result)`). The earliest match in the reply is used. A block with no code in it counts as no block.
3. The code runs in the sandbox. Its output becomes the next user message, `Observation: ...`. A reply without a code block gets a reminder asking for a Thought and exactly one block instead, and is kept in the history cut to 150 characters (`NO_CODE_REPLY_LIMIT`) with the marker `[reply cut]`, since a long prose reply would otherwise be sent again at every later step (the input estimate counts the cut size). When a reply in another format was converted, the observation starts with a note showing the Python code that was run, and a code block tagged `Python` (or any tag other than `python`/`py`) is run with a note asking for the lowercase tag. A reply whose `python` block was opened but never closed (cut off by the token limit) runs nothing and gets a message saying so; this is checked on the full reply, before it is cut to 150 characters.
4. If the code calls `final_answer()`, the answer is stored and the rest of the code still runs; once the run is over, the loop ends and returns the answer.

Each step is recorded as a `StepMetrics` (tokens, request time, raw LLM output, sandbox input and output, retries, API URL and model), and the agent entry points build the `SolutionOutput` from them. Observations (`agent/observation.py`) contain the printed output, the last three lines of an error, and a note when the run timed out, the sandbox restarted (variables lost) or the output was truncated.

The LLM layer is in `llms/`. `make_generate` binds the loop to one model and one provider: the provider is chosen from `models_config.json` by its `base_url`, and its keys are read from the environment (`<key_prefix>`, then `<key_prefix>_1`, `<key_prefix>_2`, ...). A URL missing from the config is accepted too: `guess_provider` derives the key variable from the host name (`https://api.together.xyz/v1` gives `TOGETHER_API_KEY`), and the run fails at start-up with a clear message if no such key is set. Requests go to `<base_url>/chat/completions` with a 60-second timeout, the stop sequences `<end_code>` and `Observation:`, and a cap of 400 output tokens per generation. A reply whose content is a list of parts (as reasoning models send it) is joined from its text parts, and a 200 reply that can't be parsed is treated like a server error (code 502). `handle_request` tries the keys in order:

- a 401, 402 or 403 drops the key for this request;
- a 429 moves on to the next key at once; when every key has been tried, the rate-limited keys are retried after the shortest wait the providers gave (the `retry-after` header, or Gemini's `retryDelay`; 60 seconds when neither is given, and never more than 60), for at most 3 waits;
- a 5xx, a malformed 200 reply, a timeout or any other request error is retried up to 3 times on the same key (2 seconds apart) before moving on;
- any other error code stops the run.

When every key has failed, the run ends with the error `all keys failed`. An optional deadline caps each request's timeout and every wait; once it has passed, no request is sent and the run ends with `max_time`. Requests sent by a step that ended in failure are still counted in `total_requests`. There is no fallback between providers: a run uses one.

### MBPP Agent

`agent_mbpp/` runs the loop with a short budget: 10 iterations, 6,000 input tokens, 1,500 output tokens, 120 seconds. `mcp_setup.py` starts `mcp_tools_mbpp.py` over stdio and adds its tools to the sandbox, and the sandbox manual is appended to the system prompt (`prompt.py`). The prompt tells the model to put its function in a string `code` and the given assertions in a list `tests`, check them with `run_tests(code, tests)`, fix and repeat until `success` is true, then call `final_answer(code)`. The task's test imports are added to the first message, and the prompt asks for every import the tests need to be put in `code`. The answer is the function source; the output has `benchmark="mbpp"`. Two timers count from start-up: no request is sent after 100 seconds (`DEADLINE_SECONDS`), and each code run gets at most the time left until 110 seconds (`MAX_TIME_SECONDS` minus `SHUTDOWN_MARGIN_SECONDS`), so a step that hangs near the end can't push the run past the 120-second limit. If the loop ends without `final_answer`, the agent prints the sandbox's `code` variable and submits it if it compiles and defines a function. If the loop crashes, `solution.json` is still written, with the error `crash: ...`. If the MCP connection fails, the agent prints a clear error and exits with code 1. The sandbox and the MCP client are always closed in a `finally`.

### SWE-bench Agent
 
`agent_swebench/` runs the same loop with the SWE-bench limits: 30 iterations, 300,000 input tokens, 10,000 output tokens, 900 seconds. The time budget counts from the start of the process, so the container start-up is included.

- **Connection:** `mcp_setup.py` sets `SWE_TASK_FILE` to the absolute path of the task JSON, removes `TESTBED_PATH` from the environment (otherwise the server would work on a local folder instead of Docker), and starts `mcp_tools_swebench.py` over stdio. The connection waits up to 300 seconds (`MCP_CONNECT_TIMEOUT`), because the server starts the task's container before it answers and may first have to pull the image. The server starts the task's container and removes it when it exits. The agent never manages Docker itself.
- **Prompt:** `prompt.py` builds the first message from the repository, the issue and the hints (if any). The system prompt asks the model to explore with the search tools, read small line ranges, make the smallest `edit_file` change, never edit test files, and read the test results in the `run_tests` output rather than its exit code (the eval script always exits with 0). Once the tests pass, the model submits `final_answer(get_patch())`. It also tells the model to work only from the repository and the task description, and never to look for the fix outside them (V.1 and VI.4.1 of the subject). Two rules came from the runs on the exam-pool tasks: `search_code` takes a file name pattern such as `*.py` as `file_pattern`, never a path (a path matches nothing and gives a false "no lines matched"), and `old_str` should be a short piece of one line, without the line number prefix, the indentation or the closing brackets, because retyping those wrongly was the usual cause of failing edits. The rules are general: none of them names a task.
- **Output:** `benchmark="swebench"`, `task_id` is the instance id, and `solution` is the git patch.
- **Fallback:** the loop gets the time limit minus `TIME_MARGIN_SECONDS` (360 seconds), kept in reserve for the end of the run. If the model's answer is not a diff (it never called `final_answer`, or passed plain text to it), the agent calls `get_patch` itself and submits the repository diff, so edits made before the loop stopped (or crashed) are not lost.
- **Cleanup:** the sandbox and the MCP client are closed in a `finally`, so the container is removed after a normal run or an error. A SIGTERM handler turns the signal into `sys.exit(1)`, so the same cleanup runs when the moulinette kills a timed-out agent. A container that outlives a SIGKILL stops by itself after 20 minutes.

[↑ Back to top](#top)

## Sandbox Design

Sandboxed code runs in a separate child process, connected to the parent by a `multiprocessing` pipe. The child keeps one namespace between runs, so variables persist across steps. If the child crashes, times out or sends something unexpected, it is restarted and the result reports that the state was reset.

Restrictions, configured through `SandboxConfig` (JSON file or defaults):

- **Imports:** `__import__` is replaced by an allowlist check; an entry ending in `.*` also allows that module's submodules. Attributes of allowed modules that lead to non-allowed modules (e.g. `random._os`) are found at startup and blocked.
- **Filesystem:** `open()` resolves the path with `os.path.realpath` and only opens files inside `allowed_directories`.
- **Builtins:** only an allowlist of builtins is available.
- **Network:** `socket.socket` and `socket.getaddrinfo` are replaced in the child.
- **AST check:** code accessing dunder names or frame/traceback attributes is rejected before it runs. So is code using functions that reach attributes or run `eval` through a string (`operator.attrgetter`, `string.Formatter`, `typing.get_type_hints` and a few others in `STRING_ACCESS_BLACKLIST`), whether they are used by name, as an attribute or imported under another name.
- **Timeout:** enforced by the parent; the child is killed when the time runs out. Time spent in MCP tool calls doesn't count.
- **Memory:** `RLIMIT_AS` in the child, plus a 100 MB per-file size limit. The limit counts the child's whole virtual memory, including what it inherits from the parent at the fork, so code gets somewhat less than `max_memory_mb` (a little over 300 MB of the default 512).

Printed output is streamed to the parent while the code runs, so partial output survives a timeout. Output and errors are truncated to a limit (10,000 characters by default), keeping the first quarter and the last three quarters with a marker stating how much was cut.

`final_answer()` is always in the namespace and is not an MCP tool. It stores its argument and returns, so the code after it still runs. The child sends the stored answer back with the run's result, and the agent loop stops once the run is over. There is no exception to catch, so `except` clauses in generated code can't lose the answer.

`SystemExit` and `KeyboardInterrupt` are available to the code and are not caught silently: when the code raises one, its traceback comes back as the error of that run and reaches the agent loop in the observation (V.2, exception propagation). The child ignores SIGINT, so a real Ctrl+C is handled by the parent and stops the agent.

MCP tools are injected into the namespace as wrapper functions. A call is sent from the child to the parent, which checks and maps the arguments (positional arguments are matched to the tool's schema parameters) and calls the server. If the server provides resources or prompts, `read_resource_uri(uri)` and `read_prompt_info(name, args)` are added the same way. The manual given to the LLM is generated from the connected server's tool, resource and prompt listings; each parameter is shown with its Python type (e.g. `test_list: list[str]`) and its default, if any (e.g. `pattern: str = '*'`).

[↑ Back to top](#top)

## Tool Implementation

### MBPP Tools

`run_tests(code, test_list)` runs each assertion in its own Python subprocess together with the candidate code, with a 5-second timeout per assertion, so one failing or hanging test doesn't hide the others. It returns a JSON string with `success` (true only if every assertion passed) and `output` (one PASS, FAIL or TIMEOUT line per assertion, with the last line of the error for failures; a failed `==` assertion reports the value it got, as `got <value>`). Error messages are cut to 300 characters with a marker. Each subprocess gets only `PATH` as its environment, so the candidate code can't read API keys or other variables of the server. An empty test list returns `success: false`. Imports needed by the tests must be included in `code`.

The server supports stdio and streamable HTTP (see Instructions).

### SWE-bench Tools

Each tool is registered in `mcp_tools_swebench.py` as a thin wrapper that resolves paths, turns errors into `ToolError` messages the LLM can read, and truncates long output. The implementations in `swebench_tools/` never touch the repository directly: they read, write and run commands through a workspace (`WorkspaceBase`). `LocalWorkspace` works on a local folder, `DockerWorkspace` inside the task's container through `docker exec`.

The subject leaves several details of the tools open (V.4, V.5). The choices made, and why:

- **Return values:** the subject describes some outputs only as "output", and doesn't say what `run_tests()` returns. The return value is the only thing the LLM gets back, so every tool returns its result as text; `run_tests()` returns the eval script's exit code, stdout and stderr.
- **Paths:** relative paths are resolved from the repository root: `TESTBED_PATH` locally, `/testbed` in the container. A path starting with `/testbed` is mapped to the repository root, so paths written for the container also work on a local folder. With neither `TESTBED_PATH` nor `SWE_TASK_FILE`, the server still starts and works on a local `/testbed`, so `uv run sandbox --mcp-stdio "python mcp_tools_swebench.py"` never fails to connect.
- **Docker (V.4):** the sandbox runs on the host and the tools reach into the container (option b). The tool server owns the container: it is removed when the server exits or gets SIGTERM, and stops by itself after 20 minutes if the server is killed with SIGKILL. The container runs with `--network none`, so code in it (e.g. through `run_command`) can't reach the network or fetch a solution; the eval scripts of all 6 exam-pool tasks were checked to run without it. Shell commands run through `bash -lc` so the task's conda environment is active, and every command is stopped by `timeout` inside the container.
- **`read_file`:** lines are numbered from 1, like `cat -n`. An `end_line` past the end of the file returns the rest of the file with a note giving its line count, instead of an error.
- **`edit_file`:** `old_str` must occur exactly once; otherwise nothing is changed and the error says how often it was found. This avoids editing the wrong place silently. After a `.py` file is edited, a warning is added if it no longer compiles (required by V.1).
- **`list_files`:** `pattern` is a shell-style file name pattern (e.g. `*.py`). Subdirectories are searched, `.git` is skipped, and only files are listed.
- **`search_code`:** `pattern` is an extended regex (`grep -E`), `file_pattern` a shell-style pattern for which files to search, and the whole repository is searched. A search that runs past its time limit fails with a `TIMEOUT` error rather than reporting matches.
- **`search_function_or_class_definition_in_code`:** finds lines that define the name with `def`, `async def` or `class`.
- **`find_references`:** the subject doesn't say what `filepath` and `line` are for. They are used to leave the definition itself out of the results.
- **`get_patch`:** new, untracked files are included in the diff (`git add -N`), so a fix that adds a file is complete. An empty diff returns a message instead of an empty string.
- **Long output:** tool results longer than 9,000 characters keep their start and end with a marker saying how much was cut, so the LLM knows output is missing (V.1). `get_patch` is never cut, since a cut patch would be broken.

[↑ Back to top](#top)

## Benchmark Results and Analysis

The full report is in [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md), and the backing `solution.json` files are in `bench/`. Five models from two providers were run on the same three SWE-bench Verified tasks (`sympy__sympy-13480`, `pydata__xarray-4629`, `sympy__sympy-14711`), with the same prompt, tools and limits, and every run was validated with the moulinette.

| Provider | Model | Passed | Iterations on sympy-14711 | Avg response time |
|---|---|---|---|---|
| Mistral | `codestral-latest` | 2/3 | 27 (fail) | 866 ms |
| Mistral | `ministral-14b-latest` | 3/3 | 30 | 1,349 ms |
| Mistral | `ministral-8b-latest` | 3/3 | 20 | 1,161 ms |
| Mistral | `ministral-3b-latest` | 2/3 | 30 (fail) | 857 ms |
| Google | `gemini-3.1-flash-lite` | 3/3 | 21 | 2,685 ms |

- 13 of the 15 runs pass. Every model solves sympy-13480 and xarray-4629 with the same fix in 4 to 9 iterations (except `ministral-3b-latest` on sympy-13480), so only sympy-14711 separates them.
- **Selected model for SWE-bench: `gemini-3.1-flash-lite`.** It passes the three tasks above and, on the final code, all 6 tasks of the exam pool (slowest task 156 s of the 900 s allowed), against 5 of 6 for `ministral-8b-latest`. It is slower per request (2,685 ms against 857 to 1,349 ms for the Mistral models), and its free tier allows about 15 requests per minute, so its tasks are run one at a time. The runner-up is `ministral-8b-latest`: it passes the three tasks with the fewest iterations and tokens on sympy-14711 (20 iterations, 110,927 input tokens) and submits as soon as its tests pass.
- **MBPP:** `qwen/qwen3.8-27b` on Groq passes 15 of 15 tasks in three series of 5 on the final code, and 37 of 40 in two earlier series of 20.
- **Reliability:** 212 requests, no retries and no failed request during the runs. Gemini's free tier allows about 15 requests per minute, so its runs were launched one at a time.
- **Ablation:** with the `get_patch` fallback removed, the 2 runs that ended without `final_answer` fail, so 11 of 15 runs pass instead of 13. Removing the `search_code` rule from the prompt changes nothing measurable with Gemini on scikit-learn-13439 (3 of 3 runs pass with and without it).
- **Docker cleanup:** no container is left after 6 SWE-bench runs, or after the agent is killed with `kill -9` during a run.
- **Disregarded:** `codestral-latest` (hits the input token cap on sympy-14711), `ministral-3b-latest` (repeats failing edits, one invalid patch), reasoning models such as `mistral-large-4` (their reasoning uses up the 400-token reply cap), and `mistral-small-latest` / `mistral-medium-latest` (no free quota on our key).

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

As part of the research process, especially where the subject left a behaviour unspecified (for example empty test lists, exposing MCP resources and prompts, or truncating long output), I (speterse) compared how several other students had interpreted the requirement, weighed the trade-offs of each approach, and designed and wrote my own implementation from that comparison. The following github repo's were viewed:
- kylianmthr/AgentSmith
- sousampere/42_agent_smith
- Naitchi/Agent-Smith
- Gabinap/agent_smith
- tlaranje/Agent-Smith

### AI Usage

- Explaining new concepts and libraries: mcp 1.26.0 (FastMCP and MCPClient, stdio and HTTP, resources and prompts), asyncio, multiprocessing pipes, the Docker CLI, and how SIGTERM and SIGKILL are delivered.
- Comparing free LLM providers and their limits (Groq, Gemini, OpenRouter, Mistral).
- Docstrings (Google style, 79 characters), README sections, and keeping them accurate after code changes.
- Parts of this README
- Debugging and testing.
- Resolving an issue with the moulinette code preventing it from using Python 3.10 correctly.
- Helping understand the structure of the existing code and how its elements connect to each other.
- Auditing the code of `agent/`, `llms/`, `agent_mbpp/` and `agent_swebench/` against the subject.
- Fixing the issues found by the audit.
- Helping with prompting (system prompts of both agents).
- Diagnosing failed runs from the `solution.json` traces.
- Testing.
- Writing the MBPP script (`scripts/eval_mbpp.sh`).
- Writing the benchmark report.

[↑ Back to top](#top)
