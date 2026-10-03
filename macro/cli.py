"""The command line: python -m macro <command>."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from macro import config
from macro.build import build_dist
from macro.errors import SourceError
from macro.facts import build_facts
from macro.fedwatch import FedWatchError, add_months
from macro.odds import build_odds
from macro.snapshot import build_snapshot
from macro.sources import fomc, futures, nyfed, treasury

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
    ends = [meeting.end for meeting in meetings]
    future = [end for end in ends if end > today]
    if not future:
        raise SourceError("FOMC calendar: no future meeting. Update data/fomc_meetings.json")
    target = future[0]

    yields = treasury.load(client, cache / "treasury", today)
    fed = nyfed.load(client, today)
    target_month = (target.year, target.month)
    prices = futures.load(client, [add_months(target_month, shift) for shift in CONTRACT_SHIFTS])
    try:
        odds = build_odds(target, ends, prices, fed)
    except FedWatchError as exc:
        raise SourceError(f"odds: {exc}") from None

    snapshot = build_snapshot(now, yields, fed, meetings, odds)
    facts = {"snapshot_id": snapshot["snapshot_id"], **build_facts(yields, fed, odds, today)}
    build_dist(dist, site, snapshot)
    work.mkdir(parents=True, exist_ok=True)
    (work / "facts.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    return {"snapshot": snapshot, "facts": facts, "future_meetings": len(future)}


def summary_lines(result: dict) -> list[str]:
    snapshot, facts = result["snapshot"], result["facts"]
    latest, fed, odds = facts["curves"][0], facts["fed_funds"], snapshot["odds"]
    shown = ", ".join(
        f"{tenor} {latest['yields'][tenor]:.2f}" for tenor in ("3M", "2Y", "10Y", "30Y") if tenor in latest["yields"]
    )
    summary = odds["summary"]
    lines = [
        f"Snapshot {snapshot['snapshot_id']}",
        f"Yields as of {latest['date']}: {shown}",
        f"Fed funds as of {fed['effr_date']}: EFFR {fed['effr']:.2f}, "
        f"target {fed['target_lower']:.2f}-{fed['target_upper']:.2f}",
        f"Odds for {odds['meeting']} (priced {odds['priced_on']}): "
        f"cut {summary['cut']}, hold {summary['hold']}, hike {summary['hike']}",
        "Built dist/ (no analysis yet) and work/facts.json",
    ]
    if result["future_meetings"] < 2:
        lines.append("Warning: fewer than two future meetings are listed. Update data/fomc_meetings.json")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m macro", description="Builds the macros page.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("refresh", help="fetch the data, calculate, and build dist/")
    args = parser.parse_args(argv)

    if args.command == "refresh":
        try:
            with make_client() as client:
                result = refresh(client, utc_now(), **default_paths())
        except SourceError as exc:
            print(f"Refresh stopped: {exc}", file=sys.stderr)
            print("dist/ was not changed.", file=sys.stderr)
            return 1
        print("\n".join(summary_lines(result)))
        return 0
    return 2
