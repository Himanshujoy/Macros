"""Builds the odds block of data.json from futures prices."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from macro.dates import Month, months_back, on_or_before
from macro.errors import SourceError
from macro.fedwatch import STEP, MissingPrice, distribution
from macro.sources.fomc import Meeting, upcoming
from macro.sources.nyfed import FedFundsTable

SHOWN_FROM = 0.0005  # a range appears in the table once any column gives it at least 0.05%
STALE_AFTER_DAYS = 5  # the rate table may trail the pricing date by a long weekend, not more
NOW_FALLBACK_DAYS = 3  # how many of the latest price days to try for "now"


def comparison_dates(price_days: list[date]) -> list[tuple[str, date | None]]:
    """The four pricing dates: now, the price day before it, and a week and a month earlier."""
    now = price_days[-1]
    earlier = price_days[:-1]
    return [
        ("now", now),
        ("d1", earlier[-1] if earlier else None),
        ("w1", on_or_before(earlier, now - timedelta(days=7))),
        ("m1", on_or_before(earlier, months_back(now, 1))),
    ]


def build_odds(
    now: datetime,
    meetings: list[Meeting],
    prices: dict[Month, dict[date, float]],
    fed: FedFundsTable,
) -> dict:
    """Probabilities by target range for the next meeting whose statement is still ahead of `now`."""
    ahead = upcoming(meetings, now)
    if not ahead:
        raise SourceError("FOMC calendar: no future meeting. Update data/fomc_meetings.json")
    target = ahead[0].end
    ends = [meeting.end for meeting in meetings]
    statement_at = {meeting.end: meeting.statement_at for meeting in meetings}
    price_days = sorted(prices.get((target.year, target.month), {}))
    if not price_days:
        raise SourceError(f"odds: no futures prices for the {target} meeting")
    rates = fed.effr_by_date()

    def priced_on(day: date, live: bool) -> tuple[dict[float, float], tuple[float, float]]:
        """Shares by the lower bound of each target range, and the range in force, as priced on `day`.

        The base range comes from the latest published row. A meeting that ended on or after
        that row's date is not in the row yet, so it is counted here. Among those, a meeting
        whose outcome the prices already reflect counts as a whole move.
        """
        base_day, lower, upper = fed.target_row(day)
        if (day - base_day).days > STALE_AFTER_DAYS:
            raise SourceError(f"odds: New York Fed data stops at {base_day}, too far behind prices of {day}")
        pending = [end for end in ends if base_day <= end <= target]
        if live:
            decided = [end for end in pending if statement_at[end] <= now]
            late = [end for end in decided if end > day]
            if late:
                raise SourceError(f"odds: prices have not caught up with the {late[0]} decision. Refresh later")
        else:
            decided = [end for end in pending if end <= day]  # a finished daily bar follows the statement
        shares = distribution(day, pending, ends, prices, rates, decided)
        settled = next(iter(distribution(day, decided, ends, prices, rates, decided))) if decided else 0
        by_lower = {round(lower + STEP * count, 2): share for count, share in shares.items()}
        return by_lower, (round(lower + STEP * settled, 2), round(upper + STEP * settled, 2))

    now_day = None
    failure: MissingPrice | None = None
    for candidate in reversed(price_days[-NOW_FALLBACK_DAYS:]):
        try:
            now_shares, current = priced_on(candidate, live=True)
        except MissingPrice as exc:
            failure = failure or exc
            continue
        now_day = candidate
        break
    if now_day is None:
        raise SourceError(f"odds: {failure}")

    columns = comparison_dates([day for day in price_days if day <= now_day])
    by_column: dict[str, dict[float, float] | None] = {"now": now_shares}
    for key, day in columns[1:]:
        if day is None:
            by_column[key] = None
            continue
        try:
            by_column[key] = priced_on(day, live=False)[0]
        except MissingPrice:
            by_column[key] = None

    lowers = sorted(
        {
            lower
            for shares in by_column.values()
            if shares is not None
            for lower, share in shares.items()
            if share >= SHOWN_FROM
        }
    )
    outcomes = []
    for lower in lowers:
        row: dict = {"range": [lower, round(lower + STEP, 2)]}
        for key, _ in columns:
            shares = by_column[key]
            row[key] = None if shares is None else round(100 * shares.get(lower, 0.0), 1)
        outcomes.append(row)

    held = current[0]
    return {
        "meeting": target.isoformat(),
        "priced_on": now_day.isoformat(),
        "current_range": [current[0], current[1]],
        "columns": [{"key": key, "date": day.isoformat() if day else None} for key, day in columns],
        "outcomes": outcomes,
        "summary": {
            "cut": round(100 * sum((share for lower, share in now_shares.items() if lower < held), 0.0), 1),
            "hold": round(100 * now_shares.get(held, 0.0), 1),
            "hike": round(100 * sum((share for lower, share in now_shares.items() if lower > held), 0.0), 1),
        },
    }
