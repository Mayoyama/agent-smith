# Lint flags
MYPY_FLAGS = --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
MYPY_EXCLUDES = --exclude '.venv|moulinette|common/models_public.py'
FLAKE8_EXCLUDES = --extend-exclude=.venv,moulinette,common/models_public.py

# LLM (override: make run-mbpp MODEL=... URL=...)
MODEL ?= gemini-3.1-flash-lite
URL ?= https://generativelanguage.googleapis.com/v1beta/openai

# Task and solution files
TASK ?= cache/mbpp_task.json
SOLUTION ?= cache/mbpp_solution.json
SWE_TASK ?= cache/swebench_task.json
SWE_SOLUTION ?= cache/swebench_solution.json
ID ?=
SEED ?=
FULL ?=

# Sandbox (empty CONFIG = subject defaults)
CONFIG ?=
TESTBED ?=
PORT ?= 8000

# Moulinette (default is next to student folder)
MOULINETTE_DIR ?= ../moulinette
MOULINETTE_ENV ?=
MOULINETTE = cd $(MOULINETTE_DIR) && $(if $(MOULINETTE_ENV),UV_PROJECT_ENVIRONMENT=$(MOULINETTE_ENV),) \
	PYTHONPATH=. uv run --python 3.12 moulinette_eval

# =================================================
# EVAL RULES
# =================================================

# Use on fresh clone (need to unzip moulinette first)
setup:
	uv sync
	cd $(MOULINETTE_DIR) && uv sync

pull-images:
	@echo "Pre-pulling Docker images for SWE-bench"
	docker pull python:3.11-slim
	$(MOULINETTE) warmup

# make sandbox CONFIG=sandbox_template.json
sandbox:
	uv run sandbox $(CONFIG)

# make sandbox-mbpp CONFIG=sandbox_template.json
sandbox-mbpp:
	uv run sandbox $(CONFIG) --mcp-stdio "python mcp_tools_mbpp.py"

# make sandbox-stdio SERVER="python ../exams/sandbox_tests/simple_mcp_server.py --stdio"
sandbox-stdio:
	uv run sandbox $(CONFIG) --mcp-stdio "$(SERVER)"

# make sandbox-swebench TESTBED=../my_repo                   (local folder)
# make sandbox-swebench SWE_TASK=cache/swebench_task.json    (Docker; dump-swebench first)
sandbox-swebench:
	$(if $(TESTBED),TESTBED_PATH=$(TESTBED),SWE_TASK_FILE=$(abspath $(SWE_TASK))) \
		uv run sandbox $(CONFIG) --mcp-stdio "python mcp_tools_swebench.py"

# http-setup in seperate window then run sandbox-http in another
http-setup:
	uv run python mcp_tools_mbpp.py --http --port $(PORT)

sandbox-http:
	uv run sandbox $(CONFIG) --mcp-server http://127.0.0.1:$(PORT)/mcp


# Run single task after modifications: useful for testing live coding without full pull again
# make dump-mbpp                 (random task)
# make dump-mbpp ID=11
# make dump-mbpp SEED=42         (same random task every time)
dump-mbpp:
	mkdir -p cache
	$(MOULINETTE) dump mbpp -o $(abspath $(TASK)) $(if $(ID),-t $(ID),) $(if $(SEED),-s $(SEED),)


# make run-mbpp                  (Gemini, cache/mbpp_task.json)
# make run-mbpp MODEL=qwen/qwen3.8-27b URL=https://api.groq.com/openai/v1
run-mbpp:
	uv run python -m agent_mbpp --task-file $(TASK) --output $(SOLUTION) \
		--model-name "$(MODEL)" --provider-url "$(URL)"
	grep -E '"(success|iterations|error)"' $(SOLUTION)


# make display                   (last MBPP solution)
# make display SOLUTION=cache/swebench_solution.json FULL=1
display:
	$(MOULINETTE) display $(abspath $(SOLUTION)) $(if $(FULL),--full,)


# =================================================
# TESTING RULES - NOT FOR EVAL
# =================================================
# make dump-swebench             (random task)
# make dump-swebench ID=sympy__sympy-14711
dump-swebench:
	mkdir -p cache
	$(MOULINETTE) dump swebench -o $(abspath $(SWE_TASK)) $(if $(ID),-t $(ID),)


# make validate-mbpp
# make validate-mbpp TASK=cache/t1.json SOLUTION=cache/s1.json
validate-mbpp:
	$(MOULINETTE) validate mbpp $(abspath $(TASK)) $(abspath $(SOLUTION))

# make validate-swebench         (on school PCs: inside rootlesskit bash)
validate-swebench:
	$(MOULINETTE) validate swebench $(abspath $(SWE_TASK)) $(abspath $(SWE_SOLUTION))

# make run-swebench MODEL=ministral-8b-latest URL=https://api.mistral.ai/v1
run-swebench:
	uv run python -m agent_swebench --task-file $(SWE_TASK) --output $(SWE_SOLUTION) \
		--model-name "$(MODEL)" --provider-url "$(URL)"
	grep -E '"(success|iterations|error)"' $(SWE_SOLUTION)

lint:
	uv run python -m flake8 . ${FLAKE8_EXCLUDES}
	uv run python -m mypy . ${MYPY_FLAGS} ${MYPY_EXCLUDES}

clean:
	find . -not -path './.venv/*' -type d \( -name "__pycache__" -o -name ".mypy_cache" -o -name ".pytest_cache" \)  -exec rm -rf {} +
	find . -type f \( -name "*.pyo" -o -name "*.pyc" -o -name "*~" \) -delete

.PHONY: lint clean run-swebench validate-swebench validate-mbpp dump-swebench display run-mbpp dump-mbpp sandbox-http http-setup sandbox-swebench sandbox-mbpp sandbox pull-images setup
