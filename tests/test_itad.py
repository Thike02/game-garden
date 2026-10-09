import json
from datetime import datetime

import httpx
import pytest

from game_garden.itad import API_BASE, ItadClient, ItadError


def make_client(handler) -> ItadClient:
    http = httpx.Client(base_url=API_BASE, transport=httpx.MockTransport(handler))
    return ItadClient("test-key", http=http, max_retries=0)


def deal(price: int, regular: int, cut: int) -> dict:
    return {
        "price": {"amount": price, "amountInt": price, "currency": "JPY"},
        "regular": {"amount": regular, "amountInt": regular, "currency": "JPY"},
        "cut": cut,
    }


def test_lookup_omits_unknown_apps():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/lookup/id/shop/61/v1"
        assert json.loads(request.content) == ["app/10", "app/20"]
        return httpx.Response(200, json={"app/10": "itad-10", "app/20": None})

    assert make_client(handler).lookup_steam_apps([10, 20]) == {10: "itad-10"}


def test_history_requests_full_range():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["since"].startswith("2000-")
        assert request.url.params["shops"] == "61"
        return httpx.Response(
            200,
            json=[
                {"timestamp": "2026-10-01T19:46:22+02:00", "shop": {"id": 61, "name": "Steam"}, "deal": deal(1840, 2300, 20)}
            ],
        )

    points = make_client(handler).get_price_history("itad-10", country="JP")
    assert points[0].price == 1840
    assert points[0].regular_price == 2300
    assert points[0].discount_pct == 20
    assert points[0].at == datetime.fromisoformat("2026-10-01T19:46:22+02:00")


def test_steam_lows():
    def handler(request: httpx.Request) -> httpx.Response:
        low = {"shop": {"id": 61, "name": "Steam"}, "timestamp": "2025-12-18T20:18:19+01:00", **deal(1150, 2300, 50)}
        return httpx.Response(200, json=[{"id": "itad-10", "lows": [low]}, {"id": "itad-20", "lows": []}])

    lows = make_client(handler).get_steam_lows(["itad-10", "itad-20"], country="JP")
    assert list(lows) == ["itad-10"]
    assert lows["itad-10"].price == 1150


def test_bad_key():
    with pytest.raises(ItadError):
        make_client(lambda request: httpx.Response(403)).lookup_steam_apps([10])
