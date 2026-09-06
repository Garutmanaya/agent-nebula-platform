.PHONY: help sync lint test check build clean

help:
	@printf '%s\n' \
	  'help  - show available developer targets' \
	  'sync  - synchronize development dependencies' \
	  'lint  - run Ruff static validation' \
	  'test  - run the automated test suite' \
	  'check - run the standard lint + test quality gate' \
	  'build - build the Python distribution artifacts' \
	  'clean - remove generated local build/test artifacts'

sync:
	uv sync --all-extras

lint:
	uv run ruff check src tests

test:
	uv run pytest

check: lint test

build:
	uv build

clean:
	rm -rf build dist .pytest_cache .ruff_cache
	find src tests -type d -name __pycache__ -prune -exec rm -rf {} +
