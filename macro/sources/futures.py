"""Closing prices of 30-Day Federal Funds futures, from Yahoo's chart endpoint."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from macro.dates import Month
from macro.errors import SourceError

MONTH_CODES = "FGHJKMNQUVXZ"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
PRICE_BOUNDS = (80.0, 101.0)  # an implied rate between -1% and 20%


def symbol(month: Month) -> str:
    year, number = month
    return f"ZQ{MONTH_CODES[number - 1]}{year % 100:02d}.CBT"


def parse_chart(payload: object) -> dict[date, float]:
    """Closing price by trading day.

    Each bar is dated on the exchange's own clock, bar by bar, so a reply that spans a
    daylight-saving change is still dated correctly.
    """
    try:
        result = payload["chart"]["result"][0]
        zone = ZoneInfo(result["meta"]["exchangeTimezoneName"])
        stamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        prices: dict[date, float] = {}
        for stamp, close in zip(stamps, closes, strict=True):
            if close is None:
                continue
            price = round(float(close), 4)
            if not PRICE_BOUNDS[0] < price < PRICE_BOUNDS[1]:
                raise SourceError(f"Yahoo: implausible futures price {close!r}")
            prices[datetime.fromtimestamp(stamp, zone).date()] = price
    except SourceError:
        raise
    except (KeyError, IndexError, TypeError, ValueError):
        raise SourceError("Yahoo: unexpected reply") from None
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
