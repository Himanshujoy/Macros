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
