"""Concrete pathfinding strategy implementations (e.g. custom Dijkstra/BFS variants)."""

import heapq

from flyin.model import Connection, Network

from .algorithm import PathfindingStrategy
from .exceptions import PathNotFoundError


class DijkstraStrategy(PathfindingStrategy):
    def find_path(self, network: Network) -> list[Connection]:
        assert network.start is not None
        assert network.end is not None
        heap: list[tuple[int, int, str]] = []
        visited: set[str] = set()
        distances: dict[str, tuple[int, int]] = {}
        previous: dict[str, tuple[str, Connection]] = {}
        distances[network.start.name] = (0, 0)
        heapq.heappush(heap, (0, 0, network.start.name))
        while heap:
            current_distance, current_priority_score, current_zone = (
                heapq.heappop(heap)
            )
            if current_zone in visited:
                continue
            else:
                visited.add(current_zone)
            if current_zone == network.end.name:
                path = []
                while current_zone != network.start.name:
                    prev_zone, connection = previous[current_zone]
                    path.append(connection)
                    current_zone = prev_zone
                path.reverse()
                return path
            for connection in network.adjacency[current_zone]:
                neighbor_name = (
                    connection.zone2_name
                    if current_zone == connection.zone1_name
                    else connection.zone1_name
                )
                neighbor_type = network.zones[neighbor_name].zone_type
                priority_delta = -1 if neighbor_type == "priority" else 0
                if neighbor_name in visited:
                    continue
                else:
                    if (
                        neighbor_type == "normal"
                        or neighbor_type == "priority"
                    ):
                        cost = 1
                    elif neighbor_type == "restricted":
                        cost = 2
                    else:
                        continue
                    new_distance = current_distance + cost
                    new_priority_score = (
                        current_priority_score + priority_delta
                    )
                    new_key = (new_distance, new_priority_score)
                    if new_key < distances.get(
                        neighbor_name, (float("inf"), float("inf"))
                    ):
                        distances[neighbor_name] = new_key
                        previous[neighbor_name] = (current_zone, connection)
                        heapq.heappush(
                            heap,
                            (new_distance, new_priority_score, neighbor_name),
                        )
        raise PathNotFoundError()
