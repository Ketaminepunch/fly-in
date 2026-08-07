.PHONY: install run debug clean lint lint-strict test fuzz fuzz-search

install:
	uv sync
MAP?= maps/easy/02_simple_fork.txt
ARGS ?=
run:
	uv run python main.py $(MAP) $(ARGS)

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

# Deep, seedable fuzzing pass against the parser (tests/tester.py).
# `make test` above already runs a fast pass of the same file (a few
# hundred Hypothesis examples + a 200-iteration fuzz smoke test); use
# this target when you want to crank iterations way up. Each run
# writes its own timestamped log under tests/fuzz_logs/ (gitignored).
MODE ?= both
N ?= 20000
fuzz:
	uv run python -m tests.tester --mode $(MODE) -n $(N) \
		$(if $(SEED),--seed $(SEED),)

# Search past fuzz runs, e.g. make fuzz-search ARGS="--unexpected-only"
# See tests/README.md for nushell/jq alternatives.
ARGS ?=
fuzz-search:
	uv run python -m tests.fuzz $(ARGS)
