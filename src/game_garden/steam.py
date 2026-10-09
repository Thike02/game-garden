"""Thin client for the Steam Web API endpoints Game Garden uses."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

API_BASE = "https://api.steampowered.com"
STORE_ASSET_BASE = "https://shared.cloudflare.steamstatic.com/store_item_assets/"
# Fallback only: newer apps keep their header under a hashed folder, which only the store API knows.
HEADER_IMAGE_URL = STORE_ASSET_BASE + "steam/apps/{appid}/header.jpg"
STORE_ITEMS_BATCH = 100

# Store prices come in hundredths; currencies without a minor unit are stored in whole units.
COUNTRY_CURRENCY = {"JP": "JPY", "US": "USD", "GB": "GBP", "KR": "KRW", "CN": "CNY", "TW": "TWD"}
ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW"}


class SteamError(RuntimeError):
    pass


class SteamPrivateProfileError(SteamError):
    pass


@dataclass(frozen=True)
class PlayerSummary:
    steam_id: str
    display_name: str
    avatar_url: str | None


@dataclass(frozen=True)
class OwnedGame:
    appid: int
    name: str
    playtime_minutes: int
    last_played_at: datetime | None

    @property
    def header_image_url(self) -> str:
        return HEADER_IMAGE_URL.format(appid=self.appid)


@dataclass(frozen=True)
class AchievementDef:
    api_name: str
    display_name: str
    description: str | None
    icon_url: str | None
    icon_gray_url: str | None
    hidden: bool


@dataclass(frozen=True)
class PlayerAchievement:
    api_name: str
    unlocked_at: datetime | None


@dataclass(frozen=True)
class WishlistItem:
    appid: int
    priority: int | None
    added_at: datetime | None


@dataclass(frozen=True)
class StorePrice:
    price: int  # current price in minor units (JPY: yen), sale included, bundle discount excluded
    regular_price: int
    discount_pct: int
    currency: str
    sale_ends_at: datetime | None = None


@dataclass(frozen=True)
class StoreItem:
    appid: int
    name: str
    coming_soon: bool
    price: StorePrice | None  # None when not purchasable (unreleased, delisted, ...)
    header_image_url: str


def _from_unix(value: int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def header_image_from_assets(appid: int, assets: dict | None) -> str:
    """Resolve the header image from the store API's `assets` (e.g. "<hash>/header.jpg")."""
    if assets and assets.get("asset_url_format") and assets.get("header"):
        return STORE_ASSET_BASE + assets["asset_url_format"].replace("${FILENAME}", assets["header"])
    return HEADER_IMAGE_URL.format(appid=appid)


def parse_store_price(option: dict | None, *, is_free: bool, currency: str) -> StorePrice | None:
    if is_free:
        return StorePrice(price=0, regular_price=0, discount_pct=0, currency=currency)
    if not option or "final_price_in_cents" not in option:
        return None
    divisor = 100 if currency in ZERO_DECIMAL_CURRENCIES else 1
    # A "bundle discount" only applies because the user owns part of a package; it is not a sale.
    price = int(option.get("price_before_bundle_discount") or option["final_price_in_cents"])
    regular = int(option.get("original_price_in_cents") or price)
    discount_pct = int(option.get("discount_pct") or 0)
    end_dates = [d["discount_end_date"] for d in option.get("active_discounts", []) if d.get("discount_end_date")]
    return StorePrice(
        price=price // divisor,
        regular_price=regular // divisor,
        discount_pct=discount_pct,
        currency=currency,
        sale_ends_at=_from_unix(min(end_dates)) if discount_pct and end_dates else None,
    )


class SteamClient:
    def __init__(
        self,
        api_key: str,
        *,
        language: str = "japanese",
        http: httpx.Client | None = None,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._language = language
        self._http = http or httpx.Client(base_url=API_BASE, timeout=30.0)
        self._max_retries = max_retries

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SteamClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, **params: object) -> httpx.Response:
        params = {"key": self._api_key, **params}
        for attempt in range(self._max_retries + 1):
            response = self._http.get(path, params=params)
            # 429 / 5xx are transient on Steam's side; back off and retry.
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self._max_retries:
                    time.sleep(2**attempt)
                    continue
            return response
        return response

    def _get_json(self, path: str, **params: object) -> dict:
        response = self._get(path, **params)
        if response.status_code == 403:
            raise SteamError(f"{path}: 403 Forbidden (check STEAM_API_KEY)")
        response.raise_for_status()
        return response.json()

    def get_player_summary(self, steam_id: str) -> PlayerSummary:
        data = self._get_json("/ISteamUser/GetPlayerSummaries/v2/", steamids=steam_id)
        players = data.get("response", {}).get("players", [])
        if not players:
            raise SteamError(f"Steam user {steam_id} not found (check STEAM_ID)")
        p = players[0]
        return PlayerSummary(
            steam_id=p["steamid"],
            display_name=p.get("personaname") or p["steamid"],
            avatar_url=p.get("avatarfull"),
        )

    def get_owned_games(self, steam_id: str) -> list[OwnedGame]:
        data = self._get_json(
            "/IPlayerService/GetOwnedGames/v1/",
            steamid=steam_id,
            include_appinfo=1,
            include_played_free_games=1,
            # Defaults to true and silently drops many small indie titles from the list.
            skip_unvetted_apps=0,
        )
        response = data.get("response", {})
        # A private "Game details" setting yields an empty response instead of an error.
        if "games" not in response:
            raise SteamPrivateProfileError(
                "Owned games are not visible. Set Steam profile > Privacy > Game details to Public."
            )
        return [
            OwnedGame(
                appid=g["appid"],
                name=g.get("name") or f"App {g['appid']}",
                playtime_minutes=g.get("playtime_forever", 0),
                last_played_at=_from_unix(g.get("rtime_last_played")),
            )
            for g in response["games"]
        ]

    def get_achievement_schema(self, appid: int) -> list[AchievementDef]:
        response = self._get("/ISteamUserStats/GetSchemaForGame/v2/", appid=appid, l=self._language)
        # Delisted / stat-less apps answer 400 or 403 here; treat them as having no achievements.
        if response.status_code in (400, 403, 404):
            return []
        response.raise_for_status()
        stats = response.json().get("game", {}).get("availableGameStats", {})
        return [
            AchievementDef(
                api_name=a["name"],
                display_name=a.get("displayName") or a["name"],
                description=a.get("description") or None,
                icon_url=a.get("icon"),
                icon_gray_url=a.get("icongray"),
                hidden=bool(a.get("hidden")),
            )
            for a in stats.get("achievements", [])
        ]

    def get_global_achievement_percentages(self, appid: int) -> dict[str, float]:
        response = self._get(
            "/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/", gameid=appid
        )
        if response.status_code in (400, 403, 404):
            return {}
        response.raise_for_status()
        achievements = response.json().get("achievementpercentages", {}).get("achievements", [])
        # `percent` is a number on older responses and a string on newer ones.
        return {a["name"]: float(a["percent"]) for a in achievements}

    def get_player_achievements(self, steam_id: str, appid: int) -> list[PlayerAchievement]:
        """Return only the unlocked achievements."""
        response = self._get(
            "/ISteamUserStats/GetPlayerAchievements/v1/", steamid=steam_id, appid=appid
        )
        if response.status_code in (400, 403):
            try:
                error = response.json().get("playerstats", {}).get("error", "")
            except ValueError:
                error = ""
            if "not public" in error.lower() or "private" in error.lower():
                raise SteamPrivateProfileError(
                    "Achievements are not visible. Set Steam profile > Privacy > Game details to Public."
                )
            # "Requested app has no stats" and similar.
            return []
        response.raise_for_status()
        achievements = response.json().get("playerstats", {}).get("achievements", [])
        return [
            PlayerAchievement(api_name=a["apiname"], unlocked_at=_from_unix(a.get("unlocktime")))
            for a in achievements
            if a.get("achieved")
        ]

    def get_wishlist(self, steam_id: str) -> list[WishlistItem]:
        data = self._get_json("/IWishlistService/GetWishlist/v1/", steamid=steam_id)
        response = data.get("response", {})
        # Private profiles (and, indistinguishably, empty wishlists) return no "items".
        # Refuse rather than let the caller mark every wishlist entry as removed.
        if "items" not in response:
            raise SteamPrivateProfileError(
                "Wishlist is empty or not visible. Set Steam profile > Privacy > Game details to Public."
            )
        return [
            WishlistItem(appid=i["appid"], priority=i.get("priority"), added_at=_from_unix(i.get("date_added")))
            for i in response["items"]
        ]

    def get_store_items(self, appids: Sequence[int], *, country_code: str) -> list[StoreItem]:
        currency = COUNTRY_CURRENCY.get(country_code.upper())
        if currency is None:
            raise SteamError(f"Unsupported STEAM_COUNTRY_CODE {country_code!r}; add it to COUNTRY_CURRENCY")
        items: list[StoreItem] = []
        for start in range(0, len(appids), STORE_ITEMS_BATCH):
            request = {
                "ids": [{"appid": appid} for appid in appids[start : start + STORE_ITEMS_BATCH]],
                "context": {"language": self._language, "country_code": country_code.upper()},
                "data_request": {"include_release": True, "include_assets": True},
            }
            data = self._get_json("/IStoreBrowseService/GetItems/v1/", input_json=json.dumps(request))
            for item in data.get("response", {}).get("store_items", []):
                if item.get("success") != 1:
                    continue
                items.append(
                    StoreItem(
                        appid=item["appid"],
                        name=item.get("name") or f"App {item['appid']}",
                        coming_soon=bool(item.get("is_coming_soon")),
                        price=parse_store_price(
                            item.get("best_purchase_option"), is_free=bool(item.get("is_free")), currency=currency
                        ),
                        header_image_url=header_image_from_assets(item["appid"], item.get("assets")),
                    )
                )
        return items
