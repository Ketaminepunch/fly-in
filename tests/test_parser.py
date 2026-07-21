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


@pytest.mark.parametrize(
    "bad_content",
    [
        # duplicate start_hub
        """nb_drones: 5
    start_hub: hub 0 0
    start_hub: hub2 1 1
    end_hub: goal 10 10
    """,
        # duplicate end_hub
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    end_hub: goal2 11 11
    """,
        # missing start_hub
        """nb_drones: 5
    end_hub: goal 10 10
    """,
        # missing end_hub
        """nb_drones: 5
    start_hub: hub 0 0
    """,
        # missing both
        "nb_drones: 5\n",
    ],
)
def test_start_end_hub_cardinality(tmp_path: Path, bad_content: str) -> None:
    bad_map = tmp_path / "bad_map.txt"
    bad_map.write_text(bad_content)
    with pytest.raises(ParsingError):
        parse_map_file(str(bad_map))


@pytest.mark.parametrize(
    "bad_content",
    [
        # duplicate zone name
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    hub: roof1 3 4
    hub: roof1 5 5
    """,
        # duplicate connection, same order
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    hub: roof1 3 4
    connection: hub-roof1
    connection: hub-roof1
    """,
        # duplicate connection, reversed order
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    hub: roof1 3 4
    connection: hub-roof1
    connection: roof1-hub
    """,
        # connection references an undefined zone
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    connection: hub-nonexistent
    """,
    ],
)
def test_zone_and_connection_uniqueness(
    tmp_path: Path, bad_content: str
) -> None:
    bad_map = tmp_path / "bad_map.txt"
    bad_map.write_text(bad_content)
    with pytest.raises(ParsingError):
        parse_map_file(str(bad_map))


def test_comment_as_first_line(tmp_path: Path) -> None:
    good_map = tmp_path / "good_map.txt"
    good_map.write_text(
        "# just a comment\n"
        "nb_drones: 5\n"
        "start_hub: hub 0 0\n"
        "end_hub: goal 10 10\n"
    )
    network = parse_map_file(str(good_map))
    assert network.nb_drones == 5
