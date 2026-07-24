"""Tests for flyin.pathfinding: path costs, priority handling, and disjoint routing."""

from flyin.parser.map_parser import parse_map_file
from flyin.pathfinding.strategies import DijkstraStrategy


def test_dijkstra_baseline_path() -> None:
    network = parse_map_file("maps/easy/02_simple_fork.txt")
    strategy = DijkstraStrategy()
    path = strategy.find_path(network, "start", set(), set())
    assert [c.name for c in path] == [
        "start-junction",
        "junction-path_a",
        "path_a-goal",
    ]


def test_dijkstra_reroutes_around_blocked_zone() -> None:
    network = parse_map_file("maps/easy/02_simple_fork.txt")
    strategy = DijkstraStrategy()
    path = strategy.find_path(network, "start", {"path_a"}, set())
    assert [c.name for c in path] == [
        "start-junction",
        "junction-path_b",
        "path_b-goal",
    ]


def test_dijkstra_reroutes_around_blocked_connection() -> None:
    network = parse_map_file("maps/easy/02_simple_fork.txt")
    strategy = DijkstraStrategy()
    path = strategy.find_path(
        network, "start", set(), {"junction-path_a"}
    )
    assert [c.name for c in path] == [
        "start-junction",
        "junction-path_b",
        "path_b-goal",
    ]
