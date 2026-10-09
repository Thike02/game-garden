"""Client for the IsThereAnyDeal API (Steam shop only)."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import httpx

API_BASE = "https://api.isthereanydeal.com"
STEAM_SHOP_ID = 61
LOOKUP_BATCH = 200
# ITAD returns only ~3 months of history unless `since` is given.
HISTORY_SINCE = "2000-01-01T00:00:00Z"


class ItadError(RuntimeError):
    pass


@dataclass(frozen=True)
class PricePoint:
    at: datetime
    price: int  # minor units, ITAD's amountInt (JPY: yen)
    regular_price: int
    discount_pct: int
    currency: str


def _parse_point(timestamp: str, price: dict, regular: dict, cut: int | None) -> PricePoint:
    return PricePoint(
        at=datetime.fromisoformat(timestamp),
        price=price["amountInt"],
        regular_price=regular["amountInt"],
        discount_pct=cut or 0,
        currency=price["currency"],
    )


class ItadClient:
    def __init__(self, api_key: str, *, http: httpx.Client | None = None, max_retries: int = 3) -> None:
        self._api_key = api_key
        self._http = http or httpx.Client(base_url=API_BASE, timeout=30.0)
        self._max_retries = max_retries

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ItadClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(self, method: str, path: str, *, params: dict | None = None, json: object = None) -> object:
        params = {"key": self._api_key, **(params or {})}
        for attempt in range(self._max_retries + 1):
            response = self._http.request(method, path, params=params, json=json)
            if (response.status_code == 429 or response.status_code >= 500) and attempt < self._max_retries:
                time.sleep(2**attempt)
                continue
            break
        if response.status_code in (401, 403):
            raise ItadError(f"{path}: {response.status_code} (check ITAD_API_KEY)")
        response.raise_for_status()
        return response.json()

    def lookup_steam_apps(self, appids: Sequence[int]) -> dict[int, str]:
        """Map Steam appids to ITAD game ids. Unknown apps are omitted."""
        found: dict[int, str] = {}
        for start in range(0, len(appids), LOOKUP_BATCH):
            batch = [f"app/{appid}" for appid in appids[start : start + LOOKUP_BATCH]]
            data = self._request("POST", f"/lookup/id/shop/{STEAM_SHOP_ID}/v1", json=batch)
            for key, game_id in data.items():
                if game_id:
                    found[int(key.removeprefix("app/"))] = game_id
        return found

    def get_price_history(self, game_id: str, *, country: str) -> list[PricePoint]:
        """Steam price changes, newest first."""
        data = self._request(
            "GET",
            "/games/history/v2",
            params={"id": game_id, "country": country, "shops": STEAM_SHOP_ID, "since": HISTORY_SINCE},
        )
        return [
            _parse_point(entry["timestamp"], entry["deal"]["price"], entry["deal"]["regular"], entry["deal"].get("cut"))
            for entry in data
        ]

    def get_steam_lows(self, game_ids: Sequence[str], *, country: str) -> dict[str, PricePoint]:
        """All-time lowest Steam price per ITAD game id."""
        lows: dict[str, PricePoint] = {}
        for start in range(0, len(game_ids), LOOKUP_BATCH):
            data = self._request(
                "POST",
                "/games/storelow/v2",
                params={"country": country, "shops": STEAM_SHOP_ID},
                json=list(game_ids[start : start + LOOKUP_BATCH]),
            )
            for entry in data:
                for low in entry.get("lows", []):
                    if low["shop"]["id"] == STEAM_SHOP_ID:
                        lows[entry["id"]] = _parse_point(low["timestamp"], low["price"], low["regular"], low.get("cut"))
        return lows
