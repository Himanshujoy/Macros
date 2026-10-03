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
