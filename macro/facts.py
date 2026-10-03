"""The numbers handed to the analysis writer and printed in the PDF. Pure functions."""
from __future__ import annotations

from datetime import date, timedelta

from macro.dates import months_back, on_or_before
from macro.errors import SourceError
from macro.sources.nyfed import FedFundsTable
from macro.sources.treasury import YieldTable

SPREADS = [("10Y-2Y", "10Y", "2Y"), ("10Y-3M", "10Y", "3M"), ("30Y-5Y", "30Y", "5Y")]


def basis_points(later: float | None, earlier: float | None) -> int | None:
    if later is None or earlier is None:
        return None
    return round((later - earlier) * 100)


def curves_on_lookback_dates(yields: YieldTable) -> list[dict]:
    """The curve on the latest date and one week, one month, three months and one year earlier."""
    latest = yields.dates[-1]
    wanted = [
        ("latest", latest),
        ("1 week earlier", latest - timedelta(days=7)),
        ("1 month earlier", months_back(latest, 1)),
        ("3 months earlier", months_back(latest, 3)),
        ("1 year earlier", months_back(latest, 12)),
    ]
    curves = []
    for label, target in wanted:
        day = on_or_before(yields.dates, target)
        if day is None:
            raise SourceError(f"facts: no yield data on or before {target}")
        index = yields.dates.index(day)
        points = {
            tenor.label: yields.values[tenor.label][index]
            for tenor in yields.tenors
            if yields.values[tenor.label][index] is not None
        }
        curves.append({"label": label, "date": day.isoformat(), "yields": points})
    return curves


def last_target_change(fed: FedFundsTable) -> dict | None:
    """The first day of the current target, with the range before and after."""
    current = (fed.target_lower[-1], fed.target_upper[-1])
    for index in range(len(fed.dates) - 1, 0, -1):
        before = (fed.target_lower[index - 1], fed.target_upper[index - 1])
        if before != current:
            return {"date": fed.dates[index].isoformat(), "from": list(before), "to": list(current)}
    return None


def build_facts(yields: YieldTable, fed: FedFundsTable, odds: dict, today: date) -> dict:
    curves = curves_on_lookback_dates(yields)
    newest = curves[0]
    spreads = [
        {
            "label": curve["label"],
            "date": curve["date"],
            **{
                name: basis_points(curve["yields"].get(long_leg), curve["yields"].get(short_leg))
                for name, long_leg, short_leg in SPREADS
            },
        }
        for curve in curves
    ]
    changes = [
        {
            "label": curve["label"],
            "from": curve["date"],
            "to": newest["date"],
            "by_tenor": {
                tenor: basis_points(value, curve["yields"][tenor])
                for tenor, value in newest["yields"].items()
                if tenor in curve["yields"]
            },
        }
        for curve in curves[1:]
    ]
    meeting = date.fromisoformat(odds["meeting"])
    return {
        "as_of": newest["date"],
        "curves": curves,
        "spreads_bp": spreads,
        "changes_bp": changes,
        "fed_funds": {
            "target_lower": fed.target_lower[-1],
            "target_upper": fed.target_upper[-1],
            "effr": fed.effr[-1],
            "effr_date": fed.dates[-1].isoformat(),
            "last_change": last_target_change(fed),
        },
        "odds": odds,
        "next_meeting": {"date": meeting.isoformat(), "days_away": (meeting - today).days},
    }
