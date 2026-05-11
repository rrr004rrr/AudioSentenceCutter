def format_seconds(value: float) -> str:
    """Format seconds with at least 2 digits before the decimal and exactly 2 after.

    Examples: 7.2 -> "07.20", 123.456 -> "123.46", 0 -> "00.00".
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "00.00"
    if v < 0:
        v = 0.0
    return f"{v:05.2f}"


# Output modes for build_timecode_string — these mirror the three formats
# requested by PM 林聖璇 (吉的堡):
#   play     -> start1,end1, start2,end2, ..., startN,endN
#   repeat-1 -> 0, end1,     start2,end2, ..., startN,endN
#   repeat-2 -> end1,start2, end2,start3, ..., endN,total
TIMECODE_MODES = ("play", "repeat-1", "repeat-2")


def build_timecode_string(segments, total_duration: float, mode: str = "play") -> str:
    """Render a comma-separated timecode list per the selected mode.

    `segments` must be objects exposing .start / .end floats.
    """
    parts = []
    n = len(segments)
    if n == 0:
        return ""

    if mode == "play":
        for seg in segments:
            parts.append(format_seconds(seg.start))
            parts.append(format_seconds(seg.end))
    elif mode == "repeat-1":
        parts.append(format_seconds(0))
        parts.append(format_seconds(segments[0].end))
        for seg in segments[1:]:
            parts.append(format_seconds(seg.start))
            parts.append(format_seconds(seg.end))
    elif mode == "repeat-2":
        for i, seg in enumerate(segments):
            parts.append(format_seconds(seg.end))
            if i + 1 < n:
                parts.append(format_seconds(segments[i + 1].start))
            else:
                parts.append(format_seconds(total_duration))
    else:
        raise ValueError(f"Unknown timecode mode: {mode!r}")

    return ",".join(parts)
