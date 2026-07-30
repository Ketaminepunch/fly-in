class PathNotFoundError(Exception):
    """Raised when no route exists between the start and end zones."""

    def __init__(self, message: str = "No path exists from start to end zone"):
        """Build the exception with a default or custom message."""
        super().__init__(message)
