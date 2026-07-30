class BlockedZoneError(Exception):
    """Raised when a drone would be moved into a blocked/invalid zone."""

    def __init__(self, message: str = "Cannot move into blocked/invalid zone"):
        """Build the exception with a default or custom message."""
        super().__init__(message)
