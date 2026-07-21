"""Parsing error types, raised with the offending line and cause."""


class ParsingError(Exception):
    def __init__(self, message: str = "Error: ParsingError") -> None:
        super().__init__(message)
