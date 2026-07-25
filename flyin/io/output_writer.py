"""Writes turn-by-turn drone movements in the required `D<ID>-<zone>` line format."""


def format_turns(turn_log: list[dict[int, str]]) -> list[str]:
    turns_formatted: list[str] = []
    for turn in turn_log:
        sorted_log = sorted(turn.items())
        turns_formatted.append(
            " ".join(
                [f"D{drone_id}-{token}" for drone_id, token in sorted_log]
            )
        )
    return turns_formatted



