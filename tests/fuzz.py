"""Search tests/fuzz_logs/ for fuzz-harness runs and cases.

Each `make fuzz` / `tester.py` invocation writes its own timestamped
JSON file under tests/fuzz_logs/ (one run per file, so the directory
never balloons into a single ever-growing document). This tool loads
every file in that directory as one run, in timestamp order, and lets
you filter across all of them.

Examples:

    python -m tests.fuzz --list-runs
    python -m tests.fuzz --outcome ParsingError --contains dash
    python -m tests.fuzz --unexpected-only
    python -m tests.fuzz --seed 1 --iteration 3 --content

See tests/README.md for nushell/jq alternatives to this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator, cast

DEFAULT_LOG_DIR = Path(__file__).resolve().parent / "fuzz_logs"

# An "expected" outcome is either a clean parse or the documented
# ParsingError. Anything else is a crash the parser should not raise.
EXPECTED_OUTCOMES = ("ok", "ParsingError")


def _supports_color() -> bool:
    """True if stdout is a terminal that likely renders ANSI colors."""
    return sys.stdout.isatty()


def _colorize(text: str, code: str) -> str:
    """Wrap `text` in the given ANSI code, unless stdout isn't a tty."""
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _green(text: str) -> str:
    """Color `text` green for terminal output."""
    return _colorize(text, "32")


def _red(text: str) -> str:
    """Color `text` red for terminal output."""
    return _colorize(text, "31")


def case_expected(case: dict[str, Any]) -> bool:
    """True if `case` is a documented parser result, not a crash.

    Reads the "expected" field written by tester.py directly;
    falls back to checking "outcome" for older log files that predate
    that field.
    """
    if "expected" in case:
        return bool(case["expected"])
    return str(case.get("outcome", "")) in EXPECTED_OUTCOMES


def load_runs(log_dir: Path) -> list[dict[str, Any]]:
    """Load every `fuzz_log_*.json` file in `log_dir` as one run each.

    Files are sorted by name, which sorts chronologically since each
    is timestamped `fuzz_log_<UTC timestamp>.json`. Unreadable or
    non-JSON files are skipped rather than failing the whole load.
    """
    if not log_dir.is_dir():
        return []
    runs: list[dict[str, Any]] = []
    for path in sorted(log_dir.glob("fuzz_log_*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        runs.append(cast(dict[str, Any], run))
    return runs


def print_run_summary(index: int, run: dict[str, Any]) -> None:
    """Print one line summarizing a run, tagged EXPECTED/UNEXPECTED."""
    crashes = run.get("crashes", 0)
    tag = _green("EXPECTED") if crashes == 0 else _red("UNEXPECTED")
    num_cases = len(run.get("cases", []))
    print(
        f"[{index}] {run.get('timestamp')} "
        f"mode={run.get('mode')} seed={run.get('seed')} "
        f"fuzz_iterations={run.get('fuzz_iterations')} "
        f"cases={num_cases} crashes={crashes} [{tag}]"
    )


def iter_cases(
    runs: list[dict[str, Any]],
    run_index: int | None,
    seed: int | None,
) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield (run_index, case) for cases in the selected run(s)."""
    for index, run in enumerate(runs):
        if run_index is not None and index != run_index:
            continue
        if seed is not None and run.get("seed") != seed:
            continue
        for case in run.get("cases", []):
            yield index, case


def case_matches(
    case: dict[str, Any],
    outcome: str | None,
    contains: str | None,
    iteration: int | None,
    engine: str | None,
    strategy: str | None,
    unexpected_only: bool,
) -> bool:
    """True if `case` satisfies all the given filters."""
    if iteration is not None and case.get("iteration") != iteration:
        return False
    if engine is not None and case.get("engine") != engine:
        return False
    if strategy is not None and case.get("strategy") != strategy:
        return False
    if unexpected_only and case_expected(case):
        return False
    if outcome is not None and str(case.get("outcome", "")) != outcome:
        return False
    content = str(case.get("content", ""))
    if contains is not None and contains not in content:
        return False
    return True


def print_case(run_index: int, case: dict[str, Any], content: bool) -> None:
    """Print one matching case, tagged EXPECTED/UNEXPECTED."""
    tag = _green("EXPECTED") if case_expected(case) else _red("UNEXPECTED")
    print(
        f"run={run_index} engine={case.get('engine')} "
        f"strategy={case.get('strategy')} "
        f"iteration={case.get('iteration')} "
        f"outcome={case.get('outcome')} [{tag}]"
    )
    if content:
        print("--- content ---")
        print(case.get("content", ""))
        print("---------------")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--log-dir", type=Path, default=DEFAULT_LOG_DIR,
        help="directory of per-run fuzz logs (default: tests/fuzz_logs)",
    )
    parser.add_argument(
        "--list-runs", action="store_true",
        help="list run summaries (index, seed, iterations) and exit",
    )
    parser.add_argument(
        "--run", type=int, default=None,
        help="only search this run index (see --list-runs)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="only search runs started with this seed",
    )
    parser.add_argument(
        "--iteration", type=int, default=None,
        help="only this iteration number within a run",
    )
    parser.add_argument(
        "--engine", choices=["fuzz", "property"], default=None,
        help="only cases from this engine",
    )
    parser.add_argument(
        "--strategy", default=None,
        help='only cases from this strategy, e.g. "mutation", '
        '"structured", "pure_garbage", "adversarial_alphabet"',
    )
    parser.add_argument(
        "--outcome", default=None,
        help='exact outcome to match: "ok", "ParsingError", or the '
        "class name of an unexpected exception",
    )
    parser.add_argument(
        "--unexpected-only", action="store_true",
        help='shortcut for outcomes other than "ok"/"ParsingError" - '
        "i.e. cases where the parser did NOT behave as expected",
    )
    parser.add_argument(
        "--contains", default=None,
        help="substring to search for in the case's map text",
    )
    parser.add_argument(
        "--limit", type=int, default=20,
        help="max matching cases to print, 0 = no limit (default: 20)",
    )
    parser.add_argument(
        "--content", action="store_true",
        help="print each matching case's full map text",
    )
    return parser


def main() -> int:
    """Parse args, filter tests/fuzz_logs/, and print matches."""
    args = build_parser().parse_args()

    runs = load_runs(args.log_dir)
    if not runs:
        print(f"no runs found in {args.log_dir}")
        return 1

    if args.list_runs:
        for index, run in enumerate(runs):
            print_run_summary(index, run)
        return 0

    shown = 0
    for run_index, case in iter_cases(runs, args.run, args.seed):
        if not case_matches(
            case, args.outcome, args.contains, args.iteration,
            args.engine, args.strategy, args.unexpected_only,
        ):
            continue
        print_case(run_index, case, args.content)
        shown += 1
        if args.limit and shown >= args.limit:
            print(f"... limit of {args.limit} reached, see --limit")
            break

    if shown == 0:
        print("no matching cases")
        return 1
    print(f"\n{shown} matching case(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
