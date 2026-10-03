# Macros Page, Plan 1b: Review Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the defects an independent review found in the Plan 1 data pipeline, so the odds are labelled with the right target range around a rate change, futures prices are dated correctly across a clock change, and failures are reported plainly.

**Architecture:** Same modules as Plan 1. The odds block now decides for itself which meeting is next and which meetings the published rate table has not caught up with. Every changed file is replaced in full.

**Tech Stack:** Python 3.14 on the Mac, with all code kept compatible with Python 3.12. httpx 0.28.1, pytest 9.1.1. No new dependencies.

**Supersedes:** for every file listed below, the content in `2026-10-04-macros-1-data-pipeline.md`.

---

## What the review found and what changes

| Finding | Fix | Where |
|---|---|---|
| Odds were labelled one target range off when priced on a meeting day, or the day after a move while the New York Fed's table was a day behind | The base range comes from the latest published row. Every meeting that ended on or after that row's date is counted. A meeting whose outcome the prices already reflect counts as a whole move | `macro/odds.py`, `macro/fedwatch.py`, `macro/sources/nyfed.py` |
| The odds and the countdown could point at different meetings on a meeting day | The target is the next meeting whose statement is still ahead, the same rule the countdown uses | `macro/odds.py`, `macro/cli.py` |
| Futures bars were dated one day early after the US clocks change | Each bar is dated in the exchange's time zone, bar by bar | `macro/sources/futures.py` |
| `dist/` was deleted before the new one was in place | Two renames, with the old folder put back if the second fails | `macro/build.py` |
| Malformed replies and build problems surfaced as tracebacks | Row parsing raises `SourceError`; `BuildError` for build problems; the command prints one line for anything unexpected, with `--debug` for the full error | `macro/errors.py`, sources, `macro/build.py`, `macro/cli.py` |
| The Treasury cache could miss the last days of a year for good | A cached year is trusted only if it was fetched after that year ended. A damaged cache file is fetched again | `macro/sources/treasury.py` |
| No sanity bounds on yields, rates and prices | Implausible values stop the refresh | sources |
| An empty Treasury file in the first days of January stopped every refresh | An empty file for the current year means "no rows yet" | `macro/sources/treasury.py` |
| "Now" used the latest day of one contract, so one missing bar stopped the refresh | "Now" falls back up to two price days | `macro/odds.py` |
| The last rate change had no size | `last_change` carries `effective` and `change_bp` | `macro/facts.py` |
| Test gaps | Cut and large-move cases through the odds block, a recorded Yahoo reply, real New York Fed rows, clock-change bars, failure paths, and a guard on name lookups | `tests/` |

The shape of `data.json` is unchanged. In `work/facts.json`, `fed_funds.last_change.date` is renamed `effective` and gains `change_bp`.

## Rules for whoever executes this plan

- **Never run `git add`, `commit`, `push`, `stash`, `reset`, `checkout` or `restore`.** The owner makes every commit. Each task ends with a checkpoint. Stop there and report.
- **Tests never touch a real service.** Do not run `python -m macro refresh`.
- **Nothing in this plan touches the box or Cloudflare.** Do not run `ssh`.
- Run every command from the project root, `/Users/himanshusrivastava/Projects/Macros`, with `.venv/bin/python`.
- Each file below is shown in full and **replaces** the existing file of the same path. Copy it exactly.
- Keep the code compatible with Python 3.12.

---

### Task 1: The network guard, error types and date helpers

**Files:**
- Replace: `tests/conftest.py`, `tests/test_network_guard.py`, `tests/test_dates.py`
- Replace: `macro/errors.py`, `macro/dates.py`

The guard now also blocks name lookups. `MacroError` becomes the base of every error a command reports plainly. `Month` and `add_months` move into `macro/dates.py` so the sources and the calculation share them.

- [ ] **Step 1: Replace the three test files**

**File: `tests/conftest.py`**

```python
"""Shared test setup. The guard makes a forgotten mock fail loudly instead of calling a real service."""
import socket

import pytest

_real_connect = socket.socket.connect
_real_getaddrinfo = socket.getaddrinfo
_LOCAL = ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL:
            raise RuntimeError(f"test tried to open a network connection to {host!r}")
        return _real_connect(self, address, *args, **kwargs)

    def guarded_lookup(host, *args, **kwargs):
        if host is not None and host not in _LOCAL:
            raise RuntimeError(f"test tried to look up {host!r} on the network")
        return _real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_lookup)
```

**File: `tests/test_network_guard.py`**

```python
import socket

import pytest


def test_the_guard_blocks_connections_outside_localhost():
    with socket.socket() as sock, pytest.raises(RuntimeError, match="network"):
        sock.settimeout(0.5)
        sock.connect(("192.0.2.1", 80))  # TEST-NET-1: a reserved address that is never a real host


def test_the_guard_blocks_name_lookups():
    with pytest.raises(RuntimeError, match="look up"):
        socket.getaddrinfo("example.invalid", 443)


def test_the_guard_allows_localhost():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.socket() as client:
            client.connect(server.getsockname())
    assert socket.getaddrinfo("localhost", 80)
```

**File: `tests/test_dates.py`**

```python
from datetime import date

from macro.dates import add_months, months_back, on_or_before


def test_add_months_crosses_year_boundaries():
    assert add_months((2026, 12), 1) == (2027, 1)
    assert add_months((2027, 1), -1) == (2026, 12)
    assert add_months((2026, 10), -2) == (2026, 8)


def test_months_back_keeps_the_day_when_it_exists():
    assert months_back(date(2026, 10, 2), 1) == date(2026, 9, 2)
    assert months_back(date(2026, 10, 2), 12) == date(2025, 10, 2)


def test_months_back_clamps_to_the_end_of_a_shorter_month():
    assert months_back(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert months_back(date(2024, 2, 29), 12) == date(2023, 2, 28)


def test_months_back_crosses_a_year_boundary():
    assert months_back(date(2027, 1, 15), 3) == date(2026, 10, 15)


def test_on_or_before_finds_the_latest_day_not_after_the_limit():
    days = [date(2026, 9, 24), date(2026, 9, 25), date(2026, 10, 1)]
    assert on_or_before(days, date(2026, 9, 27)) == date(2026, 9, 25)
    assert on_or_before(days, date(2026, 9, 25)) == date(2026, 9, 25)
    assert on_or_before(days, date(2026, 9, 1)) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dates.py tests/test_network_guard.py`

Expected: FAIL with `ImportError: cannot import name 'add_months' from 'macro.dates'`

- [ ] **Step 3: Replace the two modules**

**File: `macro/errors.py`**

```python
"""Errors the commands report to the owner in plain words."""


class MacroError(Exception):
    """Any failure a command reports as a plain message, without a traceback."""


class SourceError(MacroError):
    """A data source failed or returned something unexpected."""


class BuildError(MacroError):
    """The output folder could not be built."""
```

**File: `macro/dates.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dates.py tests/test_network_guard.py`

Expected: `8 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `103 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/conftest.py`, `tests/test_network_guard.py`, `tests/test_dates.py`, `macro/errors.py`, `macro/dates.py`. Suggested message: `fix: guard name lookups; shared error base and month helpers`.

---

### Task 2: The three network sources

**Files:**
- Replace: `tests/samples.py`, `tests/test_treasury.py`, `tests/test_nyfed.py`, `tests/test_futures.py`
- Replace: `macro/sources/treasury.py`, `macro/sources/nyfed.py`, `macro/sources/futures.py`

What changes:

- **Treasury:** sanity bounds and a row-width check; an index file, `saved.json`, records the day each year was fetched, and a year is taken from the cache only if that day is after the year ended; a damaged cache file is fetched again; an empty file for the current year means no rows yet; files are written through a temporary file.
- **New York Fed:** `target_row` returns the date of the row that supplied the range; a malformed row is a `SourceError`; rates are bounds-checked.
- **Futures:** each bar is dated in the exchange's time zone; prices are bounds-checked; any malformed reply is a `SourceError`.
- **Samples:** a recorded Yahoo reply, three real New York Fed rows, and a rate table that can be extended for later dates.

- [ ] **Step 1: Replace the four test files**

**File: `tests/samples.py`**

```python
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
```

**File: `tests/test_treasury.py`**

```python
import json
from datetime import date

import httpx
import pytest

from macro.errors import SourceError
from macro.sources import treasury
from samples import CSV_1990, CSV_2025_GAP, CSV_2026, OLD_HEADER, treasury_csv_for


def test_parse_tenor_labels_and_years():
    assert treasury.parse_tenor("1 Mo") == treasury.Tenor("1M", 1 / 12)
    assert treasury.parse_tenor("1.5 Month") == treasury.Tenor("1.5M", 1.5 / 12)
    assert treasury.parse_tenor("10 Yr") == treasury.Tenor("10Y", 10.0)


def test_parse_tenor_rejects_unknown_columns():
    with pytest.raises(SourceError, match="unknown column"):
        treasury.parse_tenor("10 Year Real")


def test_parse_year_reads_dates_and_values():
    tenors, rows = treasury.parse_year_csv(CSV_2026)
    assert [t.label for t in tenors] == [
        "1M", "1.5M", "2M", "3M", "4M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y",
    ]
    assert rows[0][0] == date(2026, 10, 2)
    assert rows[0][1]["10Y"] == 5.28
    assert len(rows) == 3


def test_a_blank_cell_becomes_none():
    _, rows = treasury.parse_year_csv(CSV_2025_GAP)
    by_date = dict(rows)
    assert by_date[date(2025, 2, 14)]["1.5M"] is None
    assert by_date[date(2025, 2, 18)]["1.5M"] == 4.41


def test_older_years_have_fewer_tenors():
    tenors, rows = treasury.parse_year_csv(CSV_1990)
    assert [t.label for t in tenors] == ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]
    assert rows[0][1]["30Y"] == 8.26


def test_parse_year_rejects_a_page_that_is_not_the_csv():
    with pytest.raises(SourceError):
        treasury.parse_year_csv("<html>Access denied</html>")


@pytest.mark.parametrize("cell", ["nan", "inf", "404", "-9", "abc"])
def test_an_implausible_yield_is_a_source_error(cell):
    text = f"{OLD_HEADER}\n12/31/1990,{cell},6.73,6.82,7.15,7.40,7.68,8.00,8.08,8.26"
    with pytest.raises(SourceError):
        treasury.parse_year_csv(text)


def test_a_row_of_the_wrong_width_is_a_source_error():
    with pytest.raises(SourceError, match="cells"):
        treasury.parse_year_csv(f"{OLD_HEADER}\n12/31/1990,6.63,6.73")


def test_build_table_merges_years_oldest_first_and_fills_gaps():
    table = treasury.build_table([treasury.parse_year_csv(CSV_2026), treasury.parse_year_csv(CSV_1990)])
    assert table.dates[0] == date(1990, 12, 31)
    assert table.dates[-1] == date(2026, 10, 2)
    assert [t.label for t in table.tenors][:3] == ["1M", "1.5M", "2M"]
    assert table.values["1M"][0] is None
    assert table.values["10Y"] == [8.08, 5.29, 5.24, 5.28]


def year_of(request):
    return int(request.url.params["field_tdr_date_value"])


class Recorder:
    """A fake Treasury site that remembers which years were asked for."""

    def __init__(self, reply=treasury_csv_for):
        self.seen = []
        self.reply = reply

    def __call__(self, request):
        self.seen.append(year_of(request))
        return httpx.Response(200, text=self.reply(year_of(request)))

    def load(self, cache_dir, today):
        self.seen.clear()
        with httpx.Client(transport=httpx.MockTransport(self)) as client:
            return treasury.load(client, cache_dir, today)


def test_load_caches_past_years_and_refetches_the_current_year(tmp_path):
    site = Recorder()
    site.load(tmp_path, date(2026, 10, 3))
    assert site.seen == list(range(1990, 2027))
    table = site.load(tmp_path, date(2026, 10, 3))
    assert site.seen == [2026]
    assert table.dates[-1] == date(2026, 10, 2)


def test_a_year_fetched_before_it_ended_is_fetched_again_however_late(tmp_path):
    site = Recorder()
    site.load(tmp_path, date(2026, 12, 20))
    site.load(tmp_path, date(2027, 2, 3))  # no refresh in between: 2026 was last saved on 20 December
    assert site.seen == [2026, 2027]
    site.load(tmp_path, date(2027, 2, 4))  # now 2026 was saved after it ended, so it is final
    assert site.seen == [2027]


def test_a_damaged_cache_file_is_fetched_again(tmp_path):
    site = Recorder()
    site.load(tmp_path, date(2026, 10, 3))
    (tmp_path / "2001.csv").write_text("<html>half a page")
    site.load(tmp_path, date(2026, 10, 3))
    assert site.seen == [2001, 2026]
    assert (tmp_path / "2001.csv").read_text() == treasury_csv_for(2001)


def test_a_missing_or_broken_index_means_fetch_everything_again(tmp_path):
    site = Recorder()
    site.load(tmp_path, date(2026, 10, 3))
    (tmp_path / "saved.json").write_text("not json")
    site.load(tmp_path, date(2026, 10, 3))
    assert site.seen == list(range(1990, 2027))
    assert json.loads((tmp_path / "saved.json").read_text())["2025"] == "2026-10-03"


def test_an_empty_file_for_the_new_year_is_not_an_error(tmp_path):
    site = Recorder(lambda year: "" if year == 2027 else treasury_csv_for(year))
    table = site.load(tmp_path, date(2027, 1, 2))
    assert table.dates[-1] == date(2026, 10, 2)


def test_an_empty_file_for_a_past_year_is_an_error(tmp_path):
    site = Recorder(lambda year: "" if year == 2005 else treasury_csv_for(year))
    with pytest.raises(SourceError):
        site.load(tmp_path, date(2026, 10, 3))


def test_a_bad_download_stops_the_load_and_is_not_cached(tmp_path):
    site = Recorder(lambda year: "<html>Access denied</html>")
    with pytest.raises(SourceError):
        site.load(tmp_path, date(2026, 10, 3))
    assert list(tmp_path.iterdir()) == []


def test_a_failed_request_is_reported_as_a_source_error(tmp_path):
    def handler(request):
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises(SourceError, match="1990"):
        treasury.load(client, tmp_path, date(2026, 10, 3))
```

**File: `tests/test_nyfed.py`**

```python
from datetime import date

import httpx
import pytest

from macro.errors import SourceError
from macro.sources import nyfed
from samples import NYFED_REAL_ROWS, effr_payload


def test_parse_orders_rows_oldest_first():
    table = nyfed.parse(effr_payload())
    assert table.dates[0] == date(2008, 12, 15)
    assert table.dates[-1] == date(2026, 10, 1)
    assert table.effr[-1] == 3.88


def test_rows_recorded_from_the_real_api_parse():
    table = nyfed.parse({"refRates": NYFED_REAL_ROWS})
    assert table.dates == [date(2000, 7, 3), date(2026, 9, 30), date(2026, 10, 1)]
    assert table.effr == [7.03, 3.88, 3.88]
    assert (table.target_lower[0], table.target_upper[0]) == (6.5, 6.5)
    assert (table.target_lower[-1], table.target_upper[-1]) == (3.75, 4.0)


def test_a_single_target_fills_both_bounds():
    table = nyfed.parse(effr_payload())
    assert (table.target_lower[0], table.target_upper[0]) == (1.0, 1.0)
    assert (table.target_lower[1], table.target_upper[1]) == (0.0, 0.25)


def test_target_row_gives_the_row_date_and_the_range_it_carries():
    table = nyfed.parse(effr_payload())
    assert table.target_row(date(2026, 9, 16)) == (date(2026, 9, 16), 3.5, 3.75)  # the meeting day: old range
    assert table.target_row(date(2026, 9, 17)) == (date(2026, 9, 17), 3.75, 4.0)
    assert table.target_row(date(2026, 9, 20)) == (date(2026, 9, 18), 3.75, 4.0)  # a Sunday


def test_target_on_returns_the_range_in_force():
    table = nyfed.parse(effr_payload())
    assert table.target_on(date(2026, 9, 16)) == (3.5, 3.75)
    assert table.target_on(date(2026, 9, 20)) == (3.75, 4.0)


def test_target_row_before_the_data_is_an_error():
    table = nyfed.parse(effr_payload())
    with pytest.raises(SourceError):
        table.target_row(date(2000, 1, 1))


def test_effr_by_date():
    table = nyfed.parse(effr_payload())
    assert table.effr_by_date()[date(2026, 8, 31)] == 3.63


def test_rows_without_a_rate_are_skipped():
    payload = {
        "refRates": [
            {"effectiveDate": "2026-10-01", "percentRate": 3.88, "targetRateFrom": 3.75, "targetRateTo": 4.0},
            {"effectiveDate": "2026-09-30"},
        ]
    }
    assert nyfed.parse(payload).dates == [date(2026, 10, 1)]


@pytest.mark.parametrize("payload", [{}, {"refRates": []}, {"refRates": None}, []])
def test_unexpected_replies_are_source_errors(payload):
    with pytest.raises(SourceError):
        nyfed.parse(payload)


GOOD = {"effectiveDate": "2026-10-01", "percentRate": 3.88, "targetRateFrom": 3.75, "targetRateTo": 4.0}


@pytest.mark.parametrize(
    "row",
    [
        None,
        "a string",
        {**GOOD, "effectiveDate": "1 Oct 2026"},
        {"percentRate": 3.88, "targetRateFrom": 3.75},
        {**GOOD, "percentRate": "n/a"},
        {**GOOD, "percentRate": 388},
        {"effectiveDate": "2026-10-01", "percentRate": 3.88},
    ],
)
def test_a_malformed_row_is_a_source_error(row):
    with pytest.raises(SourceError, match="unexpected row"):
        nyfed.parse({"refRates": [GOOD, row]})


def test_load_asks_for_the_full_history():
    asked = {}

    def handler(request):
        asked.update(dict(request.url.params))
        return httpx.Response(200, json=effr_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        table = nyfed.load(client, date(2026, 10, 3))
    assert asked == {"startDate": "2000-07-03", "endDate": "2026-10-03"}
    assert table.dates[-1] == date(2026, 10, 1)


def test_a_failed_request_is_a_source_error():
    def handler(request):
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client, pytest.raises(SourceError):
        nyfed.load(client, date(2026, 10, 3))
```

**File: `tests/test_futures.py`**

```python
from datetime import date, datetime, timezone

import httpx
import pytest

from macro.errors import SourceError
from macro.sources import futures
from samples import PRICES, YAHOO_REAL_REPLY, chart_payload


def test_symbols_use_the_exchange_month_codes():
    assert futures.symbol((2026, 10)) == "ZQV26.CBT"
    assert futures.symbol((2026, 11)) == "ZQX26.CBT"
    assert futures.symbol((2027, 1)) == "ZQF27.CBT"


def test_a_recorded_reply_parses_to_the_right_days_and_prices():
    assert futures.parse_chart(YAHOO_REAL_REPLY) == PRICES[(2026, 10)]


def test_bars_either_side_of_a_clock_change_keep_their_own_dates():
    # Read after the US clocks go back on 1 November 2026: the reply's single offset is the
    # winter one, but the October bars were stamped at midnight in summer time.
    bars = {date(2026, 10, 29): 4, date(2026, 10, 30): 4, date(2026, 11, 2): 5}
    stamps = [int(datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc).timestamp()) for d, hour in bars.items()]
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"gmtoffset": -18000, "exchangeTimezoneName": "America/New_York"},
                    "timestamp": stamps,
                    "indicators": {"quote": [{"close": [96.1, 96.2, 96.3]}]},
                }
            ]
        }
    }
    assert futures.parse_chart(payload) == {date(2026, 10, 29): 96.1, date(2026, 10, 30): 96.2, date(2026, 11, 2): 96.3}


def test_parse_chart_skips_days_without_a_close():
    payload = chart_payload({date(2026, 10, 1): 96.115, date(2026, 10, 2): 96.12})
    payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][0] = None
    assert futures.parse_chart(payload) == {date(2026, 10, 2): 96.12}


def test_parse_chart_rounds_float_noise():
    payload = chart_payload({date(2026, 10, 2): 96.12000274658203})
    assert futures.parse_chart(payload) == {date(2026, 10, 2): 96.12}


@pytest.mark.parametrize("price", [9.607, 961.2, float("nan"), "n/a"])
def test_an_implausible_price_is_a_source_error(price):
    with pytest.raises(SourceError):
        futures.parse_chart(chart_payload({date(2026, 10, 2): price}))


def broken(change):
    payload = chart_payload({date(2026, 10, 2): 96.12})
    change(payload["chart"]["result"][0])
    return payload


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"chart": {"result": None, "error": {"code": "Not Found"}}},
        {"chart": {"result": [{}]}},
        broken(lambda result: result.update(timestamp=None)),
        broken(lambda result: result["meta"].update(exchangeTimezoneName="Mars/Olympus")),
        broken(lambda result: result["meta"].pop("exchangeTimezoneName")),
        broken(lambda result: result["indicators"]["quote"][0].update(close=None)),
        broken(lambda result: result["indicators"]["quote"][0].update(close=[96.1, 96.2])),
    ],
)
def test_an_unexpected_reply_is_a_source_error(payload):
    with pytest.raises(SourceError):
        futures.parse_chart(payload)


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_load_fetches_each_contract_and_treats_404_as_no_data():
    def handler(request):
        if "ZQQ26.CBT" in request.url.path:
            return httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found"}}})
        assert request.url.params["interval"] == "1d"
        return httpx.Response(200, json=chart_payload(PRICES[(2026, 10)]))

    with client_for(handler) as client:
        loaded = futures.load(client, [(2026, 8), (2026, 10)])
    assert loaded[(2026, 8)] == {}
    assert loaded[(2026, 10)] == PRICES[(2026, 10)]


def test_a_server_error_is_a_source_error():
    def handler(request):
        return httpx.Response(500)

    with client_for(handler) as client, pytest.raises(SourceError, match="ZQV26"):
        futures.load(client, [(2026, 10)])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_treasury.py tests/test_nyfed.py tests/test_futures.py`

Expected: `28 failed, 34 passed`. The failures are the new cases: the cache index, bounds, `target_row`, malformed rows and the clock-change bars.

- [ ] **Step 3: Replace the three sources**

**File: `macro/sources/treasury.py`**

```python
"""US Treasury daily par yield curve rates, one CSV file per year."""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx

from macro.errors import SourceError

FIRST_YEAR = 1990
YEAR_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
INDEX_NAME = "saved.json"  # for each cached year, the day its file was fetched
YIELD_BOUNDS = (-5.0, 30.0)
_HEADER = re.compile(r"^(\d+(?:\.\d+)?) (Mo|Month|Yr)$")


@dataclass(frozen=True)
class Tenor:
    label: str
    years: float


@dataclass(frozen=True)
class YieldTable:
    """Yields by tenor. Every list in `values` is aligned with `dates`; None means not published."""

    tenors: list[Tenor]
    dates: list[date]
    values: dict[str, list[float | None]]


ParsedYear = tuple[list[Tenor], list[tuple[date, dict[str, float | None]]]]


def parse_tenor(header: str) -> Tenor:
    """Turns a column heading such as "1.5 Month" or "10 Yr" into a tenor."""
    match = _HEADER.match(header.strip())
    if not match:
        raise SourceError(f"Treasury: unknown column {header!r}")
    number, unit = match.group(1), match.group(2)
    if unit == "Yr":
        return Tenor(f"{number}Y", float(number))
    return Tenor(f"{number}M", float(number) / 12)


def parse_year_csv(text: str) -> ParsedYear:
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or header[0].strip() != "Date":
        raise SourceError("Treasury: the file does not start with a Date column")
    tenors = [parse_tenor(name) for name in header[1:]]
    rows: list[tuple[date, dict[str, float | None]]] = []
    for line in reader:
        if not line or not line[0].strip():
            continue
        if len(line) != len(header):
            raise SourceError(f"Treasury: a row has {len(line)} cells where the header has {len(header)}")
        try:
            day = datetime.strptime(line[0].strip(), "%m/%d/%Y").date()
        except ValueError:
            raise SourceError(f"Treasury: bad date {line[0]!r}") from None
        values: dict[str, float | None] = {}
        for tenor, cell in zip(tenors, line[1:]):
            cell = cell.strip()
            if cell in ("", "N/A"):
                values[tenor.label] = None
                continue
            try:
                value = float(cell)
            except ValueError:
                raise SourceError(f"Treasury: bad value {cell!r} on {day}") from None
            if not YIELD_BOUNDS[0] < value < YIELD_BOUNDS[1]:
                raise SourceError(f"Treasury: implausible yield {cell!r} on {day}")
            values[tenor.label] = value
        rows.append((day, values))
    return tenors, rows


def build_table(parsed: list[ParsedYear]) -> YieldTable:
    tenors: dict[str, Tenor] = {}
    by_date: dict[date, dict[str, float | None]] = {}
    for year_tenors, rows in parsed:
        for tenor in year_tenors:
            tenors.setdefault(tenor.label, tenor)
        for day, values in rows:
            by_date[day] = values
    if not by_date:
        raise SourceError("Treasury: no rows")
    ordered = sorted(tenors.values(), key=lambda tenor: tenor.years)
    dates = sorted(by_date)
    values = {tenor.label: [by_date[day].get(tenor.label) for day in dates] for tenor in ordered}
    return YieldTable(ordered, dates, values)


def fetch_year(client: httpx.Client, year: int) -> str:
    try:
        response = client.get(YEAR_URL.format(year=year))
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SourceError(f"Treasury: the {year} download failed: {exc}") from None
    return response.text


def _read_index(cache_dir: Path) -> dict[str, str]:
    try:
        raw = json.loads((cache_dir / INDEX_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(path: Path, text: str) -> None:
    """Writes through a temporary file, so an interrupted write never leaves half a file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _cached_year(cache_dir: Path, index: dict[str, str], year: int) -> ParsedYear | None:
    """A cached year, but only if its file was fetched after that year ended and still parses."""
    saved = index.get(str(year))
    if not isinstance(saved, str) or saved <= f"{year}-12-31":
        return None
    try:
        return parse_year_csv((cache_dir / f"{year}.csv").read_text(encoding="utf-8"))
    except (OSError, SourceError):
        return None


def load(client: httpx.Client, cache_dir: Path, today: date) -> YieldTable:
    """Every year from 1990.

    A year comes from the cache only if its file was fetched after the year ended. The current
    year, and a past year last fetched before it ended, are fetched again.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    index = _read_index(cache_dir)
    parsed: list[ParsedYear] = []
    for year in range(FIRST_YEAR, today.year + 1):
        result = _cached_year(cache_dir, index, year) if year < today.year else None
        if result is None:
            text = fetch_year(client, year)
            if year == today.year and not text.strip():
                result = ([], [])  # the new year's file can be empty until its first trading day
            else:
                result = parse_year_csv(text)  # parse before caching, so a bad file is never cached
            _write(cache_dir / f"{year}.csv", text)
            index[str(year)] = today.isoformat()
            _write(cache_dir / INDEX_NAME, json.dumps(index, indent=0, sort_keys=True) + "\n")
        if not result[1] and year < today.year:
            raise SourceError(f"Treasury: {year} has no rows")
        parsed.append(result)
    return build_table(parsed)
```

**File: `macro/sources/nyfed.py`**

```python
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
```

**File: `macro/sources/futures.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_treasury.py tests/test_nyfed.py tests/test_futures.py`

Expected: `62 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `133 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the seven above. Suggested message: `fix: source parsing bounds, Treasury cache finality, futures bar dates`.

---

### Task 3: The odds, the facts, the build and the command

**Files:**
- Replace: `tests/test_fedwatch.py`, `tests/test_odds.py`, `tests/test_facts.py`, `tests/test_build.py`, `tests/test_cli.py`
- Replace: `macro/fedwatch.py`, `macro/odds.py`, `macro/facts.py`, `macro/build.py`, `macro/cli.py`, `.gitignore`

What changes:

- **`fedwatch.distribution`** takes the list of pending meetings and, optionally, which of them are already decided. A decided meeting counts as its nearest whole number of moves.
- **`build_odds(now, meetings, prices, fed)`** picks the next meeting by statement time. For each pricing date it reads the latest published rate row, counts every meeting from that row's date to the target, and treats a meeting as decided once the prices reflect it. `current_range` is the base range plus the decided moves.
- **`build_dist`** swaps with two renames and raises `BuildError`.
- **The command** prints one line for any failure, and `refresh --debug` shows the full error.

- [ ] **Step 1: Replace the five test files**

**File: `tests/test_fedwatch.py`**

```python
from datetime import date

import pytest

from macro import fedwatch
from samples import MEETING_ENDS, PRICES, effr_rows

RATES = {date.fromisoformat(row["effectiveDate"]): row["percentRate"] for row in effr_rows()}
MEETING_MONTHS = {(day.year, day.month) for day in MEETING_ENDS}
SEPTEMBER, OCTOBER = date(2026, 9, 16), date(2026, 10, 28)


def percent(distribution):
    return {moves: round(100 * share, 1) for moves, share in sorted(distribution.items())}


def has_meeting(month):
    return month in MEETING_MONTHS


def priced(day, pending, prices=PRICES, decided=()):
    return fedwatch.distribution(day, pending, MEETING_ENDS, prices, RATES, decided)


def test_month_average_counts_calendar_days_and_carries_over_weekends():
    assert fedwatch.month_average(RATES, (2026, 8)) == pytest.approx(3.63)


def test_month_average_weights_a_mid_month_change_by_calendar_days():
    # September 2026: 16 days at 3.63, then 14 days at 3.88.
    assert fedwatch.month_average(RATES, (2026, 9)) == pytest.approx((16 * 3.63 + 14 * 3.88) / 30)


def test_month_average_without_any_rate_is_a_missing_price():
    with pytest.raises(fedwatch.MissingPrice):
        fedwatch.month_average({}, (2026, 8))


@pytest.mark.parametrize(
    "moves, expected",
    [
        (0.25, {0: 0.75, 1: 0.25}),
        (1.25, {1: 0.75, 2: 0.25}),
        (-0.25, {-1: 0.25, 0: 0.75}),
        (-1.5, {-2: 0.5, -1: 0.5}),
        (1.0, {1: 1.0}),
        (0.0, {0: 1.0}),
    ],
)
def test_split_shares_a_move_count_between_two_neighbours(moves, expected):
    assert fedwatch.split(moves) == pytest.approx(expected)


def test_combine_adds_move_counts_across_meetings():
    combined = fedwatch.combine({0: 0.5, 1: 0.5}, {0: 0.75, 1: 0.25})
    assert combined == pytest.approx({0: 0.375, 1: 0.5, 2: 0.125})


def test_rule_one_works_back_from_an_anchor_month_after_the_meeting():
    implied = {(2026, 10): 100 - 96.12, (2026, 11): 100 - 96.07}
    moves = fedwatch.expected_moves(OCTOBER, implied.__getitem__, has_meeting)
    assert moves == pytest.approx(0.2214, abs=1e-4)


def test_rule_two_works_forward_from_an_anchor_month_before_the_meeting():
    implied = {(2026, 11): 100 - 96.07, (2026, 12): 100 - 95.925}
    moves = fedwatch.expected_moves(date(2026, 12, 9), implied.__getitem__, has_meeting)
    assert moves == pytest.approx(0.8173, abs=1e-4)


def test_a_meeting_month_with_no_anchor_neighbour_is_an_error():
    with pytest.raises(fedwatch.FedWatchError, match="no anchor"):
        fedwatch.expected_moves(OCTOBER, lambda month: 4.0, lambda month: True)


def test_rule_two_cannot_use_a_meeting_on_the_last_day_of_the_month():
    def only_this_and_next(month):
        return month in {(2026, 10), (2026, 11)}

    with pytest.raises(fedwatch.FedWatchError, match="last day"):
        fedwatch.expected_moves(date(2026, 10, 31), lambda month: 4.0, only_this_and_next)


def test_check_row_2_october():
    assert percent(priced(date(2026, 10, 2), [OCTOBER])) == {0: 77.9, 1: 22.1}


def test_check_row_25_september():
    assert percent(priced(date(2026, 9, 25), [OCTOBER])) == {0: 35.8, 1: 64.2}


def test_check_row_3_september_chains_two_meetings():
    assert percent(priced(date(2026, 9, 3), [SEPTEMBER, OCTOBER])) == {0: 38.8, 1: 48.7, 2: 12.5}


def test_check_row_3_september_with_cmes_september_price():
    prices = {**PRICES, (2026, 9): {date(2026, 9, 3): 96.3125}}
    assert percent(priced(date(2026, 9, 3), [SEPTEMBER, OCTOBER], prices)) == {0: 37.2, 1: 49.7, 2: 13.1}


def test_a_decided_meeting_counts_as_a_whole_move():
    # Priced on 25 September, after the 16 September hike: the September contract implies 0.99 of a move.
    undecided = priced(date(2026, 9, 25), [SEPTEMBER, OCTOBER])
    decided = priced(date(2026, 9, 25), [SEPTEMBER, OCTOBER], decided=[SEPTEMBER])
    assert percent(decided) == {1: 35.8, 2: 64.2}
    assert 0 in undecided and undecided[0] > 0  # without the flag, noise leaks into "no move"


def test_only_the_decided_meetings_gives_the_settled_move_count():
    assert priced(date(2026, 9, 25), [SEPTEMBER], decided=[SEPTEMBER]) == {1: 1.0}


def test_a_missing_contract_price_is_reported():
    prices = {month: days for month, days in PRICES.items() if month != (2026, 11)}
    with pytest.raises(fedwatch.MissingPrice, match="2026, 11"):
        priced(date(2026, 10, 2), [OCTOBER], prices)


def test_no_meeting_to_price_is_an_error():
    with pytest.raises(fedwatch.FedWatchError, match="no meeting"):
        priced(date(2026, 10, 2), [])


def test_a_pending_meeting_in_a_finished_month_is_an_error():
    with pytest.raises(fedwatch.FedWatchError, match="not caught up"):
        priced(date(2026, 10, 2), [SEPTEMBER, OCTOBER])
```

**File: `tests/test_odds.py`**

```python
from datetime import date, datetime, timezone

import pytest

from macro.errors import SourceError
from macro.odds import build_odds, comparison_dates
from macro.sources import nyfed
from samples import MEETINGS, PRICES, effr_payload, effr_rows

FED = nyfed.parse(effr_payload())
NOW = datetime(2026, 10, 3, 18, 15, tzinfo=timezone.utc)


def at(year, month, day, hour=12):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def on(day, source_day, months=(9, 10, 11, 12), **overrides):
    """Prices on `day` for each contract that traded on `source_day`, copied from it unless overridden."""
    prices = {
        (2026, month): {day: PRICES[(2026, month)][source_day]}
        for month in months
        if source_day in PRICES[(2026, month)]
    }
    for month, price in overrides.items():
        prices[(2026, int(month.removeprefix("m")))] = {day: price}
    return prices


def table_until(last):
    """The rate table as published up to `last`."""
    return nyfed.parse(effr_payload(until=last))


def test_comparison_dates_step_back_through_the_price_days():
    assert comparison_dates(sorted(PRICES[(2026, 10)])) == [
        ("now", date(2026, 10, 2)),
        ("d1", date(2026, 10, 1)),
        ("w1", date(2026, 9, 25)),
        ("m1", date(2026, 9, 2)),
    ]


def test_comparison_dates_with_a_single_price_day():
    assert comparison_dates([date(2026, 10, 2)]) == [
        ("now", date(2026, 10, 2)),
        ("d1", None),
        ("w1", None),
        ("m1", None),
    ]


def test_build_odds_matches_the_recorded_figures():
    odds = build_odds(NOW, MEETINGS, PRICES, FED)
    assert odds["meeting"] == "2026-10-28"
    assert odds["priced_on"] == "2026-10-02"
    assert odds["current_range"] == [3.75, 4.0]
    assert odds["columns"] == [
        {"key": "now", "date": "2026-10-02"},
        {"key": "d1", "date": "2026-10-01"},
        {"key": "w1", "date": "2026-09-25"},
        {"key": "m1", "date": "2026-09-02"},
    ]
    assert odds["outcomes"] == [
        {"range": [3.5, 3.75], "now": 0.0, "d1": 0.0, "w1": 0.0, "m1": 27.0},
        {"range": [3.75, 4.0], "now": 77.9, "d1": 75.6, "w1": 35.8, "m1": 55.2},
        {"range": [4.0, 4.25], "now": 22.1, "d1": 24.4, "w1": 64.2, "m1": 17.9},
    ]
    assert odds["summary"] == {"cut": 0.0, "hold": 77.9, "hike": 22.1}


def test_the_day_after_a_move_the_new_range_is_used_even_though_the_rate_table_lags():
    # 17 September: the Fed raised the range the day before, and the New York Fed has not
    # published the row for the 17th yet. Its latest row still carries the old range.
    lagging = nyfed.parse({"refRates": [row for row in effr_rows() if row["effectiveDate"] <= "2026-09-16"]})
    odds = build_odds(at(2026, 9, 17), MEETINGS, on(date(2026, 9, 17), date(2026, 9, 25)), lagging)
    assert odds["current_range"] == [3.75, 4.0]
    assert [(row["range"], row["now"]) for row in odds["outcomes"]] == [([3.75, 4.0], 35.8), ([4.0, 4.25], 64.2)]
    assert odds["summary"] == {"cut": 0.0, "hold": 35.8, "hike": 64.2}


def test_a_comparison_date_on_a_meeting_day_counts_that_meeting_as_decided():
    # The same prices on the meeting day and the day after must land on the same ranges.
    prices = on(date(2026, 9, 17), date(2026, 9, 25))
    for month, days in on(date(2026, 9, 16), date(2026, 9, 25)).items():
        prices[month].update(days)
    odds = build_odds(at(2026, 9, 17), MEETINGS, prices, FED)
    assert [column["date"] for column in odds["columns"][:2]] == ["2026-09-17", "2026-09-16"]
    assert [(row["range"], row["now"], row["d1"]) for row in odds["outcomes"]] == [
        ([3.75, 4.0], 35.8, 35.8),
        ([4.0, 4.25], 64.2, 64.2),
    ]


def test_on_a_meeting_day_before_the_statement_the_odds_are_for_that_meeting():
    fed = table_until(date(2026, 10, 27))
    odds = build_odds(at(2026, 10, 28, hour=10), MEETINGS, on(date(2026, 10, 28), date(2026, 10, 2)), fed)
    assert odds["meeting"] == "2026-10-28"
    assert odds["priced_on"] == "2026-10-28"
    assert odds["summary"] == {"cut": 0.0, "hold": 77.9, "hike": 22.1}


def test_after_the_statement_the_odds_move_to_the_next_meeting_and_count_the_decision():
    # 28 October, an hour after a 25 bp hike. October now averages 28 days at 3.88 and
    # 3 at 4.13; November trades at the new rate.
    fed = table_until(date(2026, 10, 27))
    prices = on(date(2026, 10, 28), date(2026, 10, 2), m10=96.0958, m11=95.87, m12=95.80)
    odds = build_odds(at(2026, 10, 28, hour=19), MEETINGS, prices, fed)
    assert odds["meeting"] == "2026-12-09"
    assert odds["current_range"] == [4.0, 4.25]
    assert [(row["range"], row["now"]) for row in odds["outcomes"]] == [([4.0, 4.25], 60.5), ([4.25, 4.5], 39.5)]
    assert odds["summary"] == {"cut": 0.0, "hold": 60.5, "hike": 39.5}


def test_after_the_statement_prices_from_the_day_before_stop_the_build():
    fed = table_until(date(2026, 10, 27))
    prices = on(date(2026, 10, 27), date(2026, 10, 2))
    with pytest.raises(SourceError, match="not caught up with the 2026-10-28"):
        build_odds(at(2026, 10, 28, hour=19), MEETINGS, prices, fed)


def test_a_priced_cut_lands_below_the_current_range():
    odds = build_odds(NOW, MEETINGS, on(date(2026, 10, 2), date(2026, 10, 2), m10=96.20, m11=96.30), FED)
    assert [(row["range"], row["now"]) for row in odds["outcomes"]] == [([3.5, 3.75], 44.3), ([3.75, 4.0], 55.7)]
    assert odds["summary"] == {"cut": 44.3, "hold": 55.7, "hike": 0.0}


def test_a_move_larger_than_25_bp_spreads_over_the_two_ranges_it_falls_between():
    odds = build_odds(NOW, MEETINGS, on(date(2026, 10, 2), date(2026, 10, 2), m11=95.57), FED)
    assert [(row["range"], row["now"]) for row in odds["outcomes"]] == [([4.25, 4.5], 56.4), ([4.5, 4.75], 43.6)]
    assert odds["summary"] == {"cut": 0.0, "hold": 0.0, "hike": 100.0}


def test_now_falls_back_a_day_when_a_contract_has_no_bar_for_the_latest_day():
    prices = {month: dict(days) for month, days in PRICES.items()}
    del prices[(2026, 11)][date(2026, 10, 2)]
    odds = build_odds(NOW, MEETINGS, prices, FED)
    assert odds["priced_on"] == "2026-10-01"
    assert odds["columns"][0] == {"key": "now", "date": "2026-10-01"}
    assert odds["summary"] == {"cut": 0.0, "hold": 75.6, "hike": 24.4}


def test_a_column_without_prices_is_none_not_an_error():
    prices = {month: days for month, days in PRICES.items() if month != (2026, 9)}
    odds = build_odds(NOW, MEETINGS, prices, FED)
    assert [row["m1"] for row in odds["outcomes"]] == [None, None]
    assert [row["now"] for row in odds["outcomes"]] == [77.9, 22.1]


def test_no_prices_for_the_meeting_month_stops_the_build():
    with pytest.raises(SourceError, match="no futures prices"):
        build_odds(NOW, MEETINGS, {}, FED)


def test_a_missing_price_on_every_recent_day_stops_the_build():
    prices = {month: days for month, days in PRICES.items() if month != (2026, 11)}
    with pytest.raises(SourceError, match="2026, 11"):
        build_odds(NOW, MEETINGS, prices, FED)


def test_a_rate_table_far_behind_the_prices_stops_the_build():
    stale = nyfed.parse({"refRates": [row for row in effr_rows() if row["effectiveDate"] <= "2026-09-16"]})
    with pytest.raises(SourceError, match="stops at 2026-09-16"):
        build_odds(NOW, MEETINGS, PRICES, stale)


def test_no_meeting_ahead_stops_the_build():
    with pytest.raises(SourceError, match="no future meeting"):
        build_odds(at(2027, 6, 1), MEETINGS, PRICES, FED)
```

**File: `tests/test_facts.py`**

```python
from datetime import date

import pytest

from macro.errors import SourceError
from macro.facts import build_facts
from macro.sources import nyfed
from macro.sources.treasury import Tenor, YieldTable
from samples import effr_payload

FED = nyfed.parse(effr_payload())
ODDS = {"meeting": "2026-10-28", "summary": {"cut": 0.0, "hold": 77.9, "hike": 22.1}}
TODAY = date(2026, 10, 3)

TENORS = [Tenor("3M", 0.25), Tenor("2Y", 2.0), Tenor("5Y", 5.0), Tenor("10Y", 10.0), Tenor("30Y", 30.0)]
TABLE = YieldTable(
    tenors=TENORS,
    dates=[date(2025, 10, 2), date(2026, 7, 2), date(2026, 9, 2), date(2026, 9, 25), date(2026, 10, 2)],
    values={
        "3M": [4.00, 3.60, 3.70, 4.10, 4.19],
        "2Y": [3.60, 3.50, 3.90, 4.70, 4.83],
        "5Y": [3.70, 3.75, 4.20, 4.95, 5.06],
        "10Y": [4.10, 4.20, 4.60, 5.15, 5.28],
        "30Y": [None, 4.80, 5.10, 5.55, 5.63],
    },
)


def facts():
    return build_facts(TABLE, FED, ODDS, TODAY)


def test_curves_are_taken_on_five_dates():
    curves = facts()["curves"]
    assert [(curve["label"], curve["date"]) for curve in curves] == [
        ("latest", "2026-10-02"),
        ("1 week earlier", "2026-09-25"),
        ("1 month earlier", "2026-09-02"),
        ("3 months earlier", "2026-07-02"),
        ("1 year earlier", "2025-10-02"),
    ]
    assert curves[0]["yields"]["10Y"] == 5.28


def test_a_tenor_with_no_value_is_left_out_of_that_curve():
    assert "30Y" not in facts()["curves"][4]["yields"]


def test_a_lookback_resolves_to_the_latest_earlier_date():
    table = YieldTable(TENORS, [date(2025, 9, 30), date(2026, 10, 2)], {t.label: [1.0, 2.0] for t in TENORS})
    curves = build_facts(table, FED, ODDS, TODAY)["curves"]
    assert [curve["date"] for curve in curves] == ["2026-10-02"] + ["2025-09-30"] * 4


def test_no_data_before_a_lookback_is_a_source_error():
    table = YieldTable(TENORS, [date(2026, 10, 2)], {t.label: [1.0] for t in TENORS})
    with pytest.raises(SourceError, match="no yield data"):
        build_facts(table, FED, ODDS, TODAY)


def test_spreads_are_in_basis_points():
    assert facts()["spreads_bp"][0] == {
        "label": "latest",
        "date": "2026-10-02",
        "10Y-2Y": 45,
        "10Y-3M": 109,
        "30Y-5Y": 57,
    }


def test_a_spread_with_a_missing_leg_is_none():
    assert facts()["spreads_bp"][4]["30Y-5Y"] is None


def test_changes_run_from_each_earlier_date_to_the_latest():
    week = facts()["changes_bp"][0]
    assert week["label"] == "1 week earlier"
    assert (week["from"], week["to"]) == ("2026-09-25", "2026-10-02")
    assert week["by_tenor"] == {"3M": 9, "2Y": 13, "5Y": 11, "10Y": 13, "30Y": 8}


def test_a_change_skips_tenors_missing_on_the_earlier_date():
    assert "30Y" not in facts()["changes_bp"][3]["by_tenor"]


def test_fed_funds_facts_include_the_last_target_change():
    assert facts()["fed_funds"] == {
        "target_lower": 3.75,
        "target_upper": 4.0,
        "effr": 3.88,
        "effr_date": "2026-10-01",
        "last_change": {"effective": "2026-09-17", "from": [3.5, 3.75], "to": [3.75, 4.0], "change_bp": 25},
    }


def test_the_next_meeting_and_the_odds_are_included():
    result = facts()
    assert result["next_meeting"] == {"date": "2026-10-28", "days_away": 25}
    assert result["odds"] == ODDS
    assert result["as_of"] == "2026-10-02"
```

**File: `tests/test_build.py`**

```python
import hashlib
import json

import pytest

from macro.build import build_dist, write_manifest
from macro.errors import BuildError

SNAPSHOT = {"snapshot_id": "20261003T181500Z", "value": 1}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_writes_the_data_file_manifest_and_checksums(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT
    manifest = json.loads((dist / "manifest.json").read_text())
    assert manifest["snapshot_id"] == "20261003T181500Z"
    assert manifest["files"] == {
        "data.json": {
            "sha256": sha(dist / "data.json"),
            "bytes": (dist / "data.json").stat().st_size,
            "content_type": "application/json",
        }
    }
    assert (dist / "SHA256SUMS").read_text().splitlines() == [
        f"{sha(dist / 'data.json')}  data.json",
        f"{sha(dist / 'manifest.json')}  manifest.json",
    ]


def test_site_files_are_copied_and_listed_but_hidden_files_are_not(tmp_path):
    site = tmp_path / "site"
    (site / "vendor").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html>")
    (site / "vendor" / "lib.js").write_text("// lib")
    (site / ".DS_Store").write_text("finder")
    dist = tmp_path / "dist"
    build_dist(dist, site, SNAPSHOT)
    files = json.loads((dist / "manifest.json").read_text())["files"]
    assert sorted(files) == ["data.json", "index.html", "vendor/lib.js"]
    assert files["index.html"]["content_type"] == "text/html; charset=utf-8"
    assert files["vendor/lib.js"]["content_type"] == "text/javascript; charset=utf-8"
    assert not (dist / ".DS_Store").exists()


def test_a_rebuild_replaces_the_old_dist(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    (dist / "stale.txt").write_text("old")
    build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert not (dist / "stale.txt").exists()
    assert json.loads((dist / "data.json").read_text())["value"] == 2


def test_a_failed_build_leaves_the_old_dist_alone(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    with pytest.raises(BuildError, match="JSON"):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": float("nan")})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_a_swap_that_fails_puts_the_old_dist_back(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    real_rename = type(dist).rename

    def failing_rename(self, target):
        if self.name == "dist.tmp":
            raise OSError("disk full")
        return real_rename(self, target)

    monkeypatch.setattr(type(dist), "rename", failing_rename)
    with pytest.raises(OSError, match="disk full"):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_nothing_is_left_behind_after_a_build(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert sorted(path.name for path in tmp_path.iterdir()) == ["dist"]


def test_a_file_with_an_unknown_type_stops_the_build(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "notes.docx").write_text("x")
    with pytest.raises(BuildError, match="notes.docx"):
        build_dist(tmp_path / "dist", site, SNAPSHOT)


def test_write_manifest_can_be_rerun_after_adding_a_file(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    (dist / "analysis.pdf").write_bytes(b"%PDF-1.4")
    write_manifest(dist, "20261003T181500Z")
    files = json.loads((dist / "manifest.json").read_text())["files"]
    assert sorted(files) == ["analysis.pdf", "data.json"]
    assert files["analysis.pdf"]["content_type"] == "application/pdf"
```

**File: `tests/test_cli.py`**

```python
import json
from datetime import datetime, timezone

import httpx
import pytest

from macro import cli
from macro.errors import SourceError
from samples import PRICES, chart_payload, effr_payload, treasury_csv_for

NOW = datetime(2026, 10, 3, 18, 15, 0, tzinfo=timezone.utc)
SYMBOLS = {"ZQU26.CBT": (2026, 9), "ZQV26.CBT": (2026, 10), "ZQX26.CBT": (2026, 11)}


def handler(request):
    host = request.url.host
    if host == "home.treasury.gov":
        return httpx.Response(200, text=treasury_csv_for(int(request.url.params["field_tdr_date_value"])))
    if host == "markets.newyorkfed.org":
        return httpx.Response(200, json=effr_payload())
    if host == "query1.finance.yahoo.com":
        symbol = request.url.path.rsplit("/", 1)[-1]
        if symbol in SYMBOLS:
            return httpx.Response(200, json=chart_payload(PRICES[SYMBOLS[symbol]]))
        return httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found"}}})
    return httpx.Response(500)


def all_fail(request):
    return httpx.Response(503)


def client_with(transport_handler):
    return httpx.Client(transport=httpx.MockTransport(transport_handler))


@pytest.fixture
def paths(tmp_path):
    calendar = tmp_path / "fomc_meetings.json"
    meetings = ["2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09", "2027-01-27"]
    calendar.write_text(json.dumps({"meetings": meetings}))
    return {
        "dist": tmp_path / "dist",
        "work": tmp_path / "work",
        "cache": tmp_path / "cache",
        "site": tmp_path / "site",
        "calendar_file": calendar,
    }


def run(paths, transport_handler=handler):
    with client_with(transport_handler) as client:
        return cli.refresh(client, NOW, **paths)


def test_refresh_builds_dist_and_the_facts_file(paths):
    run(paths)
    data = json.loads((paths["dist"] / "data.json").read_text())
    assert data["snapshot_id"] == "20261003T181500Z"
    assert data["yields"]["as_of"] == "2026-10-02"
    assert data["fed_funds"]["as_of"] == "2026-10-01"
    assert data["odds"]["summary"] == {"cut": 0.0, "hold": 77.9, "hike": 22.1}
    assert data["fomc"]["meetings"][0]["end"] == "2026-10-28"
    assert (paths["dist"] / "manifest.json").exists()
    facts = json.loads((paths["work"] / "facts.json").read_text())
    assert facts["snapshot_id"] == "20261003T181500Z"
    assert facts["next_meeting"] == {"date": "2026-10-28", "days_away": 25}


def test_summary_lines_name_the_headline_numbers(paths):
    text = "\n".join(cli.summary_lines(run(paths)))
    assert "20261003T181500Z" in text
    assert "10Y 5.28" in text
    assert "current range 3.75-4.00" in text
    assert "hold 77.9" in text
    assert "hike 22.1" in text


def test_a_failing_source_stops_the_refresh_and_leaves_dist_alone(paths):
    run(paths)
    before = (paths["dist"] / "data.json").read_bytes()

    def broken(request):
        if request.url.host == "markets.newyorkfed.org":
            return httpx.Response(503)
        return handler(request)

    with pytest.raises(SourceError, match="New York Fed"):
        run(paths, broken)
    assert (paths["dist"] / "data.json").read_bytes() == before


def test_a_calendar_with_no_future_meeting_stops_the_refresh(paths):
    paths["calendar_file"].write_text(json.dumps({"meetings": ["2026-09-16"]}))
    with pytest.raises(SourceError, match="no future meeting"):
        run(paths)


def test_a_short_calendar_is_flagged_in_the_summary(paths):
    paths["calendar_file"].write_text(json.dumps({"meetings": ["2026-07-29", "2026-09-16", "2026-10-28"]}))
    lines = cli.summary_lines(run(paths))
    assert any("fomc_meetings.json" in line for line in lines)


def test_main_reports_a_source_error_and_returns_1(paths, monkeypatch, capsys):
    monkeypatch.setattr(cli, "make_client", lambda: client_with(all_fail))
    monkeypatch.setattr(cli, "default_paths", lambda: paths)
    monkeypatch.setattr(cli, "utc_now", lambda: NOW)
    assert cli.main(["refresh"]) == 1
    err = capsys.readouterr().err
    assert "Refresh stopped" in err
    assert "dist/ was not changed" in err


def test_main_prints_the_summary_and_returns_0(paths, monkeypatch, capsys):
    monkeypatch.setattr(cli, "make_client", lambda: client_with(handler))
    monkeypatch.setattr(cli, "default_paths", lambda: paths)
    monkeypatch.setattr(cli, "utc_now", lambda: NOW)
    assert cli.main(["refresh"]) == 0
    assert "hold 77.9" in capsys.readouterr().out


def patch_main(monkeypatch, paths, transport_handler=handler):
    monkeypatch.setattr(cli, "make_client", lambda: client_with(transport_handler))
    monkeypatch.setattr(cli, "default_paths", lambda: paths)
    monkeypatch.setattr(cli, "utc_now", lambda: NOW)


def test_a_problem_found_after_fetching_is_reported_plainly_and_leaves_dist_alone(paths, monkeypatch, capsys):
    run(paths)
    before = (paths["dist"] / "data.json").read_bytes()
    paths["site"].mkdir()
    (paths["site"] / "notes.docx").write_text("a file type the server does not serve")
    patch_main(monkeypatch, paths)
    assert cli.main(["refresh"]) == 1
    assert "no content type for notes.docx" in capsys.readouterr().err
    assert (paths["dist"] / "data.json").read_bytes() == before


def test_an_unexpected_error_is_reported_in_one_line(paths, monkeypatch, capsys):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    patch_main(monkeypatch, paths)
    monkeypatch.setattr(cli, "refresh", explode)
    assert cli.main(["refresh"]) == 1
    err = capsys.readouterr().err
    assert "unexpected error: RuntimeError: boom" in err
    assert "--debug" in err
    assert "Traceback" not in err


def test_debug_lets_the_full_error_through(paths, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    patch_main(monkeypatch, paths)
    monkeypatch.setattr(cli, "refresh", explode)
    with pytest.raises(RuntimeError, match="boom"):
        cli.main(["refresh", "--debug"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_fedwatch.py tests/test_odds.py tests/test_facts.py tests/test_build.py tests/test_cli.py`

Expected: `30 failed, 37 passed`

- [ ] **Step 3: Replace the five modules and `.gitignore`**

**File: `macro/fedwatch.py`**

```python
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
```

**File: `macro/odds.py`**

```python
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
```

**File: `macro/facts.py`**

```python
"""The numbers handed to the analysis writer and printed in the PDF. Pure functions."""
from __future__ import annotations

from datetime import date, timedelta

from macro.dates import months_back, on_or_before
from macro.errors import SourceError
from macro.sources.nyfed import FedFundsTable
from macro.sources.treasury import YieldTable

SPREADS = [("10Y-2Y", "10Y", "2Y"), ("10Y-3M", "10Y", "3M"), ("30Y-5Y", "30Y", "5Y")]


def basis_points(later: float | None, earlier: float | None) -> int | None:
    if later is None or earlier is None:
        return None
    return round((later - earlier) * 100)


def curves_on_lookback_dates(yields: YieldTable) -> list[dict]:
    """The curve on the latest date and one week, one month, three months and one year earlier."""
    latest = yields.dates[-1]
    wanted = [
        ("latest", latest),
        ("1 week earlier", latest - timedelta(days=7)),
        ("1 month earlier", months_back(latest, 1)),
        ("3 months earlier", months_back(latest, 3)),
        ("1 year earlier", months_back(latest, 12)),
    ]
    curves = []
    for label, target in wanted:
        day = on_or_before(yields.dates, target)
        if day is None:
            raise SourceError(f"facts: no yield data on or before {target}")
        index = yields.dates.index(day)
        points = {
            tenor.label: yields.values[tenor.label][index]
            for tenor in yields.tenors
            if yields.values[tenor.label][index] is not None
        }
        curves.append({"label": label, "date": day.isoformat(), "yields": points})
    return curves


def last_target_change(fed: FedFundsTable) -> dict | None:
    """The latest change in the published target: its first day in force, the ranges and the size."""
    current = (fed.target_lower[-1], fed.target_upper[-1])
    for index in range(len(fed.dates) - 1, 0, -1):
        before = (fed.target_lower[index - 1], fed.target_upper[index - 1])
        if before != current:
            return {
                "effective": fed.dates[index].isoformat(),
                "from": list(before),
                "to": list(current),
                "change_bp": basis_points(current[0], before[0]),
            }
    return None


def build_facts(yields: YieldTable, fed: FedFundsTable, odds: dict, today: date) -> dict:
    curves = curves_on_lookback_dates(yields)
    newest = curves[0]
    spreads = [
        {
            "label": curve["label"],
            "date": curve["date"],
            **{
                name: basis_points(curve["yields"].get(long_leg), curve["yields"].get(short_leg))
                for name, long_leg, short_leg in SPREADS
            },
        }
        for curve in curves
    ]
    changes = [
        {
            "label": curve["label"],
            "from": curve["date"],
            "to": newest["date"],
            "by_tenor": {
                tenor: basis_points(value, curve["yields"][tenor])
                for tenor, value in newest["yields"].items()
                if tenor in curve["yields"]
            },
        }
        for curve in curves[1:]
    ]
    meeting = date.fromisoformat(odds["meeting"])
    return {
        "as_of": newest["date"],
        "curves": curves,
        "spreads_bp": spreads,
        "changes_bp": changes,
        "fed_funds": {
            "target_lower": fed.target_lower[-1],
            "target_upper": fed.target_upper[-1],
            "effr": fed.effr[-1],
            "effr_date": fed.dates[-1].isoformat(),
            "last_change": last_target_change(fed),
        },
        "odds": odds,
        "next_meeting": {"date": meeting.isoformat(), "days_away": (meeting - today).days},
    }
```

**File: `macro/build.py`**

```python
"""Writes dist/: the page files, data.json, and a manifest and checksum list of everything in it."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from macro.errors import BuildError

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
}
INTERNAL = ("manifest.json", "SHA256SUMS")


def write_manifest(dist: Path, snapshot_id: str) -> None:
    """Lists every file the server may serve. Rerun it after adding a file to dist/."""
    files: dict[str, dict] = {}
    for path in sorted(item for item in dist.rglob("*") if item.is_file()):
        name = path.relative_to(dist).as_posix()
        if name in INTERNAL:
            continue
        content_type = CONTENT_TYPES.get(path.suffix.lower())
        if content_type is None:
            raise BuildError(f"build: no content type for {name}")
        data = path.read_bytes()
        files[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "content_type": content_type,
        }
    manifest = dist / "manifest.json"
    manifest.write_text(json.dumps({"snapshot_id": snapshot_id, "files": files}, indent=2) + "\n", encoding="utf-8")
    lines = [f"{meta['sha256']}  {name}\n" for name, meta in files.items()]
    lines.append(f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}  manifest.json\n")
    (dist / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def build_dist(dist: Path, site: Path, snapshot: dict) -> None:
    """Builds in a temporary folder and swaps it in, so a failure leaves the old dist/ in place."""
    staging = dist.with_name(dist.name + ".tmp")
    previous = dist.with_name(dist.name + ".old")
    for leftover in (staging, previous):
        if leftover.exists():
            shutil.rmtree(leftover)
    if site.is_dir():
        shutil.copytree(site, staging, ignore=shutil.ignore_patterns(".*"))
    else:
        staging.mkdir(parents=True)
    try:
        data = json.dumps(snapshot, separators=(",", ":"), allow_nan=False)
    except ValueError as exc:
        raise BuildError(f"build: the data cannot be written as JSON: {exc}") from None
    (staging / "data.json").write_text(data, encoding="utf-8")
    write_manifest(staging, snapshot["snapshot_id"])

    # Two renames, so dist/ is never missing for longer than the gap between them.
    if dist.exists():
        dist.rename(previous)
    try:
        staging.rename(dist)
    except OSError:
        if previous.exists():
            previous.rename(dist)
        raise
    if previous.exists():
        shutil.rmtree(previous)
```

**File: `macro/cli.py`**

```python
"""The command line: python -m macro <command>."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from macro import config
from macro.build import build_dist
from macro.dates import add_months
from macro.errors import MacroError, SourceError
from macro.facts import build_facts
from macro.fedwatch import FedWatchError
from macro.odds import build_odds
from macro.snapshot import build_snapshot
from macro.sources import fomc, futures, nyfed, treasury

CONTRACT_SHIFTS = (-2, -1, 0, 1)  # months around the meeting month whose contracts are fetched


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.HTTP_TIMEOUT,
        follow_redirects=True,
    )


def default_paths() -> dict[str, Path]:
    return {
        "dist": config.DIST_DIR,
        "work": config.WORK_DIR,
        "cache": config.CACHE_DIR,
        "site": config.SITE_DIR,
        "calendar_file": config.DATA_DIR / "fomc_meetings.json",
    }


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def refresh(
    client: httpx.Client,
    now: datetime,
    *,
    dist: Path,
    work: Path,
    cache: Path,
    site: Path,
    calendar_file: Path,
) -> dict:
    """Fetches every source, calculates, and only then replaces dist/."""
    today = now.date()
    meetings = fomc.load(calendar_file)
    ahead = fomc.upcoming(meetings, now)
    if not ahead:
        raise SourceError("FOMC calendar: no future meeting. Update data/fomc_meetings.json")
    target = ahead[0].end

    yields = treasury.load(client, cache / "treasury", today)
    fed = nyfed.load(client, today)
    target_month = (target.year, target.month)
    prices = futures.load(client, [add_months(target_month, shift) for shift in CONTRACT_SHIFTS])
    try:
        odds = build_odds(now, meetings, prices, fed)
    except FedWatchError as exc:
        raise SourceError(f"odds: {exc}") from None

    snapshot = build_snapshot(now, yields, fed, meetings, odds)
    facts = {"snapshot_id": snapshot["snapshot_id"], **build_facts(yields, fed, odds, today)}
    build_dist(dist, site, snapshot)
    work.mkdir(parents=True, exist_ok=True)
    (work / "facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    return {"snapshot": snapshot, "facts": facts, "future_meetings": len(ahead)}


def summary_lines(result: dict) -> list[str]:
    snapshot, facts = result["snapshot"], result["facts"]
    latest, fed, odds = facts["curves"][0], facts["fed_funds"], snapshot["odds"]
    shown = ", ".join(
        f"{tenor} {latest['yields'][tenor]:.2f}" for tenor in ("3M", "2Y", "10Y", "30Y") if tenor in latest["yields"]
    )
    summary = odds["summary"]
    low, high = odds["current_range"]
    lines = [
        f"Snapshot {snapshot['snapshot_id']}",
        f"Yields as of {latest['date']}: {shown}",
        f"Fed funds as of {fed['effr_date']}: EFFR {fed['effr']:.2f}, "
        f"published target {fed['target_lower']:.2f}-{fed['target_upper']:.2f}",
        f"Odds for {odds['meeting']} (priced {odds['priced_on']}, current range {low:.2f}-{high:.2f}): "
        f"cut {summary['cut']}, hold {summary['hold']}, hike {summary['hike']}",
        "Built dist/ (no analysis yet) and work/facts.json",
    ]
    if result["future_meetings"] < 2:
        lines.append("Warning: fewer than two future meetings are listed. Update data/fomc_meetings.json")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m macro", description="Builds the macros page.")
    commands = parser.add_subparsers(dest="command", required=True)
    refresh_parser = commands.add_parser("refresh", help="fetch the data, calculate, and build dist/")
    refresh_parser.add_argument("--debug", action="store_true", help="show the full error instead of a one-line message")
    args = parser.parse_args(argv)

    if args.command == "refresh":
        try:
            with make_client() as client:
                result = refresh(client, utc_now(), **default_paths())
        except MacroError as exc:
            if args.debug:
                raise
            print(f"Refresh stopped: {exc}", file=sys.stderr)
            print("dist/ was not changed.", file=sys.stderr)
            return 1
        except Exception as exc:  # a bug or an unforeseen reply: say so plainly
            if args.debug:
                raise
            print(f"Refresh stopped by an unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("Run it again with --debug to see the full error.", file=sys.stderr)
            return 1
        print("\n".join(summary_lines(result)))
        return 0
    return 2
```

**File: `.gitignore`**

```text
.env
.venv/
dist/
dist.tmp/
dist.old/
work/
.cache/
__pycache__/
.pytest_cache/
.DS_Store
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_fedwatch.py tests/test_odds.py tests/test_facts.py tests/test_build.py tests/test_cli.py`

Expected: `67 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `150 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the eleven above. Suggested message: `fix: odds around rate changes, safe dist swap, plain failure messages`.

---

### Task 4: Real refresh with the fixed code

This task runs the command against the real sources. It adds no code. The cache now needs its index, so this first run fetches every Treasury year again: about 42 read-only requests.

- [ ] **Step 1: Run the refresh**

Run: `.venv/bin/python -m macro refresh`

Expected: five lines in this shape, with current values.

```text
Snapshot 20261004T093000Z
Yields as of 2026-10-02: 3M 4.19, 2Y 4.83, 10Y 5.28, 30Y 5.63
Fed funds as of 2026-10-01: EFFR 3.88, published target 3.75-4.00
Odds for 2026-10-28 (priced 2026-10-02, current range 3.75-4.00): cut 0.0, hold 77.9, hike 22.1
Built dist/ (no analysis yet) and work/facts.json
```

- [ ] **Step 2: Confirm the cache index and a fast second run**

Run:

```bash
ls .cache/treasury | wc -l
.venv/bin/python -m macro refresh
```

Expected: 38 files (37 years and `saved.json`), and a second run that finishes in a few seconds.

- [ ] **Step 3: Checkpoint**

Stop and report the printed summary. Nothing new to commit: `dist/`, `work/` and `.cache/` are git-ignored.
