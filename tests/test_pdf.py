import json
import re
import zlib
from datetime import datetime, timezone

from analysis_samples import facts, written
from macro import analysis
from macro.pdf import build_pdf, page_count

REFRESHED = datetime(2026, 10, 3, 18, 15, tzinfo=timezone.utc)


def draw(facts_used=None, **changes):
    text = analysis.parse(json.dumps(written(**changes)))
    return build_pdf(text, facts_used or facts(), REFRESHED)


def text_of(pdf):
    """Everything written on the pages, in order. fpdf2 compresses each page's content."""
    pages = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, flags=re.S):
        try:
            pages.append(zlib.decompress(stream).decode("cp1252"))
        except (zlib.error, UnicodeDecodeError):
            continue
    strings = re.findall(r"\((.*?)\) Tj", "\n".join(pages))
    return "\n".join(string.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\") for string in strings)


def test_it_is_a_pdf_with_at_least_one_page():
    pdf = draw()
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert page_count(pdf) >= 1


def test_it_holds_every_heading_in_order():
    text = text_of(draw())
    headings = [
        "US macro snapshot",
        "Data used",
        "What the yield curve says now",
        "What the change says about the outlook",
        "What the rate odds say",
        "Outlook by asset class",
        "Bonds",
        "Rates",
        "Foreign exchange",
        "Equities",
        "Sources and notices",
    ]
    places = [text.index(heading) for heading in headings]
    assert places == sorted(places)
    assert "\nOther\n" not in text


def test_the_optional_section_gets_its_own_heading():
    content = written()
    content["outlook"]["other"] = " ".join(["extra"] * 50)
    text = text_of(draw(outlook=content["outlook"]))
    assert text.index("Equities") < text.index("Other") < text.index("Sources and notices")


def test_the_numbers_come_from_the_facts():
    text = text_of(draw())
    for expected in ["2 Oct 2026", "1 year earlier", "5.28", "4.10", "10Y minus 2Y", "109", "77.9", "64.2"]:
        assert expected in text, expected
    assert "3.75–4.00% (current)" in text
    assert "the target range is 3.75–4.00% and the effective rate was 3.88% on 1 Oct 2026" in text
    assert "changed by +25 basis points, from 3.50–3.75%, in force from 17 Sep 2026" in text
    assert "Odds for the FOMC decision of 28 Oct 2026, 25 days away, percent" in text
    assert "Cut 0.0%, hold 77.9%, hike 22.1%." in text


def test_the_notices_name_the_model_and_the_sources():
    text = " ".join(text_of(draw(model="Test Model 9")).split())
    assert "Analysis written 3 Oct 2026, 19:00 UTC by Test Model 9, an AI model." in text
    assert "Data refreshed 3 Oct 2026, 18:15 UTC" in text
    assert "written by an AI model (Test Model 9) from the data shown above. It can be wrong. Not investment advice." in text
    assert "U.S. Department of the Treasury, Daily Treasury Par Yield Curve Rates" in text
    assert "The EFFR is subject to the Terms of Use posted at newyorkfed.org" in text
    assert "These are not CME FedWatch figures." in text


def test_the_distance_to_the_meeting_is_written_in_words():
    for days, words in [(25, "25 days away"), (1, "1 day away"), (0, "today")]:
        changed = facts()
        changed["next_meeting"]["days_away"] = days
        assert f"Odds for the FOMC decision of 28 Oct 2026, {words}, percent" in text_of(draw(changed))


def test_a_missing_number_is_printed_as_not_available():
    changed = facts()
    del changed["curves"][4]["yields"]["30Y"]
    changed["spreads_bp"][4]["30Y-5Y"] = None
    changed["odds"]["columns"][3]["date"] = None
    for outcome in changed["odds"]["outcomes"]:
        outcome["m1"] = None
    text = text_of(draw(changed))
    assert text.count("n/a") == 5
    assert "no data" in text


def test_a_range_that_never_changed_is_left_out_of_the_sentence():
    changed = facts()
    changed["fed_funds"]["last_change"] = None
    assert "last changed" not in text_of(draw(changed))


def test_typographic_characters_are_printed():
    words = " ".join(["word"] * 50)
    text = text_of(draw(curve_now=f"The Fed’s range – 3.75–4.00% – is “firm”… {words}"))
    assert "The Fed’s range – 3.75–4.00% – is “firm”…" in text


def test_the_same_inputs_give_the_same_bytes():
    assert draw() == draw()
    assert draw() != draw(model="Another Model")


def test_long_texts_run_on_to_more_pages():
    long = " ".join(["considerable"] * 160)
    outlook = {name: long for name in ("bonds", "rates", "fx", "equities", "other")}
    pdf = draw(curve_now=long, curve_change=long, rate_odds=long, outlook=outlook)
    pages = page_count(pdf)
    assert pages >= 3
    text = " ".join(text_of(pdf).split())  # the total is written as a piece of its own
    assert f"page 1 of {pages}" in text and f"page {pages} of {pages}" in text
