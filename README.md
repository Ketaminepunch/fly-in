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

### Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)


## Algorithm choices and implementation strategy



## Visual representation

TODO: Describe the terminal and/or pygame visual feedback, and how it helps
understand the simulation (see subject VII.1 and VII.6).

## Resources

TODO: List references used (documentation, articles, tutorials) and describe
how AI was used, for which tasks, and on which parts of the project.
