"""Network graph: holds zones and connections,
exposes adjacency without external graph libs."""

from .connection import Connection
from .model_exceptions import ZoneDoesntExist
from .zone import Zone


class Network:
    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.adjacency: dict[str, list[Connection]] = {}
        self.start: Zone | None = None
        self.end: Zone | None = None
        self.nb_drones: int = 0

    def add_zone(self, zone: Zone) -> None:
        self.zones[zone.name] = zone

    def add_connection(
        self, zone1_name: str, zone2_name: str, max_link_capacity: int = 1
    ) -> None:
        if max_link_capacity < 1:
            raise ValueError("Max link must be atleast 1")
        if zone1_name in self.zones and zone2_name in self.zones:
            connection = Connection(zone1_name, zone2_name, max_link_capacity)
            self.adjacency.setdefault(zone1_name, []).append(connection)
            self.adjacency.setdefault(zone2_name, []).append(connection)

        else:
            raise ZoneDoesntExist()
