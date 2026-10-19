"""Draws the analysis PDF: the data the analysis was written from, the analysis, and the notices.

The numbers come from work/facts.json, never from the analysis text. See section 6.5 of the spec.
"""
from __future__ import annotations

import math
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


# Series colours for the curve chart, in a fixed order: the latest curve first.
SERIES = [(42, 120, 214), (235, 104, 52), (27, 175, 122), (237, 161, 0), (232, 123, 164)]
GRID = (225, 224, 217)


def round_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """Round axis values that cover low to high."""
    if high <= low:
        low, high = low - 0.5, high + 0.5
    rough = (high - low) / count
    power = 10 ** math.floor(math.log10(rough))
    step = next(f * power for f in (1, 2, 2.5, 5, 10) if f * power >= rough - 1e-12)
    start = math.floor(low / step + 1e-9) * step
    ticks = []
    value = start
    while value <= high + step - 1e-9:
        ticks.append(round(value, 6))
        if value >= high - 1e-9:
            break
        value += step
    return ticks


def tick_text(value: float) -> str:
    return f"{value:g}%"


def chart_room(pdf: Report, height: float) -> None:
    if pdf.will_page_break(height):
        pdf.add_page()


def caption(pdf: Report, text: str) -> None:
    pdf.set_font(FONT, size=9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def curve_chart(pdf: Report, facts: dict) -> None:
    """The yield curve on all five dates in one chart, tenors evenly spaced."""
    curves = facts["curves"]
    tenors = list(curves[0]["yields"])
    values = [value for curve in curves for value in curve["yields"].values() if value is not None]
    if len(tenors) < 2 or not values:
        return
    chart_room(pdf, 88)
    caption(pdf, "Yield curves on the five dates, percent")
    ticks = round_ticks(min(values), max(values))
    low, high = ticks[0], ticks[-1]
    left = pdf.l_margin + 12
    top = pdf.get_y() + 3
    width = pdf.epw - 14
    height = 58
    bottom = top + height

    def x(index: int) -> float:
        return left + index * width / (len(tenors) - 1)

    def y(value: float) -> float:
        return bottom - (value - low) / (high - low) * height

    pdf.set_font(FONT, size=7.5)
    pdf.set_line_width(0.15)
    for tick in ticks:
        pdf.set_draw_color(*GRID)
        pdf.line(left, y(tick), left + width, y(tick))
        label = tick_text(tick)
        pdf.set_text_color(*MUTED)
        pdf.text(left - 2 - pdf.get_string_width(label), y(tick) + 1, label)
    for index, tenor in enumerate(tenors):
        pdf.text(x(index) - pdf.get_string_width(tenor) / 2, bottom + 4.5, tenor)

    # Oldest first, so the latest curve is drawn on top.
    for order in range(len(curves) - 1, -1, -1):
        curve = curves[order]
        points = [(x(i), y(curve["yields"][t])) for i, t in enumerate(tenors) if curve["yields"].get(t) is not None]
        if len(points) < 2:
            continue
        pdf.set_draw_color(*SERIES[order % len(SERIES)])
        pdf.set_line_width(0.7 if order == 0 else 0.4)
        pdf.polyline(points, style="D")

    # Legend: a short line in the series colour, then the date and its label.
    pdf.set_line_width(0.7)
    pdf.set_font(FONT, size=7.5)
    pdf.set_text_color(*INK)
    lx = left
    ly = bottom + 10
    for order, curve in enumerate(curves):
        label = f"{day(curve['date'])}, {curve['label']}"
        if lx + 6.5 + pdf.get_string_width(label) > pdf.l_margin + pdf.epw:
            lx = left  # no room left on this row: start another
            ly += 5
        pdf.set_draw_color(*SERIES[order % len(SERIES)])
        pdf.line(lx, ly - 1, lx + 5, ly - 1)
        pdf.text(lx + 6.5, ly, label)
        lx += 6.5 + pdf.get_string_width(label) + 5
    pdf.set_line_width(0.2)
    pdf.set_y(ly + 4)


def odds_chart(pdf: Report, odds: dict, meeting: dict) -> None:
    """Probability of each target range after the decision, as columns: the FedWatch view."""
    outcomes = odds["outcomes"]
    if not outcomes:
        return
    chart_room(pdf, 72)
    caption(pdf, f"Target range probabilities for the {day(meeting['date'])} decision, now, percent")
    left = pdf.l_margin + 12
    top = pdf.get_y() + 4
    width = pdf.epw - 14
    height = 45
    bottom = top + height

    def y(percent: float) -> float:
        return bottom - percent / 100 * height

    pdf.set_font(FONT, size=7.5)
    pdf.set_line_width(0.15)
    for tick in (0, 25, 50, 75, 100):
        pdf.set_draw_color(*(RULE if tick == 0 else GRID))
        pdf.line(left, y(tick), left + width, y(tick))
        label = f"{tick}%"
        pdf.set_text_color(*MUTED)
        pdf.text(left - 2 - pdf.get_string_width(label), y(tick) + 1, label)

    slot = width / len(outcomes)
    bar = min(14.0, slot * 0.5)
    for index, outcome in enumerate(outcomes):
        centre = left + slot * (index + 0.5)
        value = outcome["now"] or 0.0
        pdf.set_fill_color(*SERIES[0])
        if value > 0:
            pdf.rect(centre - bar / 2, y(value), bar, bottom - y(value), style="F")
        pdf.set_font(FONT, style="B", size=8.5)
        pdf.set_text_color(*INK)
        label = f"{value:.1f}%"
        pdf.text(centre - pdf.get_string_width(label) / 2, y(value) - 1.5, label)
        pdf.set_font(FONT, size=7.5)
        name = band(outcome["range"])
        pdf.text(centre - pdf.get_string_width(name) / 2, bottom + 4.5, name)
        if outcome["range"][0] == odds["current_range"][0]:
            pdf.set_text_color(*MUTED)
            pdf.text(centre - pdf.get_string_width("current") / 2, bottom + 8.5, "current")
    pdf.set_y(bottom + 12)


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
    curve_chart(pdf, facts)
    table(pdf, "Curve spreads, basis points", spread_rows(facts), first=26)
    paragraph(pdf, fed_funds_sentence(facts["fed_funds"]))
    table(
        pdf,
        f"Odds for the FOMC decision of {day(meeting['date'])}, {away(meeting['days_away'])}, percent",
        odds_rows(odds),
        first=58,
    )
    paragraph(pdf, f"Cut {summary['cut']:.1f}%, hold {summary['hold']:.1f}%, hike {summary['hike']:.1f}%.")
    odds_chart(pdf, odds, meeting)

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
