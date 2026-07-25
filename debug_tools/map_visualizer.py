"""Scratch debug tool: runs the real simulation on a map file and plays it
back with the interactive pygame visualizer (ported from ../42-fly-in).

NOT part of the graded submission. Just a quick way to eyeball a map and
watch the actual drone turn log produced by the engine/strategy.

Usage:
    python debug_tools/map_visualizer.py maps/easy/02_simple_fork.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flyin.model import Network  # noqa: E402
from flyin.parser.map_parser import parse_map_file  # noqa: E402
from flyin.pathfinding.strategies import DijkstraStrategy  # noqa: E402
from flyin.simulation.engine import orchestration  # noqa: E402

from visualizer import DroneVisualizer, ZoneData  # noqa: E402


def to_zones(network: Network) -> list[ZoneData]:
    """Network zones -> visualizer zone dicts (start/end hubs get their own
    zone_type so the visualizer rings them correctly)."""
    zones: list[ZoneData] = []
    for zone in network.zones.values():
        zone_type = zone.zone_type
        if zone.name == network.start.name:
            zone_type = "start"
        elif zone.name == network.end.name:
            zone_type = "end"
        zones.append(
            {
                "name": zone.name,
                "x": zone.x,
                "y": zone.y,
                "zone_type": zone_type,
                "max_drones": zone.capacity,
                "color": zone.color,
            }
        )
    return zones


def to_connections(network: Network) -> list[tuple[str, str]]:
    """Network adjacency (each connection listed twice) -> deduped edge list."""
    seen: set[str] = set()
    connections: list[tuple[str, str]] = []
    for conns in network.adjacency.values():
        for conn in conns:
            if conn.name in seen:
                continue
            seen.add(conn.name)
            connections.append((conn.zone1_name, conn.zone2_name))
    return connections


def to_turns(turn_log: list[dict[int, str]]) -> list[list[str]]:
    """orchestration()'s per-turn {drone_id: dest} maps -> visualizer's
    "did-dest" move strings."""
    return [
        [f"{drone_id}-{dest}" for drone_id, dest in turn.items()]
        for turn in turn_log
    ]


def main() -> None:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <map_file>")
        raise SystemExit(1)

    network = parse_map_file(sys.argv[1])
    turn_log = orchestration(network, DijkstraStrategy())

    zones = to_zones(network)
    connections = to_connections(network)
    turns = to_turns(turn_log)

    DroneVisualizer(zones, connections, turns).run()


if __name__ == "__main__":
    main()
