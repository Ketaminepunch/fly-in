"""Abstract pathfinding strategy interface used by the simulation engine."""

from abc import ABC, abstractmethod

from flyin.model import Connection, Network


class PathfindingStrategy(ABC):
    @abstractmethod
    def find_path(self, network: Network) -> list[Connection]: ...
