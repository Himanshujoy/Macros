"""Closing prices of 30-Day Federal Funds futures, from Yahoo's chart endpoint."""
from __future__ import annotations

from datetime import date, datetime, timezone

import httpx

from macro.errors import SourceError

MONTH_CODES = "FGHJKMNQUVXZ"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

Month = tuple[int, int]


def symbol(month: Month) -> str:
    year, number = month
    return f"ZQ{MONTH_CODES[number - 1]}{year % 100:02d}.CBT"


def parse_chart(payload: object) -> dict[date, float]:
    """Closing price by trading day. Timestamps are shifted to the exchange's own clock first."""
    try:
        result = payload["chart"]["result"][0]
        offset = result["meta"]["gmtoffset"]
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        raise SourceError("Yahoo: unexpected reply") from None
    prices: dict[date, float] = {}
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(stamp + offset, timezone.utc).date()
        prices[day] = round(float(close), 4)
    return prices


def fetch(client: httpx.Client, month: Month) -> dict[date, float]:
    """Three months of daily closes. Empty when Yahoo no longer lists the contract."""
    name = symbol(month)
    try:
        response = client.get(URL.format(symbol=name), params={"range": "3mo", "interval": "1d"})
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError(f"Yahoo: the {name} download failed: {exc}") from None
    return parse_chart(payload)


def load(client: httpx.Client, months: list[Month]) -> dict[Month, dict[date, float]]:
    return {month: fetch(client, month) for month in months}
