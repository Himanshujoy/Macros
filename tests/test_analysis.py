import json
from datetime import datetime, timezone

import pytest

from analysis_samples import SNAPSHOT_ID, TEXT, written
from macro import analysis
from macro.errors import AnalysisError


def words(count):
    return " ".join(["word"] * count)


def parse(**changes):
    return analysis.parse(json.dumps(written(**changes)))


def test_a_good_file_is_read_field_by_field():
    result = parse()
    assert result.snapshot_id == SNAPSHOT_ID
    assert result.model == "Claude Opus 5.5"
    assert result.written_at == datetime(2026, 10, 3, 19, 0, tzinfo=timezone.utc)
    assert result.curve_now == TEXT and result.curve_change == TEXT and result.rate_odds == TEXT
    assert list(result.outlook) == ["bonds", "rates", "fx", "equities"]
    assert len(result.texts()) == 7


def test_the_optional_section_comes_last():
    result = parse(outlook={"other": TEXT, "equities": TEXT, "fx": TEXT, "rates": TEXT, "bonds": TEXT})
    assert list(result.outlook) == ["bonds", "rates", "fx", "equities", "other"]
    assert len(result.texts()) == 8


def test_line_breaks_and_runs_of_spaces_become_single_spaces():
    result = parse(curve_now="  " + words(20) + "\n\n" + words(20) + " \t " + words(5) + "  ")
    assert result.curve_now == words(45)


def test_text_that_is_not_json_is_refused():
    with pytest.raises(AnalysisError, match="not valid JSON"):
        analysis.parse("{not json")


@pytest.mark.parametrize("raw", ["[]", '"text"', "12", "null"])
def test_anything_but_one_object_is_refused(raw):
    with pytest.raises(AnalysisError, match="one JSON object"):
        analysis.parse(raw)


@pytest.mark.parametrize("field", ["snapshot_id", "model", "written_at", "curve_now", "curve_change", "rate_odds", "outlook"])
def test_a_missing_field_is_named(field):
    content = written()
    del content[field]
    with pytest.raises(AnalysisError, match=f"the field `{field}` is missing"):
        analysis.parse(json.dumps(content))


@pytest.mark.parametrize("field", ["bonds", "rates", "fx", "equities"])
def test_a_missing_asset_class_is_named(field):
    content = written()
    del content["outlook"][field]
    with pytest.raises(AnalysisError, match=f"the field `outlook.{field}` is missing"):
        analysis.parse(json.dumps(content))


def test_the_word_limits_are_40_and_160_inclusive():
    assert parse(curve_now=words(40)).curve_now == words(40)
    assert parse(curve_now=words(160)).curve_now == words(160)
    with pytest.raises(AnalysisError, match="`curve_now` has 39 words; it needs at least 40"):
        parse(curve_now=words(39))
    with pytest.raises(AnalysisError, match="`curve_now` has 161 words; the limit is 160"):
        parse(curve_now=words(161))


def test_an_asset_class_text_is_held_to_the_same_limits():
    content = written()
    content["outlook"]["fx"] = words(12)
    with pytest.raises(AnalysisError, match="`outlook.fx` has 12 words"):
        analysis.parse(json.dumps(content))


@pytest.mark.parametrize("mark", ["*", "`", "#", "<", ">", "|"])
def test_markup_is_refused(mark):
    with pytest.raises(AnalysisError, match="`rate_odds` must be plain text"):
        parse(rate_odds=TEXT + f" {mark}bold{mark}")


@pytest.mark.parametrize("char", ["→", "中", "\U0001f600", "≤"])
def test_a_character_the_pdf_cannot_print_is_refused(char):
    with pytest.raises(AnalysisError, match="`curve_change` contains .* which the PDF cannot print"):
        parse(curve_change=TEXT + " " + char)


def test_ordinary_typography_is_allowed():
    text = TEXT + " 3.75–4.00% — the Fed’s “hold”… café €5"
    assert parse(curve_now=text).curve_now == text


@pytest.mark.parametrize("value", [12, None, ["a", "b"], {"text": "x"}, True])
def test_a_text_that_is_not_text_is_refused(value):
    with pytest.raises(AnalysisError, match="`curve_now` must be text"):
        parse(curve_now=value)


def test_an_empty_text_is_refused():
    with pytest.raises(AnalysisError, match="`curve_now` is empty"):
        parse(curve_now="   ")


def test_an_unknown_field_is_refused():
    with pytest.raises(AnalysisError, match="`summary` is not a field"):
        parse(summary=TEXT)
    content = written()
    content["outlook"]["commodities"] = TEXT
    with pytest.raises(AnalysisError, match="`outlook.commodities` is not a field"):
        analysis.parse(json.dumps(content))


def test_the_outlook_must_be_an_object():
    with pytest.raises(AnalysisError, match="`outlook` must be an object"):
        parse(outlook=TEXT)


@pytest.mark.parametrize("value", ["2026-10-03 19:00", "2026-10-03T19:00:00+00:00", "yesterday", 1790000000, None])
def test_the_time_must_be_utc_in_one_form(value):
    with pytest.raises(AnalysisError, match="`written_at` must be a UTC time"):
        parse(written_at=value)


def test_the_model_name_is_short_plain_text():
    with pytest.raises(AnalysisError, match="`model` is empty"):
        parse(model="")
    with pytest.raises(AnalysisError, match="`model` is longer than 60"):
        parse(model="m" * 61)
    with pytest.raises(AnalysisError, match="`model` must be plain text"):
        parse(model="<b>Opus</b>")


@pytest.mark.parametrize("value", ["", 12, None])
def test_the_snapshot_id_must_be_text(value):
    with pytest.raises(AnalysisError, match="`snapshot_id` must be the snapshot id"):
        parse(snapshot_id=value)


def test_load_reads_a_file_written_for_this_snapshot(tmp_path):
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps(written()), encoding="utf-8")
    assert analysis.load(path, SNAPSHOT_ID).model == "Claude Opus 5.5"


def test_load_refuses_a_file_written_for_another_snapshot(tmp_path):
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps(written(snapshot_id="20260901T000000Z")), encoding="utf-8")
    with pytest.raises(AnalysisError, match="written for snapshot 20260901T000000Z, but dist/ holds 20261003T181500Z"):
        analysis.load(path, SNAPSHOT_ID)


def test_load_says_how_to_get_a_missing_file_written(tmp_path):
    with pytest.raises(AnalysisError, match="analysis.json does not exist.*prompts/analysis.md"):
        analysis.load(tmp_path / "analysis.json", SNAPSHOT_ID)


def test_load_reports_a_file_that_is_not_text(tmp_path):
    path = tmp_path / "analysis.json"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(AnalysisError, match="cannot be read"):
        analysis.load(path, SNAPSHOT_ID)
