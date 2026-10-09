from datetime import date, datetime

from game_garden.itad import PricePoint
from game_garden.wishlist_sync import daily_points


def point(timestamp: str, price: int) -> PricePoint:
    return PricePoint(
        at=datetime.fromisoformat(timestamp), price=price, regular_price=2300, discount_pct=0, currency="JPY"
    )


def test_last_change_of_the_day_wins():
    points = [point("2026-10-01T10:00:00+09:00", 2300), point("2026-10-01T20:00:00+09:00", 1840)]
    assert daily_points(points)[date(2026, 10, 1)].price == 1840


def test_days_follow_japan_time():
    # 2026-10-01 20:00 UTC is already 2026-10-02 in Japan.
    days = daily_points([point("2026-10-01T20:00:00+00:00", 1840)])
    assert list(days) == [date(2026, 10, 2)]
