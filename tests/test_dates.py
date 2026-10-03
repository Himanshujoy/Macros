from datetime import date

from macro.dates import months_back, on_or_before


def test_months_back_keeps_the_day_when_it_exists():
    assert months_back(date(2026, 10, 2), 1) == date(2026, 9, 2)
    assert months_back(date(2026, 10, 2), 12) == date(2025, 10, 2)


def test_months_back_clamps_to_the_end_of_a_shorter_month():
    assert months_back(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert months_back(date(2024, 2, 29), 12) == date(2023, 2, 28)


def test_months_back_crosses_a_year_boundary():
    assert months_back(date(2027, 1, 15), 3) == date(2026, 10, 15)


def test_on_or_before_finds_the_latest_day_not_after_the_limit():
    days = [date(2026, 9, 24), date(2026, 9, 25), date(2026, 10, 1)]
    assert on_or_before(days, date(2026, 9, 27)) == date(2026, 9, 25)
    assert on_or_before(days, date(2026, 9, 25)) == date(2026, 9, 25)
    assert on_or_before(days, date(2026, 9, 1)) is None
