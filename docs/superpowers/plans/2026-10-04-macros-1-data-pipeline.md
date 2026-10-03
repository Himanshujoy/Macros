# Macros Page, Plan 1: Data Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python -m macro refresh` fetches Treasury yields, the Fed funds rate and Fed funds futures prices, calculates the rate odds and the analysis facts, and writes `dist/data.json` and `work/facts.json`.

**Architecture:** Each data source is a small module that fetches with an injected `httpx.Client` and parses into plain data. The odds calculation and the facts are pure functions with no input or output. A build step writes `dist/` through a temporary folder, so a failed refresh never replaces a good one.

**Tech Stack:** Python 3.14 on the Mac, with all code kept compatible with Python 3.12. httpx 0.28.1, pytest 9.1.1. No other dependencies.

**Spec:** `docs/superpowers/specs/2026-10-04-macros-page-design.md`. This plan covers sections 6.1 to 6.4, the facts part of 6.5, and the `refresh` command of 7.1.

---

## Roadmap

The spec is delivered as four plans. Each ends in something that runs and can be checked.

| Plan | Delivers | Touches |
|---|---|---|
| 1. Data pipeline (this file) | `python -m macro refresh` writes `dist/data.json` and `work/facts.json` | Mac only |
| 2. Server and page | `python -m macro preview` shows the interactive page locally | Mac only |
| 3. Analysis PDF | `python -m macro analysis` turns an analysis file into the PDF; the button works | Mac only |
| 4. Publish and rollout | `publish`, `rollback`, the box install and the tunnel and DNS steps | Box and Cloudflare, each step gated on the owner's go |

Plans 2 to 4 are written when the plan before them is done.

## Rules for whoever executes this plan

- **Never run `git add`, `commit`, `push`, `stash`, `reset`, `checkout` or `restore`.** The owner makes every commit. Each task ends with a checkpoint that names the files to commit and suggests a message. Stop there and report.
- **Tests never touch a real service.** HTTP goes through `httpx.MockTransport`. A guard in `tests/conftest.py` fails any test that opens a connection outside localhost.
- **Nothing in this plan touches the box or Cloudflare.** Do not run `ssh`.
- Run every command from the project root, `/Users/himanshusrivastava/Projects/Macros`.
- Use the project's interpreter: `.venv/bin/python`. It is built from the Mac's python.org Python 3.14. Do not use `/opt/homebrew/bin/python3.12`: on this Mac it cannot load its XML module, so pip fails under it.
- Keep the code compatible with Python 3.12. Use nothing added in 3.13 or 3.14.
- Each file below is shown in full. Create it exactly as shown.

## File structure

| File | Responsibility |
|---|---|
| `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore` | Project setup |
| `macro/config.py` | Paths and fixed settings |
| `macro/errors.py` | `SourceError`, raised when a source fails or returns something unexpected |
| `macro/dates.py` | Two date helpers shared by the odds and the facts |
| `macro/sources/treasury.py` | Treasury yield curve: fetch, parse, cache past years |
| `macro/sources/nyfed.py` | EFFR and target range |
| `macro/sources/fomc.py` | FOMC meeting list and statement times |
| `macro/sources/futures.py` | Fed funds futures closing prices |
| `macro/fedwatch.py` | The odds calculation, pure functions |
| `macro/odds.py` | Builds the odds block of `data.json` |
| `macro/facts.py` | The numbers given to the analysis writer |
| `macro/snapshot.py` | Assembles the `data.json` content |
| `macro/build.py` | Writes `dist/` with its manifest and checksums |
| `macro/cli.py`, `macro/__main__.py` | The `refresh` command |
| `data/fomc_meetings.json` | The meeting dates |
| `tests/conftest.py` | The network guard |
| `tests/samples.py` | Real sample data recorded on 2026-10-03, shared by the tests |
| `tests/test_*.py` | One test module per source module |

---

### Task 1: Project setup and the network guard

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`
- Create: `macro/__init__.py`, `macro/sources/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_network_guard.py`

- [ ] **Step 1: Create the setup files**

**File: `pyproject.toml`**

```toml
[project]
name = "macro"
version = "0.1.0"
description = "Builds the macros.theta-markets.com page"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [".", "tests"]
addopts = "-q"
```

**File: `requirements.txt`**

```text
httpx==0.28.1
```

**File: `requirements-dev.txt`**

```text
-r requirements.txt
pytest==9.1.1
```

**File: `.gitignore`**

```text
.env
.venv/
dist/
dist.tmp/
work/
.cache/
__pycache__/
.pytest_cache/
```

**File: `macro/__init__.py`**

```python
"""Builds the macros.theta-markets.com page."""
```

**File: `macro/sources/__init__.py`**

```python
"""One module per data source."""
```

- [ ] **Step 2: Create the virtual environment and install**

Run:

```bash
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -V
```

Expected: the last line prints `Python 3.14.` followed by a patch number.

- [ ] **Step 3: Write the failing test**

**File: `tests/test_network_guard.py`**

```python
import socket

import pytest


def test_the_guard_blocks_connections_outside_localhost():
    with socket.socket() as sock, pytest.raises(RuntimeError, match="network"):
        sock.settimeout(0.5)
        sock.connect(("192.0.2.1", 80))  # TEST-NET-1: a reserved address that is never a real host


def test_the_guard_allows_localhost():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.socket() as client:
            client.connect(server.getsockname())
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_network_guard.py`

Expected: `test_the_guard_blocks_connections_outside_localhost` FAILS, because nothing blocks the connection yet. It fails with a timeout or a connection error where the guard's `RuntimeError` should be.

- [ ] **Step 5: Write the guard**

**File: `tests/conftest.py`**

```python
"""Shared test setup. The guard makes a forgotten mock fail loudly instead of calling a real service."""
import socket

import pytest

_real_connect = socket.socket.connect
_LOCAL = ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def guarded(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL:
            raise RuntimeError(f"test tried to open a network connection to {host!r}")
        return _real_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_network_guard.py`

Expected: `2 passed`

- [ ] **Step 7: Checkpoint**

Stop and report. Do not run git. Files for the owner to commit: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `macro/__init__.py`, `macro/sources/__init__.py`, `tests/conftest.py`, `tests/test_network_guard.py`. Suggested message: `chore: project setup and test network guard`.

---

### Task 2: Shared settings, the error type and date helpers

**Files:**
- Create: `macro/config.py`, `macro/errors.py`, `macro/dates.py`
- Test: `tests/test_dates.py`

- [ ] **Step 1: Write the failing test**

**File: `tests/test_dates.py`**

```python
from datetime import date

from macro.dates import months_back, on_or_before


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

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dates.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'macro.dates'`

- [ ] **Step 3: Write the three modules**

**File: `macro/config.py`**

```python
"""Paths and fixed settings for the Mac-side commands."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
WORK_DIR = ROOT / "work"
CACHE_DIR = ROOT / ".cache"
SITE_DIR = ROOT / "site"
DATA_DIR = ROOT / "data"

USER_AGENT = "macros-page/1.0 (personal dashboard)"
HTTP_TIMEOUT = 30.0
```

**File: `macro/errors.py`**

```python
"""Errors the commands report to the owner in plain words."""


class SourceError(Exception):
    """A data source failed or returned something unexpected."""
```

**File: `macro/dates.py`**

```python
"""Date helpers shared by the odds and the facts."""
from __future__ import annotations

import calendar
from bisect import bisect_right
from datetime import date


def months_back(day: date, count: int) -> date:
    """The same day `count` months earlier, clamped to the end of a shorter month."""
    index = day.year * 12 + (day.month - 1) - count
    year, month = index // 12, index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def on_or_before(days: list[date], limit: date) -> date | None:
    """The latest day in a sorted list that is not after `limit`."""
    index = bisect_right(days, limit) - 1
    return days[index] if index >= 0 else None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dates.py`

Expected: `4 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `macro/config.py`, `macro/errors.py`, `macro/dates.py`, `tests/test_dates.py`. Suggested message: `feat: settings, error type and date helpers`.

---

### Task 3: Sample data and the Treasury source

**Files:**
- Create: `tests/samples.py`
- Create: `macro/sources/treasury.py`
- Test: `tests/test_treasury.py`

The Treasury publishes one CSV per year, newest row first. Older years have fewer tenors, and a tenor introduced mid-year leaves blank cells before its first day.

- [ ] **Step 1: Create the shared sample data**

These are real values recorded on 2026-10-03. Later tasks use the futures and EFFR samples too.

**File: `tests/samples.py`**

```python
"""Real sample data, recorded on 2026-10-03, shared by several test modules."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

CSV_2026 = """Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
10/02/2026,4.04,4.09,4.11,4.19,4.26,4.27,4.46,4.83,4.96,5.06,5.17,5.28,5.67,5.63
10/01/2026,4.06,4.10,4.13,4.17,4.26,4.27,4.44,4.78,4.91,5.01,5.12,5.24,5.64,5.61
09/30/2026,4.02,4.13,4.16,4.20,4.29,4.33,4.54,4.88,5.00,5.09,5.19,5.29,5.68,5.64"""

CSV_2025_GAP = """Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
02/18/2025,4.38,4.41,4.38,4.34,4.37,4.34,4.24,4.29,4.33,4.40,4.48,4.55,4.83,4.77
02/14/2025,4.37,,4.38,4.34,4.35,4.32,4.23,4.26,4.26,4.33,4.41,4.47,4.75,4.69"""

CSV_1990 = """Date,"3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","30 Yr"
12/31/1990,6.63,6.73,6.82,7.15,7.40,7.68,8.00,8.08,8.26"""


def treasury_csv_for(year: int) -> str:
    """A small yearly file: the real 2026 sample, or two made-up rows for any other year."""
    if year == 2026:
        return CSV_2026
    header = 'Date,"3 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","30 Yr"'
    return (
        f"{header}\n"
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

HOLIDAYS = {date(2026, 9, 7)}  # Labor Day: no rate was published


def effr_rows() -> list[dict]:
    """EFFR as published from 27 July to 1 October 2026, newest first, as the API returns it."""
    rows = []
    day = date(2026, 7, 27)
    while day <= date(2026, 10, 1):
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


def effr_payload() -> dict:
    """The recent rows plus two from December 2008, when the target became a range."""
    old = [
        {"effectiveDate": "2008-12-16", "type": "EFFR", "percentRate": 0.17, "targetRateFrom": 0.0, "targetRateTo": 0.25},
        {"effectiveDate": "2008-12-15", "type": "EFFR", "percentRate": 0.18, "targetRateFrom": 1.0},
    ]
    return {"refRates": effr_rows() + old}


def chart_payload(prices: dict[date, float]) -> dict:
    """The shape of Yahoo's chart reply. Each timestamp is midnight in New York."""
    offset = -14400
    days = sorted(prices)
    stamps = [int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()) - offset for d in days]
    return {
        "chart": {
            "result": [
                {
                    "meta": {"gmtoffset": offset},
                    "timestamp": stamps,
                    "indicators": {"quote": [{"close": [prices[d] for d in days]}]},
                }
            ],
            "error": None,
        }
    }
```

- [ ] **Step 2: Write the failing test**

**File: `tests/test_treasury.py`**

```python
from datetime import date

import httpx
import pytest

from macro.errors import SourceError
from macro.sources import treasury
from samples import CSV_1990, CSV_2025_GAP, CSV_2026, treasury_csv_for


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


def test_build_table_merges_years_oldest_first_and_fills_gaps():
    table = treasury.build_table([treasury.parse_year_csv(CSV_2026), treasury.parse_year_csv(CSV_1990)])
    assert table.dates[0] == date(1990, 12, 31)
    assert table.dates[-1] == date(2026, 10, 2)
    assert [t.label for t in table.tenors][:3] == ["1M", "1.5M", "2M"]
    assert table.values["1M"][0] is None
    assert table.values["10Y"] == [8.08, 5.29, 5.24, 5.28]


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def year_of(request):
    return int(request.url.params["field_tdr_date_value"])


def test_load_caches_past_years_and_refetches_the_current_year(tmp_path):
    seen = []

    def handler(request):
        seen.append(year_of(request))
        return httpx.Response(200, text=treasury_csv_for(year_of(request)))

    with make_client(handler) as client:
        treasury.load(client, tmp_path, date(2026, 10, 3))
        assert seen == list(range(1990, 2027))
        seen.clear()
        table = treasury.load(client, tmp_path, date(2026, 10, 3))
    assert seen == [2026]
    assert table.dates[-1] == date(2026, 10, 2)


def test_load_refetches_the_previous_year_in_january(tmp_path):
    seen = []

    def handler(request):
        seen.append(year_of(request))
        return httpx.Response(200, text=treasury_csv_for(year_of(request)))

    with make_client(handler) as client:
        treasury.load(client, tmp_path, date(2026, 10, 3))
        seen.clear()
        treasury.load(client, tmp_path, date(2027, 1, 5))
    assert seen == [2026, 2027]


def test_a_bad_download_stops_the_load_and_is_not_cached(tmp_path):
    def handler(request):
        return httpx.Response(200, text="<html>Access denied</html>")

    with make_client(handler) as client, pytest.raises(SourceError):
        treasury.load(client, tmp_path, date(2026, 10, 3))
    assert list(tmp_path.iterdir()) == []


def test_a_failed_request_is_reported_as_a_source_error(tmp_path):
    def handler(request):
        return httpx.Response(503)

    with make_client(handler) as client, pytest.raises(SourceError, match="1990"):
        treasury.load(client, tmp_path, date(2026, 10, 3))
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_treasury.py`

Expected: FAIL with `ImportError: cannot import name 'treasury' from 'macro.sources'`

- [ ] **Step 4: Write the implementation**

**File: `macro/sources/treasury.py`**

```python
"""US Treasury daily par yield curve rates, one CSV file per year."""
from __future__ import annotations

import csv
import io
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
                values[tenor.label] = float(cell)
            except ValueError:
                raise SourceError(f"Treasury: bad value {cell!r} on {day}") from None
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


def load(client: httpx.Client, cache_dir: Path, today: date) -> YieldTable:
    """Every year from 1990. Past years come from the cache; the current year is always fetched."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    fresh = {today.year, today.year - 1} if today.month == 1 else {today.year}
    parsed: list[ParsedYear] = []
    for year in range(FIRST_YEAR, today.year + 1):
        path = cache_dir / f"{year}.csv"
        if year in fresh or not path.exists():
            text = fetch_year(client, year)
            result = parse_year_csv(text)  # parse before caching, so a bad file is never cached
            path.write_text(text, encoding="utf-8")
        else:
            result = parse_year_csv(path.read_text(encoding="utf-8"))
        if not result[1] and year < today.year:
            raise SourceError(f"Treasury: {year} has no rows")
        parsed.append(result)
    return build_table(parsed)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_treasury.py`

Expected: `11 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/samples.py`, `tests/test_treasury.py`, `macro/sources/treasury.py`. Suggested message: `feat: Treasury yield curve source`.

---

### Task 4: The New York Fed source

**Files:**
- Create: `macro/sources/nyfed.py`
- Test: `tests/test_nyfed.py`

The API returns rows newest first. Before 16 December 2008 a row carries a single target in `targetRateFrom` and no `targetRateTo`.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_nyfed.py`**

```python
from datetime import date

import httpx
import pytest

from macro.errors import SourceError
from macro.sources import nyfed
from samples import effr_payload


def test_parse_orders_rows_oldest_first():
    table = nyfed.parse(effr_payload())
    assert table.dates[0] == date(2008, 12, 15)
    assert table.dates[-1] == date(2026, 10, 1)
    assert table.effr[-1] == 3.88


def test_a_single_target_fills_both_bounds():
    table = nyfed.parse(effr_payload())
    assert (table.target_lower[0], table.target_upper[0]) == (1.0, 1.0)
    assert (table.target_lower[1], table.target_upper[1]) == (0.0, 0.25)


def test_target_on_returns_the_range_in_force():
    table = nyfed.parse(effr_payload())
    assert table.target_on(date(2026, 9, 16)) == (3.5, 3.75)
    assert table.target_on(date(2026, 9, 17)) == (3.75, 4.0)
    assert table.target_on(date(2026, 9, 20)) == (3.75, 4.0)  # a Sunday


def test_target_on_before_the_data_is_an_error():
    table = nyfed.parse(effr_payload())
    with pytest.raises(SourceError):
        table.target_on(date(2000, 1, 1))


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

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_nyfed.py`

Expected: FAIL with `ImportError: cannot import name 'nyfed' from 'macro.sources'`

- [ ] **Step 3: Write the implementation**

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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_nyfed.py`

Expected: `12 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `macro/sources/nyfed.py`, `tests/test_nyfed.py`. Suggested message: `feat: New York Fed EFFR and target range source`.

---

### Task 5: The FOMC calendar

**Files:**
- Create: `data/fomc_meetings.json`
- Create: `macro/sources/fomc.py`
- Test: `tests/test_fomc.py`

The list holds the last day of each meeting. The statement is taken as 2:00 p.m. in New York on that day.

- [ ] **Step 1: Create the calendar file**

**File: `data/fomc_meetings.json`**

```json
{
  "source": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
  "checked": "2026-10-03",
  "note": "The last day of each scheduled meeting. The Fed marks future dates as tentative.",
  "meetings": [
    "2026-01-28",
    "2026-03-18",
    "2026-04-29",
    "2026-06-17",
    "2026-07-29",
    "2026-09-16",
    "2026-10-28",
    "2026-12-09",
    "2027-01-27",
    "2027-03-17",
    "2027-04-28",
    "2027-06-09",
    "2027-07-28",
    "2027-09-15",
    "2027-10-27",
    "2027-12-08",
    "2028-01-26"
  ]
}
```

- [ ] **Step 2: Write the failing test**

**File: `tests/test_fomc.py`**

```python
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from macro.errors import SourceError
from macro.sources import fomc

CALENDAR = Path(__file__).parent.parent / "data" / "fomc_meetings.json"


def test_the_shipped_calendar_loads_in_order():
    ends = [meeting.end for meeting in fomc.load(CALENDAR)]
    assert ends == sorted(ends)
    assert date(2026, 10, 28) in ends
    assert date(2027, 12, 8) in ends


def test_statement_time_is_two_pm_new_york_in_utc():
    daylight = fomc.Meeting(date(2026, 10, 28)).statement_at
    standard = fomc.Meeting(date(2026, 12, 9)).statement_at
    assert daylight == datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    assert standard == datetime(2026, 12, 9, 19, 0, tzinfo=timezone.utc)


def test_upcoming_keeps_meetings_whose_statement_is_still_ahead():
    meetings = [fomc.Meeting(date(2026, 9, 16)), fomc.Meeting(date(2026, 10, 28)), fomc.Meeting(date(2026, 12, 9))]
    just_before = datetime(2026, 10, 28, 17, 59, tzinfo=timezone.utc)
    at_the_statement = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    assert [m.end for m in fomc.upcoming(meetings, just_before)] == [date(2026, 10, 28), date(2026, 12, 9)]
    assert [m.end for m in fomc.upcoming(meetings, at_the_statement)] == [date(2026, 12, 9)]


def test_two_meetings_in_one_month_are_rejected(tmp_path):
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps({"meetings": ["2026-10-07", "2026-10-28"]}))
    with pytest.raises(SourceError, match="one month"):
        fomc.load(path)


@pytest.mark.parametrize("text", ["not json", "{}", '{"meetings": ["28 Oct"]}'])
def test_a_broken_calendar_file_is_a_source_error(tmp_path, text):
    path = tmp_path / "calendar.json"
    path.write_text(text)
    with pytest.raises(SourceError):
        fomc.load(path)


def test_a_missing_calendar_file_is_a_source_error(tmp_path):
    with pytest.raises(SourceError):
        fomc.load(tmp_path / "absent.json")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_fomc.py`

Expected: FAIL with `ImportError: cannot import name 'fomc' from 'macro.sources'`

- [ ] **Step 4: Write the implementation**

**File: `macro/sources/fomc.py`**

```python
"""FOMC meeting dates, from the fixed list in data/fomc_meetings.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from macro.errors import SourceError

NEW_YORK = ZoneInfo("America/New_York")
STATEMENT_TIME = time(14, 0)


@dataclass(frozen=True, order=True)
class Meeting:
    end: date

    @property
    def statement_at(self) -> datetime:
        """The scheduled statement: 2:00 p.m. in New York on the last day, given in UTC."""
        local = datetime.combine(self.end, STATEMENT_TIME, tzinfo=NEW_YORK)
        return local.astimezone(timezone.utc)


def load(path: Path) -> list[Meeting]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        days = [date.fromisoformat(text) for text in raw["meetings"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SourceError(f"FOMC calendar: cannot read {path.name}: {exc}") from None
    if len({(day.year, day.month) for day in days}) != len(days):
        raise SourceError("FOMC calendar: two meetings in one month")
    return sorted(Meeting(day) for day in days)


def upcoming(meetings: list[Meeting], now: datetime) -> list[Meeting]:
    """Meetings whose statement is still ahead of `now`."""
    return [meeting for meeting in meetings if meeting.statement_at > now]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_fomc.py`

Expected: `8 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `data/fomc_meetings.json`, `macro/sources/fomc.py`, `tests/test_fomc.py`. Suggested message: `feat: FOMC calendar`.

---

### Task 6: The futures price source

**Files:**
- Create: `macro/sources/futures.py`
- Test: `tests/test_futures.py`

Contracts are monthly. The symbol is `ZQ`, a month code, a two-digit year and `.CBT`. Yahoo answers 404 for a contract it no longer lists; that is not an error here.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_futures.py`**

```python
from datetime import date

import httpx
import pytest

from macro.errors import SourceError
from macro.sources import futures
from samples import PRICES, chart_payload


def test_symbols_use_the_exchange_month_codes():
    assert futures.symbol((2026, 10)) == "ZQV26.CBT"
    assert futures.symbol((2026, 11)) == "ZQX26.CBT"
    assert futures.symbol((2027, 1)) == "ZQF27.CBT"


def test_parse_chart_dates_prices_in_exchange_time():
    assert futures.parse_chart(chart_payload(PRICES[(2026, 10)])) == PRICES[(2026, 10)]


def test_parse_chart_skips_days_without_a_close():
    payload = chart_payload({date(2026, 10, 1): 96.115, date(2026, 10, 2): 96.12})
    payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][0] = None
    assert futures.parse_chart(payload) == {date(2026, 10, 2): 96.12}


def test_parse_chart_rounds_float_noise():
    payload = chart_payload({date(2026, 10, 2): 96.12000274658203})
    assert futures.parse_chart(payload) == {date(2026, 10, 2): 96.12}


@pytest.mark.parametrize(
    "payload",
    [{}, {"chart": {"result": None, "error": {"code": "Not Found"}}}, {"chart": {"result": [{}]}}],
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

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_futures.py`

Expected: FAIL with `ImportError: cannot import name 'futures' from 'macro.sources'`

- [ ] **Step 3: Write the implementation**

**File: `macro/sources/futures.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_futures.py`

Expected: `9 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `macro/sources/futures.py`, `tests/test_futures.py`. Suggested message: `feat: Fed funds futures price source`.

---

### Task 7: The odds calculation

**Files:**
- Create: `macro/fedwatch.py`
- Test: `tests/test_fedwatch.py`

This is section 6.4 of the spec. Read it before starting. In short:

- A month's implied rate is `100 - price`. For a month that ended before the pricing date, it is the calendar-day average of EFFR.
- A month with no meeting is an anchor: one rate all month.
- For a meeting month with `N` days whose meeting ends on day `M`: if the next month is an anchor, `end = I(next)` and `start = (I * N - end * (N - M)) / M`. Otherwise, if the previous month is an anchor, `start = I(previous)` and `end = (I * N - start * M) / (N - M)`.
- The expected number of 25 bp moves is `(end - start) / 0.25`, split between its two neighbouring whole numbers.
- Several pending meetings combine by convolution.

The four "check row" tests reproduce the figures in the spec's check table.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_fedwatch.py`**

```python
from datetime import date

import pytest

from macro import fedwatch
from samples import MEETING_ENDS, PRICES, effr_rows

RATES = {date.fromisoformat(row["effectiveDate"]): row["percentRate"] for row in effr_rows()}
MEETING_MONTHS = {(day.year, day.month) for day in MEETING_ENDS}
TARGET = date(2026, 10, 28)


def percent(distribution):
    return {moves: round(100 * share, 1) for moves, share in sorted(distribution.items())}


def has_meeting(month):
    return month in MEETING_MONTHS


def test_add_months_crosses_year_boundaries():
    assert fedwatch.add_months((2026, 12), 1) == (2027, 1)
    assert fedwatch.add_months((2027, 1), -1) == (2026, 12)
    assert fedwatch.add_months((2026, 10), -2) == (2026, 8)


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
    moves = fedwatch.expected_moves(date(2026, 10, 28), implied.__getitem__, has_meeting)
    assert moves == pytest.approx(0.2214, abs=1e-4)


def test_rule_two_works_forward_from_an_anchor_month_before_the_meeting():
    implied = {(2026, 11): 100 - 96.07, (2026, 12): 100 - 95.925}
    moves = fedwatch.expected_moves(date(2026, 12, 9), implied.__getitem__, has_meeting)
    assert moves == pytest.approx(0.8173, abs=1e-4)


def test_a_meeting_month_with_no_anchor_neighbour_is_an_error():
    with pytest.raises(fedwatch.FedWatchError, match="no anchor"):
        fedwatch.expected_moves(date(2026, 10, 28), lambda month: 4.0, lambda month: True)


def test_rule_two_cannot_use_a_meeting_on_the_last_day_of_the_month():
    def only_this_and_next(month):
        return month in {(2026, 10), (2026, 11)}

    with pytest.raises(fedwatch.FedWatchError, match="last day"):
        fedwatch.expected_moves(date(2026, 10, 31), lambda month: 4.0, only_this_and_next)


def test_check_row_2_october():
    result = fedwatch.distribution(date(2026, 10, 2), TARGET, MEETING_ENDS, PRICES, RATES)
    assert percent(result) == {0: 77.9, 1: 22.1}


def test_check_row_25_september():
    result = fedwatch.distribution(date(2026, 9, 25), TARGET, MEETING_ENDS, PRICES, RATES)
    assert percent(result) == {0: 35.8, 1: 64.2}


def test_check_row_3_september_chains_two_meetings():
    result = fedwatch.distribution(date(2026, 9, 3), TARGET, MEETING_ENDS, PRICES, RATES)
    assert percent(result) == {0: 38.8, 1: 48.7, 2: 12.5}


def test_check_row_3_september_with_cmes_september_price():
    prices = {**PRICES, (2026, 9): {date(2026, 9, 3): 96.3125}}
    result = fedwatch.distribution(date(2026, 9, 3), TARGET, MEETING_ENDS, prices, RATES)
    assert percent(result) == {0: 37.2, 1: 49.7, 2: 13.1}


def test_a_missing_contract_price_is_reported():
    prices = {month: days for month, days in PRICES.items() if month != (2026, 11)}
    with pytest.raises(fedwatch.MissingPrice, match="2026, 11"):
        fedwatch.distribution(date(2026, 10, 2), TARGET, MEETING_ENDS, prices, RATES)


def test_no_pending_meeting_is_an_error():
    with pytest.raises(fedwatch.FedWatchError, match="no meeting"):
        fedwatch.distribution(TARGET, TARGET, MEETING_ENDS, PRICES, RATES)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_fedwatch.py`

Expected: FAIL with `ImportError: cannot import name 'fedwatch' from 'macro'`

- [ ] **Step 3: Write the implementation**

**File: `macro/fedwatch.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_fedwatch.py`

Expected: `21 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `macro/fedwatch.py`, `tests/test_fedwatch.py`. Suggested message: `feat: rate-odds calculation`.

---

### Task 8: The odds block

**Files:**
- Create: `macro/odds.py`
- Test: `tests/test_odds.py`

This turns the calculation into the `odds` part of `data.json`: four comparison columns, one row per target range, and a cut, hold and hike summary. A comparison column with no price data is `None`. A missing price for "now" stops the build.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_odds.py`**

```python
from datetime import date

import pytest

from macro.errors import SourceError
from macro.odds import build_odds, comparison_dates
from macro.sources import nyfed
from samples import MEETING_ENDS, PRICES, effr_payload

FED = nyfed.parse(effr_payload())
TARGET = date(2026, 10, 28)


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
    odds = build_odds(TARGET, MEETING_ENDS, PRICES, FED)
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


def test_a_column_without_prices_is_none_not_an_error():
    prices = {month: days for month, days in PRICES.items() if month != (2026, 9)}
    odds = build_odds(TARGET, MEETING_ENDS, prices, FED)
    assert [row["m1"] for row in odds["outcomes"]] == [None, None]
    assert [row["now"] for row in odds["outcomes"]] == [77.9, 22.1]


def test_no_prices_for_the_meeting_month_stops_the_build():
    with pytest.raises(SourceError, match="no futures prices"):
        build_odds(TARGET, MEETING_ENDS, {}, FED)


def test_a_missing_price_for_now_stops_the_build():
    prices = {month: days for month, days in PRICES.items() if month != (2026, 11)}
    with pytest.raises(SourceError, match="2026, 11"):
        build_odds(TARGET, MEETING_ENDS, prices, FED)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_odds.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'macro.odds'`

- [ ] **Step 3: Write the implementation**

**File: `macro/odds.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_odds.py`

Expected: `6 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `macro/odds.py`, `tests/test_odds.py`. Suggested message: `feat: odds block for data.json`.

---

### Task 9: The analysis facts

**Files:**
- Create: `macro/facts.py`
- Test: `tests/test_facts.py`

These are the numbers the analysis writer receives and the PDF prints (spec section 6.5). The writer explains them and never calculates.

- [ ] **Step 1: Write the failing test**

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
        "last_change": {"date": "2026-09-17", "from": [3.5, 3.75], "to": [3.75, 4.0]},
    }


def test_the_next_meeting_and_the_odds_are_included():
    result = facts()
    assert result["next_meeting"] == {"date": "2026-10-28", "days_away": 25}
    assert result["odds"] == ODDS
    assert result["as_of"] == "2026-10-02"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_facts.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'macro.facts'`

- [ ] **Step 3: Write the implementation**

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
    """The first day of the current target, with the range before and after."""
    current = (fed.target_lower[-1], fed.target_upper[-1])
    for index in range(len(fed.dates) - 1, 0, -1):
        before = (fed.target_lower[index - 1], fed.target_upper[index - 1])
        if before != current:
            return {"date": fed.dates[index].isoformat(), "from": list(before), "to": list(current)}
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

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_facts.py`

Expected: `10 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `macro/facts.py`, `tests/test_facts.py`. Suggested message: `feat: analysis facts`.

---

### Task 10: The snapshot and the build

**Files:**
- Create: `macro/snapshot.py`, `macro/build.py`
- Test: `tests/test_snapshot.py`, `tests/test_build.py`

`snapshot.py` assembles the content of `data.json` (spec section 6.3). `build.py` writes `dist/` through a temporary folder and lists every file in `manifest.json` and `SHA256SUMS`. Plan 2 adds the page files under `site/`; the build already copies that folder when it exists.

- [ ] **Step 1: Write the failing tests**

**File: `tests/test_snapshot.py`**

```python
from datetime import date, datetime, timezone

from macro.snapshot import build_snapshot, snapshot_id
from macro.sources import nyfed
from macro.sources.fomc import Meeting
from macro.sources.treasury import Tenor, YieldTable
from samples import effr_payload

NOW = datetime(2026, 10, 3, 18, 15, 0, tzinfo=timezone.utc)
FED = nyfed.parse(effr_payload())
TABLE = YieldTable(
    tenors=[Tenor("3M", 0.25), Tenor("10Y", 10.0)],
    dates=[date(2026, 10, 1), date(2026, 10, 2)],
    values={"3M": [4.17, 4.19], "10Y": [5.24, None]},
)
MEETINGS = [Meeting(date(2026, 9, 16)), Meeting(date(2026, 10, 28)), Meeting(date(2026, 12, 9))]
ODDS = {"meeting": "2026-10-28"}


def snapshot():
    return build_snapshot(NOW, TABLE, FED, MEETINGS, ODDS)


def test_snapshot_id_is_the_utc_build_time():
    assert snapshot_id(NOW) == "20261003T181500Z"


def test_snapshot_carries_identity_and_no_analysis_yet():
    result = snapshot()
    assert result["snapshot_id"] == "20261003T181500Z"
    assert result["build_id"] == "20261003T181500Z"
    assert result["generated_at"] == "2026-10-03T18:15:00Z"
    assert result["analysis"] is None
    assert result["odds"] == ODDS


def test_yields_are_one_array_per_tenor_aligned_with_dates():
    assert snapshot()["yields"] == {
        "as_of": "2026-10-02",
        "tenors": [{"label": "3M", "years": 0.25}, {"label": "10Y", "years": 10.0}],
        "dates": ["2026-10-01", "2026-10-02"],
        "values": [[4.17, 4.19], [5.24, None]],
    }


def test_fed_funds_arrays_are_aligned():
    fed = snapshot()["fed_funds"]
    assert fed["as_of"] == "2026-10-01"
    assert len(fed["dates"]) == len(fed["effr"]) == len(fed["target_lower"]) == len(fed["target_upper"])
    assert fed["dates"][0] == "2008-12-15"
    assert (fed["target_lower"][0], fed["target_upper"][0]) == (1.0, 1.0)


def test_only_future_meetings_are_listed():
    assert snapshot()["fomc"]["meetings"] == [
        {"end": "2026-10-28", "statement_at": "2026-10-28T18:00:00Z"},
        {"end": "2026-12-09", "statement_at": "2026-12-09T19:00:00Z"},
    ]
```

**File: `tests/test_build.py`**

```python
import hashlib
import json

import pytest

from macro.build import build_dist, write_manifest

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
    with pytest.raises(ValueError):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": float("nan")})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_a_file_with_an_unknown_type_stops_the_build(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "notes.docx").write_text("x")
    with pytest.raises(ValueError, match="notes.docx"):
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

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py tests/test_build.py`

Expected: both modules FAIL to import, with `ModuleNotFoundError: No module named 'macro.snapshot'` and `No module named 'macro.build'`

- [ ] **Step 3: Write the implementations**

**File: `macro/snapshot.py`**

```python
"""Assembles the content of data.json, the one file the page reads."""
from __future__ import annotations

from datetime import datetime

from macro.sources.fomc import Meeting, upcoming
from macro.sources.nyfed import FedFundsTable
from macro.sources.treasury import YieldTable

STAMP = "%Y-%m-%dT%H:%M:%SZ"


def snapshot_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def build_snapshot(
    now: datetime,
    yields: YieldTable,
    fed: FedFundsTable,
    meetings: list[Meeting],
    odds: dict,
) -> dict:
    identity = snapshot_id(now)
    return {
        "snapshot_id": identity,
        "build_id": identity,
        "generated_at": now.strftime(STAMP),
        "yields": {
            "as_of": yields.dates[-1].isoformat(),
            "tenors": [{"label": tenor.label, "years": round(tenor.years, 4)} for tenor in yields.tenors],
            "dates": [day.isoformat() for day in yields.dates],
            "values": [yields.values[tenor.label] for tenor in yields.tenors],
        },
        "fed_funds": {
            "as_of": fed.dates[-1].isoformat(),
            "dates": [day.isoformat() for day in fed.dates],
            "effr": fed.effr,
            "target_lower": fed.target_lower,
            "target_upper": fed.target_upper,
        },
        "fomc": {
            "meetings": [
                {"end": meeting.end.isoformat(), "statement_at": meeting.statement_at.strftime(STAMP)}
                for meeting in upcoming(meetings, now)
            ]
        },
        "odds": odds,
        "analysis": None,
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
            raise ValueError(f"build: no content type for {name}")
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
    """Builds in a temporary folder and swaps it in, so a failure leaves the old dist/ alone."""
    staging = dist.with_name(dist.name + ".tmp")
    if staging.exists():
        shutil.rmtree(staging)
    if site.is_dir():
        shutil.copytree(site, staging, ignore=shutil.ignore_patterns(".*"))
    else:
        staging.mkdir(parents=True)
    data = json.dumps(snapshot, separators=(",", ":"), allow_nan=False)
    (staging / "data.json").write_text(data, encoding="utf-8")
    write_manifest(staging, snapshot["snapshot_id"])
    if dist.exists():
        shutil.rmtree(dist)
    staging.rename(dist)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py tests/test_build.py`

Expected: `11 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `macro/snapshot.py`, `macro/build.py`, `tests/test_snapshot.py`, `tests/test_build.py`. Suggested message: `feat: snapshot assembly and dist build`.

---

### Task 11: The refresh command

**Files:**
- Create: `macro/cli.py`, `macro/__main__.py`
- Test: `tests/test_cli.py`

`refresh` fetches every source and calculates everything before it touches `dist/`. Any `SourceError` stops it with a plain message and exit code 1, and `dist/` stays as it was.

Futures contracts are fetched for the meeting month, the two months before it and the month after. That covers both rules of the calculation and a one-month comparison that reaches back across an earlier meeting.

- [ ] **Step 1: Write the failing test**

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py`

Expected: FAIL with `ImportError: cannot import name 'cli' from 'macro'`

- [ ] **Step 3: Write the implementation**

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
from macro.errors import SourceError
from macro.facts import build_facts
from macro.fedwatch import FedWatchError, add_months
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
    ends = [meeting.end for meeting in meetings]
    future = [end for end in ends if end > today]
    if not future:
        raise SourceError("FOMC calendar: no future meeting. Update data/fomc_meetings.json")
    target = future[0]

    yields = treasury.load(client, cache / "treasury", today)
    fed = nyfed.load(client, today)
    target_month = (target.year, target.month)
    prices = futures.load(client, [add_months(target_month, shift) for shift in CONTRACT_SHIFTS])
    try:
        odds = build_odds(target, ends, prices, fed)
    except FedWatchError as exc:
        raise SourceError(f"odds: {exc}") from None

    snapshot = build_snapshot(now, yields, fed, meetings, odds)
    facts = {"snapshot_id": snapshot["snapshot_id"], **build_facts(yields, fed, odds, today)}
    build_dist(dist, site, snapshot)
    work.mkdir(parents=True, exist_ok=True)
    (work / "facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    return {"snapshot": snapshot, "facts": facts, "future_meetings": len(future)}


def summary_lines(result: dict) -> list[str]:
    snapshot, facts = result["snapshot"], result["facts"]
    latest, fed, odds = facts["curves"][0], facts["fed_funds"], snapshot["odds"]
    shown = ", ".join(
        f"{tenor} {latest['yields'][tenor]:.2f}" for tenor in ("3M", "2Y", "10Y", "30Y") if tenor in latest["yields"]
    )
    summary = odds["summary"]
    lines = [
        f"Snapshot {snapshot['snapshot_id']}",
        f"Yields as of {latest['date']}: {shown}",
        f"Fed funds as of {fed['effr_date']}: EFFR {fed['effr']:.2f}, "
        f"target {fed['target_lower']:.2f}-{fed['target_upper']:.2f}",
        f"Odds for {odds['meeting']} (priced {odds['priced_on']}): "
        f"cut {summary['cut']}, hold {summary['hold']}, hike {summary['hike']}",
        "Built dist/ (no analysis yet) and work/facts.json",
    ]
    if result["future_meetings"] < 2:
        lines.append("Warning: fewer than two future meetings are listed. Update data/fomc_meetings.json")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m macro", description="Builds the macros page.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("refresh", help="fetch the data, calculate, and build dist/")
    args = parser.parse_args(argv)

    if args.command == "refresh":
        try:
            with make_client() as client:
                result = refresh(client, utc_now(), **default_paths())
        except SourceError as exc:
            print(f"Refresh stopped: {exc}", file=sys.stderr)
            print("dist/ was not changed.", file=sys.stderr)
            return 1
        print("\n".join(summary_lines(result)))
        return 0
    return 2
```

**File: `macro/__main__.py`**

```python
import sys

from macro.cli import main

sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli.py`

Expected: `7 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: every test passes, with no failures and no errors.

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `macro/cli.py`, `macro/__main__.py`, `tests/test_cli.py`. Suggested message: `feat: refresh command`.

---

### Task 12: First real refresh

This task runs the command against the real sources. It is not a test and adds no code. It makes about 42 read-only requests: one Treasury file per year since 1990, one to the New York Fed and four to Yahoo. Later runs fetch only the current Treasury year.

- [ ] **Step 1: Run the refresh**

Run: `.venv/bin/python -m macro refresh`

Expected: five lines in this shape, with current values.

```text
Snapshot 20261004T093000Z
Yields as of 2026-10-02: 3M 4.19, 2Y 4.83, 10Y 5.28, 30Y 5.63
Fed funds as of 2026-10-01: EFFR 3.88, target 3.75-4.00
Odds for 2026-10-28 (priced 2026-10-02): cut 0.0, hold 77.9, hike 22.1
Built dist/ (no analysis yet) and work/facts.json
```

If it prints `Refresh stopped:` instead, report the message and stop. Do not work around a failing source.

- [ ] **Step 2: Check the output files**

Run:

```bash
ls -la dist work
.venv/bin/python -c "
import json
d = json.load(open('dist/data.json'))
print('dates:', len(d['yields']['dates']), d['yields']['dates'][0], '->', d['yields']['dates'][-1])
print('tenors:', [t['label'] for t in d['yields']['tenors']])
print('fed funds rows:', len(d['fed_funds']['dates']), d['fed_funds']['dates'][0])
print('odds rows:', d['odds']['outcomes'])
print('next meetings:', [m['end'] for m in d['fomc']['meetings']][:3])
"
```

Expected:

- `dist/` holds `data.json`, `manifest.json` and `SHA256SUMS`. `work/` holds `facts.json`.
- About 9,200 dates, starting `1990-01-02`.
- Fourteen tenors, from `1M` to `30Y`.
- Fed funds rows starting `2000-07-03`.
- One odds row per target range, each with `now`, `d1`, `w1` and `m1`.

- [ ] **Step 3: Run it again to confirm the cache**

Run: `.venv/bin/python -m macro refresh`

Expected: the same five lines with a new snapshot id, and it finishes in a few seconds because past years come from `.cache/`.

- [ ] **Step 4: Checkpoint**

Stop and report the printed summary to the owner so they can compare it with FRED, the New York Fed page and CME FedWatch. Nothing new to commit: `dist/`, `work/` and `.cache/` are git-ignored.
