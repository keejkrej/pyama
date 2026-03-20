def parse_position_range(text: str, length: int | None = None) -> list[int]:
    normalized = text.strip()
    if not normalized:
        raise ValueError("Position specification cannot be empty")
    if "-" in normalized:
        raise ValueError("Dash syntax is not supported; use slice syntax (e.g. 0:6,7,9:12)")

    if normalized.lower() == "all":
        if length is None:
            return []
        return list(range(length))

    values: set[int] = set()
    for segment in normalized.split(","):
        segment = segment.strip()
        if not segment:
            continue
        if ":" in segment:
            parts = segment.split(":")
            if len(parts) > 3:
                raise ValueError(f"Invalid slice segment: {segment!r}")
            start = int(parts[0]) if parts[0] else None
            stop = int(parts[1]) if len(parts) > 1 and parts[1] else None
            step = int(parts[2]) if len(parts) == 3 and parts[2] else None
            if step == 0:
                raise ValueError(f"Slice step cannot be zero: {segment!r}")
            if stop is None:
                if length is None:
                    raise ValueError(f"Slice stop is required without known length: {segment!r}")
                stop = length
            values.update(range(start or 0, stop, step or 1))
        else:
            values.add(int(segment))

    if not values:
        raise ValueError(f"Slice string {text!r} produced no indices")

    if length is not None:
        max_index = length - 1
        for index in values:
            if index < 0 or index > max_index:
                raise ValueError(f"Position index {index} out of range [0, {max_index}]")
    elif any(index < 0 for index in values):
        raise ValueError("Position indices must be >= 0 without known length")

    return sorted(values)


__all__ = ["parse_position_range"]
