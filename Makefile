MYPY_FLAGS = --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
MYPY_EXCLUDES = --exclude '.venv|moulinette|common/models_public.py'
FLAKE8_EXCLUDES = --extend-exclude=.venv,moulinette,common/models_public.py

lint:
	uv run python -m flake8 . ${FLAKE8_EXCLUDES}
	uv run python -m mypy . ${MYPY_FLAGS} ${MYPY_EXCLUDES}

.PHONY: lint