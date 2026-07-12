class ZoneDoesntExist(Exception):
    def __init__(
        self, message: str = "Error: can't connect to nonexistent Zone"
    ) -> None:
        super().__init__(message)
