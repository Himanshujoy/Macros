import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from macro.errors import SourceError
from macro.sources import fomc

CALENDAR = Path(__file__).parent.parent / "data" / "fomc_meetings.json"


def test_the_shipped_calendar_loads_in_order():
    ends = [meeting.end for meeting in fomc.load(CALENDAR)]
    assert ends == sorted(ends)
    assert date(2026, 10, 28) in ends
    assert date(2027, 12, 8) in ends


def test_statement_time_is_two_pm_new_york_in_utc():
    daylight = fomc.Meeting(date(2026, 10, 28)).statement_at
    standard = fomc.Meeting(date(2026, 12, 9)).statement_at
    assert daylight == datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    assert standard == datetime(2026, 12, 9, 19, 0, tzinfo=timezone.utc)


def test_upcoming_keeps_meetings_whose_statement_is_still_ahead():
    meetings = [fomc.Meeting(date(2026, 9, 16)), fomc.Meeting(date(2026, 10, 28)), fomc.Meeting(date(2026, 12, 9))]
    just_before = datetime(2026, 10, 28, 17, 59, tzinfo=timezone.utc)
    at_the_statement = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
    assert [m.end for m in fomc.upcoming(meetings, just_before)] == [date(2026, 10, 28), date(2026, 12, 9)]
    assert [m.end for m in fomc.upcoming(meetings, at_the_statement)] == [date(2026, 12, 9)]


def test_two_meetings_in_one_month_are_rejected(tmp_path):
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps({"meetings": ["2026-10-07", "2026-10-28"]}))
    with pytest.raises(SourceError, match="one month"):
        fomc.load(path)


@pytest.mark.parametrize("text", ["not json", "{}", '{"meetings": ["28 Oct"]}'])
def test_a_broken_calendar_file_is_a_source_error(tmp_path, text):
    path = tmp_path / "calendar.json"
    path.write_text(text)
    with pytest.raises(SourceError):
        fomc.load(path)


def test_a_missing_calendar_file_is_a_source_error(tmp_path):
    with pytest.raises(SourceError):
        fomc.load(tmp_path / "absent.json")
