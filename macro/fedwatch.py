"""Rate-move probabilities from Fed funds futures, with the method CME publishes for FedWatch.

Pure functions: no input or output. See section 6.4 of the design spec.
"""
from __future__ import annotations

import calendar
import math
from collections.abc import Callable
from datetime import date, timedelta

Month = tuple[int, int]
STEP = 0.25


class FedWatchError(Exception):
    """The calculation cannot be done with this calendar or these prices."""


class MissingPrice(FedWatchError):
    """A price or rate the calculation needs is not available."""


def add_months(month: Month, count: int) -> Month:
    index = month[0] * 12 + (month[1] - 1) + count
    return (index // 12, index % 12 + 1)


def days_in(month: Month) -> int:
    return calendar.monthrange(month[0], month[1])[1]


def month_average(rates: dict[date, float], month: Month) -> float:
    """Calendar-day average of a finished month. A day with no rate carries the last published one."""
    first = date(month[0], month[1], 1)
    last: float | None = None
    for back in range(1, 11):
        earlier = first - timedelta(days=back)
        if earlier in rates:
            last = rates[earlier]
            break
    total = 0.0
    for offset in range(days_in(month)):
        day = first + timedelta(days=offset)
        last = rates.get(day, last)
        if last is None:
            raise MissingPrice(f"no rate on or before {day}")
        total += last
    return total / days_in(month)


def expected_moves(
    meeting_end: date,
    implied: Callable[[Month], float],
    has_meeting: Callable[[Month], bool],
) -> float:
    """The expected number of 25 bp moves at one meeting. Negative means cuts."""
    month = (meeting_end.year, meeting_end.month)
    days, meeting_day = days_in(month), meeting_end.day
    rate = implied(month)
    following, previous = add_months(month, 1), add_months(month, -1)
    if not has_meeting(following):
        end = implied(following)
        start = (rate * days - end * (days - meeting_day)) / meeting_day
    elif not has_meeting(previous):
        if meeting_day == days:
            raise FedWatchError(f"the meeting ends on the last day of {month}: the new rate cannot be inferred")
        start = implied(previous)
        end = (rate * days - start * meeting_day) / (days - meeting_day)
    else:
        raise FedWatchError(f"no anchor month next to {month}")
    return (end - start) / STEP


def split(moves: float) -> dict[int, float]:
    """Shares a fractional move count between the whole numbers either side of it."""
    low = math.floor(moves)
    high_share = moves - low
    shares = {low: 1.0 - high_share}
    if high_share > 0:
        shares[low + 1] = high_share
    return shares


def combine(first: dict[int, float], second: dict[int, float]) -> dict[int, float]:
    """The distribution of the total moves over two meetings."""
    total: dict[int, float] = {}
    for moves_a, share_a in first.items():
        for moves_b, share_b in second.items():
            total[moves_a + moves_b] = total.get(moves_a + moves_b, 0.0) + share_a * share_b
    return total


def distribution(
    pricing_date: date,
    target_end: date,
    meeting_ends: list[date],
    prices: dict[Month, dict[date, float]],
    rates: dict[date, float],
) -> dict[int, float]:
    """Probability of each total number of 25 bp moves from the pricing date to the target meeting.

    `prices` maps a contract month to its closing price by day. `rates` is EFFR by day.
    """
    meeting_months = {(day.year, day.month) for day in meeting_ends}
    pricing_month = (pricing_date.year, pricing_date.month)

    def implied(month: Month) -> float:
        if month < pricing_month:
            return month_average(rates, month)
        try:
            return 100.0 - prices[month][pricing_date]
        except KeyError:
            raise MissingPrice(f"no price for {month} on {pricing_date}") from None

    pending = sorted(day for day in meeting_ends if pricing_date < day <= target_end)
    if not pending:
        raise FedWatchError("no meeting between the pricing date and the target")
    total = {0: 1.0}
    for meeting_end in pending:
        moves = expected_moves(meeting_end, implied, lambda month: month in meeting_months)
        total = combine(total, split(moves))
    return total
