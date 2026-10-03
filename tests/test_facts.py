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
