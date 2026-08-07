*This project has been created as part of the 42 curriculum by vsack.*

# Fly-in

## Description

The fly-in project is primarily about pathfinding.The goal is to get an input map and for any given map try to minimize the turns needed for all drones to get from the start node to the finish node. The main challenges were orchestration of all drones simulatinously,visualization and parsing.
The finished program takes an input file with a specific format and out of that creates a map of nodes and connections. The it calulates the path of the drones with the dijkstra algorithm. The paths are printed to the terminal and an interactive visualizer shows the process more clearly.Every Zone and connection have a maximum capacity which makes the pathfinding more difficult.


A valid map is a combination of zones and connections with a findable path from start to end. There are 4 different types of zones:
<ol>
<li> Normal Zone: Normal zone one turn to travel to it
<li> Priority Zone: Just like the normal zone but should be prioritized if it doesnt lead to more turns.
<li> Restricted Zone: For this zone it takes 2 turns for a drone to land on it instead of one.
<li> Blocked Zone: This zone is impossible to reach and should be ignored in pathfinding.


## Instructions

### Install

```sh
make install
```

### Run

```sh
make run
```

### Debug

```sh
make debug
```

### Lint / type-check

```sh
make lint
make lint-strict   # optional, stricter mypy
```

### Run with flags

```sh
make run MAP=path_to_map ARGS=--no_gui
```

### Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)


## Algorithm choices and implementation strategy

Pathfinding is a custom Dijkstra variant (`flyin/pathfinding/strategies.py`)
sitting behind a `PathfindingStrategy` interface, so alternative strategies
could be swapped in without touching the simulation engine. Each edge is
ranked by a `(distance, priority_score)` pair: `distance` is the real
travel cost (1 turn for normal/priority zones, 2 for restricted, blocked
zones excluded entirely), and `priority_score` is a tie-breaker that
prefers routes through priority zones when they don't add turns.

Multi-drone orchestration (`flyin/simulation/engine.py`) plans every
drone's path up front against a shared set of congestion counters
(`connection_reservations` / `zone_reservations`, one increment per planned
occupancy), so later drones route around zones/connections that earlier
drones already claimed instead of just following the same shortest path.
Each planned edge cost also folds in `reservations // capacity`, so heavily
booked zones/connections get progressively more expensive rather than
being hard-blocked.

The engine then steps turn by turn: `scheduler.resolve_turn` admits as many
proposed moves as current capacity allows, repeatedly scanning the pending
set until a full pass makes no more progress (so a move freed up by another
drone landing can still go through in the same turn). Any drone stuck for
two consecutive turns gets a fresh path replanned from its current position,
avoiding zones/connections that are at capacity right now.

## Visual representation

The CLI prints the required `D<id>-<zone|connection>` turn log to the
terminal, then opens an interactive pygame viewer
(`flyin/visualization/graphical_renderer.py`) over the same turn log.

The network is drawn as zones (colored by type - normal/priority/
restricted/blocked) connected by their links, with drones rendered as
colored tokens that animate smoothly between zones/connections as turns
advance. This makes congestion, rerouting, and the restricted-zone
two-turn delay visible as they happen, rather than only inferable from
the raw text log.

Playback controls:

| Input | Action |
|---|---|
| `Space` | Play / pause |
| `←` / `→` | Step one turn back / forward |
| `↑` / `↓` | Increase / decrease playback speed |
| `+` / `-` / mouse wheel | Zoom in / out (centered on the cursor) |
| Left-click drag | Pan the view |
| Window resize | View refits automatically |

A HUD bar at the bottom shows the current turn index and playback speed.

## Resources

#### Links:
- [Dijkstra's algorithm - Wikipedia](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm) -
  the base algorithm `DijkstraStrategy` extends with zone-type costs and a
  priority tie-break.
- [Red Blob Games - Introduction to A*](https://www.redblobgames.com/pathfinding/a-star/introduction.html) -
  walks through Dijkstra/BFS/A* with interactive visuals; explains why a
  priority-queue-based search behaves the way it does.
- [Python `heapq` docs](https://docs.python.org/3/library/heapq.html) -
  the min-heap used to drive the Dijkstra loop in `strategies.py`.
- [Multi-Agent Path Finding - Wikipedia](https://en.wikipedia.org/wiki/Multi-agent_pathfinding) -
  the general problem class this project's capacity/congestion handling
  (`engine.py`, `scheduler.py`) is a simplified instance of.
- [Pygame documentation](https://www.pygame.org/docs/) -
  reference for the drawing/event-loop APIs used in `graphical_renderer.py`.
- [Python `argparse` docs](https://docs.python.org/3/library/argparse.html) -
  used for CLI argument parsing in `cli.py`.
- [Colleagues fly-in](https://github.com/0xveya/42-fly-in)-
    i used veya's visualizer for debugging purposes while i didnt have my own yet. Altough i wrote my own in the end ofcourse.

#### AI usage:
Claude was used for understanding how to apply the learned knowledge into python. It was also used for testing but no submitted code was written by AI.
