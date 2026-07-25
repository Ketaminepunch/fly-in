"""Command-line argument parsing and program orchestration."""

import argparse

from flyin.io.output_writer import format_turns
from flyin.parser.map_parser import parse_map_file
from flyin.pathfinding.strategies import DijkstraStrategy
from flyin.simulation.engine import orchestration


def argument_parsing() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parsing arguments for fly-in"
    )
    parser.add_argument("map_path", help="path to map file")
    parser.add_argument(
        "-d", "--drones", type=int, default=None, help="override drone count"
    )
    args = parser.parse_args()
    return args


def main() -> None:
    args = argument_parsing()
    map_path = args.map_path
    network = parse_map_file(map_path)
    strategy = DijkstraStrategy()
    turn_log = orchestration(network, strategy)
    formatted_turns = format_turns(turn_log)
    for line in formatted_turns:
        print(line)
