"""Command-line argument parsing and program orchestration."""

import argparse
import sys

from flyin.io.output_writer import format_turns
from flyin.parser.exceptions import ParsingError
from flyin.parser.map_parser import parse_map_file
from flyin.pathfinding.exceptions import PathNotFoundError
from flyin.pathfinding.strategies import DijkstraStrategy
from flyin.simulation.engine import orchestration
from flyin.visualization.graphical_renderer import PygameRender


def argument_parsing() -> argparse.Namespace:
    """Parse and return the command-line arguments for the program."""
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
    """Parse arguments, run the simulation, and print/render the result."""
    try:
        args = argument_parsing()
        map_path = args.map_path
        try:
            network = parse_map_file(map_path)
        except ParsingError as e:
            print(f"Parsing Error {e}")
            sys.exit(1)

        strategy = DijkstraStrategy()
        try:
            turn_log = orchestration(network, strategy)
        except PathNotFoundError as e:
            print(f"Error {e}")
            sys.exit(1)
        formatted_turns = format_turns(turn_log)
        for line in formatted_turns:
            print(line)
        renderer = PygameRender(network)
        renderer.render(turn_log)
    except KeyboardInterrupt:
        print("Bye bye!!")
        sys.exit(1)
