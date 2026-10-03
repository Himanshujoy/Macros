"""Builds the odds block of data.json from futures prices."""
from __future__ import annotations

from datetime import date, timedelta

from macro.dates import months_back, on_or_before
from macro.errors import SourceError
from macro.fedwatch import STEP, MissingPrice, Month, distribution
from macro.sources.nyfed import FedFundsTable

SHOWN_FROM = 0.0005  # a range appears in the table once any column gives it at least 0.05%


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
    target_end: date,
    meeting_ends: list[date],
    prices: dict[Month, dict[date, float]],
    fed: FedFundsTable,
) -> dict:
    """Probabilities by target range for the meeting ending on `target_end`."""
    price_days = sorted(prices.get((target_end.year, target_end.month), {}))
    if not price_days:
        raise SourceError(f"odds: no futures prices for the {target_end} meeting")
    rates = fed.effr_by_date()
    columns = comparison_dates(price_days)

    by_column: dict[str, dict[float, float] | None] = {}
    for key, day in columns:
        if day is None:
            by_column[key] = None
            continue
        try:
            moves = distribution(day, target_end, meeting_ends, prices, rates)
        except MissingPrice as exc:
            if key == "now":
                raise SourceError(f"odds: {exc}") from None
            by_column[key] = None
            continue
        lower = fed.target_on(day)[0]
        by_column[key] = {round(lower + STEP * count, 2): share for count, share in moves.items()}

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

    now_day = columns[0][1]
    current = fed.target_on(now_day)
    now = by_column["now"]
    held = round(current[0], 2)
    return {
        "meeting": target_end.isoformat(),
        "priced_on": now_day.isoformat(),
        "current_range": [current[0], current[1]],
        "columns": [{"key": key, "date": day.isoformat() if day else None} for key, day in columns],
        "outcomes": outcomes,
        "summary": {
            "cut": round(100 * sum((share for lower, share in now.items() if lower < held), 0.0), 1),
            "hold": round(100 * now.get(held, 0.0), 1),
            "hike": round(100 * sum((share for lower, share in now.items() if lower > held), 0.0), 1),
        },
    }
