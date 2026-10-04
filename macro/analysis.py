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
