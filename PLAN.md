# Fly-in — Suggested build order

Scratch working notes, not a submitted deliverable. Delete or ignore before
final submission if you want a clean root.

1. **Model** (`flyin/model/`) — `Zone`, `Connection`, `Drone`, `Network`.
   Get the plain data classes and the adjacency structure right first;
   everything else depends on them. No graph libraries.

2. **Parser** (`flyin/parser/`) — read a map file into a `Network` +
   `nb_drones`. Cover the syntax rules in subject VI and the validation
   rules in VII.4 (unique names, known zone types, duplicate connections,
   line-numbered error messages). Write `tests/test_parser.py` against
   `maps/example.txt` as you go.

3. **Simulation state & rules** (`flyin/simulation/state.py`,
   `scheduler.py`) — zone/connection occupancy, the start/end exceptions,
   and the two-turn restricted-zone transit rule (VII.2–VII.3). This is the
   trickiest correctness surface — get it covered by tests before wiring in
   pathfinding.

4. **Pathfinding** (`flyin/pathfinding/`) — start with a single-drone
   shortest-path (custom Dijkstra/BFS respecting zone costs), then extend to
   multi-drone scheduling that distributes drones across paths, waits when
   blocked, and avoids capacity conflicts (VII.1). Treat it as a strategy
   interface so you can swap/compare approaches later.

5. **Simulation engine** (`flyin/simulation/engine.py`) — drive turns using
   the scheduler + pathfinding until all drones reach the end zone.

6. **Output writer** (`flyin/io/output_writer.py`) — emit the turn-by-turn
   `D<ID>-<zone>` / `D<ID>-<connection>` format (VII.5). Cheap to build once
   the engine produces per-turn moves; validate against the subject's
   example output.

7. **Terminal + pygame renderers** (`flyin/visualization/`) — build once the
   simulation is correct, since both just observe engine state. Terminal
   first (fast feedback loop), pygame second.

8. **CLI wiring** (`flyin/cli.py`, `main.py`) — map file argument, drone
   count, renderer choice, output destination.

9. **Validate against benchmarks** (`maps/easy|medium|hard/`) — build your
   own map files per scenario named in the subject (VII.7) and confirm turn
   counts hit the targets. Fill in `flyin/metrics.py` if you want secondary
   metrics displayed.

10. **flake8 / mypy / README** — run `make lint` and `make lint-strict`
    throughout, don't leave it to the end. Fill in the README sections
    (algorithm choices, visual representation, resources/AI usage) as
    decisions get made, not retroactively.

11. **(Optional) Challenger map** — only after everything above is solid;
    purely bonus, doesn't affect grade.
