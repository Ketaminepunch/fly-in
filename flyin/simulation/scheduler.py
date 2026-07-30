"""Resolves per-turn movement conflicts against
zone and connection capacity constraints."""

from flyin.model import Connection
from flyin.simulation.state import SimulationState


def resolve_turn(
    state: SimulationState, proposed_moves: dict[int, Connection]
) -> dict[int, Connection]:
    """Admit as many proposed moves as capacity allows and apply them.

    Repeatedly scans the pending moves, accepting (and applying via
    state.move_drone) any whose connection and destination zone still
    have free capacity, until a full pass makes no further progress.
    Returns the accepted drone_id -> connection moves.
    """
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
