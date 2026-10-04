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
