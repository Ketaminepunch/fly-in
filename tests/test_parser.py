"""Tests for flyin.parser: valid maps, malformed input, and error messages."""

from pathlib import Path

import pytest

from flyin.parser.exceptions import ParsingError
from flyin.parser.map_parser import parse_map_file


def test_parse_example_map() -> None:
    network = parse_map_file("maps/example.txt")
    assert network.nb_drones == 5
    assert network.start is not None
    assert network.start.name == "hub"
    assert network.start.color == "green"
    assert network.zones["hub"] is network.start
    assert network.end is not None
    assert network.end.name == "goal"
    assert network.end.x == 10
    assert network.end.y == 10


@pytest.mark.parametrize(
    "bad_content",
    [
        "hub: something 0 0\n",
        "nb_drones: -3\n",
    ],
)
def test_invalid_first_line(tmp_path: Path, bad_content: str) -> None:
    bad_map = tmp_path / "bad_map.txt"
    bad_map.write_text(bad_content)
    with pytest.raises(ParsingError):
        parse_map_file(str(bad_map))


@pytest.mark.parametrize(
    "bad_content",
    [
        """nb_drones: 5
    connection: corridorA-tunnelB [max_link_capacity=-2]
    """,
        """nb_drones: 5
    hub: corridorA 4 3 [zone=priority color=green max_drones=-2]
    """,
    ],
)
def test_non_positive_int(tmp_path: Path, bad_content: str) -> None:
    bad_map = tmp_path / "bad_map.txt"
    bad_map.write_text(bad_content)
    with pytest.raises(ParsingError):
        parse_map_file(str(bad_map))
