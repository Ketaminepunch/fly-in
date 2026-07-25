"""Parses a map file into a Network of zones, connections and drones."""

from ..model import (
    DuplicateConnection,
    DuplicateName,
    Network,
    Zone,
    ZoneDoesntExist,
)
from .exceptions import ParsingError


def parse_map_file(path: str) -> Network:
    network = Network()
    nbr = 0
    first_line_seen = False
    start: Zone | None = None
    end: Zone | None = None
    with open(path, "r", encoding="utf-8") as f:
        for nbr, text in enumerate(f, start=1):
            stripped = text.strip()
            if not stripped or stripped.startswith("#"):
                continue
            split = stripped.split(":", 1)
            if len(split) != 2:
                raise ParsingError(nbr, "missing ':' invalid input")
            if not first_line_seen:
                first_line_seen = True
                if split[0] != "nb_drones":
                    raise ParsingError(nbr, "first line must be nb_drones")
                else:
                    try:
                        network.nb_drones = int(split[1])
                        if int(split[1]) <= 0:
                            raise ParsingError(
                                nbr,
                                "nb_drones value must be a positive integer",
                            )
                    except ValueError:
                        raise ParsingError(
                            nbr,
                            "nb_drones value must be a positive integer",
                        ) from None
            else:
                match split[0]:
                    case "start_hub" | "end_hub" | "hub":
                        zone = zone_parser(split[1], nbr)
                        try:
                            network.add_zone(zone)
                        except DuplicateName as e:
                            raise ParsingError(nbr, str(e)) from None
                        if split[0] == "start_hub":
                            if start is not None:
                                raise ParsingError(
                                    nbr, "start assigned more than once"
                                )
                            start = zone
                        elif split[0] == "end_hub":
                            if end is not None:
                                raise ParsingError(
                                    nbr, "end assigned more than once"
                                )
                            end = zone
                    case "connection":
                        zone1_name, zone2_name, capacity = connection_parser(
                            split[1], nbr
                        )
                        try:
                            network.add_connection(
                                zone1_name, zone2_name, capacity
                            )
                        except (DuplicateConnection, ZoneDoesntExist) as e:
                            raise ParsingError(nbr, str(e)) from None
                    case _:
                        raise ParsingError(
                            nbr, "invalid hub or connection keyword"
                        )
    if start is None or end is None:
        raise ParsingError(nbr, "no start/end set")
    network.start = start
    network.end = end
    return network


def connection_parser(body_text: str, line_nbr: int) -> tuple[str, str, int]:
    name, _, metadata = body_text.partition("[")
    name = name.strip()
    try:
        zone1_name, zone2_name = name.split("-")
    except ValueError:
        raise ParsingError(line_nbr, "invalid connection name") from None
    metadata = metadata.rstrip("]")
    if metadata:
        try:
            _, max_link_capacity = metadata.split("=")
        except ValueError:
            raise ParsingError(line_nbr, "invalid metadata format") from None
        try:
            max_link_nbr = int(max_link_capacity)
            if max_link_nbr <= 0:
                raise ParsingError(
                    line_nbr,
                    "max_link_capacity value must be a positive integer",
                )
        except ValueError:
            raise ParsingError(
                line_nbr,
                "max_link_capacity value must be a positive integer",
            ) from None
    else:
        max_link_nbr = 1
    return (zone1_name, zone2_name, max_link_nbr)


def zone_parser(body_text: str, line_nbr: int) -> Zone:
    namexy, _, metadata = body_text.partition("[")
    metadata = metadata.rstrip("]")
    if len(namexy.split()) != 3:
        raise ParsingError(line_nbr, "name, x or y are missing")
    name, x_str, y_str = namexy.split()
    try:
        x, y = int(x_str), int(y_str)
    except ValueError:
        raise ParsingError(
            line_nbr, "coordinate value must be an integer"
        ) from None
    try:
        meta = {
            key: value
            for key, value in (token.split("=") for token in metadata.split())
        }
    except ValueError:
        raise ParsingError(
            line_nbr, "invalid key=value syntax in metadata"
        ) from None
    VALID_ZONE_TYPES = {"normal", "blocked", "restricted", "priority"}
    zone_type = meta.get("zone", "normal")
    if zone_type not in VALID_ZONE_TYPES:
        raise ParsingError(line_nbr, f"invalid zone type '{zone_type}'")
    try:
        max_drones = int(meta.get("max_drones", 1))
        if max_drones <= 0:
            raise ParsingError(
                line_nbr, "max_drones value must be a positive integer"
            )
    except ValueError:
        raise ParsingError(
            line_nbr, "max_drones value must be a positive integer"
        ) from None

    return Zone(
        name,
        x,
        y,
        zone_type,
        max_drones,
        meta.get("color", "none"),
    )
