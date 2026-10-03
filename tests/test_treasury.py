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
