"""Parsing error types, raised with the offending line and cause."""


class ParsingError(Exception):
    """Raised when a map file line can't be parsed."""

    def __init__(self, line_nbr: int, reason: str) -> None:
        """Build the exception, prefixing the reason with its line number."""
        super().__init__(f"line {line_nbr}: {reason}")
