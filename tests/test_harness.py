"""Fuzz and property-based tests for the map parser.

Invariant under test: `parse_map_file` on any input must either return
a `Network` or raise `ParsingError` - anything else (a different
exception, or a hang) is a parser bug.

Run under pytest for a fast pass of both engines:

    pytest tests/test_harness.py -q

Run as a script for a deeper, seedable fuzzing pass (must use -m, so
the repo root is on sys.path and `flyin` is importable):

    python -m tests.test_harness --mode both -n 20000 --seed 1

Or via the Makefile:

    make fuzz N=20000 SEED=1
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from flyin.parser.exceptions import ParsingError
from flyin.parser.map_parser import parse_map_file

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = REPO_ROOT / "maps"
CRASH_DIR = Path(__file__).resolve().parent / "crashes"
LOG_DIR = Path(__file__).resolve().parent / "fuzz_logs"

# An "expected" outcome is either a clean parse or the documented
# ParsingError. Anything else is a crash the parser should not raise.
EXPECTED_OUTCOMES = ("ok", "ParsingError")

# `main()` runs the Hypothesis property tests via an in-process
# `pytest.main()` call, which re-imports this file as a distinct
# module object - a plain module-level list wouldn't be shared with
# the code below. Cases are instead staged to this on-disk file
# (path set via env var so both module instances agree on it) and
# read back once pytest.main() returns.
PROPERTY_STAGING_ENV_VAR = "FLYIN_FUZZ_PROPERTY_STAGING"


def is_expected(outcome: str) -> bool:
    """True if `outcome` is a documented parser result, not a crash."""
    return outcome in EXPECTED_OUTCOMES


FALLBACK_MAP = (
    "nb_drones: 1\n"
    "start_hub: start 0 0\n"
    "end_hub: goal 1 1\n"
    "connection: start-goal\n"
)


def _supports_color() -> bool:
    """True if stdout is a terminal that likely renders ANSI colors."""
    return sys.stdout.isatty()


def _colorize(text: str, code: str) -> str:
    """Wrap `text` in the given ANSI code, unless stdout isn't a tty."""
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(text: str) -> str:
    """Bold `text` for terminal output."""
    return _colorize(text, "1")


def _green(text: str) -> str:
    """Color `text` green for terminal output."""
    return _colorize(text, "32")


def _red(text: str) -> str:
    """Color `text` red for terminal output."""
    return _colorize(text, "31")


def _section(title: str) -> None:
    """Print a bold section header for the CLI summary."""
    print(f"\n{_bold('==>')} {_bold(title)}")


def log_run(
    log_dir: Path,
    mode: str,
    seed: int | None,
    fuzz_iterations: int | None,
    crashes: int,
    elapsed_seconds: float,
    cases: list[dict[str, object]],
) -> Path:
    """Write one CLI invocation's results as its own timestamped file.

    Each call creates a fresh file under `log_dir` (one run per file,
    named by UTC timestamp) instead of appending to a single ever-
    growing log - `cases` can hold thousands of full map texts, so a
    single shared file would balloon indefinitely across runs. `cases`
    covers whichever engine(s) `mode` selected, each tagged with an
    "engine" field ("fuzz" or "property"). Returns the path written.
    """
    timestamp = datetime.now(timezone.utc)
    record = {
        "timestamp": timestamp.isoformat(),
        "mode": mode,
        "seed": seed,
        "fuzz_iterations": fuzz_iterations,
        "crashes": crashes,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "cases": cases,
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    log_path = log_dir / f"fuzz_log_{stamp}.json"
    log_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return log_path


def _stage_property_case(strategy: str, content: str, outcome: str) -> None:
    """Append one property-test case as a JSON line to the staging file.

    No-op unless `PROPERTY_STAGING_ENV_VAR` is set (i.e. unless we're
    running under the CLI's `--mode property`/`both`, not a plain
    `pytest` invocation).
    """
    staging = os.environ.get(PROPERTY_STAGING_ENV_VAR)
    if not staging:
        return
    record = {
        "engine": "property",
        "strategy": strategy,
        "outcome": outcome,
        "expected": is_expected(outcome),
        "content": content,
    }
    with open(staging, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def run_parser_on(content: str, strategy: str = "unknown") -> None:
    """Feed `content` to the parser; only ParsingError may be raised."""
    outcome = "ok"
    crash: Exception | None = None
    with tempfile.TemporaryDirectory() as tmp_dir:
        map_path = Path(tmp_dir) / "map.txt"
        map_path.write_text(content, encoding="utf-8")
        try:
            parse_map_file(str(map_path))
        except ParsingError:
            outcome = "ParsingError"
        except Exception as exc:
            outcome = type(exc).__name__
            crash = exc
    _stage_property_case(strategy, content, outcome)
    if crash is not None:
        raise crash


# ---------------------------------------------------------------------
# Hypothesis strategies: structured-ish random maps
# ---------------------------------------------------------------------

NAMES = st.text(
    alphabet=string.ascii_letters + string.digits + "_-:[]= #",
    min_size=1,
    max_size=12,
)
WIDE_INTS = st.integers(min_value=-(10**12), max_value=10**12)
ZONE_TYPES = st.sampled_from(
    ["normal", "blocked", "restricted", "priority", "bogus"]
)


@st.composite
def nb_drones_lines(draw: st.DrawFn) -> str:
    """Build a `nb_drones:` line, valid or not."""
    value = draw(
        st.one_of(
            WIDE_INTS,
            st.text(max_size=6),
        )
    )
    return f"nb_drones: {value}"


@st.composite
def zone_metadata(draw: st.DrawFn) -> str:
    """Build an optional `[zone=... max_drones=... color=...]` block."""
    zone_type = draw(ZONE_TYPES)
    max_drones = draw(WIDE_INTS)
    color = draw(NAMES)
    body = f"zone={zone_type} max_drones={max_drones} color={color}"
    if draw(st.booleans()):
        return f" [{body}"
    return f" [{body}]"


@st.composite
def zone_lines(draw: st.DrawFn) -> str:
    """Build a `start_hub`/`end_hub`/`hub` line, valid or not."""
    kind = draw(st.sampled_from(["start_hub", "end_hub", "hub"]))
    name = draw(NAMES)
    x = draw(WIDE_INTS)
    y = draw(WIDE_INTS)
    line = f"{kind}: {name} {x} {y}"
    if draw(st.booleans()):
        line += draw(zone_metadata())
    return line


@st.composite
def connection_metadata(draw: st.DrawFn) -> str:
    """Build an optional `[max_link_capacity=N]` block."""
    capacity = draw(WIDE_INTS)
    if draw(st.booleans()):
        return f" [max_link_capacity={capacity}"
    return f" [max_link_capacity={capacity}]"


@st.composite
def connection_lines(draw: st.DrawFn) -> str:
    """Build a `connection:` line, valid or not."""
    name1 = draw(NAMES)
    name2 = draw(NAMES)
    line = f"connection: {name1}-{name2}"
    if draw(st.booleans()):
        line += draw(connection_metadata())
    return line


@st.composite
def map_texts(draw: st.DrawFn) -> str:
    """Build a full structured-ish map file body."""
    lines = [draw(nb_drones_lines())]
    body = draw(
        st.lists(
            st.one_of(zone_lines(), connection_lines()),
            max_size=15,
        )
    )
    lines.extend(body)
    return "\n".join(lines) + "\n"


ADVERSARIAL_ALPHABET = ":-[]=# \n\t0123456789hubconection_startendgl"


# ---------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------

@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(content=map_texts())
def test_property_structured_maps(content: str) -> None:
    """Structured-but-broken maps must never crash unexpectedly."""
    run_parser_on(content, strategy="structured")


@settings(max_examples=200)
@given(content=st.text(min_size=0, max_size=500))
def test_property_pure_garbage(content: str) -> None:
    """Arbitrary unicode garbage must never crash unexpectedly."""
    run_parser_on(content, strategy="pure_garbage")


@settings(max_examples=300)
@given(
    content=st.text(
        alphabet=ADVERSARIAL_ALPHABET, min_size=0, max_size=300
    )
)
def test_property_adversarial_alphabet(content: str) -> None:
    """Garbage built only from the format's own tokens/separators."""
    run_parser_on(content, strategy="adversarial_alphabet")


# ---------------------------------------------------------------------
# Raw mutation fuzzer (no Hypothesis) - also runnable as a script
# ---------------------------------------------------------------------

def load_seed_corpus() -> list[str]:
    """Read every real map file under maps/, falling back if empty."""
    if not MAPS_DIR.is_dir():
        return [FALLBACK_MAP]
    texts = [
        path.read_text(encoding="utf-8", errors="ignore")
        for path in MAPS_DIR.rglob("*.txt")
    ]
    return texts or [FALLBACK_MAP]


def mutate(text: str, rng: random.Random) -> str:
    """Apply one random mutation operator to `text`."""
    lines = text.splitlines()
    ops = [
        "drop_line",
        "dup_line",
        "shuffle",
        "flip_char",
        "truncate",
        "inject_garbage",
        "swap_bracket",
    ]
    op = rng.choice(ops)
    if op == "drop_line" and lines:
        del lines[rng.randrange(len(lines))]
    elif op == "dup_line" and lines:
        lines.insert(rng.randrange(len(lines) + 1), rng.choice(lines))
    elif op == "shuffle" and lines:
        rng.shuffle(lines)
    elif op == "flip_char" and lines:
        i = rng.randrange(len(lines))
        chars = list(lines[i])
        if chars:
            j = rng.randrange(len(chars))
            chars[j] = rng.choice(string.printable)
        lines[i] = "".join(chars)
    elif op == "truncate" and lines:
        lines = lines[: rng.randrange(len(lines) + 1)]
    elif op == "inject_garbage":
        garbage = "".join(
            rng.choices(string.printable, k=rng.randint(0, 40))
        )
        lines.insert(rng.randrange(len(lines) + 1), garbage)
    elif op == "swap_bracket" and lines:
        i = rng.randrange(len(lines))
        if "[" in lines[i] or "]" in lines[i]:
            lines[i] = lines[i].replace("[", "\0").replace(
                "]", "["
            ).replace("\0", "]")
    return "\n".join(lines) + "\n"


def run_fuzz(
    iterations: int, seed: int, save_crashes: Path | None
) -> tuple[int, list[dict[str, object]]]:
    """Run the raw mutation fuzzer.

    Returns `(crash_count, cases)`, where `cases` records every
    generated input with its outcome ("ok", "ParsingError", or a
    crash's exception class name) for JSON logging.
    """
    rng = random.Random(seed)
    corpus = load_seed_corpus()
    crashes = 0
    cases: list[dict[str, object]] = []
    for i in range(iterations):
        mutated = rng.choice(corpus)
        for _ in range(rng.randint(1, 4)):
            mutated = mutate(mutated, rng)
        outcome = "ok"
        with tempfile.TemporaryDirectory() as tmp_dir:
            map_path = Path(tmp_dir) / "map.txt"
            map_path.write_text(mutated, encoding="utf-8")
            try:
                parse_map_file(str(map_path))
            except ParsingError:
                outcome = "ParsingError"
            except Exception as exc:
                crashes += 1
                outcome = type(exc).__name__
                print(
                    _red(f"    [crash {crashes}] iteration={i}"),
                    file=sys.stderr,
                )
                traceback.print_exc()
                if save_crashes is not None:
                    save_crashes.mkdir(parents=True, exist_ok=True)
                    crash_file = save_crashes / f"crash_{crashes}.txt"
                    crash_file.write_text(mutated, encoding="utf-8")
                    print(f"      saved to {crash_file}", file=sys.stderr)
        cases.append(
            {
                "engine": "fuzz",
                "strategy": "mutation",
                "iteration": i,
                "outcome": outcome,
                "expected": is_expected(outcome),
                "content": mutated,
            }
        )
    return crashes, cases


def test_fuzz_smoke() -> None:
    """Small pytest-visible pass of the raw mutation fuzzer."""
    crashes, _ = run_fuzz(iterations=200, seed=0, save_crashes=None)
    assert crashes == 0


# ---------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------

def run_property_tests(
    staging_dir: Path,
) -> tuple[int, list[dict[str, object]]]:
    """Run the Hypothesis property tests via pytest.

    Returns `(pytest_exit_code, cases)`. Every example the property
    tests actually run against `run_parser_on` is recorded via the
    on-disk staging hand-off (see `PROPERTY_STAGING_ENV_VAR`), since
    `pytest.main()` re-imports this file as a separate module object.
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = staging_dir / f".property_staging_{os.getpid()}.jsonl"
    staging_path.write_text("", encoding="utf-8")
    os.environ[PROPERTY_STAGING_ENV_VAR] = str(staging_path)
    try:
        ret = pytest.main(
            [
                __file__,
                "-k", "property",
                "-q",
                "--no-header",
                "-p", "no:warnings",
            ]
        )
    finally:
        os.environ.pop(PROPERTY_STAGING_ENV_VAR, None)

    cases: list[dict[str, object]] = []
    if staging_path.exists():
        for line in staging_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(json.loads(line))
        staging_path.unlink()
    return ret, cases


def main() -> int:
    """Run the raw fuzzer and/or the Hypothesis property tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["fuzz", "property", "both"],
        default="both",
    )
    parser.add_argument(
        "-n", "--iterations", type=int, default=2000,
        help="raw fuzzer iterations",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--save-crashes", type=Path, default=CRASH_DIR
    )
    parser.add_argument(
        "--log-dir", type=Path, default=LOG_DIR,
        help="directory for per-run JSON logs (gitignored)",
    )
    parser.add_argument(
        "--no-json-log", action="store_true",
        help="skip writing a JSON log file for this run",
    )
    args = parser.parse_args()

    exit_code = 0
    seed: int | None = None
    all_cases: list[dict[str, object]] = []
    total_crashes = 0
    started = time.monotonic()

    if args.mode in ("fuzz", "both"):
        seed = (
            args.seed if args.seed is not None
            else random.randrange(2**32)
        )
        _section("Raw mutation fuzzer")
        print(f"    iterations : {args.iterations}")
        print(f"    seed       : {seed} (reuse with --seed {seed})")
        fuzz_started = time.monotonic()
        crashes, fuzz_cases = run_fuzz(
            args.iterations, seed, args.save_crashes
        )
        fuzz_elapsed = time.monotonic() - fuzz_started
        all_cases.extend(fuzz_cases)
        total_crashes += crashes
        passed = crashes == 0
        status = _green("PASS") if passed else _red("FAIL")
        print(
            f"    result     : {crashes} crash(es) "
            f"in {fuzz_elapsed:.1f}s [{status}]"
        )
        if not passed:
            exit_code = 1

    if args.mode in ("property", "both"):
        _section("Hypothesis property tests")
        ret, property_cases = run_property_tests(args.log_dir)
        all_cases.extend(property_cases)
        property_crashes = sum(
            1 for case in property_cases
            if not case.get("expected", True)
        )
        total_crashes += property_crashes
        passed = ret == 0
        status = _green("PASS") if passed else _red("FAIL")
        print(f"    result     : pytest exit={ret} [{status}]")
        if not passed:
            exit_code = 1

    elapsed = time.monotonic() - started
    if not args.no_json_log and all_cases:
        log_path = log_run(
            args.log_dir,
            args.mode,
            seed,
            args.iterations if args.mode in ("fuzz", "both") else None,
            total_crashes,
            elapsed,
            all_cases,
        )
        print(f"\nlog        : {log_path} ({len(all_cases)} cases)")

    overall = _green("ALL GREEN") if exit_code == 0 else _red("CRASHES FOUND")
    print(f"\n{_bold('==>')} {overall}\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
