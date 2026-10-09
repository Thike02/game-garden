from datetime import date

from game_garden.pricing import time_weighted_average


def test_prices_carry_forward_until_next_change():
    # 10 days: 6 days at 2300, then 4 days at 1150
    points = [(date(2026, 1, 1), 2300), (date(2026, 1, 7), 1150)]
    avg = time_weighted_average(points, today=date(2026, 1, 10), days=10)
    assert avg == (2300 * 6 + 1150 * 4) / 10


def test_price_before_window_counts_from_window_start():
    points = [(date(2025, 1, 1), 2300), (date(2026, 1, 9), 1150)]
    avg = time_weighted_average(points, today=date(2026, 1, 10), days=10)
    assert avg == (2300 * 8 + 1150 * 2) / 10


def test_history_shorter_than_window():
    points = [(date(2026, 1, 9), 1000), (date(2026, 1, 10), 500)]
    assert time_weighted_average(points, today=date(2026, 1, 10), days=365) == 750


def test_future_points_are_ignored():
    points = [(date(2026, 1, 1), 1000), (date(2026, 2, 1), 1)]
    assert time_weighted_average(points, today=date(2026, 1, 10), days=10) == 1000


def test_no_history():
    assert time_weighted_average([], today=date(2026, 1, 10)) is None


def test_matches_parabox_example():
    # Real Patrick's Parabox history (JPY); 365 days ending 2026-10-09 (2025-10-10 .. 2026-10-09).
    points = [
        (date(2025, 9, 1), 2300),
        (date(2025, 12, 19), 1150),
        (date(2026, 1, 6), 2300),
        (date(2026, 1, 17), 1150),
        (date(2026, 1, 31), 2300),
        (date(2026, 3, 20), 1725),
        (date(2026, 3, 27), 2300),
        (date(2026, 5, 29), 1150),
        (date(2026, 6, 5), 2300),
        (date(2026, 6, 26), 1150),
        (date(2026, 7, 10), 2300),
        (date(2026, 10, 2), 1840),
        (date(2026, 10, 9), 2300),
    ]
    assert round(time_weighted_average(points, today=date(2026, 10, 9), days=365)) == 2113
