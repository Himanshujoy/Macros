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
