"""Assembles the content of data.json, the one file the page reads."""
from __future__ import annotations

from datetime import datetime

from macro.sources.fomc import Meeting, upcoming
from macro.sources.nyfed import FedFundsTable
from macro.sources.treasury import YieldTable

STAMP = "%Y-%m-%dT%H:%M:%SZ"


def snapshot_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def build_snapshot(
    now: datetime,
    yields: YieldTable,
    fed: FedFundsTable,
    meetings: list[Meeting],
    odds: dict,
) -> dict:
    identity = snapshot_id(now)
    return {
        "snapshot_id": identity,
        "build_id": identity,
        "generated_at": now.strftime(STAMP),
        "yields": {
            "as_of": yields.dates[-1].isoformat(),
            "tenors": [{"label": tenor.label, "years": round(tenor.years, 4)} for tenor in yields.tenors],
            "dates": [day.isoformat() for day in yields.dates],
            "values": [yields.values[tenor.label] for tenor in yields.tenors],
        },
        "fed_funds": {
            "as_of": fed.dates[-1].isoformat(),
            "dates": [day.isoformat() for day in fed.dates],
            "effr": fed.effr,
            "target_lower": fed.target_lower,
            "target_upper": fed.target_upper,
        },
        "fomc": {
            "meetings": [
                {"end": meeting.end.isoformat(), "statement_at": meeting.statement_at.strftime(STAMP)}
                for meeting in upcoming(meetings, now)
            ]
        },
        "odds": odds,
        "analysis": None,
    }
