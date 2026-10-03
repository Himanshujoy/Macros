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
