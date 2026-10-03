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
