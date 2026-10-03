"""FOMC meeting dates, from the fixed list in data/fomc_meetings.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from macro.errors import SourceError

NEW_YORK = ZoneInfo("America/New_York")
STATEMENT_TIME = time(14, 0)


@dataclass(frozen=True, order=True)
class Meeting:
    end: date

    @property
    def statement_at(self) -> datetime:
        """The scheduled statement: 2:00 p.m. in New York on the last day, given in UTC."""
        local = datetime.combine(self.end, STATEMENT_TIME, tzinfo=NEW_YORK)
        return local.astimezone(timezone.utc)


def load(path: Path) -> list[Meeting]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        days = [date.fromisoformat(text) for text in raw["meetings"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SourceError(f"FOMC calendar: cannot read {path.name}: {exc}") from None
    if len({(day.year, day.month) for day in days}) != len(days):
        raise SourceError("FOMC calendar: two meetings in one month")
    return sorted(Meeting(day) for day in days)


def upcoming(meetings: list[Meeting], now: datetime) -> list[Meeting]:
    """Meetings whose statement is still ahead of `now`."""
    return [meeting for meeting in meetings if meeting.statement_at > now]
