"""Zone entity: name, coordinates, type
(normal/blocked/restricted/priority), capacity."""


class Zone:
    """Zone entity: name, coordinates,
    type (normal/blocked/restricted/priority), capacity."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: str,
        capacity: int,
        color: str,
    ) -> None:
        """Store the zone's identity, position, type, capacity and color."""
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.capacity = capacity
        self.color: str = color
