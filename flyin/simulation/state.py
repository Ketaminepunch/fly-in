"""Mutable simulation state: drone positions, zone
occupancy and in-transit links per turn."""

from flyin.model import Connection, Drone
from flyin.model.network import Network

from .exceptions import BlockedZoneError


class Location:
    def __init__(
        self,
        zone: str | None = None,
        connection: Connection | None = None,
        destination: str | None = None,
        turns_remaining: int | None = None,
    ):
        self.zone = zone
        self.connection = connection
        self.destination = destination
        self.turns_remaining = turns_remaining


class SimulationState:
    def __init__(self, network: Network, drones: list[Drone]):
        assert network.start is not None
        self.network = network
        self.turn: int = 0
        self.drone_locations: dict[int, Location] = {
            drone.id: Location(zone=network.start.name) for drone in drones
        }

    def zone_occupancy(self, zone_name: str) -> int:
        matches = 0
        for location in self.drone_locations.values():
            if location.zone == zone_name:
                matches += 1
            elif location.destination == zone_name:
                matches += 1
        return matches

    def connection_occupancy(self, connection: Connection) -> int:
        matches = 0
        for location in self.drone_locations.values():
            if connection == location.connection:
                matches += 1
        return matches

    def zone_has_capacity(self, zone_name: str) -> bool:
        assert self.network.start is not None
        assert self.network.end is not None
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
        return (
            self.connection_occupancy(connection)
            < connection.max_link_capacity
        )

    def move_drone(self, drone_id: int, connection: Connection) -> None:
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
        self.turn += 1

    def land_arrivals(self) -> list[int]:
        landing_drones: list[int] = []
        for drone_id, location in self.drone_locations.items():
            if location.turns_remaining is not None:
                self.drone_locations[drone_id] = Location(
                    zone=location.destination
                )
                landing_drones.append(drone_id)
        return landing_drones
