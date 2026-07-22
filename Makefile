.PHONY: setup test lint type adr new coverage vulture fix radon treepeat ci

setup:
	uv venv
	uv sync --python .venv/bin/python

test:
	uv run pytest

lint:
	uv run ruff check .

vulture:
	uv run vulture --min-confidence 55 wellstatus

fix:
	uv run ruff check . --fix

type:
	uv run mypy

radon:
	uv run .github/scripts/check_radon.sh

treepeat:
	uv run treepeat detect .

ci: test lint type radon treepeat vulture
