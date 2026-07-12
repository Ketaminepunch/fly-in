"""Drone entity: identifier, current position/zone, and in-transit connection state."""


class Drone:
    """Drone entity: just the ID of the Drone"""

    def __init__(self, id: int) -> None:
        self.id = id
