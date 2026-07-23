"""Resolves per-turn movement conflicts against
zone and connection capacity constraints."""

from flyin.model import Connection
from flyin.simulation.state import SimulationState


def resolve_turn(
    state: SimulationState, proposed_moves: dict[int, Connection]
) -> dict[int, Connection]:
    accepted: dict[int, Connection] = {}
    pending = dict(proposed_moves)
    while True:
        progress = False
        for drone_id, connection in list(pending.items()):
            location = state.drone_locations[drone_id]
            destination_name = (
                connection.zone2_name
                if location.zone == connection.zone1_name
                else connection.zone1_name
            )
            if state.connection_has_capacity(
                connection
            ) and state.zone_has_capacity(destination_name):
                state.move_drone(drone_id, connection)
                accepted[drone_id] = connection
                del pending[drone_id]
                progress = True
        if not progress:
            break
    return accepted
