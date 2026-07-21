"""Parses a map file into a Network of zones, connections and drones."""

from ..model import Connection, Drone, Network, Zone
from .exceptions import ParsingError


def parse_map_file(path: str) -> Network:
    network = Network()
    with open(path, "r", encoding="utf-8") as f:
        for nbr, text in enumerate(f, start=1):
            stripped = text.strip()
            if not stripped or stripped.startswith("#"):
                continue
            split = stripped.split(":", 1)
            if len(split) != 2:
                raise ParsingError(
                    f"Line {nbr} Error: Missing ':' invalid input"
                )
            if nbr == 1:
                if split[0] != "nb_drones":
                    raise ParsingError(
                        f"Line {nbr} Error: First line must be nb_drones"
                    )
                else:
                    try:
                        network.nb_drones = int(split[1])
                        if int(split[1]) <= 0:
                            raise ParsingError(
                                f"line {nbr}: nb_drones value must"
                                f" be a positive integer"
                            )
                    except ValueError:
                        raise ParsingError(
                            f"line {nbr}: nb_drones value must be a positive integer"
                        ) from None
    return network


def zone_parser(body_text: str, line_nbr: int) -> Zone:
    namexy, _, metadata = body_text.partition("[")
    if len(namexy.split()) != 3:
        raise ParsingError(f"Line {line_nbr} Error: name,x or y are missing")
    name, x_str, y_str = namexy.split()
    try:
        x, y = int(x_str), int(y_str)
    except ValueError:
        raise ParsingError(
            f"Line {line_nbr} Error: Coordinate value must be a integer"
        ) from None
    try:
        meta = {
            key: value
            for key, value in (token.split("=") for token in metadata.split())
        }
    except ValueError:
        raise ParsingError(
            f"Line {line_nbr} Error: Invalid key,value syntax in metadata"
        ) from None
    VALID_ZONE_TYPES = {"normal", "blocked", "restricted", "priority"}
    zone_type = meta.get("zone", "normal")
    if zone_type not in VALID_ZONE_TYPES:
        raise ParsingError(f"line {line_nbr}: invalid zone type '{zone_type}'")
    try:
        max_drones = int(meta.get("max_drones", 1))
        if max_drones <= 0:
            raise ParsingError(
                f"line {line_nbr}: max_drones value must be a positive integer"
            )
    except ValueError:
        raise ParsingError(
            f"line {line_nbr}: max_drones value must be a positive integer"
        ) from None

    return Zone(
        name,
        x,
        y,
        zone_type,
        max_drones,
        meta.get("color", "none"),
    )
