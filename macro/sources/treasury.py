"""US Treasury daily par yield curve rates, one CSV file per year."""
from __future__ import annotations

import csv
import io
import json
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
INDEX_NAME = "saved.json"  # for each cached year, the day its file was fetched
YIELD_BOUNDS = (-5.0, 30.0)
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
        if len(line) != len(header):
            raise SourceError(f"Treasury: a row has {len(line)} cells where the header has {len(header)}")
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
                value = float(cell)
            except ValueError:
                raise SourceError(f"Treasury: bad value {cell!r} on {day}") from None
            if not YIELD_BOUNDS[0] < value < YIELD_BOUNDS[1]:
                raise SourceError(f"Treasury: implausible yield {cell!r} on {day}")
            values[tenor.label] = value
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


def _read_index(cache_dir: Path) -> dict[str, str]:
    try:
        raw = json.loads((cache_dir / INDEX_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(path: Path, text: str) -> None:
    """Writes through a temporary file, so an interrupted write never leaves half a file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _cached_year(cache_dir: Path, index: dict[str, str], year: int) -> ParsedYear | None:
    """A cached year, but only if its file was fetched after that year ended and still parses."""
    saved = index.get(str(year))
    if not isinstance(saved, str) or saved <= f"{year}-12-31":
        return None
    try:
        return parse_year_csv((cache_dir / f"{year}.csv").read_text(encoding="utf-8"))
    except (OSError, SourceError):
        return None


def load(client: httpx.Client, cache_dir: Path, today: date) -> YieldTable:
    """Every year from 1990.

    A year comes from the cache only if its file was fetched after the year ended. The current
    year, and a past year last fetched before it ended, are fetched again.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    index = _read_index(cache_dir)
    parsed: list[ParsedYear] = []
    for year in range(FIRST_YEAR, today.year + 1):
        result = _cached_year(cache_dir, index, year) if year < today.year else None
        if result is None:
            text = fetch_year(client, year)
            if year == today.year and not text.strip():
                result = ([], [])  # the new year's file can be empty until its first trading day
            else:
                result = parse_year_csv(text)  # parse before caching, so a bad file is never cached
            _write(cache_dir / f"{year}.csv", text)
            index[str(year)] = today.isoformat()
            _write(cache_dir / INDEX_NAME, json.dumps(index, indent=0, sort_keys=True) + "\n")
        if not result[1] and year < today.year:
            raise SourceError(f"Treasury: {year} has no rows")
        parsed.append(result)
    return build_table(parsed)
