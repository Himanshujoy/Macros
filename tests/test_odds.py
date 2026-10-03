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
