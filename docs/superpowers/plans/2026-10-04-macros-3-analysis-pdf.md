# Macros Page, Plan 3: The Analysis PDF

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python -m macro analysis` turns a written analysis into a PDF, puts it into `dist/`, and the page's "Explain Macros" button opens it.

**Architecture:** The analysis arrives as a file, `work/analysis.json`, written by a model from `prompts/analysis.md` and `work/facts.json`. `macro/analysis.py` checks that file and trusts nothing in it until it passes. `macro/pdf.py` draws the PDF: the numbers come from `work/facts.json`, the words from the checked analysis. `macro/build.py` puts the PDF into a copy of `dist/`, records it in `data.json` and the manifest, and swaps the copy in. The page needs no change: it already shows the button when `data.json` names an analysis.

**Tech Stack:** Python 3.14 on the Mac, with all code kept compatible with Python 3.12. fpdf2 2.8.9 draws the PDF with a built-in font; it runs on the Mac only and is never installed on the box. httpx 0.28.1, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-10-04-macros-page-design.md`, sections 5.6 (the button), 6.3 (the `analysis` field), 6.5 (the analysis and the PDF), 7.1 (the command) and 13 (testing). The spec was updated alongside this plan.

**Supersedes:** for every file listed below, the content in the earlier plans.

---

## Roadmap

| Plan | Delivers | Status |
|---|---|---|
| 1 and 1b. Data pipeline | `python -m macro refresh` | Done |
| 2a, 2b, 2c. Server, preview and the page | `python -m macro preview` and the finished page | Done |
| 3. Analysis PDF (this file) | `python -m macro analysis`, and a working "Explain Macros" button | This plan |
| 4. Publish and rollout | `publish`, `rollback`, the box install, tunnel and DNS | Next, each step gated on the owner's go |

## How an analysis is made

1. `python -m macro refresh` builds `dist/` without an analysis and writes the numbers to `work/facts.json`.
2. A model writes `work/analysis.json` from `prompts/analysis.md` and `work/facts.json`. For now that is an Opus subagent in a Claude Code session. Later an API call can write the same file from the same prompt.
3. `python -m macro analysis` checks the file, draws the PDF and puts it into `dist/`.
4. `python -m macro preview` shows the page with the button working. The owner reads the PDF before publishing.

Four decisions shape the code:

- **The analysis file is not trusted.** A model wrote it. Every field is checked: the right fields and no others, plain text, 40 to 160 words each, only characters the PDF can print, and written for the snapshot that is in `dist/`.
- **Numbers never come from the analysis.** The "Data used" tables in the PDF are drawn from `work/facts.json`, which the code computed. The analysis only supplies the paragraphs.
- **The PDF's name holds its checksum.** It is `analysis-` plus the first twelve characters of the PDF's checksum. The server caches a PDF for a year, so a rewritten analysis under the old name would stay hidden behind the cached copy. A new name is a new address.
- **`dist/` is changed by swapping.** The command works on a copy of `dist/` and swaps it in at the end, as the refresh does, so a failure leaves `dist/` as it was.

## Rules for whoever executes this plan

- **Never run `git add`, `commit`, `push`, `stash`, `reset`, `checkout` or `restore`.** The owner makes every commit. Each task ends with a checkpoint. Stop there and report.
- **Tests never touch a real service.** Do not run `python -m macro refresh`, `python -m macro analysis` or `python -m macro preview` unless a step says so.
- **Task 1 installs one package** and the three it needs, from PyPI. No other task before Task 6 uses the network.
- **Nothing in this plan touches the box or Cloudflare.** Do not run `ssh`.
- Run every command from the project root, `/Users/himanshusrivastava/Projects/Macros`, with `.venv/bin/python`.
- Each file below is shown in full. It **replaces** an existing file of the same path, or creates it. Copy it exactly.
- Keep the code compatible with Python 3.12.

## File structure

| File | Responsibility |
|---|---|
| `requirements.txt` | Now also pins fpdf2 |
| `macro/errors.py` | Now also has `AnalysisError` |
| `macro/analysis.py` | Reads an analysis file and checks it |
| `macro/pdf.py` | Draws the PDF from the facts and a checked analysis |
| `macro/build.py` | Now also puts the PDF into `dist/` and records it. The swap of `dist/` is shared by both jobs |
| `macro/cli.py` | Now also has the `analysis` command. `refresh` and `analysis` report failures the same way |
| `prompts/analysis.md` | The instructions the writer of an analysis follows |
| `tests/analysis_samples.py` | A facts file and an analysis file, in the real shapes, for the tests |
| `tests/test_analysis.py`, `tests/test_pdf.py`, `tests/test_prompt.py` | New tests |
| `tests/test_build.py`, `tests/test_cli.py` | Extended for the PDF in `dist/` and for the command |

---

### Task 1: Add fpdf2

**Files:**
- Replace: `requirements.txt`

fpdf2 draws PDFs in pure Python. It brings three packages with it: Pillow, defusedxml and fontTools. All four stay on the Mac. The box runs only `server/serve.py`, which uses the standard library.

- [ ] **Step 1: Replace the requirements file**

**File: `requirements.txt`**

```text
httpx==0.28.1
fpdf2==2.8.9
```

- [ ] **Step 2: Install**

Run: `.venv/bin/python -m pip install -r requirements-dev.txt`

Expected: the last lines include `Successfully installed` and `fpdf2-2.8.9`.

- [ ] **Step 3: Check the version**

Run: `.venv/bin/python -c "import fpdf; print(fpdf.__version__)"`

Expected: `2.8.9`

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `243 passed`

- [ ] **Step 5: Checkpoint**

Stop and report. Do not run git. Files: `requirements.txt`. Suggested message: `chore: add fpdf2 for the analysis PDF`.

---

### Task 2: The analysis file and its checks

**Files:**
- Create: `tests/analysis_samples.py`, `tests/test_analysis.py`
- Replace: `macro/errors.py`
- Create: `macro/analysis.py`

The file a writer produces, `work/analysis.json`:

| Field | Content |
|---|---|
| `snapshot_id` | The snapshot the text was written for |
| `model` | The name printed in the notices, for example "Claude Opus 5.5" |
| `written_at` | A UTC time such as `2026-10-04T01:30:00Z` |
| `curve_now`, `curve_change`, `rate_odds` | Three texts |
| `outlook` | An object with the texts `bonds`, `rates`, `fx`, `equities`, and optionally `other` |

What the checks refuse, each with a message that names the field:

- Text that is not valid JSON, or is not one object.
- A missing field, or a field that is not in the table.
- A text of fewer than 40 or more than 160 words.
- Markdown or HTML: the characters `*`, `` ` ``, `#`, `<`, `>` and `|`. The text is printed as it is, so these would show as stray symbols.
- A character the PDF's built-in font cannot print. Dashes, curly quotes and an ellipsis are fine; an arrow or an emoji is not.
- A `snapshot_id` other than the one in `dist/`.

Line breaks and runs of spaces inside a text become single spaces, so each text is one paragraph.

- [ ] **Step 1: Write the failing test**

**File: `tests/analysis_samples.py`**

```python
"""A facts file and an analysis file in the shapes the real ones have, for the analysis and PDF tests."""

SNAPSHOT_ID = "20261003T181500Z"
TEXT = " ".join(["word"] * 60)

LABELS = ["latest", "1 week earlier", "1 month earlier", "3 months earlier", "1 year earlier"]
DATES = ["2026-10-02", "2026-09-25", "2026-09-02", "2026-07-02", "2025-10-02"]
YIELDS = {
    "3M": [4.19, 4.24, 3.92, 3.82, 4.02],
    "2Y": [4.83, 4.81, 4.39, 4.14, 3.55],
    "5Y": [5.06, 4.98, 4.54, 4.23, 3.67],
    "10Y": [5.28, 5.17, 4.79, 4.49, 4.10],
    "30Y": [5.63, 5.49, 5.27, 4.98, 4.69],
}


def facts() -> dict:
    """A fresh copy each time, so a test may change it."""
    curves = [
        {"label": label, "date": day, "yields": {tenor: values[index] for tenor, values in YIELDS.items()}}
        for index, (label, day) in enumerate(zip(LABELS, DATES))
    ]
    spreads = [
        {"label": label, "date": day, "10Y-2Y": 45 - index, "10Y-3M": 109 - index, "30Y-5Y": 57 + index}
        for index, (label, day) in enumerate(zip(LABELS, DATES))
    ]
    return {
        "snapshot_id": SNAPSHOT_ID,
        "as_of": "2026-10-02",
        "curves": curves,
        "spreads_bp": spreads,
        "changes_bp": [],
        "fed_funds": {
            "target_lower": 3.75,
            "target_upper": 4.0,
            "effr": 3.88,
            "effr_date": "2026-10-01",
            "last_change": {"effective": "2026-09-17", "from": [3.5, 3.75], "to": [3.75, 4.0], "change_bp": 25},
        },
        "odds": {
            "meeting": "2026-10-28",
            "priced_on": "2026-10-02",
            "current_range": [3.75, 4.0],
            "columns": [
                {"key": "now", "date": "2026-10-02"},
                {"key": "d1", "date": "2026-10-01"},
                {"key": "w1", "date": "2026-09-25"},
                {"key": "m1", "date": "2026-09-02"},
            ],
            "outcomes": [
                {"range": [3.5, 3.75], "now": 0.0, "d1": 0.0, "w1": 0.0, "m1": 27.0},
                {"range": [3.75, 4.0], "now": 77.9, "d1": 75.6, "w1": 35.8, "m1": 55.2},
                {"range": [4.0, 4.25], "now": 22.1, "d1": 24.4, "w1": 64.2, "m1": 17.9},
            ],
            "summary": {"cut": 0.0, "hold": 77.9, "hike": 22.1},
        },
        "next_meeting": {"date": "2026-10-28", "days_away": 25},
    }


def written(**changes) -> dict:
    """The content of a good analysis file, with any top-level fields replaced."""
    content = {
        "snapshot_id": SNAPSHOT_ID,
        "model": "Claude Opus 5.5",
        "written_at": "2026-10-03T19:00:00Z",
        "curve_now": TEXT,
        "curve_change": TEXT,
        "rate_odds": TEXT,
        "outlook": {"bonds": TEXT, "rates": TEXT, "fx": TEXT, "equities": TEXT},
    }
    content.update(changes)
    return content
```

**File: `tests/test_analysis.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_analysis.py`

Expected: `1 error`, with `ImportError: cannot import name 'analysis' from 'macro'`.

- [ ] **Step 3: Write the checks**

**File: `macro/errors.py`**

```python
"""Errors the commands report to the owner in plain words."""


class MacroError(Exception):
    """Any failure a command reports as a plain message, without a traceback."""


class SourceError(MacroError):
    """A data source failed or returned something unexpected."""


class BuildError(MacroError):
    """The output folder could not be built."""


class AnalysisError(MacroError):
    """The analysis file is missing, or fails its checks."""
```

**File: `macro/analysis.py`**

```python
"""Reads an analysis file and checks it before anything is published from it.

The file is written by a model from prompts/analysis.md and work/facts.json. Nothing in it is
trusted until it has passed these checks. See section 6.5 of the design spec.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from macro.errors import AnalysisError

MIN_WORDS = 40
MAX_WORDS = 160
SECTIONS = ("curve_now", "curve_change", "rate_odds")
OUTLOOK_REQUIRED = ("bonds", "rates", "fx", "equities")
OUTLOOK_OPTIONAL = ("other",)
MAX_MODEL_LENGTH = 60
MARKUP = "*`#<>|"  # the texts are printed as they are, so Markdown or HTML would show as stray symbols
PDF_ENCODING = "cp1252"  # what the PDF's built-in font can print
WRITTEN_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class Analysis:
    """A checked analysis. `outlook` holds the asset classes in the order they are printed."""

    snapshot_id: str
    model: str
    written_at: datetime
    curve_now: str
    curve_change: str
    rate_odds: str
    outlook: dict[str, str]

    def texts(self) -> list[str]:
        return [self.curve_now, self.curve_change, self.rate_odds, *self.outlook.values()]


def printable(name: str, value: object) -> str:
    """A string on one line, free of markup, that the PDF's font can print."""
    if not isinstance(value, str):
        raise AnalysisError(f"analysis: `{name}` must be text")
    text = " ".join(value.split())
    if not text:
        raise AnalysisError(f"analysis: `{name}` is empty")
    for char in text:
        if char in MARKUP:
            raise AnalysisError(f"analysis: `{name}` must be plain text, but contains {char!r}")
        try:
            char.encode(PDF_ENCODING)
        except UnicodeEncodeError:
            raise AnalysisError(f"analysis: `{name}` contains {char!r}, which the PDF cannot print") from None
    return text


def section(name: str, value: object) -> str:
    """One piece of analysis: printable text within the word limits."""
    text = printable(name, value)
    words = len(text.split())
    if words < MIN_WORDS:
        raise AnalysisError(f"analysis: `{name}` has {words} words; it needs at least {MIN_WORDS}")
    if words > MAX_WORDS:
        raise AnalysisError(f"analysis: `{name}` has {words} words; the limit is {MAX_WORDS}")
    return text


def only_known(found: dict, known: tuple[str, ...], prefix: str = "") -> None:
    for key in found:
        if key not in known:
            raise AnalysisError(f"analysis: `{prefix}{key}` is not a field this file may have")


def required(found: dict, key: str, prefix: str = "") -> object:
    if key not in found:
        raise AnalysisError(f"analysis: the field `{prefix}{key}` is missing")
    return found[key]


def parse(raw: str) -> Analysis:
    """Checks the content of an analysis file. Raises AnalysisError with the first problem found."""
    try:
        content = json.loads(raw)
    except ValueError as exc:
        raise AnalysisError(f"analysis: the file is not valid JSON ({exc})") from None
    if not isinstance(content, dict):
        raise AnalysisError("analysis: the file must hold one JSON object")
    only_known(content, ("snapshot_id", "model", "written_at", *SECTIONS, "outlook"))

    snapshot_id = required(content, "snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise AnalysisError("analysis: `snapshot_id` must be the snapshot id from work/facts.json")
    model = printable("model", required(content, "model"))
    if len(model) > MAX_MODEL_LENGTH:
        raise AnalysisError(f"analysis: `model` is longer than {MAX_MODEL_LENGTH} characters")
    written = required(content, "written_at")
    try:
        written_at = datetime.strptime(written, WRITTEN_AT_FORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        raise AnalysisError("analysis: `written_at` must be a UTC time such as 2026-10-04T01:30:00Z") from None

    sections = {name: section(name, required(content, name)) for name in SECTIONS}
    outlook = required(content, "outlook")
    if not isinstance(outlook, dict):
        raise AnalysisError("analysis: `outlook` must be an object with one text per asset class")
    only_known(outlook, OUTLOOK_REQUIRED + OUTLOOK_OPTIONAL, "outlook.")
    classes = {name: section(f"outlook.{name}", required(outlook, name, "outlook.")) for name in OUTLOOK_REQUIRED}
    for name in OUTLOOK_OPTIONAL:
        if name in outlook:
            classes[name] = section(f"outlook.{name}", outlook[name])
    return Analysis(snapshot_id=snapshot_id, model=model, written_at=written_at, outlook=classes, **sections)


def load(path: Path, snapshot_id: str) -> Analysis:
    """Reads and checks the analysis file, and makes sure it was written for this snapshot."""
    shown = f"{path.parent.name}/{path.name}"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise AnalysisError(
            f"analysis: {shown} does not exist. Have it written from prompts/analysis.md and work/facts.json"
        ) from None
    except (OSError, UnicodeDecodeError) as exc:
        raise AnalysisError(f"analysis: {shown} cannot be read ({exc})") from None
    analysis = parse(raw)
    if analysis.snapshot_id != snapshot_id:
        raise AnalysisError(
            f"analysis: written for snapshot {analysis.snapshot_id}, but dist/ holds {snapshot_id}. "
            "Have it rewritten from the current work/facts.json"
        )
    return analysis
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_analysis.py`

Expected: `53 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `296 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the four above. Suggested message: `feat: read and check an analysis file`.

---

### Task 3: The PDF

**Files:**
- Create: `tests/test_pdf.py`
- Create: `macro/pdf.py`

One function, `build_pdf(analysis, facts, refreshed_at)`, returns the PDF as bytes. The page is A4 portrait in Helvetica, a built-in font. In order:

1. The title, and one line saying when the data was refreshed, when and by which model the analysis was written, that it can be wrong, and that it is not investment advice.
2. "Data used": the yields for 3M, 2Y, 5Y, 10Y and 30Y on the five dates; the three spreads; the target range and the effective rate; the odds table and the cut, hold and hike totals. A missing number is printed as `n/a`.
3. The three texts, each under its heading, then "Outlook by asset class" with a sub-heading for each class.
4. "Sources and notices": the Treasury credit, the New York Fed's required notice, the odds note, and the AI notice.

Three details:

- fpdf2's built-in fonts print the Windows-1252 character set once `core_fonts_encoding` is set to `cp1252`. That covers dashes and curly quotes. `macro/analysis.py` refuses anything outside it, so the drawing never meets a character it cannot print.
- The PDF's creation date is set to the analysis's `written_at`, so the same inputs always give the same bytes. The file's name depends on those bytes (Task 4).
- A heading is never left alone at the foot of a page: it moves to the next page with its text.

The tests read the PDF back. fpdf2 compresses each page, so the test helper `text_of` inflates the pages and collects the text.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_pdf.py`**

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pdf.py`

Expected: `1 error`, with `ModuleNotFoundError: No module named 'macro.pdf'`.

- [ ] **Step 3: Write the drawing**

**File: `macro/pdf.py`**

```python
"""Draws the analysis PDF: the data the analysis was written from, the analysis, and the notices.

The numbers come from work/facts.json, never from the analysis text. See section 6.5 of the spec.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from fpdf import FPDF
from fpdf.enums import TableBordersLayout, XPos, YPos
from fpdf.fonts import FontFace

from macro.analysis import PDF_ENCODING, Analysis

FONT = "Helvetica"
INK = (20, 20, 20)
MUTED = (95, 95, 90)
RULE = (200, 200, 195)
SHADE = (242, 242, 239)
MARGIN = 18.0  # millimetres, on every side

SHOWN_TENORS = ("3M", "2Y", "5Y", "10Y", "30Y")
SPREADS = (("10Y-2Y", "10Y minus 2Y"), ("10Y-3M", "10Y minus 3M"), ("30Y-5Y", "30Y minus 5Y"))
ODDS_COLUMNS = {"now": "Now", "d1": "1 day earlier", "w1": "1 week earlier", "m1": "1 month earlier"}
SECTION_TITLES = (
    ("curve_now", "What the yield curve says now"),
    ("curve_change", "What the change says about the outlook"),
    ("rate_odds", "What the rate odds say"),
)
OUTLOOK_HEADING = "Outlook by asset class"
OUTLOOK_TITLES = {"bonds": "Bonds", "rates": "Rates", "fx": "Foreign exchange", "equities": "Equities", "other": "Other"}

TREASURY_NOTICE = "Yields: U.S. Department of the Treasury, Daily Treasury Par Yield Curve Rates."
NYFED_NOTICE = (
    "The EFFR is subject to the Terms of Use posted at newyorkfed.org. The New York Fed is not responsible for "
    "publication of the EFFR by theta-markets.com, does not sanction or endorse any particular republication, "
    "and has no liability for your use."
)
ODDS_NOTICE = (
    "Rate odds: own calculation from 30-Day Federal Funds futures prices, using the method CME Group publishes "
    "for its FedWatch tool. These are not CME FedWatch figures."
)


def day(iso: str) -> str:
    """ "2026-10-02" becomes "2 Oct 2026"."""
    value = date.fromisoformat(iso)
    return f"{value.day} {value:%b %Y}"


def moment(value: datetime) -> str:
    """A UTC time as "4 Oct 2026, 01:30 UTC"."""
    return f"{value.day} {value:%b %Y, %H:%M} UTC"


def number(value: float | None, digits: int) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def band(pair: list[float]) -> str:
    """A target range as "3.75–4.00%"."""
    return f"{pair[0]:.2f}–{pair[1]:.2f}%"


def away(days: int) -> str:
    """How far off the meeting is, in words."""
    if days <= 0:
        return "today"
    return "1 day away" if days == 1 else f"{days} days away"


class Report(FPDF):
    """An A4 page with the site's name and the page number at the foot."""

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(FONT, size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 4, f"macros.theta-markets.com  ·  page {self.page_no()} of {{nb}}", align="C")


def heading(pdf: Report, text: str, size: float = 12.5, room: float = 26) -> None:
    """A heading that is never left alone at the foot of a page: it needs `room` millimetres under it."""
    if pdf.will_page_break(room):
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font(FONT, style="B", size=size)
    pdf.set_text_color(*INK)
    pdf.cell(0, 6.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(0.8)


def paragraph(pdf: Report, text: str, size: float = 10, colour: tuple[int, int, int] = INK) -> None:
    pdf.set_font(FONT, size=size)
    pdf.set_text_color(*colour)
    pdf.multi_cell(0, size * 0.52, text, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1.6)


def table(pdf: Report, caption: str, rows: list[list[str]], first: float) -> None:
    """A table whose first column is labels and whose other columns are numbers, under a small caption."""
    if pdf.will_page_break(8 + 6 * len(rows)):
        pdf.add_page()
    pdf.set_font(FONT, size=9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, caption, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*INK)
    columns = len(rows[0])
    other = (pdf.epw - first) / (columns - 1)
    pdf.set_draw_color(*RULE)
    with pdf.table(
        col_widths=(first, *([other] * (columns - 1))),
        text_align=("LEFT", *(["RIGHT"] * (columns - 1))),
        borders_layout=TableBordersLayout.HORIZONTAL_LINES,
        headings_style=FontFace(emphasis="BOLD", fill_color=SHADE),
        line_height=4.6,
        padding=(1.2, 1.5),
    ) as drawn:
        for cells in rows:
            row = drawn.row()
            for cell in cells:
                row.cell(cell)
    pdf.ln(3)


def yields_rows(facts: dict) -> list[list[str]]:
    curves = facts["curves"]
    head = ["Tenor", *(f"{day(curve['date'])}\n{curve['label']}" for curve in curves)]
    body = [[tenor, *(number(curve["yields"].get(tenor), 2) for curve in curves)] for tenor in SHOWN_TENORS]
    return [head, *body]


def spread_rows(facts: dict) -> list[list[str]]:
    spreads = facts["spreads_bp"]
    head = ["Spread", *(f"{day(entry['date'])}\n{entry['label']}" for entry in spreads)]
    body = [[title, *(number(entry.get(key), 0) for entry in spreads)] for key, title in SPREADS]
    return [head, *body]


def odds_rows(odds: dict) -> list[list[str]]:
    head = ["Target range after the decision"]
    for column in odds["columns"]:
        when = day(column["date"]) if column["date"] else "no data"
        head.append(f"{ODDS_COLUMNS[column['key']]}\n{when}")
    body = []
    for outcome in odds["outcomes"]:
        label = band(outcome["range"])
        if outcome["range"][0] == odds["current_range"][0]:
            label += " (current)"
        body.append([label, *(number(outcome[column["key"]], 1) for column in odds["columns"])])
    return [head, *body]


def fed_funds_sentence(fed: dict) -> str:
    text = (
        f"Fed funds: the target range is {band([fed['target_lower'], fed['target_upper']])} and the effective rate "
        f"was {fed['effr']:.2f}% on {day(fed['effr_date'])}."
    )
    change = fed["last_change"]
    if change:
        text += (
            f" The range last changed by {change['change_bp']:+d} basis points, "
            f"from {band(change['from'])}, in force from {day(change['effective'])}."
        )
    return text


def build_pdf(analysis: Analysis, facts: dict, refreshed_at: datetime) -> bytes:
    """The whole document as bytes. The same inputs always give the same bytes."""
    pdf = Report(orientation="portrait", unit="mm", format="A4")
    pdf.core_fonts_encoding = PDF_ENCODING
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(True, margin=MARGIN)
    pdf.set_title("US macro snapshot: analysis")
    pdf.set_author(analysis.model)
    pdf.set_creator("macros.theta-markets.com")
    pdf.set_creation_date(analysis.written_at)
    pdf.add_page()

    pdf.set_font(FONT, style="B", size=18)
    pdf.set_text_color(*INK)
    pdf.cell(0, 9, "US macro snapshot", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    paragraph(
        pdf,
        f"Yields as of {day(facts['as_of'])}. Data refreshed {moment(refreshed_at)}. "
        f"Analysis written {moment(analysis.written_at)} by {analysis.model}, an AI model. "
        "It can be wrong. Not investment advice.",
        size=9,
        colour=MUTED,
    )

    odds = facts["odds"]
    meeting = facts["next_meeting"]
    summary = odds["summary"]
    heading(pdf, "Data used")
    table(pdf, "Treasury par yields, percent", yields_rows(facts), first=26)
    table(pdf, "Curve spreads, basis points", spread_rows(facts), first=26)
    paragraph(pdf, fed_funds_sentence(facts["fed_funds"]))
    table(
        pdf,
        f"Odds for the FOMC decision of {day(meeting['date'])}, {away(meeting['days_away'])}, percent",
        odds_rows(odds),
        first=58,
    )
    paragraph(pdf, f"Cut {summary['cut']:.1f}%, hold {summary['hold']:.1f}%, hike {summary['hike']:.1f}%.")

    for name, title in SECTION_TITLES:
        heading(pdf, title)
        paragraph(pdf, getattr(analysis, name))
    heading(pdf, OUTLOOK_HEADING)
    for name, text in analysis.outlook.items():
        heading(pdf, OUTLOOK_TITLES[name], size=10.5, room=18)
        paragraph(pdf, text)

    heading(pdf, "Sources and notices", size=10.5, room=40)
    for notice in (
        TREASURY_NOTICE,
        NYFED_NOTICE,
        ODDS_NOTICE,
        f"The analysis was written by an AI model ({analysis.model}) from the data shown above. "
        "It can be wrong. Not investment advice.",
    ):
        paragraph(pdf, notice, size=8.5, colour=MUTED)
    return bytes(pdf.output())


def page_count(pdf: bytes) -> int:
    """How many pages a PDF made by `build_pdf` has."""
    found = re.search(rb"/Count (\d+)", pdf)
    return int(found.group(1)) if found else 0
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_pdf.py`

Expected: `11 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `307 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/test_pdf.py`, `macro/pdf.py`. Suggested message: `feat: draw the analysis PDF`.

---

### Task 4: The PDF goes into dist/, and the command

**Files:**
- Replace: `tests/test_build.py`, `tests/test_cli.py`
- Replace: `macro/build.py`, `macro/cli.py`

`macro/build.py` now leaves hidden files out of the manifest. Finder drops a `.DS_Store` into any folder it has shown, and one in `dist/` used to stop the build. This was found by the review of Plan 2.

`macro/build.py` also gains `add_analysis(dist, pdf, model, generated_at)`. It copies `dist/` to a work folder, removes any earlier analysis PDF from the copy, writes the new one under its checksum name, sets `analysis` in `data.json` to `{file, model, generated_at}`, rewrites the manifest and the checksum list, and swaps the copy in. The swap is the same two renames the refresh uses, now in one shared function.

`macro/cli.py` gains the command. `python -m macro analysis`:

1. Reads `dist/data.json` and `work/facts.json`, and stops if either is missing or they come from different refreshes.
2. Reads and checks `work/analysis.json` (Task 2).
3. Draws the PDF (Task 3) and adds it to `dist/`.
4. Prints four lines: the snapshot and the writer, the size of the text, the file added, and a reminder to read it in the preview.

A failure prints `Analysis stopped:` and the reason, then `dist/ was not changed.`, and the command returns 1. `refresh` reports its failures through the same code.

A new refresh builds `dist/` again without an analysis, so an analysis never outlives the data it was written for.

- [ ] **Step 1: Replace the two test files**

**File: `tests/test_build.py`**

```python
import hashlib
import json

import pytest

from macro.build import add_analysis, build_dist, write_manifest
from macro.errors import BuildError

SNAPSHOT = {"snapshot_id": "20261003T181500Z", "value": 1}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_writes_the_data_file_manifest_and_checksums(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT
    manifest = json.loads((dist / "manifest.json").read_text())
    assert manifest["snapshot_id"] == "20261003T181500Z"
    assert manifest["files"] == {
        "data.json": {
            "sha256": sha(dist / "data.json"),
            "bytes": (dist / "data.json").stat().st_size,
            "content_type": "application/json",
        }
    }
    assert (dist / "SHA256SUMS").read_text().splitlines() == [
        f"{sha(dist / 'data.json')}  data.json",
        f"{sha(dist / 'manifest.json')}  manifest.json",
    ]


def test_site_files_are_copied_and_listed_but_hidden_files_are_not(tmp_path):
    site = tmp_path / "site"
    (site / "vendor").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html>")
    (site / "vendor" / "lib.js").write_text("// lib")
    (site / ".DS_Store").write_text("finder")
    dist = tmp_path / "dist"
    build_dist(dist, site, SNAPSHOT)
    files = json.loads((dist / "manifest.json").read_text())["files"]
    assert sorted(files) == ["data.json", "index.html", "vendor/lib.js"]
    assert files["index.html"]["content_type"] == "text/html; charset=utf-8"
    assert files["vendor/lib.js"]["content_type"] == "text/javascript; charset=utf-8"
    assert not (dist / ".DS_Store").exists()


def test_a_rebuild_replaces_the_old_dist(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    (dist / "stale.txt").write_text("old")
    build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert not (dist / "stale.txt").exists()
    assert json.loads((dist / "data.json").read_text())["value"] == 2


def test_a_failed_build_leaves_the_old_dist_alone(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    with pytest.raises(BuildError, match="JSON"):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": float("nan")})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_a_swap_that_fails_puts_the_old_dist_back(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    real_rename = type(dist).rename

    def failing_rename(self, target):
        if self.name == "dist.tmp":
            raise OSError("disk full")
        return real_rename(self, target)

    monkeypatch.setattr(type(dist), "rename", failing_rename)
    with pytest.raises(OSError, match="disk full"):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_nothing_is_left_behind_after_a_build(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": 2})
    assert sorted(path.name for path in tmp_path.iterdir()) == ["dist"]


def test_a_file_with_an_unknown_type_stops_the_build(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "notes.docx").write_text("x")
    with pytest.raises(BuildError, match="notes.docx"):
        build_dist(tmp_path / "dist", site, SNAPSHOT)


def test_write_manifest_can_be_rerun_after_adding_a_file(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    (dist / "analysis.pdf").write_bytes(b"%PDF-1.4")
    write_manifest(dist, "20261003T181500Z")
    files = json.loads((dist / "manifest.json").read_text())["files"]
    assert sorted(files) == ["analysis.pdf", "data.json"]
    assert files["analysis.pdf"]["content_type"] == "application/pdf"


def test_an_old_dist_stranded_by_an_interrupted_run_is_put_back_first(tmp_path):
    dist = tmp_path / "dist"
    build_dist(dist, tmp_path / "no-site", SNAPSHOT)
    dist.rename(tmp_path / "dist.old")  # as if a run had stopped between its two renames
    with pytest.raises(BuildError):
        build_dist(dist, tmp_path / "no-site", {**SNAPSHOT, "value": float("nan")})
    assert json.loads((dist / "data.json").read_text()) == SNAPSHOT


def test_the_page_and_its_own_scripts_get_the_build_id_in_their_addresses(tmp_path):
    site = tmp_path / "site"
    (site / "vendor").mkdir(parents=True)
    (site / "index.html").write_text('<script src="app.js?v={{BUILD_ID}}"></script>')
    (site / "app.js").write_text('import "./lib.js?v={{BUILD_ID}}";')
    (site / "lib.js").write_text("// nothing to fill in")
    (site / "style.css").write_text("/* {{BUILD_ID}} is left alone in a stylesheet */")
    (site / "vendor" / "other.js").write_text("// {{BUILD_ID}} is left alone in a file that is not ours")
    dist = tmp_path / "dist"
    build_dist(dist, site, {**SNAPSHOT, "build_id": "B7"})
    assert (dist / "index.html").read_text() == '<script src="app.js?v=B7"></script>'
    assert (dist / "app.js").read_text() == 'import "./lib.js?v=B7";'
    assert (dist / "lib.js").read_text() == "// nothing to fill in"
    assert "{{BUILD_ID}}" in (dist / "style.css").read_text()
    assert "{{BUILD_ID}}" in (dist / "vendor" / "other.js").read_text()
    files = json.loads((dist / "manifest.json").read_text())["files"]
    for name in ("index.html", "app.js"):
        assert files[name]["sha256"] == sha(dist / name)


def test_without_a_build_id_the_snapshot_id_is_used(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "app.js").write_text('import "./lib.js?v={{BUILD_ID}}";')
    dist = tmp_path / "dist"
    build_dist(dist, site, SNAPSHOT)
    assert (dist / "app.js").read_text() == 'import "./lib.js?v=20261003T181500Z";'


# --- the analysis PDF

PDF = b"%PDF-1.3 a first analysis"
WRITTEN = "2026-10-03T19:00:00Z"


def built(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<!doctype html>")
    dist = tmp_path / "dist"
    build_dist(dist, site, {**SNAPSHOT, "analysis": None})
    return dist


def test_an_analysis_is_added_recorded_and_listed(tmp_path):
    dist = built(tmp_path)
    name = add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert name == f"analysis-{hashlib.sha256(PDF).hexdigest()[:12]}.pdf"
    assert (dist / name).read_bytes() == PDF
    data = json.loads((dist / "data.json").read_text())
    assert data["analysis"] == {"file": name, "model": "Claude Opus 5.5", "generated_at": WRITTEN}
    assert data["snapshot_id"] == SNAPSHOT["snapshot_id"] and data["value"] == 1
    manifest = json.loads((dist / "manifest.json").read_text())
    assert manifest["snapshot_id"] == SNAPSHOT["snapshot_id"]
    assert sorted(manifest["files"]) == sorted([name, "data.json", "index.html"])
    assert manifest["files"][name] == {
        "sha256": hashlib.sha256(PDF).hexdigest(),
        "bytes": len(PDF),
        "content_type": "application/pdf",
    }
    assert manifest["files"]["data.json"]["sha256"] == sha(dist / "data.json")
    assert f"{sha(dist / 'manifest.json')}  manifest.json" in (dist / "SHA256SUMS").read_text()


def test_a_rewritten_analysis_replaces_the_first_under_a_new_name(tmp_path):
    dist = built(tmp_path)
    first = add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    second = add_analysis(dist, b"%PDF-1.3 a second analysis", "Claude Opus 5.5", "2026-10-03T20:00:00Z")
    assert first != second
    assert sorted(path.name for path in dist.glob("*.pdf")) == [second]
    data = json.loads((dist / "data.json").read_text())
    assert data["analysis"]["file"] == second and data["analysis"]["generated_at"] == "2026-10-03T20:00:00Z"
    assert first not in json.loads((dist / "manifest.json").read_text())["files"]


def test_the_same_analysis_keeps_its_name(tmp_path):
    dist = built(tmp_path)
    assert add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN) == add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)


def test_an_analysis_needs_a_built_dist(tmp_path):
    with pytest.raises(BuildError, match="Run refresh first"):
        add_analysis(tmp_path / "dist", PDF, "Claude Opus 5.5", WRITTEN)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "data.json").write_text("not json")
    with pytest.raises(BuildError, match="Run refresh first"):
        add_analysis(tmp_path / "dist", PDF, "Claude Opus 5.5", WRITTEN)


def test_a_failure_while_adding_an_analysis_leaves_dist_alone(tmp_path, monkeypatch):
    dist = built(tmp_path)
    before = {path.name: path.read_bytes() for path in dist.iterdir()}

    def broken(folder, snapshot_id):
        raise OSError("disk full")

    monkeypatch.setattr("macro.build.write_manifest", broken)
    with pytest.raises(OSError, match="disk full"):
        add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before


def test_a_hidden_file_left_in_dist_is_neither_listed_nor_a_reason_to_stop(tmp_path):
    dist = built(tmp_path)
    (dist / ".DS_Store").write_bytes(b"left by Finder")
    write_manifest(dist, SNAPSHOT["snapshot_id"])
    assert ".DS_Store" not in json.loads((dist / "manifest.json").read_text())["files"]
    name = add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert sorted(json.loads((dist / "manifest.json").read_text())["files"]) == sorted([name, "data.json", "index.html"])
    assert not (dist / ".DS_Store").exists()


def test_nothing_is_left_behind_after_adding_an_analysis(tmp_path):
    dist = built(tmp_path)
    add_analysis(dist, PDF, "Claude Opus 5.5", WRITTEN)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["dist", "site"]
```

**File: `tests/test_cli.py`**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_build.py tests/test_cli.py`

Expected: `1 error`, with `ImportError: cannot import name 'add_analysis' from 'macro.build'`.

- [ ] **Step 3: Replace the two modules**

**File: `macro/build.py`**

```python
"""Writes dist/: the page files, data.json, the analysis PDF, and a manifest and checksum list of it all."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from macro.errors import BuildError

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
}
INTERNAL = ("manifest.json", "SHA256SUMS")
BUILD_ID_MARK = "{{BUILD_ID}}"  # replaced with the build id, so asset addresses change with every build
STAMPED = ("index.html", "*.js")  # where the mark is filled in: the site's top folder only, never vendor/
ANALYSIS_FILES = "analysis-*.pdf"  # an analysis PDF is named after its own checksum


def write_manifest(dist: Path, snapshot_id: str) -> None:
    """Lists every file the server may serve. Rerun it after adding a file to dist/."""
    files: dict[str, dict] = {}
    for path in sorted(item for item in dist.rglob("*") if item.is_file()):
        inside = path.relative_to(dist)
        name = inside.as_posix()
        if name in INTERNAL or any(part.startswith(".") for part in inside.parts):
            continue  # the manifest and checksum list themselves, and hidden files such as .DS_Store
        content_type = CONTENT_TYPES.get(path.suffix.lower())
        if content_type is None:
            raise BuildError(f"build: no content type for {name}")
        data = path.read_bytes()
        files[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "content_type": content_type,
        }
    manifest = dist / "manifest.json"
    manifest.write_text(json.dumps({"snapshot_id": snapshot_id, "files": files}, indent=2) + "\n", encoding="utf-8")
    lines = [f"{meta['sha256']}  {name}\n" for name, meta in files.items()]
    lines.append(f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}  manifest.json\n")
    (dist / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def work_folders(dist: Path) -> tuple[Path, Path]:
    """The folder to build in and the folder the old dist/ is parked in, both made ready for a new run."""
    staging = dist.with_name(dist.name + ".tmp")
    previous = dist.with_name(dist.name + ".old")
    if previous.exists() and not dist.exists():
        previous.rename(dist)  # an earlier run stopped between the two renames: put the old folder back
    for leftover in (staging, previous):
        if leftover.exists():
            shutil.rmtree(leftover)
    return staging, previous


def swap_in(staging: Path, dist: Path, previous: Path) -> None:
    """Two renames, so dist/ is never missing for longer than the gap between them."""
    if dist.exists():
        dist.rename(previous)
    try:
        staging.rename(dist)
    except OSError:
        if previous.exists():
            previous.rename(dist)
        raise
    shutil.rmtree(previous, ignore_errors=True)


def as_json(snapshot: dict) -> str:
    try:
        return json.dumps(snapshot, separators=(",", ":"), allow_nan=False)
    except ValueError as exc:
        raise BuildError(f"build: the data cannot be written as JSON: {exc}") from None


def build_dist(dist: Path, site: Path, snapshot: dict) -> None:
    """Builds in a temporary folder and swaps it in, so a failure leaves the old dist/ in place."""
    staging, previous = work_folders(dist)
    if site.is_dir():
        shutil.copytree(site, staging, ignore=shutil.ignore_patterns(".*"))
    else:
        staging.mkdir(parents=True)
    (staging / "data.json").write_text(as_json(snapshot), encoding="utf-8")
    build_id = str(snapshot.get("build_id", snapshot["snapshot_id"]))
    for pattern in STAMPED:
        for path in staging.glob(pattern):
            text = path.read_text(encoding="utf-8")
            if BUILD_ID_MARK in text:
                path.write_text(text.replace(BUILD_ID_MARK, build_id), encoding="utf-8")
    write_manifest(staging, snapshot["snapshot_id"])
    swap_in(staging, dist, previous)


def add_analysis(dist: Path, pdf: bytes, model: str, generated_at: str) -> str:
    """Puts the analysis PDF into dist/ and records it in data.json. Returns the PDF's file name.

    The name holds the start of the PDF's checksum. A rewritten analysis therefore gets a new
    address, and no browser shows an old copy it has cached. The work is done on a copy of dist/
    that is swapped in at the end, so a failure leaves dist/ as it was.
    """
    staging, previous = work_folders(dist)
    try:
        snapshot = json.loads((dist / "data.json").read_text(encoding="utf-8"))
        snapshot_id = snapshot["snapshot_id"]
    except (OSError, ValueError, KeyError, TypeError):
        raise BuildError("build: dist/ holds no snapshot to add an analysis to. Run refresh first") from None
    shutil.copytree(dist, staging, ignore=shutil.ignore_patterns(".*"))
    for earlier in staging.glob(ANALYSIS_FILES):
        earlier.unlink()
    name = f"analysis-{hashlib.sha256(pdf).hexdigest()[:12]}.pdf"
    (staging / name).write_bytes(pdf)
    snapshot["analysis"] = {"file": name, "model": model, "generated_at": generated_at}
    (staging / "data.json").write_text(as_json(snapshot), encoding="utf-8")
    write_manifest(staging, snapshot_id)
    swap_in(staging, dist, previous)
    return name
```

**File: `macro/cli.py`**

```python
"""The command line: python -m macro <command>."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from macro import analysis, config
from macro.build import add_analysis, build_dist
from macro.dates import add_months
from macro.errors import AnalysisError, MacroError, SourceError
from macro.facts import build_facts
from macro.fedwatch import FedWatchError
from macro.odds import build_odds
from macro.pdf import build_pdf, moment, page_count
from macro.snapshot import STAMP, build_snapshot
from macro.sources import fomc, futures, nyfed, treasury
from server import serve

CONTRACT_SHIFTS = (-2, -1, 0, 1)  # months around the meeting month whose contracts are fetched


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.HTTP_TIMEOUT,
        follow_redirects=True,
    )


def default_paths() -> dict[str, Path]:
    return {
        "dist": config.DIST_DIR,
        "work": config.WORK_DIR,
        "cache": config.CACHE_DIR,
        "site": config.SITE_DIR,
        "calendar_file": config.DATA_DIR / "fomc_meetings.json",
    }


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def refresh(
    client: httpx.Client,
    now: datetime,
    *,
    dist: Path,
    work: Path,
    cache: Path,
    site: Path,
    calendar_file: Path,
) -> dict:
    """Fetches every source, calculates, and only then replaces dist/."""
    today = now.date()
    meetings = fomc.load(calendar_file)
    ahead = fomc.upcoming(meetings, now)
    if not ahead:
        raise SourceError("FOMC calendar: no future meeting. Update data/fomc_meetings.json")
    target = ahead[0].end

    yields = treasury.load(client, cache / "treasury", today)
    fed = nyfed.load(client, today)
    target_month = (target.year, target.month)
    prices = futures.load(client, [add_months(target_month, shift) for shift in CONTRACT_SHIFTS])
    try:
        odds = build_odds(now, meetings, prices, fed)
    except FedWatchError as exc:
        raise SourceError(f"odds: {exc}") from None

    snapshot = build_snapshot(now, yields, fed, meetings, odds)
    facts = {"snapshot_id": snapshot["snapshot_id"], **build_facts(yields, fed, odds, today)}
    build_dist(dist, site, snapshot)
    work.mkdir(parents=True, exist_ok=True)
    (work / "facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    return {"snapshot": snapshot, "facts": facts, "future_meetings": len(ahead)}


def summary_lines(result: dict) -> list[str]:
    snapshot, facts = result["snapshot"], result["facts"]
    latest, fed, odds = facts["curves"][0], facts["fed_funds"], snapshot["odds"]
    shown = ", ".join(
        f"{tenor} {latest['yields'][tenor]:.2f}" for tenor in ("3M", "2Y", "10Y", "30Y") if tenor in latest["yields"]
    )
    summary = odds["summary"]
    low, high = odds["current_range"]
    lines = [
        f"Snapshot {snapshot['snapshot_id']}",
        f"Yields as of {latest['date']}: {shown}",
        f"Fed funds as of {fed['effr_date']}: EFFR {fed['effr']:.2f}, "
        f"published target {fed['target_lower']:.2f}-{fed['target_upper']:.2f}",
        f"Odds for {odds['meeting']} (priced {odds['priced_on']}, current range {low:.2f}-{high:.2f}): "
        f"cut {summary['cut']}, hold {summary['hold']}, hike {summary['hike']}",
        "Built dist/ (no analysis yet) and work/facts.json",
    ]
    if result["future_meetings"] < 2:
        lines.append("Warning: fewer than two future meetings are listed. Update data/fomc_meetings.json")
    return lines


def read_json(path: Path, missing: str) -> dict:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise AnalysisError(missing) from None
    if not isinstance(content, dict) or not isinstance(content.get("snapshot_id"), str):
        raise AnalysisError(missing)
    return content


def add_the_analysis(*, dist: Path, work: Path) -> dict:
    """Checks work/analysis.json against the snapshot in dist/, draws the PDF and puts it into dist/."""
    again = "Run `python -m macro refresh` first"
    snapshot = read_json(dist / "data.json", f"analysis: dist/ holds no snapshot. {again}")
    facts = read_json(work / "facts.json", f"analysis: work/facts.json is missing or unreadable. {again}")
    if facts["snapshot_id"] != snapshot["snapshot_id"]:
        raise AnalysisError(f"analysis: work/facts.json and dist/ come from different refreshes. {again}")
    written = analysis.load(work / "analysis.json", snapshot["snapshot_id"])
    refreshed_at = datetime.strptime(snapshot["generated_at"], STAMP).replace(tzinfo=timezone.utc)
    pdf = build_pdf(written, facts, refreshed_at)
    name = add_analysis(dist, pdf, written.model, written.written_at.strftime(STAMP))
    return {"analysis": written, "file": name, "bytes": len(pdf), "pages": page_count(pdf)}


def analysis_lines(result: dict) -> list[str]:
    written = result["analysis"]
    texts = written.texts()
    pages = "1 page" if result["pages"] == 1 else f"{result['pages']} pages"
    return [
        f"Analysis for snapshot {written.snapshot_id} by {written.model}, written {moment(written.written_at)}",
        f"{len(texts)} sections, {sum(len(text.split()) for text in texts)} words",
        f"Added {result['file']} to dist/ ({pages}, {max(1, round(result['bytes'] / 1024))} KB)",
        "Read it in `python -m macro preview` before publishing",
    ]


def run_command(label: str, debug: bool, action) -> int:
    """Runs one command and turns a failure into a plain message. `action` returns the lines to print."""
    try:
        lines = action()
    except MacroError as exc:
        if debug:
            raise
        print(f"{label} stopped: {exc}", file=sys.stderr)
        print("dist/ was not changed.", file=sys.stderr)
        return 1
    except Exception as exc:  # a bug or an unforeseen reply: say so plainly
        if debug:
            raise
        print(f"{label} stopped by an unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("Run it again with --debug to see the full error.", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m macro", description="Builds the macros page.")
    commands = parser.add_subparsers(dest="command", required=True)
    debug_help = "show the full error instead of a one-line message"
    refresh_parser = commands.add_parser("refresh", help="fetch the data, calculate, and build dist/")
    refresh_parser.add_argument("--debug", action="store_true", help=debug_help)
    analysis_parser = commands.add_parser("analysis", help="check work/analysis.json, draw the PDF and add it to dist/")
    analysis_parser.add_argument("--debug", action="store_true", help=debug_help)
    preview_parser = commands.add_parser("preview", help="serve dist/ on this Mac, to look at it before publishing")
    preview_parser.add_argument("--port", type=int, default=serve.DEFAULT_PORT, help="port on 127.0.0.1")
    args = parser.parse_args(argv)

    if args.command == "preview":
        dist = default_paths()["dist"]
        if not (dist / "manifest.json").is_file():
            print("Nothing to preview. Run `python -m macro refresh` first.", file=sys.stderr)
            return 1
        try:
            return serve.run(dist, args.port)
        except OSError as exc:
            print(f"Preview cannot use port {args.port}: {exc}. Try --port with another number.", file=sys.stderr)
            return 1

    if args.command == "refresh":

        def refresh_now() -> list[str]:
            with make_client() as client:
                return summary_lines(refresh(client, utc_now(), **default_paths()))

        return run_command("Refresh", args.debug, refresh_now)

    if args.command == "analysis":

        def analyse_now() -> list[str]:
            paths = default_paths()
            return analysis_lines(add_the_analysis(dist=paths["dist"], work=paths["work"]))

        return run_command("Analysis", args.debug, analyse_now)
    return 2
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_build.py tests/test_cli.py`

Expected: `42 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `325 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: the four above. Suggested message: `feat: python -m macro analysis adds the PDF to dist/`.

---

### Task 5: The writer's instructions

**Files:**
- Create: `tests/test_prompt.py`
- Create: `prompts/analysis.md`

`prompts/analysis.md` is what the writer of an analysis is given, together with `work/facts.json`. Keeping it in the project means every analysis follows the same instructions, whoever or whatever writes it.

It tells the writer what each field of the facts file holds, which fields to write, and eight rules. The three that matter most: use only the numbers in the facts file, say plainly what the data cannot show, and read the earlier odds against the target range that was in force on that date.

The last of those came from a trial. A month before this plan was written the target range was a quarter point lower, so a range that reads as "a cut" today was "no change" then. A writer who labels the earlier columns by today's range gets it wrong.

The test keeps the instructions and the checks in step. If a field or a limit changes in `macro/analysis.py` and not in the prompt, a careful writer would still be refused; the test fails first.

- [ ] **Step 1: Write the failing test**

**File: `tests/test_prompt.py`**

```python
"""The writer's instructions and the checks must agree, or a careful writer would still be refused."""
from pathlib import Path

from macro import analysis

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "analysis.md").read_text(encoding="utf-8")


def test_the_prompt_names_every_field_the_checks_know():
    for field in ("snapshot_id", "model", "written_at", *analysis.SECTIONS):
        assert f"`{field}`" in PROMPT, field
    for name in analysis.OUTLOOK_REQUIRED + analysis.OUTLOOK_OPTIONAL:
        assert f"`outlook.{name}`" in PROMPT, name


def test_the_prompt_states_the_word_limits_and_the_refused_characters():
    assert f"{analysis.MIN_WORDS} to {analysis.MAX_WORDS} words" in PROMPT
    for mark in analysis.MARKUP:
        assert mark in PROMPT, mark


def test_the_prompt_tells_the_writer_to_stay_inside_the_facts():
    assert "Use only the numbers in the facts file" in PROMPT
    assert "Plain text only" in PROMPT
    assert "work/facts.json" in PROMPT and "work/analysis.json" in PROMPT
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_prompt.py`

Expected: `1 error`, with `FileNotFoundError` for `prompts/analysis.md`.

- [ ] **Step 3: Write the instructions**

**File: `prompts/analysis.md`**

```markdown
# Writing the macro analysis

You are writing a short analysis of one snapshot of US interest-rate data. It is printed as a PDF next to the numbers it was written from, and read by a few people who follow markets but are not bond specialists.

## What you are given

One file, `work/facts.json`. Every number in it was computed in code and is correct. Read all of it before you write.

| Field | What it holds |
|---|---|
| `snapshot_id` | The snapshot these facts belong to. Copy it into your output unchanged |
| `as_of` | The date of the latest yields |
| `curves` | The Treasury par yield curve, in percent, on five dates: the latest, and one week, one month, three months and one year earlier |
| `spreads_bp` | On each of those dates, in basis points: 10Y minus 2Y, 10Y minus 3M, and 30Y minus 5Y |
| `changes_bp` | The change from each earlier date to the latest, for each tenor, in basis points |
| `fed_funds` | The target range, the effective federal funds rate (EFFR) and its date, and the last change in the range |
| `odds` | The chance, in percent, of each target range after the next FOMC decision, as priced now and one day, one week and one month earlier. `current_range` is the range in force now. `summary` adds the "now" column up into cut, hold and hike, and describes that column only. These are the project's own calculation from fed funds futures prices |
| `next_meeting` | The date of that decision and how many days away it is |

## What to write

Write one JSON object to `work/analysis.json` with exactly these fields and no others:

| Field | Content |
|---|---|
| `snapshot_id` | Copied from `work/facts.json` |
| `model` | Your model's name as it should be printed, for example `Claude Opus 5.5` |
| `written_at` | The time you finish, in UTC, in the form `2026-10-04T01:30:00Z`. In a terminal, `date -u +%Y-%m-%dT%H:%M:%SZ` prints it |
| `curve_now` | What the latest curve says about economic conditions |
| `curve_change` | What the change over the four earlier dates says about the outlook |
| `rate_odds` | What the cut, hold and hike odds say, and how they have moved |
| `outlook.bonds` | The likely effect on bonds |
| `outlook.rates` | The likely effect on short-term interest rates and money markets |
| `outlook.fx` | The likely effect on the dollar |
| `outlook.equities` | The likely effect on shares |
| `outlook.other` | Optional. Anything else worth noting. Leave the field out if there is nothing |

`outlook` is an object holding the `bonds`, `rates`, `fx`, `equities` and optional `other` texts.

## Rules

1. **Use only the numbers in the facts file.** Do not bring in anything from outside it: no news, no data releases, no events, no levels of other markets, no dates of things that happened. You do not know them, and a reader cannot check them.
2. **Keep every number's value and unit**: percent for yields and odds, basis points for spreads and changes. Write yields and rates with two decimals (4.00%), odds with one (27.0%), and dates in words (28 October 2026). You may compare two given numbers ("higher than", "about twice"). Do not work out new figures.
3. **Read the earlier odds against the range in force then.** An earlier column gives the chance of each target range as priced on that column's date, and the range in force may have been different on that date. `fed_funds.last_change` gives the day the present range took effect and the range before it. For an earlier column, name the target range. Call it a cut, a hold or a rise only once you have checked which range was in force on that date.
4. **Say what the data cannot show.** The facts hold no exchange rates and no share prices. In `outlook.fx` and `outlook.equities`, say so, and reason only from the direction of rates.
5. **State uncertainty plainly.** These are readings of market prices, not forecasts. Say "suggests" or "is consistent with" where that is the truth. Never tell the reader to buy or sell anything.
6. **Plain text only.** Each text is one paragraph. No Markdown, no lists, no headings and no line breaks. The characters `*`, `` ` ``, `#`, `<`, `>` and `|` are rejected.
7. **Each text is 40 to 160 words.** Aim for 80 to 120.
8. **Write plainly.** Short sentences and common words. Explain a term the first time you use it if a general reader might not know it. Do not repeat the same point in two sections.

## How it is checked

`python -m macro analysis` reads your file. It stops and names the problem if the file is not valid JSON, a field is missing or unknown, a text is too short, too long or not plain text, or `snapshot_id` does not match the snapshot in `dist/`. Fix the file and run the command again.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_prompt.py`

Expected: `3 passed`

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest`

Expected: `328 passed`

- [ ] **Step 6: Checkpoint**

Stop and report. Do not run git. Files: `tests/test_prompt.py`, `prompts/analysis.md`. Suggested message: `feat: instructions for whoever writes the analysis`.

---

### Task 6: Try it

This task runs the real commands and has a real analysis written. It adds no code. The refresh makes six read-only requests.

- [ ] **Step 1: Build**

Run: `.venv/bin/python -m macro refresh`

Expected: the five summary lines, ending `Built dist/ (no analysis yet) and work/facts.json`.

- [ ] **Step 2: Confirm the command refuses to run without a fresh analysis**

Run: `.venv/bin/python -m macro analysis`

Expected: `Analysis stopped:` and a reason, then `dist/ was not changed.` The reason is that `work/analysis.json` does not exist, or, if one is left from an earlier refresh, that it was written for another snapshot.

- [ ] **Step 3: Have the analysis written**

In the Claude Code session, dispatch one subagent on the most capable model with this task and nothing else:

> Read `/Users/himanshusrivastava/Projects/Macros/prompts/analysis.md` and follow it exactly. The facts are in `/Users/himanshusrivastava/Projects/Macros/work/facts.json`. Write your analysis to `/Users/himanshusrivastava/Projects/Macros/work/analysis.json`. Change no other file and run no command other than `date`.

Expected: `work/analysis.json` exists.

- [ ] **Step 4: Check it and draw the PDF**

Run: `.venv/bin/python -m macro analysis`

Expected: four lines, such as:

```
Analysis for snapshot 20261004T002349Z by Claude Opus 5.5, written 4 Oct 2026, 01:30 UTC
7 sections, 660 words
Added analysis-b4bf08d128e4.pdf to dist/ (2 pages, 6 KB)
Read it in `python -m macro preview` before publishing
```

If it prints `Analysis stopped:`, the reason names the field. Send the reason back to the writer, have the file corrected, and run the command again.

- [ ] **Step 5: Start the preview in one terminal**

Run: `.venv/bin/python -m macro preview`

- [ ] **Step 6: Look at it**

Open `http://127.0.0.1:8081/` in a browser.

| Try | Expect |
|---|---|
| The header | "Explain Macros" is a solid button, beside "AI-written analysis of this data" and the date |
| Press the button | The PDF opens in a new tab |
| Read the PDF | The numbers under "Data used" match the page. Every claim in the text can be traced to those numbers. Nothing is stated that the data cannot show |
| The foot of the page | A line says the analysis was written by an AI model, names it, and says it can be wrong |

The owner reads the whole PDF. If anything in it is wrong or overconfident, have the analysis rewritten and run Step 4 again; the PDF gets a new address, so the browser shows the new one.

- [ ] **Step 7: Stop the preview**

Press Ctrl-C in the first terminal.

- [ ] **Step 8: Checkpoint**

Stop and report what the owner saw. Nothing new to commit: `work/` and `dist/` are not in git.
