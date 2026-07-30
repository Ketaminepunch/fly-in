"""Mutable simulation state: drone positions, zone
occupancy and in-transit links per turn."""

from flyin.model import Connection, Drone
from flyin.model.network import Network

from .exceptions import BlockedZoneError


class Location:
    """A drone's position: either sitting in a zone or in transit on a
    connection towards a destination zone."""

    def __init__(
        self,
        zone: str | None = None,
        connection: Connection | None = None,
        destination: str | None = None,
        turns_remaining: int | None = None,
    ):
        """Store the zone/in-transit fields describing this location."""
        self.zone = zone
        self.connection = connection
        self.destination = destination
        self.turns_remaining = turns_remaining


class SimulationState:
    """Tracks turn number and every drone's location for one simulation."""

    def __init__(self, network: Network, drones: list[Drone]):
        """Place every drone in the network's start zone at turn 0."""
        self.network = network
        self.turn: int = 0
        self.drone_locations: dict[int, Location] = {
            drone.id: Location(zone=network.start.name) for drone in drones
        }

    def zone_occupancy(self, zone_name: str) -> int:
        """Count drones currently in, or arriving into, the given zone."""
        matches = 0
        for location in self.drone_locations.values():
            if location.zone == zone_name:
                matches += 1
            elif location.destination == zone_name:
                matches += 1
        return matches

    def connection_occupancy(self, connection: Connection) -> int:
        """Count drones currently in transit on the given connection."""
        matches = 0
        for location in self.drone_locations.values():
            if connection == location.connection:
                matches += 1
        return matches

    def zone_has_capacity(self, zone_name: str) -> bool:
        """Return whether a drone can currently enter the given zone.

        Blocked zones never have capacity; the start/end zones always do;
        other zones depend on current occupancy versus their capacity.
        """
        if self.network.zones[zone_name].zone_type == "blocked":
            return False
        if (
            zone_name == self.network.start.name
            or zone_name == self.network.end.name
        ):
            return True
        else:
            return (
                self.zone_occupancy(zone_name)
                < self.network.zones[zone_name].capacity
            )

    def connection_has_capacity(self, connection: Connection) -> bool:
        """Return whether the connection has a free slot for another drone."""
        return (
            self.connection_occupancy(connection)
            < connection.max_link_capacity
        )

    def move_drone(self, drone_id: int, connection: Connection) -> None:
        """Advance a drone onto connection, updating its location in place.

        Normal/priority destinations land the drone immediately; restricted
        destinations put it in transit for one turn; any other destination
        type raises BlockedZoneError.
        """
        location = self.drone_locations[drone_id]
        assert location.zone is not None
        destination_name = (
            connection.zone2_name
            if location.zone == connection.zone1_name
            else connection.zone1_name
        )
        destination_type = self.network.zones[destination_name].zone_type
        match destination_type:
            case "normal" | "priority":
                self.drone_locations[drone_id] = Location(
                    zone=destination_name
                )
            case "restricted":
                self.drone_locations[drone_id] = Location(
                    connection=connection,
                    destination=destination_name,
                    turns_remaining=1,
                )
            case _:
                raise BlockedZoneError()

    def advance_turn(self) -> None:
        """Increment the turn counter."""
        self.turn += 1

    def land_arrivals(self) -> list[int]:
        """Land every drone whose in-transit wait has elapsed.

        Moves each such drone's location to its destination zone and
        returns the ids of drones that landed this call.
        """
        landing_drones: list[int] = []
        for drone_id, location in self.drone_locations.items():
            if location.turns_remaining is not None:
                self.drone_locations[drone_id] = Location(
                    zone=location.destination
                )
                landing_drones.append(drone_id)
        return landing_drones
