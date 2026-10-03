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
