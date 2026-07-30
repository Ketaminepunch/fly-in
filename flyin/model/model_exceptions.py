class ZoneDoesntExist(Exception):
    """Raised when a connection references a zone that isn't registered."""

    def __init__(
        self, message: str = "Can't connect to nonexistent Zone"
    ) -> None:
        """Build the exception with a default or custom message."""
        super().__init__(message)


class DuplicateName(Exception):
    """Raised when adding a zone whose name is already registered."""

    def __init__(self, message: str = "Duplicate Zone name") -> None:
        """Build the exception with a default or custom message."""
        super().__init__(message)


class DuplicateConnection(Exception):
    """Raised when adding a connection that already exists between zones."""

    def __init__(self, message: str = "Duplicate Connection") -> None:
        """Build the exception with a default or custom message."""
        super().__init__(message)
