from datetime import UTC, datetime

import httpx
import pytest

from game_garden.steam import API_BASE, SteamClient, SteamPrivateProfileError


def make_client(handler) -> SteamClient:
    http = httpx.Client(base_url=API_BASE, transport=httpx.MockTransport(handler))
    return SteamClient("test-key", http=http, max_retries=0)


def test_owned_games_parsed():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/IPlayerService/GetOwnedGames/v1/"
        assert request.url.params["key"] == "test-key"
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
