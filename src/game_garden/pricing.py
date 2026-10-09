"""Price statistics over price_history rows."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta


def time_weighted_average(points: Sequence[tuple[date, int]], *, today: date, days: int = 365) -> float | None:
    """Average daily price over the last `days` days up to and including `today`.

    `points` are (day, price) pairs sorted by day. ITAD history only has the days a price
    changed, so each price is carried forward until the next point; a plain mean of the
    rows would over-count sale days.
    """
    window_start = today - timedelta(days=days - 1)
    in_effect = [p for p in points if p[0] <= window_start]
    later = [p for p in points if window_start < p[0] <= today]
    if in_effect:
        segments = [(window_start, in_effect[-1][1]), *later]
    elif later:
        segments = later  # history starts inside the window
    else:
        return None

    total = 0
    for i, (start, price) in enumerate(segments):
        end = segments[i + 1][0] if i + 1 < len(segments) else today + timedelta(days=1)
        total += price * (end - start).days
    return total / ((today + timedelta(days=1)) - segments[0][0]).days
