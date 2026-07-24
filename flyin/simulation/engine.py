"""Drives the turn-by-turn simulation from start zone to end zone for all drones."""

from flyin.model import Connection, Drone, Network
from flyin.pathfinding.algorithm import PathfindingStrategy
from flyin.pathfinding.exceptions import PathNotFoundError
from flyin.simulation.scheduler import resolve_turn
from flyin.simulation.state import SimulationState


def orchestration(
    network: Network, strategy: PathfindingStrategy
) -> list[dict[int, str]]:
    assert network.start is not None
    assert network.end is not None
    drone_paths: dict[int, list[Connection]] = {}
    drone_progress: dict[int, int] = {}
    drone_list: list[Drone] = []
    stuck_counter: dict[int, int] = {}
    turn_log: list[dict[int, str]] = []
    for i in range(network.nb_drones):
        drone_list.append(Drone(i + 1))
    for drone in drone_list:
        drone_paths[drone.id] = strategy.find_path(
            network, network.start.name, set(), set()
        )
        stuck_counter[drone.id] = 0
        drone_progress[drone.id] = 0
    state = SimulationState(network, drone_list)
    while not all(
        location.zone == network.end.name
        for location in state.drone_locations.values()
    ):
        proposed_moves = {}
        turn_moves: dict[int, str] = {}
        for drone in drone_list:
            location = state.drone_locations[drone.id]
            if location.zone is not None and drone_progress[drone.id] < len(
                drone_paths[drone.id]
            ):
                proposed_moves[drone.id] = drone_paths[drone.id][
                    drone_progress[drone.id]
                ]
        accepted = resolve_turn(state, proposed_moves)
        for drone_id in accepted:
            drone_progress[drone_id] += 1
            stuck_counter[drone_id] = 0
            location = state.drone_locations[drone_id]
            if location.zone is not None:
                turn_moves[drone_id] = location.zone
            else:
                assert location.connection is not None
                turn_moves[drone_id] = location.connection.name
        turn_log.append(turn_moves)
        stuck_ids = proposed_moves.keys() - accepted.keys()
        for drone_id in stuck_ids:
            stuck_counter[drone_id] += 1
        for drone in drone_list:
            if stuck_counter[drone.id] >= 2:
                current_zone = state.drone_locations[drone.id].zone
                if current_zone is None:
                    continue
                else:
                    blocked_zones = {
                        name
                        for name in network.zones
                        if not state.zone_has_capacity(name)
                    }
                    blocked_connections = {
                        connection.name
                        for connections in network.adjacency.values()
                        for connection in connections
                        if not state.connection_has_capacity(connection)
                    }
                    try:
                        drone_paths[drone.id] = strategy.find_path(
                            network,
                            current_zone,
                            blocked_zones,
                            blocked_connections,
                        )
                        drone_progress[drone.id] = 0
                        stuck_counter[drone.id] = 0
                    except PathNotFoundError:
                        continue
        state.advance_turn()
    return turn_log
