"""Thin client for the Steam Web API endpoints Game Garden uses."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

API_BASE = "https://api.steampowered.com"
HEADER_IMAGE_URL = "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"


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


def _from_unix(value: int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


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
