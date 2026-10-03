"""Effective federal funds rate and target range from the New York Fed's data API."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date

import httpx

from macro.errors import SourceError

URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
FIRST_DATE = date(2000, 7, 3)


@dataclass(frozen=True)
class FedFundsTable:
    """Aligned lists, oldest first. Before 16 December 2008 the two target bounds are equal."""

    dates: list[date]
    effr: list[float]
    target_lower: list[float | None]
    target_upper: list[float | None]

    def target_on(self, day: date) -> tuple[float, float]:
        """The target range in force on a day. Weekends and holidays take the last published row."""
        index = bisect_right(self.dates, day) - 1
        while index >= 0 and self.target_lower[index] is None:
            index -= 1
        if index < 0:
            raise SourceError(f"New York Fed: no target range on or before {day}")
        return (self.target_lower[index], self.target_upper[index])

    def effr_by_date(self) -> dict[date, float]:
        return dict(zip(self.dates, self.effr))


def parse(payload: object) -> FedFundsTable:
    rows = payload.get("refRates") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SourceError("New York Fed: unexpected reply")
    points = []
    for row in rows:
        rate = row.get("percentRate")
        if rate is None:
            continue
        lower = row.get("targetRateFrom")
        upper = row.get("targetRateTo")
        if upper is None:
            upper = lower
        if lower is None:
            lower = upper
        points.append((date.fromisoformat(row["effectiveDate"]), float(rate), lower, upper))
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
