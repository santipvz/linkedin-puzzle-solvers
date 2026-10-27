from ..domain.models import JsonDict


def should_recompute(puzzle_name: str, cached: JsonDict) -> bool:
    if not isinstance(cached, dict):
        return False

    if puzzle_name == "tango":
        board_size = int(cached.get("board_size") or 0)
        details = cached.get("details") if isinstance(cached.get("details"), dict) else {}
        parse_reliable = details.get("parse_reliable")
        fixed_count = int(details.get("fixed_count") or 0)
        constraint_count = int(details.get("constraint_count") or 0)

        if board_size != 6:
            return True
        if parse_reliable is None:
            return True
        if not bool(cached.get("solved")) and fixed_count < 4 and constraint_count >= 2:
            return True

        return False

    if puzzle_name == "patches":
        details = cached.get("details") if isinstance(cached.get("details"), dict) else {}
        return details.get("parse_reliable") is False

    if puzzle_name != "queens":
        return False

    if bool(cached.get("solved")):
        return False

    error_text = str(cached.get("error") or "").lower()
    if "cannot have a valid solution" not in error_text:
        return False

    details = cached.get("details") if isinstance(cached.get("details"), dict) else {}
    iterations = int(details.get("iterations") or 0)
    board_size = int(cached.get("board_size") or 0)
    regions_detected = int(details.get("regions_detected") or 0)

    # Old queens pre-validation false negatives fail before backtracking starts.
    return iterations == 0 and board_size > 0 and regions_detected == board_size
