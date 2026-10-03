"""US Treasury daily par yield curve rates, one CSV file per year."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx

from macro.errors import SourceError

FIRST_YEAR = 1990
YEAR_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
_HEADER = re.compile(r"^(\d+(?:\.\d+)?) (Mo|Month|Yr)$")


@dataclass(frozen=True)
class Tenor:
    label: str
    years: float


@dataclass(frozen=True)
class YieldTable:
    """Yields by tenor. Every list in `values` is aligned with `dates`; None means not published."""

    tenors: list[Tenor]
    dates: list[date]
    values: dict[str, list[float | None]]


ParsedYear = tuple[list[Tenor], list[tuple[date, dict[str, float | None]]]]


def parse_tenor(header: str) -> Tenor:
    """Turns a column heading such as "1.5 Month" or "10 Yr" into a tenor."""
    match = _HEADER.match(header.strip())
    if not match:
        raise SourceError(f"Treasury: unknown column {header!r}")
    number, unit = match.group(1), match.group(2)
    if unit == "Yr":
        return Tenor(f"{number}Y", float(number))
    return Tenor(f"{number}M", float(number) / 12)


def parse_year_csv(text: str) -> ParsedYear:
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or header[0].strip() != "Date":
        raise SourceError("Treasury: the file does not start with a Date column")
    tenors = [parse_tenor(name) for name in header[1:]]
    rows: list[tuple[date, dict[str, float | None]]] = []
    for line in reader:
        if not line or not line[0].strip():
            continue
        try:
            day = datetime.strptime(line[0].strip(), "%m/%d/%Y").date()
        except ValueError:
            raise SourceError(f"Treasury: bad date {line[0]!r}") from None
        values: dict[str, float | None] = {}
        for tenor, cell in zip(tenors, line[1:]):
            cell = cell.strip()
            if cell in ("", "N/A"):
                values[tenor.label] = None
                continue
            try:
                values[tenor.label] = float(cell)
            except ValueError:
                raise SourceError(f"Treasury: bad value {cell!r} on {day}") from None
        rows.append((day, values))
    return tenors, rows


def build_table(parsed: list[ParsedYear]) -> YieldTable:
    tenors: dict[str, Tenor] = {}
    by_date: dict[date, dict[str, float | None]] = {}
    for year_tenors, rows in parsed:
        for tenor in year_tenors:
            tenors.setdefault(tenor.label, tenor)
        for day, values in rows:
            by_date[day] = values
    if not by_date:
        raise SourceError("Treasury: no rows")
    ordered = sorted(tenors.values(), key=lambda tenor: tenor.years)
    dates = sorted(by_date)
    values = {tenor.label: [by_date[day].get(tenor.label) for day in dates] for tenor in ordered}
    return YieldTable(ordered, dates, values)


def fetch_year(client: httpx.Client, year: int) -> str:
    try:
        response = client.get(YEAR_URL.format(year=year))
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SourceError(f"Treasury: the {year} download failed: {exc}") from None
    return response.text


def load(client: httpx.Client, cache_dir: Path, today: date) -> YieldTable:
    """Every year from 1990. Past years come from the cache; the current year is always fetched."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    fresh = {today.year, today.year - 1} if today.month == 1 else {today.year}
    parsed: list[ParsedYear] = []
    for year in range(FIRST_YEAR, today.year + 1):
        path = cache_dir / f"{year}.csv"
        if year in fresh or not path.exists():
            text = fetch_year(client, year)
            result = parse_year_csv(text)  # parse before caching, so a bad file is never cached
            path.write_text(text, encoding="utf-8")
        else:
            result = parse_year_csv(path.read_text(encoding="utf-8"))
        if not result[1] and year < today.year:
            raise SourceError(f"Treasury: {year} has no rows")
        parsed.append(result)
    return build_table(parsed)
