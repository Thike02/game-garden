from dataclasses import replace
from datetime import UTC, date, datetime

from game_garden.db import JST
from game_garden.notify import (
    SaleCandidate,
    already_notified,
    build_embed,
    format_price,
    sale_started_on,
    should_notify,
    sort_key,
)

BASE = SaleCandidate(
    game_id=1,
    appid=3470530,
    name="花束を君に贈ろう",
    header_image_url="https://example.com/header.jpg",
    price=3465,
    regular_price=4950,
    discount_pct=30,
    currency="JPY",
    sale_ends_at=datetime(2026, 10, 15, 17, 0, tzinfo=UTC),
    lowest_price=3465,
    average=4613.0,
)


def test_historical_low_needs_a_sale():
    never_on_sale = replace(BASE, price=4950, discount_pct=0, lowest_price=4950)
    assert BASE.is_historical_low
    assert not never_on_sale.is_historical_low


def test_should_notify_threshold_or_low():
    small_sale = replace(BASE, discount_pct=10, price=4455, lowest_price=2000)
    small_sale_at_low = replace(small_sale, lowest_price=4455)
    assert should_notify(BASE, 20)
    assert not should_notify(small_sale, 20)
    assert should_notify(small_sale_at_low, 20)


def test_lows_first_then_bigger_discounts():
    low = replace(BASE, name="low", discount_pct=20, price=3960, lowest_price=3960)
    big = replace(BASE, name="big", discount_pct=50, price=2475, lowest_price=1000)
    mid = replace(BASE, name="mid", discount_pct=30, lowest_price=1000)
    assert [c.name for c in sorted([mid, big, low], key=sort_key)] == ["low", "big", "mid"]


def test_sale_start_is_day_after_last_regular_day():
    history = [(date(2026, 9, 1), 0), (date(2026, 10, 2), 0), (date(2026, 10, 3), 30), (date(2026, 10, 9), 30)]
    assert sale_started_on(history, date(2026, 10, 9)) == date(2026, 10, 3)
    assert sale_started_on([(date(2026, 10, 9), 30)], date(2026, 10, 9)) is None


def test_already_notified_in_this_sale():
    sale_start = date(2026, 10, 3)
    notified = [(datetime(2026, 10, 4, 6, 0, tzinfo=JST), 3465)]
    assert already_notified(notified, sale_start, 3465)
    # Deeper discount during the same sale -> notify again
    assert not already_notified(notified, sale_start, 2970)
    # Notification from a previous sale doesn't count
    assert not already_notified(notified, date(2026, 10, 5), 3465)


def test_embed_for_historical_low():
    embed = build_embed(BASE)
    assert embed["title"] == "🏆 花束を君に贈ろう"
    assert embed["url"] == "https://store.steampowered.com/app/3470530/"
    assert embed["color"] == 0xF1C40F
    assert "~~¥4,950~~ → **¥3,465（-30%）**" in embed["description"]
    assert "過去最安値！" in embed["description"]
    assert "1年の平均 ¥4,613 より25%安い" in embed["description"]
    assert "セール終了：10/16 02:00" in embed["description"]
    assert embed["thumbnail"]["url"] == "https://example.com/header.jpg"


def test_embed_for_regular_sale():
    sale = replace(BASE, lowest_price=2340, sale_ends_at=None, header_image_url=None)
    embed = build_embed(sale)
    assert embed["title"] == "花束を君に贈ろう"
    assert embed["color"] == 0x2ECC71
    assert "最安値 ¥2,340" in embed["description"]
    assert "セール終了" not in embed["description"]
    assert "thumbnail" not in embed


def test_format_price():
    assert format_price(3465, "JPY") == "¥3,465"
    assert format_price(1999, "USD") == "19.99 USD"
