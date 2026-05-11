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
