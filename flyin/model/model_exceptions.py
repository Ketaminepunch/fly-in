class ZoneDoesntExist(Exception):
    def __init__(
        self, message: str = "Can't connect to nonexistent Zone"
    ) -> None:
        super().__init__(message)


class DuplicateName(Exception):
    def __init__(self, message: str = "Duplicate Zone name") -> None:
        super().__init__(message)


class DuplicateConnection(Exception):
    def __init__(self, message: str = "Duplicate Connection") -> None:
        super().__init__(message)
