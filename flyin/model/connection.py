"""Connection entity: bidirectional edge between two zones with a link capacity."""


class Connection:
    """Connection entity: zone1, zone2, capacity."""

    def __init__(
        self, zone1_name: str, zone2_name: str, max_link_capacity: int
    ) -> None:
        self.zone1_name = zone1_name
        self.zone2_name = zone2_name
        self.max_link_capacity = max_link_capacity
        self.name = f"{zone1_name}-{zone2_name}"
