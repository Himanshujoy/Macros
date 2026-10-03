# Macros Page, Plan 2a: Server and Preview

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python -m macro preview` serves the built `dist/` folder on this Mac with the same web server the box will run, and the remaining review findings in the data pipeline are fixed.

**Architecture:** `server/serve.py` is one standard-library file. It serves only the files a release's manifest lists, from a folder or a link to one, and reads the manifest again whenever it changes. The same file runs on the box under systemd and on the Mac for preview. A placeholder page proves the data file loads; Plan 2b replaces it with the charts.

**Tech Stack:** Python 3.14 on the Mac, with all code kept compatible with Python 3.12 (a static check puts the minimum at 3.11). httpx 0.28.1, pytest 9.1.1. The server imports nothing outside the standard library.

**Spec:** `docs/superpowers/specs/2026-10-04-macros-page-design.md`, sections 7.1 (`preview`) and 8.2 (the server). The unit file, the box install and publishing are Plan 4.

**Supersedes:** for every file listed below, the content in the two earlier plans.

---

## Roadmap

| Plan | Delivers | Status |
|---|---|---|
| 1 and 1b. Data pipeline | `python -m macro refresh` | Done |
| 2a. Server and preview (this file) | `python -m macro preview`, serving a placeholder page | This plan |
| 2b. The page | The charts, sliders, odds and countdown | Next |
| 3. Analysis PDF | `python -m macro analysis` | Later |
| 4. Publish and rollout | `publish`, `rollback`, the box install, tunnel and DNS | Later, each step gated on the owner's go |

## Rules for whoever executes this plan

- **Never run `git add`, `commit`, `push`, `stash`, `reset`, `checkout` or `restore`.** The owner makes every commit. Each task ends with a checkpoint. Stop there and report.
- **Tests never touch a real service.** They talk only to a server on localhost. Do not run `python -m macro refresh` or `python -m macro preview` unless a step says so.
- **Nothing in this plan touches the box or Cloudflare.** Do not run `ssh`.
- Run every command from the project root, `/Users/himanshusrivastava/Projects/Macros`, with `.venv/bin/python`.
- Each file below is shown in full. It **replaces** an existing file of the same path, or creates it. Copy it exactly.
- Keep the code compatible with Python 3.12. `server/serve.py` must import nothing outside the standard library.

## File structure

| File | Responsibility |
|---|---|
| `server/serve.py` | The web server: which files may be served, how each request is answered, the self-test, the command line |
| `server/__init__.py` | Makes `server` importable for preview and tests |
| `tests/test_serve.py` | The server's tests, against a live server on a free localhost port |
| `macro/build.py` | Now also writes the build id into the page and recovers from an interrupted swap |
| `macro/cli.py` | Now also has the `preview` command |
| `site/index.html`, `site/app.js`, `site/style.css` | A placeholder page, replaced in Plan 2b |
| `site/robots.txt` | Tells search engines to stay away |
| `macro/sources/*.py`, `macro/fedwatch.py`, `macro/odds.py` | Follow-up fixes from the re-review |

---

### Task 1: Follow-up fixes from the re-review

**Files:**
- Replace: `tests/test_treasury.py`, `tests/test_fedwatch.py`, `tests/test_odds.py`, `tests/test_futures.py`, `tests/test_nyfed.py`
- Replace: `macro/sources/treasury.py`, `macro/fedwatch.py`, `macro/odds.py`, `macro/sources/futures.py`, `macro/sources/nyfed.py`

The re-review confirmed the Plan 1b fixes and found these:

| Finding | Fix |
|---|---|
| Right after a statement, the day's price bar can still hold pre-statement prices, and the code turned them into a certain decision | The build waits 30 minutes after a statement. A decided meeting whose prices are not within a quarter of a move of a whole number is treated as "no price yet" |
| An empty Treasury file for the current year was accepted on any date, so the page could silently fall back to last December | A file with no rows is accepted only for the current year in the first seven days of January. Nothing without rows is cached |
| A past year with a header and no rows was cached and blocked later runs | The row check now comes before the cache write |
| A year fetched in the first days of January could miss its last row for good | A year is final only once fetched on or after 8 January of the next year |
| A decided meeting in a finished month stopped the build even when an earlier price day would work | That case is now "no price yet", so "now" falls back a day and a comparison column goes blank |
| An absurd timestamp raised `OverflowError`; a bad New York Fed row was reported without its date | Both are plain `SourceError`s; the row error names the date and cause |

- [ ] **Step 1: Replace the five test files**

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


def test_an_empty_file_for_the_current_year_later_in_the_year_is_an_error_and_keeps_the_cache(tmp_path):
    site = Recorder()
    site.load(tmp_path, date(2026, 10, 3))
    emptied = Recorder(lambda year: "" if year == 2026 else treasury_csv_for(year))
    with pytest.raises(SourceError, match="2026 file is empty"):
        emptied.load(tmp_path, date(2026, 10, 4))
    assert (tmp_path / "2026.csv").read_text() == CSV_2026


def test_a_header_with_no_rows_is_accepted_only_in_the_first_week_of_january(tmp_path):
    site = Recorder(lambda year: OLD_HEADER if year == 2027 else treasury_csv_for(year))
    assert site.load(tmp_path, date(2027, 1, 7)).dates[-1] == date(2026, 10, 2)
    with pytest.raises(SourceError, match="2027 has no rows"):
        site.load(tmp_path, date(2027, 1, 8))


def test_a_past_year_with_no_rows_is_not_cached_so_the_next_run_asks_again(tmp_path):
    site = Recorder(lambda year: OLD_HEADER if year == 1997 else treasury_csv_for(year))
    with pytest.raises(SourceError, match="1997 has no rows"):
        site.load(tmp_path, date(2026, 10, 3))
    assert not (tmp_path / "1997.csv").exists()
    with pytest.raises(SourceError, match="1997 has no rows"):
        site.load(tmp_path, date(2026, 10, 3))
    assert site.seen == [1997]


def test_a_year_is_final_only_once_fetched_on_or_after_8_january(tmp_path):
    site = Recorder()
    site.load(tmp_path, date(2027, 1, 3))  # the Treasury may not have posted 31 December yet
    site.load(tmp_path, date(2027, 1, 7))
    assert site.seen == [2026, 2027]
    site.load(tmp_path, date(2027, 1, 8))
    assert site.seen == [2026, 2027]
    site.load(tmp_path, date(2027, 1, 9))  # 2026 was saved on the 8th, so now it is final
    assert site.seen == [2027]
```

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


def test_a_decided_meeting_without_a_clear_outcome_in_the_prices_is_a_missing_price():
    # Priced on 3 September the market gave 0.47 of a move: nowhere near a decision.
    with pytest.raises(fedwatch.MissingPrice, match="clear outcome"):
        priced(date(2026, 9, 3), [SEPTEMBER, OCTOBER], decided=[SEPTEMBER])
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


def test_just_after_a_statement_the_build_waits_for_prices_to_settle():
    fed = table_until(date(2026, 10, 27))
    prices = on(date(2026, 10, 28), date(2026, 10, 2))
    just_after = datetime(2026, 10, 28, 18, 5, tzinfo=timezone.utc)
    with pytest.raises(SourceError, match="Refresh after 18:30 UTC"):
        build_odds(just_after, MEETINGS, prices, fed)


def test_prices_that_do_not_show_a_clear_decision_stop_the_build():
    # An hour after the statement the only bar still holds the morning's prices: 0.22 of a move
    # would round to "no change", but 0.45 is not a decision at all.
    fed = table_until(date(2026, 10, 27))
    prices = on(date(2026, 10, 28), date(2026, 10, 2), m11=96.0143)
    with pytest.raises(SourceError, match="clear outcome"):
        build_odds(at(2026, 10, 28, hour=19), MEETINGS, prices, fed)


def test_a_decided_cut_lowers_the_current_range():
    # 28 October, an hour after a 25 bp cut: October averages 28 days at 3.88 and 3 at 3.63.
    fed = table_until(date(2026, 10, 27))
    prices = on(date(2026, 10, 28), date(2026, 10, 2), m10=96.1442, m11=96.37, m12=96.40)
    odds = build_odds(at(2026, 10, 28, hour=19), MEETINGS, prices, fed)
    assert odds["current_range"] == [3.5, 3.75]
    assert [(row["range"], row["now"]) for row in odds["outcomes"]] == [([3.25, 3.5], 16.9), ([3.5, 3.75], 83.1)]
    assert odds["summary"] == {"cut": 16.9, "hold": 83.1, "hike": 0.0}
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


def test_an_absurd_timestamp_is_a_source_error():
    payload = chart_payload({date(2026, 10, 2): 96.12})
    payload["chart"]["result"][0]["timestamp"] = [10**20]
    with pytest.raises(SourceError):
        futures.parse_chart(payload)
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


def test_a_malformed_row_is_named_by_its_date_and_cause():
    with pytest.raises(SourceError, match="dated 2026-10-01: ValueError"):
        nyfed.parse({"refRates": [{**GOOD, "percentRate": "n/a"}]})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_treasury.py tests/test_fedwatch.py tests/test_odds.py tests/test_futures.py tests/test_nyfed.py`

Expected: `9 failed, 102 passed`. The failures are the new cases.

- [ ] **Step 3: Replace the five modules**

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
FINAL_FROM = "-01-08"  # a past year is final once fetched on or after 8 January of the next year
NEW_YEAR_GRACE_DAYS = 7  # how far into January the new year's file may still have no rows
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
    """A cached year, but only if its file was fetched once the year was over and still has rows.

    The Treasury can post a year's last rows a few days late, so "over" means 8 January.
    """
    saved = index.get(str(year))
    if not isinstance(saved, str) or saved < f"{year + 1}{FINAL_FROM}":
        return None
    try:
        result = parse_year_csv((cache_dir / f"{year}.csv").read_text(encoding="utf-8"))
    except (OSError, SourceError):
        return None
    return result if result[1] else None


def load(client: httpx.Client, cache_dir: Path, today: date) -> YieldTable:
    """Every year from 1990.

    A year comes from the cache only if its file was fetched once that year was over. The
    current year, and a past year last fetched before then, are fetched again. A file with
    no rows is never cached, except the new year's file in the first days of January.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    index = _read_index(cache_dir)
    parsed: list[ParsedYear] = []
    for year in range(FIRST_YEAR, today.year + 1):
        result = _cached_year(cache_dir, index, year) if year < today.year else None
        if result is None:
            text = fetch_year(client, year)
            new_year = year == today.year and today.month == 1 and today.day <= NEW_YEAR_GRACE_DAYS
            if not text.strip():
                if not new_year:
                    raise SourceError(f"Treasury: the {year} file is empty")
                result = ([], [])  # the new year's file can be empty until its first trading day
            else:
                result = parse_year_csv(text)
            if not result[1] and not new_year:
                raise SourceError(f"Treasury: {year} has no rows")
            # Only a file that parsed and has rows gets this far, so a bad one is never cached.
            _write(cache_dir / f"{year}.csv", text)
            index[str(year)] = today.isoformat()
            _write(cache_dir / INDEX_NAME, json.dumps(index, indent=0, sort_keys=True) + "\n")
        parsed.append(result)
    return build_table(parsed)
```

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
DECIDED_TOLERANCE = 0.25  # a decided meeting's implied moves must be this close to a whole number


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
    its nearest whole number of moves, with certainty. If the prices are not within a quarter
    of a move of a whole number, they do not reflect the outcome yet, and that is reported as
    a missing price. `meeting_ends` is the whole calendar,
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
            raise MissingPrice(f"the rate table has not caught up with the {meeting_end} meeting")
        moves = expected_moves(meeting_end, implied, lambda month: month in meeting_months)
        if meeting_end in decided:
            if abs(moves - round(moves)) > DECIDED_TOLERANCE:
                raise MissingPrice(f"prices on {pricing_date} do not show a clear outcome for the {meeting_end} meeting")
            shares = {round(moves): 1.0}
        else:
            shares = split(moves)
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
SETTLE_MINUTES = 30  # after a statement, quotes need this long to show the outcome


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
            for end in decided:
                settled_at = statement_at[end] + timedelta(minutes=SETTLE_MINUTES)
                if now < settled_at:
                    raise SourceError(
                        f"odds: the {end} statement has only just come out. Refresh after {settled_at:%H:%M} UTC"
                    )
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
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError):
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
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            label = row.get("effectiveDate") if isinstance(row, dict) else None
            where = f" dated {label}" if isinstance(label, str) else ""
            raise SourceError(f"New York Fed: unexpected row in the reply{where}: {type(exc).__name__}") from None
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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_treasury.py tests/test_fedwatch.py tests/test_odds.py tests/test_futures.py tests/test_nyfed.py`

Expected: `111 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `160 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the ten above. Suggested message: `fix: settle window after a statement, Treasury cache rules, plainer errors`.

---

### Task 2: The web server

**Files:**
- Create: `server/__init__.py`, `server/serve.py`
- Test: `tests/test_serve.py`

This is section 8.2 of the spec. The rules, in short:

- It listens on `127.0.0.1` only.
- It serves only the files the release's manifest lists. `/` means `index.html`. Anything else is a plain 404, including the manifest itself.
- `GET` and `HEAD` only; anything else is a 405.
- `/healthz` answers `ok`, even with no release. Every other address answers 503 until a release exists.
- It sends an `ETag` and answers `If-None-Match` with 304.
- An address with `?v=` is cached for a year; everything else for a minute; errors are not cached.
- Every response tells search engines not to index. HTML responses carry the content security policy.
- It logs the method, path and status. It never logs or sends an address, a header, a version string or a traceback.
- A silent connection is closed after 15 seconds.
- It notices a new release on the next request. No restart.
- `serve.py --self-test` checks these rules against a sample held in memory and writes nothing. Plan 4 runs it on the box before the service starts.

The tests start a real server on a free localhost port and talk to it with `http.client`.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_serve.py`**

```python
import http.client
import json
import os
import socket
import threading
import time

import pytest

from macro.build import write_manifest
from server import serve

FILES = {
    "index.html": "<!doctype html><title>t</title>",
    "app.js": "console.log(1)",
    "vendor/lib.js": "// lib",
    "data.json": '{"snapshot_id": "A"}',
    "analysis.pdf": "%PDF-1.4",
    "robots.txt": "User-agent: *\nDisallow: /\n",
}


def make_release(folder, snapshot_id="A", files=FILES):
    for name, text in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    write_manifest(folder, snapshot_id)
    return folder


class Running:
    """A server on a free localhost port, with its log lines collected."""

    def __init__(self, site, **options):
        self.lines = []
        self.server = serve.Server(site, 0, log=self.lines.append, **options)
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()

    def request(self, method, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
        finally:
            connection.close()

    def get(self, path, headers=None):
        return self.request("GET", path, headers)

    def raw(self, data, wait=2.0):
        with socket.create_connection(("127.0.0.1", self.port), timeout=wait) as sock:
            if data:
                sock.sendall(data)
            chunks = []
            try:
                while chunk := sock.recv(4096):
                    chunks.append(chunk)
            except TimeoutError:
                chunks.append(b"<<still open>>")
            return b"".join(chunks)

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def release(tmp_path):
    return make_release(tmp_path / "releases" / "A")


@pytest.fixture
def running(release):
    server = Running(serve.DiskSite(release))
    yield server
    server.close()


# --- which files a release may serve


@pytest.mark.parametrize("name", ["index.html", "vendor/lib.js", "a-b_c.1.json"])
def test_plain_relative_paths_are_safe(name):
    assert serve.safe_name(name)


@pytest.mark.parametrize(
    "name",
    ["", "/etc/passwd", "../x", "a/../x", "a//b", "a/", "./a", "a\\b", "a%2e", "a?b", "a#b", "a\nb", "manifest.json", "SHA256SUMS", 7, None],
)
def test_anything_else_is_not(name):
    assert not serve.safe_name(name)


def test_load_release_lists_the_manifest_files(release):
    loaded = serve.load_release(release)
    assert loaded.snapshot_id == "A"
    assert sorted(loaded.files) == sorted(FILES)
    assert loaded.files["index.html"].content_type == "text/html; charset=utf-8"
    assert loaded.files["index.html"].etag.startswith('"') and len(loaded.files["index.html"].etag) == 18


def rewrite_manifest(release, change):
    path = release / "manifest.json"
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))


def test_a_folder_without_a_manifest_is_not_a_release(tmp_path):
    assert serve.load_release(tmp_path) is None


def test_a_manifest_that_is_not_json_is_not_a_release(release):
    (release / "manifest.json").write_text("not json")
    assert serve.load_release(release) is None


def test_a_manifest_naming_a_path_outside_the_folder_is_rejected(release):
    rewrite_manifest(release, lambda m: m["files"].update({"../secret.txt": m["files"]["robots.txt"]}))
    assert serve.load_release(release) is None


def test_a_manifest_naming_a_missing_file_is_rejected(release):
    (release / "app.js").unlink()
    assert serve.load_release(release) is None


def test_a_link_that_leaves_the_folder_is_rejected(release, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    (release / "robots.txt").unlink()
    (release / "robots.txt").symlink_to(secret)
    assert serve.load_release(release) is None


def test_a_content_type_that_could_split_a_header_is_rejected(release):
    rewrite_manifest(release, lambda m: m["files"]["app.js"].update(content_type="text/plain\r\nX-Evil: 1"))
    assert serve.load_release(release) is None


# --- what the server answers


def test_the_root_serves_the_page_with_its_headers(running):
    status, headers, body = running.get("/")
    assert status == 200
    assert body == FILES["index.html"].encode()
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert headers["content-security-policy"] == serve.CSP
    assert headers["cache-control"] == "public, max-age=60"
    assert headers["x-robots-tag"] == "noindex, nofollow"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["content-length"] == str(len(body))


def test_other_files_get_their_type_and_no_page_policy(running):
    status, headers, body = running.get("/vendor/lib.js")
    assert (status, body) == (200, b"// lib")
    assert headers["content-type"] == "text/javascript; charset=utf-8"
    assert "content-security-policy" not in headers
    assert running.get("/data.json")[1]["content-type"] == "application/json"
    assert running.get("/robots.txt")[2] == FILES["robots.txt"].encode()


def test_the_pdf_opens_inline(running):
    headers = running.get("/analysis.pdf")[1]
    assert headers["content-type"] == "application/pdf"
    assert headers["content-disposition"] == 'inline; filename="macro-analysis.pdf"'


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/app.js?v=20261004T101500Z", "public, max-age=31536000, immutable"),
        ("/app.js?x=1&v=2", "public, max-age=31536000, immutable"),
        ("/app.js", "public, max-age=60"),
        ("/app.js?v=", "public, max-age=60"),
        ("/app.js?version=2", "public, max-age=60"),
    ],
)
def test_only_a_versioned_address_is_cached_for_long(running, path, expected):
    assert running.get(path)[1]["cache-control"] == expected


def test_an_unchanged_file_answers_304(running):
    etag = running.get("/app.js")[1]["etag"]
    for header in (etag, "W/" + etag, f'"other", {etag}', "*"):
        status, headers, body = running.get("/app.js", {"If-None-Match": header})
        assert (status, body) == (304, b"")
        assert headers["etag"] == etag
    assert running.get("/app.js", {"If-None-Match": '"something-else"'})[0] == 200


def test_head_sends_headers_only(running):
    status, headers, body = running.request("HEAD", "/")
    assert (status, body) == (200, b"")
    assert headers["content-length"] == str(len(FILES["index.html"]))


@pytest.mark.parametrize(
    "path",
    ["/nope", "/manifest.json", "/SHA256SUMS", "/../data.json", "/vendor/../data.json", "/%2e%2e/data.json", "/vendor", "/vendor/", "/index.html/"],
)
def test_anything_not_in_the_manifest_is_a_plain_404(running, path):
    status, headers, body = running.get(path)
    assert (status, body) == (404, b"Not Found\n")
    assert headers["content-type"] == "text/plain; charset=utf-8"
    assert headers["cache-control"] == "no-store"
    assert headers["x-robots-tag"] == "noindex, nofollow"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def test_other_methods_are_refused(running, method):
    status, headers, body = running.request(method, "/")
    assert (status, body) == (405, b"Method Not Allowed\n")
    assert headers["allow"] == "GET, HEAD"
    assert headers["connection"] == "close"


def test_the_health_check_answers_even_without_a_release(tmp_path):
    server = Running(serve.DiskSite(tmp_path / "missing"))
    try:
        assert server.get("/healthz")[:1] == (200,)
        assert server.get("/healthz")[2] == b"ok\n"
        status, _, body = server.get("/")
        assert (status, body) == (503, b"Service Unavailable\n")
    finally:
        server.close()


def test_no_version_string_is_sent(running):
    for path in ("/", "/nope", "/healthz"):
        headers = running.get(path)[1]
        assert "server" not in headers
        assert "python" not in json.dumps(headers).lower()


def test_two_requests_can_share_one_connection(running):
    connection = http.client.HTTPConnection("127.0.0.1", running.port, timeout=5)
    try:
        for path in ("/", "/app.js"):
            connection.request("GET", path)
            response = connection.getresponse()
            assert response.status == 200
            response.read()
    finally:
        connection.close()


# --- releases changing underneath it


def test_switching_the_link_serves_the_new_release_without_a_restart(tmp_path):
    make_release(tmp_path / "releases" / "A")
    make_release(tmp_path / "releases" / "B", "B", {**FILES, "data.json": '{"snapshot_id": "B"}'})
    current = tmp_path / "current"
    current.symlink_to("releases/A")
    server = Running(serve.DiskSite(current))
    try:
        assert json.loads(server.get("/data.json")[2])["snapshot_id"] == "A"
        replacement = tmp_path / "current.new"
        replacement.symlink_to("releases/B")
        os.replace(replacement, current)
        assert json.loads(server.get("/data.json")[2])["snapshot_id"] == "B"
    finally:
        server.close()


def test_a_folder_rebuilt_in_place_is_read_again(release, running):
    before = running.get("/data.json")[1]["etag"]
    (release / "data.json").write_text('{"snapshot_id": "A2", "more": true}')
    write_manifest(release, "A2")
    status, headers, body = running.get("/data.json")
    assert json.loads(body)["snapshot_id"] == "A2"
    assert headers["etag"] != before


def test_a_file_that_vanishes_gives_a_plain_500_and_no_traceback(release, running):
    assert running.get("/app.js")[0] == 200
    (release / "app.js").unlink()
    status, headers, body = running.get("/app.js")
    assert (status, body) == (500, b"Internal Server Error\n")
    assert "error FileNotFoundError" in running.lines


# --- logs and connections


def test_the_log_has_method_path_and_status_and_nothing_about_the_visitor(running):
    running.get("/app.js?v=1", {"User-Agent": "secret-agent", "CF-Connecting-IP": "203.0.113.9"})
    running.get("/nope")
    assert running.lines == ["GET /app.js 200", "GET /nope 404"]


def test_a_request_that_is_not_http_gets_a_plain_refusal(running):
    reply = running.raw(b"NOT HTTP\r\n\r\n")
    assert b"Bad Request" in reply
    assert b"Traceback" not in reply and b"Python" not in reply


def test_a_silent_connection_is_closed(release):
    server = Running(serve.DiskSite(release), idle_timeout=0.3)
    try:
        started = time.monotonic()
        assert server.raw(b"", wait=3.0) == b""
        assert time.monotonic() - started < 2.5
    finally:
        server.close()


# --- the self-test and the command line


def test_the_self_test_passes_and_reports_each_check():
    lines = []
    assert serve.self_test(log=lines.append) is True
    assert lines[-1] == "self-test passed"
    assert all(line.startswith("ok ") for line in lines[:-1])
    assert len(lines) > 15


def test_main_runs_the_self_test(capsys):
    assert serve.main(["--self-test"]) == 0
    assert "self-test passed" in capsys.readouterr().out


def test_main_needs_a_site(monkeypatch, capsys):
    monkeypatch.delenv("MACRO_SITE_DIR", raising=False)
    assert serve.main([]) == 2
    assert "MACRO_SITE_DIR" in capsys.readouterr().err


def test_main_rejects_a_port_that_is_not_a_number(tmp_path, capsys):
    assert serve.main(["--site", str(tmp_path), "--port", "eighty"]) == 2
    assert "port" in capsys.readouterr().err


def test_main_reports_a_port_it_cannot_use(release, running, capsys):
    assert serve.main(["--site", str(release), "--port", str(running.port)]) == 2
    assert "cannot listen" in capsys.readouterr().err
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_serve.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Write the server**

**File: `server/__init__.py`**

```python
"""The web server that the box runs. See serve.py."""
```

**File: `server/serve.py`**

```python
#!/usr/bin/env python3
"""Static file server for the macros page.

Standard library only, so it runs on the box's system Python with nothing installed.
It serves the files listed in the current release's manifest and nothing else.
See section 8.2 of the design spec.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import socketserver
import sys
import threading
from dataclasses import dataclass
from email.utils import formatdate
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

HOST = "127.0.0.1"  # never listens on anything but loopback
DEFAULT_PORT = 8081
IDLE_TIMEOUT = 15.0  # seconds of silence before a connection is closed
INTERNAL = ("manifest.json", "SHA256SUMS")  # part of a release, never served
SHORT_CACHE = "public, max-age=60"
LONG_CACHE = "public, max-age=31536000, immutable"
NO_CACHE = "no-store"
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
ALWAYS = {
    "X-Robots-Tag": "noindex, nofollow",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


@dataclass(frozen=True)
class Entry:
    """One file that may be served. Its bytes are on disk, or in memory for the self-test."""

    content_type: str
    etag: str
    path: Path | None = None
    data: bytes | None = None


@dataclass(frozen=True)
class Release:
    snapshot_id: str
    files: dict[str, Entry]


def read_entry(entry: Entry) -> bytes:
    return entry.data if entry.data is not None else entry.path.read_bytes()


def safe_name(name: object) -> bool:
    """True for a plain relative path such as "vendor/uplot.js": no "..", no escapes, not internal."""
    if not isinstance(name, str) or not name or name in INTERNAL:
        return False
    if name.startswith("/") or any(char in name for char in "\\%?#") or any(ord(char) < 32 for char in name):
        return False
    parts = PurePosixPath(name).parts
    return ".." not in parts and name == "/".join(parts)


def load_release(folder: Path) -> Release | None:
    """Reads a release folder's manifest. None when the folder is not a usable release."""
    try:
        root = folder.resolve()
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        files: dict[str, Entry] = {}
        for name, meta in manifest["files"].items():
            content_type = meta["content_type"]
            path = (root / name).resolve() if safe_name(name) else None
            if path is None or not path.is_relative_to(root) or not path.is_file():
                return None
            if not isinstance(content_type, str) or any(ord(char) < 32 for char in content_type):
                return None
            files[name] = Entry(content_type, '"' + str(meta["sha256"])[:16] + '"', path=path)
        return Release(str(manifest["snapshot_id"]), files)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


class DiskSite:
    """The release that `location` points at. It is read again whenever it changes."""

    def __init__(self, location: Path) -> None:
        self._location = location
        self._lock = threading.Lock()
        self._key: tuple | None = None
        self._release: Release | None = None

    def current(self) -> Release | None:
        folder = Path(os.path.realpath(self._location))
        try:
            stat = (folder / "manifest.json").stat()
            key = (str(folder), stat.st_mtime_ns, stat.st_size)
        except OSError:
            key = None
        with self._lock:
            if key != self._key:
                self._release = load_release(folder) if key else None
                self._key = key
            return self._release


class MemorySite:
    """A fixed release held in memory. Used by the self-test, which must write nothing."""

    def __init__(self, files: dict[str, tuple[str, bytes]]) -> None:
        entries = {
            name: Entry(content_type, f'"{len(data):016x}"', data=data)
            for name, (content_type, data) in files.items()
        }
        self._release = Release("self-test", entries)

    def current(self) -> Release | None:
        return self._release


def say(line: str) -> None:
    """The default log: one line to standard output, flushed so the journal sees it at once."""
    print(line, flush=True)


def plain(status: HTTPStatus, text: str | None = None) -> tuple[HTTPStatus, dict[str, str], bytes]:
    body = ((text or status.phrase) + "\n").encode()
    return status, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": NO_CACHE}, body


def etag_matches(header: str | None, etag: str) -> bool:
    """If-None-Match against our tag. A cache may have turned the tag into a weak one."""
    if not header:
        return False
    candidates = [item.strip().removeprefix("W/") for item in header.split(",")]
    return "*" in candidates or etag in candidates


def printable(text: str, limit: int = 120) -> str:
    return "".join(char if 32 < ord(char) < 127 else "?" for char in text)[:limit]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        self.timeout = self.server.idle_timeout
        super().setup()

    def do_GET(self) -> None:
        self._answer()

    def do_HEAD(self) -> None:
        self._answer()

    def _answer(self) -> None:
        try:
            status, headers, body = self._resolve()
        except Exception as exc:  # a bug or a vanished file must never become a traceback
            self.server.log(f"error {type(exc).__name__}")
            status, headers, body = plain(HTTPStatus.INTERNAL_SERVER_ERROR)
        self._send(status, headers, body)

    def _resolve(self) -> tuple[HTTPStatus, dict[str, str], bytes]:
        path, _, query = self.path.partition("?")
        if path == "/healthz":
            return plain(HTTPStatus.OK, "ok")
        release = self.server.site.current()
        if release is None:
            return plain(HTTPStatus.SERVICE_UNAVAILABLE)
        entry = release.files.get("index.html" if path == "/" else path[1:]) if path.startswith("/") else None
        if entry is None:
            return plain(HTTPStatus.NOT_FOUND)
        versioned = any(part.startswith("v=") and len(part) > 2 for part in query.split("&"))
        headers = {
            "Content-Type": entry.content_type,
            "ETag": entry.etag,
            "Cache-Control": LONG_CACHE if versioned else SHORT_CACHE,
        }
        if entry.content_type.startswith("text/html"):
            headers["Content-Security-Policy"] = CSP
        if entry.content_type == "application/pdf":
            headers["Content-Disposition"] = 'inline; filename="macro-analysis.pdf"'
        if etag_matches(self.headers.get("If-None-Match"), entry.etag):
            return HTTPStatus.NOT_MODIFIED, headers, b""
        return HTTPStatus.OK, headers, read_entry(entry)

    def _send(self, status: HTTPStatus, headers: dict[str, str], body: bytes) -> None:
        self.send_response_only(status)
        self.send_header("Date", formatdate(usegmt=True))
        for name, value in {**headers, **ALWAYS}.items():
            self.send_header(name, value)
        if status != HTTPStatus.NOT_MODIFIED:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)
        path = printable(getattr(self, "path", "") or "").partition("?")[0]
        self.server.log(f"{printable(self.command or '-', 12)} {path or '-'} {int(status)}")

    def send_error(self, code, message=None, explain=None) -> None:
        """Every error the base class raises: a plain body, no version string, connection closed."""
        try:
            status = HTTPStatus(code)
        except ValueError:
            status = HTTPStatus.BAD_REQUEST
        if status == HTTPStatus.NOT_IMPLEMENTED:  # a method other than GET or HEAD
            status = HTTPStatus.METHOD_NOT_ALLOWED
        status, headers, body = plain(status)
        if status == HTTPStatus.METHOD_NOT_ALLOWED:
            headers["Allow"] = "GET, HEAD"
        headers["Connection"] = "close"
        self.close_connection = True
        self._send(status, headers, body)

    def log_message(self, format, *args) -> None:
        self.server.log("note " + printable(format % args))


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, site, port: int, log=say, idle_timeout: float = IDLE_TIMEOUT) -> None:
        self.site = site
        self.log = log
        self.idle_timeout = idle_timeout
        super().__init__((HOST, port), Handler)

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)  # skip the hostname lookup HTTPServer would do
        self.server_name = "localhost"
        self.server_port = self.server_address[1]

    def handle_error(self, request, client_address) -> None:
        self.log(f"error {type(sys.exception()).__name__}")


def run(location: Path, port: int, log=say) -> int:
    """Serves until interrupted."""
    server = Server(DiskSite(location), port, log)
    log(f"serving {location} on http://{HOST}:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


SAMPLE = {
    "index.html": ("text/html; charset=utf-8", b"<!doctype html><title>self-test</title>"),
    "app.js": ("text/javascript; charset=utf-8", b"// self-test"),
    "data.json": ("application/json", b'{"snapshot_id":"self-test"}'),
    "analysis.pdf": ("application/pdf", b"%PDF-1.4 self-test"),
}


def self_test(log=say) -> bool:
    """Starts the server on a free port against a sample held in memory and checks its rules."""
    server = Server(MemorySite(SAMPLE), 0, log=lambda line: None)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    failures: list[str] = []

    def fetch(method: str, path: str, headers: dict[str, str] | None = None):
        connection = http.client.HTTPConnection(HOST, server.server_port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
        finally:
            connection.close()

    def check(name: str, passed: bool) -> None:
        log(("ok    " if passed else "FAIL  ") + name)
        if not passed:
            failures.append(name)

    try:
        status, headers, body = fetch("GET", "/")
        check("the page is served", status == 200 and body == SAMPLE["index.html"][1])
        check("the page carries the content security policy", headers.get("content-security-policy") == CSP)
        check("the page is cached for a minute", headers.get("cache-control") == SHORT_CACHE)
        check("search engines are told not to index", headers.get("x-robots-tag") == "noindex, nofollow")
        check("content sniffing is off", headers.get("x-content-type-options") == "nosniff")
        check("no server version is sent", "server" not in headers)
        etag = headers.get("etag", "")
        check("an unchanged file answers 304", fetch("GET", "/", {"If-None-Match": etag})[0] == 304)
        status, headers, body = fetch("HEAD", "/")
        check("HEAD sends headers only", status == 200 and body == b"" and headers.get("content-length") == "39")
        status, headers, _ = fetch("GET", "/app.js?v=1")
        check("a versioned file is cached for a year", status == 200 and headers.get("cache-control") == LONG_CACHE)
        check("scripts carry no page policy", "content-security-policy" not in headers)
        status, headers, _ = fetch("GET", "/analysis.pdf")
        check("the PDF opens inline", status == 200 and headers.get("content-disposition", "").startswith("inline"))
        check("the data file is served", fetch("GET", "/data.json")[0] == 200)
        check("an unknown path is 404", fetch("GET", "/nope")[0] == 404)
        check("the manifest is not served", fetch("GET", "/manifest.json")[0] == 404)
        check("a path that climbs out is 404", fetch("GET", "/../etc/passwd")[0] == 404)
        status, headers, _ = fetch("POST", "/")
        check("other methods are refused", status == 405 and headers.get("allow") == "GET, HEAD")
        status, _, body = fetch("GET", "/healthz")
        check("the health check answers", status == 200 and body == b"ok\n")
    except Exception as exc:
        check(f"the self-test ran without {type(exc).__name__}", False)
    finally:
        server.shutdown()
        server.server_close()
    log("self-test passed" if not failures else f"self-test FAILED: {len(failures)} check(s)")
    return not failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Static file server for the macros page.")
    parser.add_argument("--self-test", action="store_true", help="check the server's rules and exit")
    parser.add_argument("--site", default=os.environ.get("MACRO_SITE_DIR"), help="the release folder or a link to it")
    parser.add_argument("--port", default=os.environ.get("MACRO_PORT", str(DEFAULT_PORT)), help="port on 127.0.0.1")
    args = parser.parse_args(argv)
    if args.self_test:
        return 0 if self_test() else 1
    if not args.site:
        print("serve: set MACRO_SITE_DIR or pass --site", file=sys.stderr)
        return 2
    if not str(args.port).isdigit():
        print(f"serve: the port must be a number, not {args.port!r}", file=sys.stderr)
        return 2
    try:
        return run(Path(args.site), int(args.port))
    except OSError as exc:
        print(f"serve: cannot listen on {HOST}:{args.port}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_serve.py`

Expected: `64 passed`

- [ ] **Step 5: Run the self-test and the whole suite**

Run:

```bash
.venv/bin/python server/serve.py --self-test
.venv/bin/python -m pytest
```

Expected: seventeen lines starting `ok`, then `self-test passed`; and `224 passed`.

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `server/__init__.py`, `server/serve.py`, `tests/test_serve.py`. Suggested message: `feat: static web server with self-test`.

---

### Task 3: The build writes the page's build id, and a placeholder page

**Files:**
- Replace: `tests/test_build.py`, `macro/build.py`
- Create: `site/index.html`, `site/app.js`, `site/style.css`, `site/robots.txt`

The page asks for its script and stylesheet with `?v=<build id>`, so a new build is never served from an old cache. The build writes that id into `index.html` where the page says `{{BUILD_ID}}`. The build also puts back an old `dist/` left stranded by an interrupted run.

The page here is a placeholder: it loads `data.json` and prints one line. It exists so the server, the content security policy and the data file can be checked end to end. Plan 2b replaces all three page files.

- [ ] **Step 1: Replace the test file**

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


def test_an_old_dist_stranded_by_an_interrupted_run_is_put_back_first(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    dist.rename(tmp_path / "dist.old")  # as if a run had stopped between its two renames
    with pytest.raises(BuildError):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": float("nan")})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_the_page_gets_the_build_id_in_its_asset_addresses(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text('<script src="app.js?v={{BUILD_ID}}"></script>')
    (site / "app.js").write_text("// {{BUILD_ID}} is left alone outside the page")
    dist = tmp_path / "dist"
    build_dist(dist, site, {**SNAPSHOT, "build_id": "B7"})
    assert (dist / "index.html").read_text() == '<script src="app.js?v=B7"></script>'
    assert "{{BUILD_ID}}" in (dist / "app.js").read_text()
    listed = json.loads((dist / "manifest.json").read_text())["files"]["index.html"]["sha256"]
    assert listed == sha(dist / "index.html")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_build.py`

Expected: `2 failed, 8 passed`

- [ ] **Step 3: Replace the build module and create the page files**

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
BUILD_ID_MARK = "{{BUILD_ID}}"  # in index.html, replaced so asset addresses change with every build


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
    if previous.exists() and not dist.exists():
        previous.rename(dist)  # an earlier run stopped between the two renames: put the old folder back
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
    page = staging / "index.html"
    if page.is_file():
        build_id = str(snapshot.get("build_id", snapshot["snapshot_id"]))
        page.write_text(page.read_text(encoding="utf-8").replace(BUILD_ID_MARK, build_id), encoding="utf-8")
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
    shutil.rmtree(previous, ignore_errors=True)
```

**File: `site/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Macros</title>
<link rel="stylesheet" href="style.css?v={{BUILD_ID}}">
</head>
<body>
<main>
<h1>Macros</h1>
<p id="status">Loading the data…</p>
<p class="note">Placeholder page. The charts arrive with the next plan.</p>
</main>
<script type="module" src="app.js?v={{BUILD_ID}}"></script>
</body>
</html>
```

**File: `site/app.js`**

```javascript
// Placeholder page: it only proves that the data file loads. The next plan replaces it with the charts.
const status = document.getElementById("status");

async function main() {
  const response = await fetch("data.json", { cache: "no-cache" });
  if (!response.ok) throw new Error(`data.json answered ${response.status}`);
  const data = await response.json();
  const tenYear = data.yields.tenors.findIndex((tenor) => tenor.label === "10Y");
  const latest = data.yields.values[tenYear].at(-1);
  const { cut, hold, hike } = data.odds.summary;
  status.textContent =
    `Snapshot ${data.snapshot_id}. 10-year yield ${latest.toFixed(2)}% on ${data.yields.as_of}. ` +
    `Odds for ${data.odds.meeting}: cut ${cut}%, hold ${hold}%, hike ${hike}%.`;
}

main().catch((error) => {
  status.textContent = `The data could not be loaded: ${error.message}`;
});
```

**File: `site/style.css`**

```css
:root {
  color-scheme: light dark;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

body {
  margin: 0;
}

main {
  max-width: 60rem;
  margin: 0 auto;
  padding: 1.5rem 1rem;
}

.note {
  opacity: 0.7;
}
```

**File: `site/robots.txt`**

```text
User-agent: *
Disallow: /
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_build.py`

Expected: `10 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `226 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/test_build.py`, `macro/build.py` and the four files under `site/`. Suggested message: `feat: build id in the page, placeholder page, safer dist recovery`.

---

### Task 4: The preview command

**Files:**
- Replace: `tests/test_cli.py`, `macro/cli.py`

`python -m macro preview` serves `dist/` at `http://127.0.0.1:8081/` with the server from Task 2, until Ctrl-C. `--port` picks another port. It refuses to start when there is no build.

- [ ] **Step 1: Replace the test file**

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


def test_preview_needs_a_built_dist(paths, monkeypatch, capsys):
    patch_main(monkeypatch, paths)
    assert cli.main(["preview"]) == 1
    assert "refresh" in capsys.readouterr().err


def test_preview_serves_dist_on_the_chosen_port(paths, monkeypatch):
    run(paths)
    served = {}

    def fake_run(location, port):
        served.update(location=location, port=port)
        return 0

    patch_main(monkeypatch, paths)
    monkeypatch.setattr(cli.serve, "run", fake_run)
    assert cli.main(["preview", "--port", "9090"]) == 0
    assert served == {"location": paths["dist"], "port": 9090}


def test_preview_reports_a_port_it_cannot_use(paths, monkeypatch, capsys):
    run(paths)

    def busy(location, port):
        raise OSError("Address already in use")

    patch_main(monkeypatch, paths)
    monkeypatch.setattr(cli.serve, "run", busy)
    assert cli.main(["preview"]) == 1
    assert "--port" in capsys.readouterr().err
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py`

Expected: `3 failed, 10 passed`

- [ ] **Step 3: Replace the command line**

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
from server import serve

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
    preview_parser = commands.add_parser("preview", help="serve dist/ on this Mac, to look at it before publishing")
    preview_parser.add_argument("--port", type=int, default=serve.DEFAULT_PORT, help="port on 127.0.0.1")
    args = parser.parse_args(argv)

    if args.command == "preview":
        dist = default_paths()["dist"]
        if not (dist / "manifest.json").is_file():
            print("Nothing to preview. Run `python -m macro refresh` first.", file=sys.stderr)
            return 1
        try:
            return serve.run(dist, args.port)
        except OSError as exc:
            print(f"Preview cannot use port {args.port}: {exc}. Try --port with another number.", file=sys.stderr)
            return 1

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

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli.py`

Expected: `13 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `229 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/test_cli.py`, `macro/cli.py`. Suggested message: `feat: preview command`.

---

### Task 5: Try it

This task runs the real commands. It adds no code. The refresh makes six read-only requests: the current Treasury year, the New York Fed and four futures contracts.

- [ ] **Step 1: Build**

Run: `.venv/bin/python -m macro refresh`

Expected: the five summary lines, ending `Built dist/ (no analysis yet) and work/facts.json`.

- [ ] **Step 2: Start the preview in one terminal**

Run: `.venv/bin/python -m macro preview`

Expected: `serving .../dist on http://127.0.0.1:8081/`, and it keeps running.

- [ ] **Step 3: Check the answers from a second terminal**

Run:

```bash
for p in / /app.js /data.json /robots.txt /manifest.json /healthz; do
  printf "%-16s " "$p"
  curl -s -o /dev/null -w "%{http_code} %{content_type} cache=[%header{cache-control}]\n" "http://127.0.0.1:8081$p"
done
curl -s http://127.0.0.1:8081/ | grep -E "href|src"
curl -sI http://127.0.0.1:8081/ | grep -iE "content-security|x-robots|server"
```

Expected:

- `/`, `/app.js`, `/data.json` and `/robots.txt` answer 200 with `max-age=60`.
- `/manifest.json` answers 404 and `/healthz` answers 200, both `no-store`.
- The page's two asset addresses carry `?v=` followed by the snapshot id.
- The headers show the content security policy and `noindex, nofollow`, and no `Server` line.

- [ ] **Step 4: Look at it**

Open `http://127.0.0.1:8081/` in a browser. Expected: the heading "Macros" and one line with the snapshot id, the 10-year yield and the odds. The browser console shows no errors. The first terminal shows one log line per request, such as `GET / 200`, with no addresses.

- [ ] **Step 5: Stop the preview**

Press Ctrl-C in the first terminal.

- [ ] **Step 6: Checkpoint**

Stop and report what the owner saw. Nothing new to commit.
