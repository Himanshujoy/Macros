"""Date helpers shared by the sources, the odds and the facts."""
from __future__ import annotations

import calendar
from bisect import bisect_right
from datetime import date

Month = tuple[int, int]  # (year, month)


def add_months(month: Month, count: int) -> Month:
    index = month[0] * 12 + (month[1] - 1) + count
    return (index // 12, index % 12 + 1)


def months_back(day: date, count: int) -> date:
    """The same day `count` months earlier, clamped to the end of a shorter month."""
    year, month = add_months((day.year, day.month), -count)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def on_or_before(days: list[date], limit: date) -> date | None:
    """The latest day in a sorted list that is not after `limit`."""
    index = bisect_right(days, limit) - 1
    return days[index] if index >= 0 else None
