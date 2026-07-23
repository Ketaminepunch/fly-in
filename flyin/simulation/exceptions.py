class BlockedZoneError(Exception):
    def __init__(self, message: str = "Cannot move into blocked/invalid zone"):
        super().__init__(message)
