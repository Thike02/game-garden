import json
from datetime import UTC, datetime

import httpx
import pytest

from game_garden.steam import API_BASE, SteamClient, SteamError, SteamPrivateProfileError, parse_store_price


def make_client(handler) -> SteamClient:
    http = httpx.Client(base_url=API_BASE, transport=httpx.MockTransport(handler))
    return SteamClient("test-key", http=http, max_retries=0)


def test_owned_games_parsed():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/IPlayerService/GetOwnedGames/v1/"
        assert request.url.params["key"] == "test-key"
        assert request.url.params["skip_unvetted_apps"] == "0"
        return httpx.Response(
            200,
            json={
                "response": {
                    "game_count": 2,
                    "games": [
                        {"appid": 10, "name": "Counter-Strike", "playtime_forever": 120, "rtime_last_played": 1700000000},
                        {"appid": 20, "name": "Never Played", "playtime_forever": 0, "rtime_last_played": 0},
                    ],
                }
            },
        )

    games = make_client(handler).get_owned_games("7656")
    assert [g.appid for g in games] == [10, 20]
    assert games[0].playtime_minutes == 120
    assert games[0].last_played_at == datetime.fromtimestamp(1700000000, tz=UTC)
    assert games[1].last_played_at is None
    assert games[0].header_image_url.endswith("/apps/10/header.jpg")


def test_owned_games_private_profile():
    client = make_client(lambda request: httpx.Response(200, json={"response": {}}))
    with pytest.raises(SteamPrivateProfileError):
        client.get_owned_games("7656")


def test_player_achievements_only_unlocked():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "playerstats": {
                    "success": True,
                    "achievements": [
                        {"apiname": "WIN", "achieved": 1, "unlocktime": 1700000000},
                        {"apiname": "LOSE", "achieved": 0, "unlocktime": 0},
                    ],
                }
            },
        )

    unlocked = make_client(handler).get_player_achievements("7656", 10)
    assert [a.api_name for a in unlocked] == ["WIN"]


def test_player_achievements_no_stats_is_empty():
    client = make_client(
        lambda request: httpx.Response(
            400, json={"playerstats": {"error": "Requested app has no stats", "success": False}}
        )
    )
    assert client.get_player_achievements("7656", 10) == []


def test_player_achievements_private_profile():
    client = make_client(
        lambda request: httpx.Response(403, json={"playerstats": {"error": "Profile is not public", "success": False}})
    )
    with pytest.raises(SteamPrivateProfileError):
        client.get_player_achievements("7656", 10)


def test_schema_and_global_percent():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ISteamUserStats/GetSchemaForGame/v2/":
            return httpx.Response(
                200,
                json={
                    "game": {
                        "availableGameStats": {
                            "achievements": [
                                {"name": "WIN", "displayName": "勝利", "hidden": 0, "description": "", "icon": "a", "icongray": "b"},
                            ]
                        }
                    }
                },
            )
        return httpx.Response(
            200, json={"achievementpercentages": {"achievements": [{"name": "WIN", "percent": "0.7"}]}}
        )

    client = make_client(handler)
    schema = client.get_achievement_schema(10)
    assert schema[0].display_name == "勝利"
    assert schema[0].description is None
    assert client.get_global_achievement_percentages(10) == {"WIN": 0.7}


def test_schema_missing_app_is_empty():
    client = make_client(lambda request: httpx.Response(400))
    assert client.get_achievement_schema(10) == []


def test_wishlist_parsed():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/IWishlistService/GetWishlist/v1/"
        return httpx.Response(
            200, json={"response": {"items": [{"appid": 10, "priority": 3, "date_added": 1700000000}]}}
        )

    items = make_client(handler).get_wishlist("7656")
    assert items[0].appid == 10
    assert items[0].priority == 3
    assert items[0].added_at == datetime.fromtimestamp(1700000000, tz=UTC)


def test_wishlist_private_raises():
    client = make_client(lambda request: httpx.Response(200, json={"response": {}}))
    with pytest.raises(SteamPrivateProfileError):
        client.get_wishlist("7656")


def test_store_price_on_sale():
    option = {
        "final_price_in_cents": "264000",
        "original_price_in_cents": "440000",
        "discount_pct": 40,
        "active_discounts": [{"discount_amount": "176000", "discount_end_date": 1792688400}],
    }
    price = parse_store_price(option, is_free=False, currency="JPY")
    assert (price.price, price.regular_price, price.discount_pct) == (2640, 4400, 40)
    assert price.sale_ends_at == datetime.fromtimestamp(1792688400, tz=UTC)


def test_store_price_ignores_bundle_discount():
    option = {"final_price_in_cents": "153000", "bundle_discount_pct": 10, "price_before_bundle_discount": "170000"}
    price = parse_store_price(option, is_free=False, currency="JPY")
    assert (price.price, price.regular_price, price.discount_pct) == (1700, 1700, 0)
    assert price.sale_ends_at is None


def test_store_price_keeps_cents_for_usd():
    price = parse_store_price({"final_price_in_cents": "1999"}, is_free=False, currency="USD")
    assert price.price == 1999


def test_store_price_free_and_unavailable():
    assert parse_store_price(None, is_free=True, currency="JPY").price == 0
    assert parse_store_price(None, is_free=False, currency="JPY") is None


def test_store_items():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/IStoreBrowseService/GetItems/v1/"
        request_json = json.loads(request.url.params["input_json"])
        assert request_json["context"]["country_code"] == "JP"
        return httpx.Response(
            200,
            json={
                "response": {
                    "store_items": [
                        {
                            "appid": 10,
                            "success": 1,
                            "name": "Sale",
                            "best_purchase_option": {"final_price_in_cents": "50000"},
                            "assets": {"asset_url_format": "steam/apps/10/${FILENAME}?t=1", "header": "abc123/header.jpg"},
                        },
                        {"appid": 20, "success": 1, "name": "Soon", "is_coming_soon": True},
                        {"appid": 30, "success": 2},
                    ]
                }
            },
        )

    items = make_client(handler).get_store_items([10, 20, 30], country_code="jp")
    assert [i.appid for i in items] == [10, 20]
    assert items[0].price.price == 500
    assert items[1].coming_soon and items[1].price is None
    assert items[0].header_image_url.endswith("/steam/apps/10/abc123/header.jpg?t=1")
    assert items[1].header_image_url.endswith("/steam/apps/20/header.jpg")


def test_store_items_unknown_country():
    with pytest.raises(SteamError):
        make_client(lambda request: httpx.Response(200)).get_store_items([10], country_code="ZZ")
