import json
from datetime import datetime, timezone

import httpx
import pytest

from analysis_samples import written
from macro import cli
from macro.errors import AnalysisError, SourceError
from samples import PRICES, chart_payload, effr_payload, treasury_csv_for
from server import serve

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


# --- the analysis command


def write_analysis(paths, **changes):
    paths["work"].mkdir(parents=True, exist_ok=True)
    (paths["work"] / "analysis.json").write_text(json.dumps(written(**changes)), encoding="utf-8")


def analyse(paths):
    return cli.add_the_analysis(dist=paths["dist"], work=paths["work"])


def test_analysis_draws_the_pdf_and_records_it(paths):
    run(paths)
    write_analysis(paths)
    result = analyse(paths)
    name = result["file"]
    assert (paths["dist"] / name).read_bytes().startswith(b"%PDF-")
    data = json.loads((paths["dist"] / "data.json").read_text())
    assert data["analysis"] == {"file": name, "model": "Claude Opus 5.5", "generated_at": "2026-10-03T19:00:00Z"}
    assert data["odds"]["summary"] == {"cut": 0.0, "hold": 77.9, "hike": 22.1}
    assert result["pages"] >= 1 and result["bytes"] == (paths["dist"] / name).stat().st_size


def test_the_server_serves_a_release_that_has_an_analysis(paths):
    run(paths)
    write_analysis(paths)
    name = analyse(paths)["file"]
    release = serve.load_release(paths["dist"])
    assert release is not None
    assert release.files[name].content_type == "application/pdf"


def test_analysis_lines_name_the_model_the_size_and_the_file(paths):
    run(paths)
    write_analysis(paths)
    result = analyse(paths)
    lines = cli.analysis_lines(result)
    assert lines[0] == "Analysis for snapshot 20261003T181500Z by Claude Opus 5.5, written 3 Oct 2026, 19:00 UTC"
    assert lines[1] == "7 sections, 420 words"
    assert lines[2].startswith(f"Added {result['file']} to dist/ (")
    assert "preview" in lines[3]


def test_analysis_refuses_text_written_for_another_snapshot_and_leaves_dist_alone(paths):
    run(paths)
    before = {path.name: path.read_bytes() for path in paths["dist"].iterdir() if path.is_file()}
    write_analysis(paths, snapshot_id="20260901T000000Z")
    with pytest.raises(AnalysisError, match="written for snapshot 20260901T000000Z"):
        analyse(paths)
    assert {path.name: path.read_bytes() for path in paths["dist"].iterdir() if path.is_file()} == before


def test_analysis_needs_a_refresh_first(paths):
    write_analysis(paths)
    with pytest.raises(AnalysisError, match="dist/ holds no snapshot. Run `python -m macro refresh` first"):
        analyse(paths)


def test_analysis_needs_the_facts_of_the_same_refresh(paths):
    run(paths)
    write_analysis(paths)
    facts_file = paths["work"] / "facts.json"
    facts = json.loads(facts_file.read_text())
    facts_file.write_text(json.dumps({**facts, "snapshot_id": "20260901T000000Z"}))
    with pytest.raises(AnalysisError, match="different refreshes"):
        analyse(paths)
    facts_file.unlink()
    with pytest.raises(AnalysisError, match="work/facts.json is missing or unreadable"):
        analyse(paths)


def test_analysis_needs_the_analysis_file(paths):
    run(paths)
    with pytest.raises(AnalysisError, match="analysis.json does not exist"):
        analyse(paths)


def test_a_second_analysis_replaces_the_first(paths):
    run(paths)
    write_analysis(paths)
    first = analyse(paths)["file"]
    write_analysis(paths, written_at="2026-10-03T20:30:00Z", curve_now=" ".join(["revised"] * 60))
    second = analyse(paths)["file"]
    assert first != second
    assert [path.name for path in paths["dist"].glob("*.pdf")] == [second]


def test_main_runs_the_analysis_and_prints_the_summary(paths, monkeypatch, capsys):
    run(paths)
    write_analysis(paths)
    patch_main(monkeypatch, paths)
    assert cli.main(["analysis"]) == 0
    out = capsys.readouterr().out
    assert "by Claude Opus 5.5" in out and "7 sections, 420 words" in out


def test_main_reports_a_bad_analysis_and_returns_1(paths, monkeypatch, capsys):
    run(paths)
    write_analysis(paths, curve_now="too short")
    patch_main(monkeypatch, paths)
    assert cli.main(["analysis"]) == 1
    err = capsys.readouterr().err
    assert "Analysis stopped: analysis: `curve_now` has 2 words; it needs at least 40" in err
    assert "dist/ was not changed" in err
    assert not list(paths["dist"].glob("*.pdf"))


def test_a_refresh_after_an_analysis_starts_again_without_one(paths):
    run(paths)
    write_analysis(paths)
    analyse(paths)
    run(paths)
    assert json.loads((paths["dist"] / "data.json").read_text())["analysis"] is None
    assert not list(paths["dist"].glob("*.pdf"))
