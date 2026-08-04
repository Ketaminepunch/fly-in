# Tester / fuzzer

- `tester.py` - the fuzz + property-test harness. Runs under plain
  `pytest` (fast pass) or as a script for deep, seedable runs:

      make fuzz N=20000 SEED=1
      # or directly:
      uv run python -m tests.tester --mode both -n 20000 --seed 1

  Every invocation writes its own timestamped run to
  `tests/fuzz_logs/*.json` (gitignored - these can get large, since
  `content` holds every generated map text).

- `fuzz.py` - a small Python CLI for filtering those logs
  (`make fuzz-search ARGS="--unexpected-only"`). Fine for quick
  one-off lookups, but each new question means a new flag. If you're
  digging around interactively, nushell or jq get there faster.

## Digging through logs with nushell

Each log is a JSON object: top-level run metadata (`timestamp`,
`mode`, `seed`, `crashes`) plus a `cases` list, where each case has
`engine` ("fuzz"/"property"), `strategy`, `outcome`, `expected`
(bool), and `content` (the full map text fed to the parser).

Summarize one run:

    open tests/fuzz_logs/fuzz_log_<ts>.json | select timestamp mode seed crashes

Filter cases within a run - e.g. mutation-fuzzer cases that hit a
`ParsingError`:

    open tests/fuzz_logs/fuzz_log_<ts>.json
        | get cases
        | where strategy == mutation
        | where outcome == ParsingError
        | first 10

Any unexpected outcome (a real parser crash, not `ok`/`ParsingError`)
in that run:

    open tests/fuzz_logs/fuzz_log_<ts>.json | get cases | where expected == false

Same query across every run in the directory:

    ls tests/fuzz_logs/*.json
        | get name
        | each { |p| open $p | get cases }
        | flatten
        | where expected == false

List every run with a one-line summary:

    ls tests/fuzz_logs/*.json
        | get name
        | each { |p| open $p | select timestamp mode seed crashes }
        | flatten

Print one case's map text in full (swap the `where` for whatever
you're chasing):

    open tests/fuzz_logs/fuzz_log_<ts>.json
        | get cases
        | where iteration == 42
        | get content.0

## Digging through logs with jq

Summarize one run:

    jq '{timestamp, mode, seed, crashes}' tests/fuzz_logs/fuzz_log_<ts>.json

Filter cases within a run:

    jq '[.cases[] | select(.strategy == "mutation" and .outcome == "ParsingError")] | .[:10]' \
        tests/fuzz_logs/fuzz_log_<ts>.json

Unexpected outcomes across every run (`-s` slurps all files into one
array first):

    jq -s '[.[] | .cases[] | select(.expected == false)]' tests/fuzz_logs/*.json

List every run with a one-line summary:

    for f in tests/fuzz_logs/*.json; do
        jq -c --arg f "$f" '{file: $f, mode, seed, crashes}' "$f"
    done
