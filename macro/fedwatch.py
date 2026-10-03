"""Rate-move probabilities from Fed funds futures, with the method CME publishes for FedWatch.

Pure functions: no input or output. See section 6.4 of the design spec.
"""
from __future__ import annotations

import calendar
import math
from collections.abc import Callable, Collection
from datetime import date, timedelta

from macro.dates import Month, add_months

STEP = 0.25


class FedWatchError(Exception):
    """The calculation cannot be done with this calendar or these prices."""


class MissingPrice(FedWatchError):
    """A price or rate the calculation needs is not available."""


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
    pending: Collection[date],
    meeting_ends: list[date],
    prices: dict[Month, dict[date, float]],
    rates: dict[date, float],
    decided: Collection[date] = (),
) -> dict[int, float]:
    """Probability of each total number of 25 bp moves over the `pending` meetings.

    `pending` are the end dates of the meetings to count, as priced on `pricing_date`.
    `decided` are those among them whose outcome the prices already reflect: each counts as
    its nearest whole number of moves, with certainty. `meeting_ends` is the whole calendar,
    `prices` maps a contract month to its closing price by day, and `rates` is EFFR by day.
    """
    if not pending:
        raise FedWatchError("no meeting to price")
    meeting_months = {(day.year, day.month) for day in meeting_ends}
    pricing_month = (pricing_date.year, pricing_date.month)

    def implied(month: Month) -> float:
        if month < pricing_month:
            return month_average(rates, month)
        try:
            return 100.0 - prices[month][pricing_date]
        except KeyError:
            raise MissingPrice(f"no price for {month} on {pricing_date}") from None

    total = {0: 1.0}
    for meeting_end in sorted(pending):
        if (meeting_end.year, meeting_end.month) < pricing_month:
            raise FedWatchError(f"the rate table has not caught up with the {meeting_end} meeting")
        moves = expected_moves(meeting_end, implied, lambda month: month in meeting_months)
        shares = {round(moves): 1.0} if meeting_end in decided else split(moves)
        total = combine(total, shares)
    return total
