"""Tests for flyin.parser: valid maps, malformed input, and error messages."""

from pathlib import Path

import pytest

from flyin.parser.exceptions import ParsingError
from flyin.parser.map_parser import parse_map_file


def write_map(tmp_path: Path, content: str) -> str:
    map_file = tmp_path / "map.txt"
    map_file.write_text(content)
    return str(map_file)


def test_parse_real_map() -> None:
    network = parse_map_file("maps/easy/02_simple_fork.txt")
    assert network.nb_drones == 4
    assert network.start is not None
    assert network.start.name == "start"
    assert network.start.color == "green"
    assert network.zones["start"] is network.start
    assert network.end is not None
    assert network.end.name == "goal"
    assert network.zones["junction"].capacity == 2
    assert network.zones["junction"].color == "yellow"
    assert network.adjacency["start"][0].max_link_capacity == 2


def test_zone_defaults_when_no_metadata(tmp_path: Path) -> None:
    network = parse_map_file(
        write_map(
            tmp_path,
            "nb_drones: 1\n"
            "start_hub: hub 0 0\n"
            "end_hub: goal 10 10\n",
        )
    )
    assert network.zones["hub"].zone_type == "normal"
    assert network.zones["hub"].capacity == 1
    assert network.zones["hub"].color == "none"


def test_connection_defaults_when_no_metadata(tmp_path: Path) -> None:
    network = parse_map_file(
        write_map(
            tmp_path,
            "nb_drones: 1\n"
            "start_hub: hub 0 0\n"
            "end_hub: goal 10 10\n"
            "connection: hub-goal\n",
        )
    )
    assert network.adjacency["hub"][0].max_link_capacity == 1


def test_blank_lines_and_mid_file_comments_are_skipped(
    tmp_path: Path,
) -> None:
    network = parse_map_file(
        write_map(
            tmp_path,
            "\n"
            "nb_drones: 1\n"
            "\n"
            "# a comment about the start\n"
            "start_hub: hub 0 0\n"
            "\n"
            "end_hub: goal 10 10\n",
        )
    )
    assert network.nb_drones == 1


@pytest.mark.parametrize(
    "bad_content",
    [
        "hub: something 0 0\n",
        "nb_drones: -3\n",
        "nb_drones: 0\n",
        "nb_drones: abc\n",
        "Nb_drones: 5\n",
    ],
)
def test_invalid_first_line(tmp_path: Path, bad_content: str) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


@pytest.mark.parametrize(
    "bad_content",
    [
        "nb_drones 5\n",
        "just some text with no colon\n",
    ],
)
def test_missing_colon(tmp_path: Path, bad_content: str) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


def test_unknown_keyword(tmp_path: Path) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(
            write_map(
                tmp_path,
                "nb_drones: 5\n"
                "start_hub: hub 0 0\n"
                "end_hub: goal 10 10\n"
                "portal: hub-goal\n",
            )
        )


@pytest.mark.parametrize(
    "bad_content",
    [
        """nb_drones: 5
    connection: corridorA-tunnelB [max_link_capacity=-2]
    """,
        """nb_drones: 5
    connection: corridorA-tunnelB [max_link_capacity=0]
    """,
        """nb_drones: 5
    hub: corridorA 4 3 [zone=priority color=green max_drones=-2]
    """,
        """nb_drones: 5
    hub: corridorA 4 3 [zone=priority color=green max_drones=0]
    """,
    ],
)
def test_non_positive_int(tmp_path: Path, bad_content: str) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


@pytest.mark.parametrize(
    "bad_content",
    [
        # zone line missing a coordinate
        """nb_drones: 5
    start_hub: hub 0
    end_hub: goal 10 10
    """,
        # zone line with an extra token
        """nb_drones: 5
    start_hub: hub 0 0 extra
    end_hub: goal 10 10
    """,
        # non-integer coordinate
        """nb_drones: 5
    start_hub: hub zero zero
    end_hub: goal 10 10
    """,
    ],
)
def test_malformed_zone_line(tmp_path: Path, bad_content: str) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


@pytest.mark.parametrize(
    "bad_content",
    [
        # missing closing bracket
        """nb_drones: 5
    start_hub: hub 0 0 [zone=priority
    end_hub: goal 10 10
    """,
        # metadata token with no '='
        """nb_drones: 5
    start_hub: hub 0 0 [priority]
    end_hub: goal 10 10
    """,
        # unknown zone type
        """nb_drones: 5
    start_hub: hub 0 0 [zone=warzone]
    end_hub: goal 10 10
    """,
        # non-integer max_drones
        """nb_drones: 5
    start_hub: hub 0 0 [max_drones=many]
    end_hub: goal 10 10
    """,
    ],
)
def test_malformed_zone_metadata(tmp_path: Path, bad_content: str) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


@pytest.mark.parametrize(
    "bad_content",
    [
        # no dash at all
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    connection: hubgoal
    """,
        # too many dashes
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    connection: hub-way-goal
    """,
    ],
)
def test_malformed_connection_name(tmp_path: Path, bad_content: str) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


@pytest.mark.parametrize(
    "bad_content",
    [
        # missing closing bracket
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    connection: hub-goal [max_link_capacity=2
    """,
        # metadata token with no '='
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    connection: hub-goal [2]
    """,
        # non-integer capacity
        """nb_drones: 5
    start_hub: hub 0 0
    end_hub: goal 10 10
    connection: hub-goal [max_link_capacity=lots]
    """,
    ],
)
def test_malformed_connection_metadata(
    tmp_path: Path, bad_content: str
) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


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
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


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
        # connection references a zone defined later in the file
        """nb_drones: 5
    start_hub: hub 0 0
    connection: hub-goal
    end_hub: goal 10 10
    """,
    ],
)
def test_zone_and_connection_uniqueness(
    tmp_path: Path, bad_content: str
) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, bad_content))


def test_comment_as_first_line(tmp_path: Path) -> None:
    network = parse_map_file(
        write_map(
            tmp_path,
            "# just a comment\n"
            "nb_drones: 5\n"
            "start_hub: hub 0 0\n"
            "end_hub: goal 10 10\n",
        )
    )
    assert network.nb_drones == 5


def test_empty_file(tmp_path: Path) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, ""))


def test_only_comments_and_blank_lines(tmp_path: Path) -> None:
    with pytest.raises(ParsingError):
        parse_map_file(write_map(tmp_path, "# nothing here\n\n\n"))
