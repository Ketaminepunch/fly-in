"""Parsing error types, raised with the offending line and cause."""


class ParsingError(Exception):
    def __init__(self, line_nbr: int, reason: str) -> None:
        super().__init__(f"line {line_nbr}: {reason}")
