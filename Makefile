MYPY_FLAGS = --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
MYPY_EXCLUDES = --exclude '.venv|moulinette|common/models_public.py'
FLAKE8_EXCLUDES = --extend-exclude=.venv,moulinette,common/models_public.py
GROQ_MODEL ?= qwen/qwen3.8-27b
GROQ_URL ?= https://api.groq.com/openai/v1
GROQ_OUT ?= cache/mbpp_solution_groq.json
GEMINI_MODEL ?= gemini-3.1-flash-lite
GEMINI_URL ?= https://generativelanguage.googleapis.com/v1beta/openai
GEMINI_OUT ?= cache/mbpp_solution_gemini.json
RUN_MBPP = uv run python -m agent_mbpp --task-file $(TASK)
TASK ?= cache/mbpp_task.json
SEED ?=
MOULINETTE_ENV ?=
MOULINETTE = cd moulinette && $(if $(MOULINETTE_ENV),UV_PROJECT_ENVIRONMENT=$(MOULINETTE_ENV),) \
	PYTHONPATH=. uv run --python 3.12 moulinette_eval
SOLUTION ?= cache/mbpp_solution.json
SWE_TASK ?= cache/swebench_task.json
SWE_SOLUTION ?= cache/swebench_solution.json

dump-mbpp:
	mkdir -p cache
	$(MOULINETTE) dump mbpp -o ../$(TASK) $(if $(ID),-t $(ID),) $(if $(SEED),-s $(SEED),)

dump-swebench:
	mkdir -p cache
	$(MOULINETTE) dump swebench -o ../$(SWE_TASK) $(if $(ID),-t $(ID),)

pull-images:
	docker pull python:3.11-slim
	$(MOULINETTE) warmup

validate-mbpp:
	$(MOULINETTE) validate mbpp ../$(TASK) ../$(SOLUTION)

validate-swebench:
	$(MOULINETTE) validate swebench ../$(SWE_TASK) ../$(SWE_SOLUTION)

run-groq-mbpp:
	$(RUN_MBPP) --output $(GROQ_OUT) --model-name "$(GROQ_MODEL)" --provider-url "$(GROQ_URL)"
	grep -E '"(success|iterations|error)"' $(GROQ_OUT)

run-gemini-mbpp:
	$(RUN_MBPP) --output $(GEMINI_OUT) --model-name "$(GEMINI_MODEL)" --provider-url "$(GEMINI_URL)"
	grep -E '"(success|iterations|error)"' $(GEMINI_OUT)

lint:
	uv run python -m flake8 . ${FLAKE8_EXCLUDES}
	uv run python -m mypy . ${MYPY_FLAGS} ${MYPY_EXCLUDES}

clean:
	find . -not -path './.venv/*' -type d \( -name "__pycache__" -o -name ".mypy_cache" -o -name ".pytest_cache" \)  -exec rm -rf {} +
	find . -type f \( -name "*.pyo" -o -name "*.pyc" -o -name "*~" \) -delete

.PHONY: lint clean run-groq-mbpp run-gemini-mbpp dump-mbpp dump-swebench validate-mbpp validate-swebench pull-images
