from datetime import date

import pytest

from macro import fedwatch
from samples import MEETING_ENDS, PRICES, effr_rows

RATES = {date.fromisoformat(row["effectiveDate"]): row["percentRate"] for row in effr_rows()}
MEETING_MONTHS = {(day.year, day.month) for day in MEETING_ENDS}
TARGET = date(2026, 10, 28)


def percent(distribution):
    return {moves: round(100 * share, 1) for moves, share in sorted(distribution.items())}


def has_meeting(month):
    return month in MEETING_MONTHS


def test_add_months_crosses_year_boundaries():
    assert fedwatch.add_months((2026, 12), 1) == (2027, 1)
    assert fedwatch.add_months((2027, 1), -1) == (2026, 12)
    assert fedwatch.add_months((2026, 10), -2) == (2026, 8)


def test_month_average_counts_calendar_days_and_carries_over_weekends():
    assert fedwatch.month_average(RATES, (2026, 8)) == pytest.approx(3.63)


def test_month_average_weights_a_mid_month_change_by_calendar_days():
    # September 2026: 16 days at 3.63, then 14 days at 3.88.
    assert fedwatch.month_average(RATES, (2026, 9)) == pytest.approx((16 * 3.63 + 14 * 3.88) / 30)


def test_month_average_without_any_rate_is_a_missing_price():
    with pytest.raises(fedwatch.MissingPrice):
        fedwatch.month_average({}, (2026, 8))


@pytest.mark.parametrize(
    "moves, expected",
    [
        (0.25, {0: 0.75, 1: 0.25}),
        (1.25, {1: 0.75, 2: 0.25}),
        (-0.25, {-1: 0.25, 0: 0.75}),
        (-1.5, {-2: 0.5, -1: 0.5}),
        (1.0, {1: 1.0}),
        (0.0, {0: 1.0}),
    ],
)
def test_split_shares_a_move_count_between_two_neighbours(moves, expected):
    assert fedwatch.split(moves) == pytest.approx(expected)


def test_combine_adds_move_counts_across_meetings():
    combined = fedwatch.combine({0: 0.5, 1: 0.5}, {0: 0.75, 1: 0.25})
    assert combined == pytest.approx({0: 0.375, 1: 0.5, 2: 0.125})


def test_rule_one_works_back_from_an_anchor_month_after_the_meeting():
    implied = {(2026, 10): 100 - 96.12, (2026, 11): 100 - 96.07}
    moves = fedwatch.expected_moves(date(2026, 10, 28), implied.__getitem__, has_meeting)
    assert moves == pytest.approx(0.2214, abs=1e-4)


def test_rule_two_works_forward_from_an_anchor_month_before_the_meeting():
    implied = {(2026, 11): 100 - 96.07, (2026, 12): 100 - 95.925}
    moves = fedwatch.expected_moves(date(2026, 12, 9), implied.__getitem__, has_meeting)
    assert moves == pytest.approx(0.8173, abs=1e-4)


def test_a_meeting_month_with_no_anchor_neighbour_is_an_error():
    with pytest.raises(fedwatch.FedWatchError, match="no anchor"):
        fedwatch.expected_moves(date(2026, 10, 28), lambda month: 4.0, lambda month: True)


def test_rule_two_cannot_use_a_meeting_on_the_last_day_of_the_month():
    def only_this_and_next(month):
        return month in {(2026, 10), (2026, 11)}

    with pytest.raises(fedwatch.FedWatchError, match="last day"):
        fedwatch.expected_moves(date(2026, 10, 31), lambda month: 4.0, only_this_and_next)


def test_check_row_2_october():
    result = fedwatch.distribution(date(2026, 10, 2), TARGET, MEETING_ENDS, PRICES, RATES)
    assert percent(result) == {0: 77.9, 1: 22.1}


def test_check_row_25_september():
    result = fedwatch.distribution(date(2026, 9, 25), TARGET, MEETING_ENDS, PRICES, RATES)
    assert percent(result) == {0: 35.8, 1: 64.2}


def test_check_row_3_september_chains_two_meetings():
    result = fedwatch.distribution(date(2026, 9, 3), TARGET, MEETING_ENDS, PRICES, RATES)
    assert percent(result) == {0: 38.8, 1: 48.7, 2: 12.5}


def test_check_row_3_september_with_cmes_september_price():
    prices = {**PRICES, (2026, 9): {date(2026, 9, 3): 96.3125}}
    result = fedwatch.distribution(date(2026, 9, 3), TARGET, MEETING_ENDS, prices, RATES)
    assert percent(result) == {0: 37.2, 1: 49.7, 2: 13.1}


def test_a_missing_contract_price_is_reported():
    prices = {month: days for month, days in PRICES.items() if month != (2026, 11)}
    with pytest.raises(fedwatch.MissingPrice, match="2026, 11"):
        fedwatch.distribution(date(2026, 10, 2), TARGET, MEETING_ENDS, prices, RATES)


def test_no_pending_meeting_is_an_error():
    with pytest.raises(fedwatch.FedWatchError, match="no meeting"):
        fedwatch.distribution(TARGET, TARGET, MEETING_ENDS, PRICES, RATES)
