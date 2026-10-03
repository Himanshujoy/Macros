"""Sample data shared by several test modules. The values were recorded from the real sources on 2026-10-03."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from macro.sources.fomc import Meeting

NEW_YORK = ZoneInfo("America/New_York")

CSV_2026 = """Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
10/02/2026,4.04,4.09,4.11,4.19,4.26,4.27,4.46,4.83,4.96,5.06,5.17,5.28,5.67,5.63
10/01/2026,4.06,4.10,4.13,4.17,4.26,4.27,4.44,4.78,4.91,5.01,5.12,5.24,5.64,5.61
09/30/2026,4.02,4.13,4.16,4.20,4.29,4.33,4.54,4.88,5.00,5.09,5.19,5.29,5.68,5.64"""

CSV_2025_GAP = """Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
02/18/2025,4.38,4.41,4.38,4.34,4.37,4.34,4.24,4.29,4.33,4.40,4.48,4.55,4.83,4.77
02/14/2025,4.37,,4.38,4.34,4.35,4.32,4.23,4.26,4.26,4.33,4.41,4.47,4.75,4.69"""

CSV_1990 = """Date,"3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","30 Yr"
12/31/1990,6.63,6.73,6.82,7.15,7.40,7.68,8.00,8.08,8.26"""

OLD_HEADER = 'Date,"3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","30 Yr"'


def treasury_csv_for(year: int) -> str:
    """A small yearly file: the real 2026 sample, or two made-up rows for any other year."""
    if year == 2026:
        return CSV_2026
    return (
        f"{OLD_HEADER}\n"
        f"12/30/{year},6.63,6.73,6.82,7.15,7.40,7.68,8.00,8.08,8.26\n"
        f"01/02/{year},6.60,6.70,6.80,7.10,7.35,7.60,7.95,8.00,8.20"
    )


# Closing prices of 30-Day Federal Funds futures, keyed by the contract's (year, month).
PRICES: dict[tuple[int, int], dict[date, float]] = {
    (2026, 9): {
        date(2026, 9, 2): 96.2975,
        date(2026, 9, 3): 96.315,
        date(2026, 9, 24): 96.2525,
        date(2026, 9, 25): 96.255,
        date(2026, 10, 1): 96.253,
    },
    (2026, 10): {
        date(2026, 9, 2): 96.205,
        date(2026, 9, 3): 96.24,
        date(2026, 9, 24): 96.105,
        date(2026, 9, 25): 96.11,
        date(2026, 10, 1): 96.115,
        date(2026, 10, 2): 96.12,
    },
    (2026, 11): {
        date(2026, 9, 2): 96.14,
        date(2026, 9, 3): 96.18,
        date(2026, 9, 24): 95.95,
        date(2026, 9, 25): 95.965,
        date(2026, 10, 1): 96.06,
        date(2026, 10, 2): 96.07,
    },
    (2026, 12): {
        date(2026, 9, 2): 96.03,
        date(2026, 9, 3): 96.085,
        date(2026, 9, 24): 95.805,
        date(2026, 9, 25): 95.82,
        date(2026, 10, 1): 95.93,
        date(2026, 10, 2): 95.925,
    },
}

MEETING_ENDS = [date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9), date(2027, 1, 27)]
MEETINGS = [Meeting(day) for day in MEETING_ENDS]

HOLIDAYS = {date(2026, 9, 7)}  # Labor Day: no rate was published


def effr_rows(until: date = date(2026, 10, 1)) -> list[dict]:
    """EFFR as published from 27 July 2026, newest first, as the API returns it.

    Up to 1 October these are the real published values. A later `until` extends the last
    real rate and range forward, for tests that need a longer table.
    """
    rows = []
    day = date(2026, 7, 27)
    while day <= until:
        if day.weekday() < 5 and day not in HOLIDAYS:
            hiked = day >= date(2026, 9, 17)
            rows.append(
                {
                    "effectiveDate": day.isoformat(),
                    "type": "EFFR",
                    "percentRate": 3.88 if hiked else 3.63,
                    "targetRateFrom": 3.75 if hiked else 3.5,
                    "targetRateTo": 4.0 if hiked else 3.75,
                }
            )
        day += timedelta(days=1)
    rows.reverse()
    return rows


def effr_payload(until: date = date(2026, 10, 1)) -> dict:
    """The recent rows plus two from December 2008, when the target became a range."""
    old = [
        {"effectiveDate": "2008-12-16", "type": "EFFR", "percentRate": 0.17, "targetRateFrom": 0.0, "targetRateTo": 0.25},
        {"effectiveDate": "2008-12-15", "type": "EFFR", "percentRate": 0.18, "targetRateFrom": 1.0},
    ]
    return {"refRates": effr_rows(until) + old}


# Three rows exactly as the New York Fed returned them, with every field.
NYFED_REAL_ROWS = [
    {
        "effectiveDate": "2026-10-01", "type": "EFFR", "percentRate": 3.88, "percentPercentile1": 3.85,
        "percentPercentile25": 3.87, "percentPercentile75": 3.88, "percentPercentile99": 3.89,
        "targetRateFrom": 3.75, "targetRateTo": 4.00, "volumeInBillions": 120, "revisionIndicator": "",
    },
    {
        "effectiveDate": "2026-09-30", "type": "EFFR", "percentRate": 3.88, "percentPercentile1": 3.86,
        "percentPercentile25": 3.88, "percentPercentile75": 3.89, "percentPercentile99": 3.92,
        "targetRateFrom": 3.75, "targetRateTo": 4.00, "volumeInBillions": 83, "revisionIndicator": "",
    },
    {
        "effectiveDate": "2000-07-03", "type": "EFFR", "percentRate": 7.03, "targetRateFrom": 6.5,
        "intraDayLow": 5.5, "intraDayHigh": 7.5, "stdDeviation": 0.28, "revisionIndicator": "",
    },
]

# The October 2026 contract as Yahoo returned it on 2026-10-03, trimmed to six bars.
# The timestamps are the recorded ones: midnight in New York on each trading day.
YAHOO_REAL_REPLY = {
    "chart": {
        "result": [
            {
                "meta": {"symbol": "ZQV26.CBT", "gmtoffset": -14400, "exchangeTimezoneName": "America/New_York"},
                "timestamp": [1788321600, 1788408000, 1790222400, 1790308800, 1790827200, 1790913600],
                "indicators": {"quote": [{"close": [96.205, 96.24, 96.105, 96.11, 96.115, 96.12]}]},
            }
        ],
        "error": None,
    }
}


def chart_payload(prices: dict[date, float]) -> dict:
    """A reply in Yahoo's shape. Each bar is stamped at midnight in New York on its trading day."""
    days = sorted(prices)
    stamps = [int(datetime(d.year, d.month, d.day, tzinfo=NEW_YORK).timestamp()) for d in days]
    return {
        "chart": {
            "result": [
                {
                    "meta": {"gmtoffset": -14400, "exchangeTimezoneName": "America/New_York"},
                    "timestamp": stamps,
                    "indicators": {"quote": [{"close": [prices[d] for d in days]}]},
                }
            ],
            "error": None,
        }
    }
