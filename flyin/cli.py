"""Command-line argument parsing and program orchestration."""

import argparse
import sys
import time

from flyin.io.output_writer import format_turns
from flyin.parser.exceptions import ParsingError
from flyin.parser.map_parser import parse_map_file
from flyin.pathfinding.exceptions import PathNotFoundError
from flyin.pathfinding.strategies import DijkstraStrategy
from flyin.simulation.engine import orchestration

_COLORS = ["31", "32", "33", "34", "35", "36", "91", "92", "93", "94"]


def _colorize_line(line: str) -> str:
    """Color each D<id>-<token> by drone id so busy turns stay readable."""
    colored_tokens = []
    for token in line.split(" "):
        drone_id = int(token[1:].split("-", 1)[0])
        color = _COLORS[drone_id % len(_COLORS)]
        colored_tokens.append(f"\033[{color}m{token}\033[0m")
    return " ".join(colored_tokens)


def argument_parsing() -> argparse.Namespace:
    """Parse and return the command-line arguments for the program."""
    parser = argparse.ArgumentParser(
        description="Parsing arguments for fly-in"
    )
    parser.add_argument("map_path", help="path to map file")
    parser.add_argument(
        "--no_gui", action="store_true", help="runs program without gui"
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
        start_time = time.perf_counter()
        try:
            turn_log = orchestration(network, strategy)
        except PathNotFoundError as e:
            print(f"Error {e}")
            sys.exit(1)
        elapsed = time.perf_counter() - start_time
        formatted_turns = format_turns(turn_log)
        use_color = sys.stdout.isatty()
        width = len(str(len(formatted_turns)))
        for turn_nbr, line in enumerate(formatted_turns, start=1):
            if use_color:
                prefix = f"\033[2mT{turn_nbr:0{width}d} │\033[0m "
                print(prefix + (_colorize_line(line) if line else ""))
            else:
                print(line)
        if use_color:
            print(
                f"\n\033[1m{network.nb_drones} drones, "
                f"{len(formatted_turns)} turns, "
                f"{elapsed * 1000:.1f} ms\033[0m"
            )
        if not args.no_gui:
            from flyin.visualization.graphical_renderer import PygameRender

            renderer = PygameRender(network)
            renderer.render(turn_log)
    except KeyboardInterrupt:
        print("Bye bye!!")
        sys.exit(1)
