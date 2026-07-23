class PathNotFoundError(Exception):
    def __init__(self, message: str = "No path exists from start to end zone"):
        super().__init__(message)
