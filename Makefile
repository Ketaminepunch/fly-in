.PHONY: install run debug clean lint lint-strict test

install:
	uv sync
MAP?= maps/easy/02_simple_fork.txt
run:
	uv run python main.py $(MAP) 

debug:
	uv run python -m pdb main.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache

lint:
	uv run flake8 .
	uv run mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	uv run flake8 .
	uv run mypy . --strict

test:
	uv run pytest
