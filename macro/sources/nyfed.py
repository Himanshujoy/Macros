"""Effective federal funds rate and target range from the New York Fed's data API."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date

import httpx

from macro.errors import SourceError

URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
FIRST_DATE = date(2000, 7, 3)
RATE_BOUNDS = (-1.0, 25.0)


@dataclass(frozen=True)
class FedFundsTable:
    """Aligned lists, oldest first. Before 16 December 2008 the two target bounds are equal."""

    dates: list[date]
    effr: list[float]
    target_lower: list[float]
    target_upper: list[float]

    def target_row(self, day: date) -> tuple[date, float, float]:
        """The latest published row on or before a day: its date and the target range it carries.

        A row's range is the one in force that day. A decision takes effect the day after
        the meeting ends, so the row dated on a meeting day still shows the old range.
        """
        index = bisect_right(self.dates, day) - 1
        if index < 0:
            raise SourceError(f"New York Fed: no target range on or before {day}")
        return (self.dates[index], self.target_lower[index], self.target_upper[index])

    def target_on(self, day: date) -> tuple[float, float]:
        return self.target_row(day)[1:]

    def effr_by_date(self) -> dict[date, float]:
        return dict(zip(self.dates, self.effr))


def _point(row: dict) -> tuple[date, float, float, float] | None:
    rate = row.get("percentRate")
    if rate is None:
        return None
    lower = row.get("targetRateFrom")
    upper = row.get("targetRateTo")
    if upper is None:
        upper = lower
    if lower is None:
        lower = upper
    values = (float(rate), float(lower), float(upper))
    if not all(RATE_BOUNDS[0] < value < RATE_BOUNDS[1] for value in values):
        raise ValueError("rate out of bounds")
    return (date.fromisoformat(row["effectiveDate"]), *values)


def parse(payload: object) -> FedFundsTable:
    rows = payload.get("refRates") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SourceError("New York Fed: unexpected reply")
    points = []
    for row in rows:
        try:
            point = _point(row)
        except (AttributeError, KeyError, TypeError, ValueError):
            raise SourceError("New York Fed: unexpected row in the reply") from None
        if point is not None:
            points.append(point)
    if not points:
        raise SourceError("New York Fed: no rates in the reply")
    points.sort(key=lambda point: point[0])
    return FedFundsTable(
        dates=[point[0] for point in points],
        effr=[point[1] for point in points],
        target_lower=[point[2] for point in points],
        target_upper=[point[3] for point in points],
    )


def load(client: httpx.Client, today: date) -> FedFundsTable:
    params = {"startDate": FIRST_DATE.isoformat(), "endDate": today.isoformat()}
    try:
        response = client.get(URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError(f"New York Fed: the download failed: {exc}") from None
    return parse(payload)
