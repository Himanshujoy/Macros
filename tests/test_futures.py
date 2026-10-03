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
