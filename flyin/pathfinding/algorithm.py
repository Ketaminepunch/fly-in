"""Abstract pathfinding strategy interface used by the simulation engine."""

from abc import ABC, abstractmethod

from flyin.model import Connection, Network


class PathfindingStrategy(ABC):
    """Interface for algorithms that route a drone through the network."""

    @abstractmethod
    def find_path(
        self,
        network: Network,
        start_zone: str,
        blocked_zones: set[str],
        blocked_connections: set[str],
        connection_reservations: dict[str, int],
        zone_reservations: dict[str, int],
    ) -> list[Connection]:
        """Return the connection sequence from start_zone to network.end.

        Zones/connections in blocked_zones/blocked_connections must be
        avoided; the reservation dicts give current per-zone/per-connection
        occupancy, used by implementations that account for congestion.
        """
        ...
