"""Network graph: holds zones and connections,
exposes adjacency without external graph libs."""

from .connection import Connection
from .model_exceptions import (
    DuplicateConnection,
    DuplicateName,
    ZoneDoesntExist,
)
from .zone import Zone


class Network:
    """Graph of zones and connections, plus adjacency lookups by zone name."""

    start: Zone
    end: Zone

    def __init__(self) -> None:
        """Initialize an empty network with no zones, links, or drones."""
        self.zones: dict[str, Zone] = {}
        self.adjacency: dict[str, list[Connection]] = {}
        self.nb_drones: int = 0

    def add_zone(self, zone: Zone) -> None:
        """Register a zone, raising DuplicateName if its name is taken."""
        if zone.name in self.zones:
            raise DuplicateName()
        self.zones[zone.name] = zone

    def add_connection(
        self, zone1_name: str, zone2_name: str, max_link_capacity: int = 1
    ) -> None:
        """Link two existing zones with a capacity, updating adjacency.

        Raises ValueError for a non-positive capacity, DuplicateConnection
        if the link already exists, or ZoneDoesntExist if either zone is
        unregistered.
        """
        if max_link_capacity < 1:
            raise ValueError("Max link must be atleast 1")
        connection_list = self.adjacency.get(zone1_name, [])
        for connection in connection_list:
            if (
                connection.zone1_name == zone2_name
                or connection.zone2_name == zone2_name
            ):
                raise DuplicateConnection()
        if zone1_name in self.zones and zone2_name in self.zones:
            connection = Connection(zone1_name, zone2_name, max_link_capacity)
            self.adjacency.setdefault(zone1_name, []).append(connection)
            self.adjacency.setdefault(zone2_name, []).append(connection)

        else:
            raise ZoneDoesntExist()
