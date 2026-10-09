"""Games managed from the local admin: hand-entered games and Steam games missing from the owned list.

owned_games.source:
  'manual'    non-Steam game; counts and playtime typed in by hand
  'community' Steam game GetOwnedGames leaves out (e.g. a free game never launched);
              achievements come from the profile page, playtime is typed in by hand.
              If it later shows up in the owned list, the daily sync takes it over as 'steam'.
The daily sync only writes source='steam' rows, so these are never overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from supabase import Client

from game_garden import db
from game_garden.community import CommunityPageError, fetch_page_rows, icon_hash
from game_garden.config import Settings
from game_garden.images import delete_game_image
from game_garden.local_steam import played_appids, steam_dir
from game_garden.nvidia import detected_apps
from game_garden.local_state import ignored_appids
from game_garden.steam import SteamClient

PLATFORMS = ["Switch", "PS5", "PS4", "Xbox", "スマホ", "PC（Steam 以外）", "その他"]


class LibraryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    appid: int
    name: str
    header_image_url: str | None
    achievements_total: int  # 0 when the profile page has no achievements for it
    achievements_unlocked: int


def get_player_id(database: Client, steam: SteamClient, settings: Settings) -> str:
    result = database.table("players").select("id").eq("steam_id", settings.steam_id).limit(1).execute()
    if result.data:
        return result.data[0]["id"]
    from game_garden.steam_sync import upsert_player

    return upsert_player(database, steam, settings.steam_id)


def list_managed_games(database: Client, player_id: str) -> list[dict]:
    rows = (
        database.table("owned_games")
        .select(
            "game_id, source, playtime_minutes, achievements_total, achievements_unlocked, "
            "achievements_synced_at, is_visible, started_on, last_played_at, "
            "games(name, platform, steam_appid, header_image_url, nvidia_app_name)"
        )
        .eq("player_id", player_id)
        .in_("source", ["manual", "community"])
        .execute()
        .data
    )
    return sorted(rows, key=lambda r: (r["source"], r["games"]["name"].lower()))


def _refresh_activity(database: Client, player_id: str) -> None:
    database.rpc("refresh_daily_activity", {"p_player_id": player_id}).execute()


def _source_of(database: Client, player_id: str, game_id: int) -> str:
    result = (
        database.table("owned_games")
        .select("source")
        .eq("player_id", player_id)
        .eq("game_id", game_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise LibraryError("そのゲームは登録されていません")
    return result.data[0]["source"]


# ---------------------------------------------------------------------------
# Non-Steam games
# ---------------------------------------------------------------------------


def _counts(total: int | None, unlocked: int | None) -> tuple[int | None, int | None]:
    if not total:
        return None, None
    unlocked = min(max(unlocked or 0, 0), total)
    return total, unlocked


def _day_start(day: date | None) -> str | None:
    """A date typed in the admin as a timestamp: the start of that day in Japan time."""
    return datetime.combine(day, time.min, tzinfo=db.JST).isoformat() if day else None


def add_manual_game(
    database: Client,
    player_id: str,
    *,
    name: str,
    platform: str,
    image_url: str | None,
    achievements_total: int | None,
    achievements_unlocked: int | None,
    playtime_minutes: int | None,
    is_visible: bool,
    started_on: date | None = None,
    last_played_on: date | None = None,
    nvidia_app_name: str | None = None,
) -> int:
    if not name.strip():
        raise LibraryError("名前を入れてください")
    game = (
        database.table("games")
        .insert(
            {
                "platform": platform,
                "name": name.strip(),
                "header_image_url": image_url or None,
                "nvidia_app_name": nvidia_app_name or None,
            }
        )
        .execute()
        .data[0]
    )
    total, unlocked = _counts(achievements_total, achievements_unlocked)
    database.table("owned_games").insert(
        {
            "player_id": player_id,
            "game_id": game["id"],
            "source": "manual",
            "playtime_minutes": playtime_minutes or 0,
            "achievements_total": total,
            "achievements_unlocked": unlocked,
            "achievements_synced_at": db.utcnow_iso(),
            "is_visible": is_visible,
            "started_on": started_on.isoformat() if started_on else None,
            "last_played_at": _day_start(last_played_on),
        },
        returning="minimal",
    ).execute()
    return game["id"]


def update_manual_game(
    database: Client,
    player_id: str,
    game_id: int,
    *,
    name: str,
    platform: str,
    image_url: str | None,
    achievements_total: int | None,
    achievements_unlocked: int | None,
    playtime_minutes: int | None,
    started_on: date | None = None,
    last_played_on: date | None = None,
    nvidia_app_name: str | None = None,
) -> None:
    if _source_of(database, player_id, game_id) != "manual":
        raise LibraryError("手で登録したゲームだけ編集できます")
    if not name.strip():
        raise LibraryError("名前を入れてください")
    old_image = database.table("games").select("header_image_url").eq("id", game_id).execute().data[0]["header_image_url"]
    database.table("games").update(
        {
            "name": name.strip(),
            "platform": platform,
            "header_image_url": image_url or None,
            "nvidia_app_name": nvidia_app_name or None,
            "updated_at": db.utcnow_iso(),
        },
        returning="minimal",
    ).eq("id", game_id).execute()
    total, unlocked = _counts(achievements_total, achievements_unlocked)
    database.table("owned_games").update(
        {
            "playtime_minutes": playtime_minutes or 0,
            "achievements_total": total,
            "achievements_unlocked": unlocked,
            "achievements_synced_at": db.utcnow_iso(),
            "started_on": started_on.isoformat() if started_on else None,
            "last_played_at": _day_start(last_played_on),
            "updated_at": db.utcnow_iso(),
        },
        returning="minimal",
    ).eq("player_id", player_id).eq("game_id", game_id).execute()
    if old_image != (image_url or None):
        delete_game_image(database, old_image)  # only removes images we uploaded


def refresh_last_played_from_nvidia(database: Client, player_id: str) -> list[tuple[str, datetime]]:
    """Move "last played" forward from NVIDIA App's launch records. Returns what changed."""
    launches = {app.short_name: app.last_launch for app in detected_apps() if app.last_launch}
    changed = []
    for row in list_managed_games(database, player_id):
        launched = launches.get(row["games"]["nvidia_app_name"] or "")
        current = datetime.fromisoformat(row["last_played_at"]) if row["last_played_at"] else None
        if launched and (current is None or launched > current):
            database.table("owned_games").update(
                {"last_played_at": launched.isoformat(), "updated_at": db.utcnow_iso()}, returning="minimal"
            ).eq("player_id", player_id).eq("game_id", row["game_id"]).execute()
            changed.append((row["games"]["name"], launched))
    return changed


# ---------------------------------------------------------------------------
# Steam games missing from the owned list
# ---------------------------------------------------------------------------


def find_candidates(database: Client, steam: SteamClient, settings: Settings) -> list[Candidate]:
    """Apps played on this PC that the API doesn't list as owned and that have achievements."""
    known = {
        row["games"]["steam_appid"]
        for row in database.table("owned_games")
        .select("games(steam_appid)")
        .eq("player_id", get_player_id(database, steam, settings))
        .execute()
        .data
        if row["games"]["steam_appid"]
    }
    owned = {g.appid for g in steam.get_owned_games(settings.steam_id)}
    appids = sorted(played_appids(steam_dir(), settings.steam_id) - owned - known - ignored_appids())
    if not appids:
        return []

    store = {i.appid: i for i in steam.get_store_items(appids, country_code=settings.steam_country_code)}
    candidates = []
    for appid in appids:
        if appid not in store:  # tools, deleted apps
            continue
        try:
            rows = fetch_page_rows(settings.steam_id, appid)
        except Exception:  # no achievements page, or the page could not be read
            rows = []
        if not rows:
            continue
        candidates.append(
            Candidate(
                appid=appid,
                name=store[appid].name,
                header_image_url=store[appid].header_image_url,
                achievements_total=len(rows),
                achievements_unlocked=sum(1 for r in rows if r.unlocked_at),
            )
        )
    return sorted(candidates, key=lambda c: (-c.achievements_unlocked, c.name))


def add_hidden_steam_game(
    database: Client, steam: SteamClient, settings: Settings, appid: int, *, is_visible: bool
) -> int:
    player_id = get_player_id(database, steam, settings)
    items = steam.get_store_items([appid], country_code=settings.steam_country_code)
    if not items:
        raise LibraryError(f"Steam ストアに {appid} が見つかりません")
    item = items[0]
    game = db.upsert(
        database,
        "games",
        [
            {
                "platform": "steam",
                "steam_appid": appid,
                "name": item.name,
                "header_image_url": item.header_image_url,
                "updated_at": db.utcnow_iso(),
            }
        ],
        on_conflict="steam_appid",
        returning=True,
    )[0]
    existing = (
        database.table("owned_games")
        .select("source")
        .eq("player_id", player_id)
        .eq("game_id", game["id"])
        .limit(1)
        .execute()
        .data
    )
    if existing and existing[0]["source"] == "steam":
        raise LibraryError(f"{item.name} は毎日の同期でもう取り込まれています")
    if not existing:
        database.table("owned_games").insert(
            {"player_id": player_id, "game_id": game["id"], "source": "community", "is_visible": is_visible},
            returning="minimal",
        ).execute()
    sync_hidden_steam_game(database, steam, settings, game["id"])
    return game["id"]


def sync_hidden_steam_game(database: Client, steam: SteamClient, settings: Settings, game_id: int) -> tuple[int, int]:
    """Refresh one 'community' game's achievements from the profile page. Returns (unlocked, total)."""
    player_id = get_player_id(database, steam, settings)
    if _source_of(database, player_id, game_id) != "community":
        raise LibraryError("Steam の一覧に出てこないゲームだけ更新できます")
    appid = database.table("games").select("steam_appid").eq("id", game_id).execute().data[0]["steam_appid"]

    now = db.utcnow_iso()
    schema = steam.get_achievement_schema(appid)
    unlocked: list[tuple[str, str | None]] = []
    if schema:
        percents = steam.get_global_achievement_percentages(appid)
        db.upsert(
            database,
            "achievements",
            [
                {
                    "game_id": game_id,
                    "api_name": a.api_name,
                    "display_name": a.display_name,
                    "description": a.description,
                    "icon_url": a.icon_url,
                    "icon_gray_url": a.icon_gray_url,
                    "hidden": a.hidden,
                    "global_percent": percents.get(a.api_name),
                    "updated_at": now,
                }
                for a in schema
            ],
            on_conflict="game_id,api_name",
        )
        # The page has no API names; its icons are the schema's colour (unlocked) or grey (locked) icons.
        by_icon = {}
        for a in schema:
            for url in (a.icon_url, a.icon_gray_url):
                if h := icon_hash(url):
                    by_icon[h] = a.api_name
        try:
            rows = fetch_page_rows(settings.steam_id, appid)
        except CommunityPageError as e:
            raise LibraryError(f"プロフィールの実績ページを読めませんでした：{e}") from e
        unlocked = [
            (by_icon[r.icon_hash], r.unlocked_at.isoformat())
            for r in rows
            if r.unlocked_at and r.icon_hash in by_icon
        ]
        db.upsert(
            database,
            "player_achievements",
            [{"player_id": player_id, "game_id": game_id, "api_name": n, "unlocked_at": t} for n, t in unlocked],
            on_conflict="player_id,game_id,api_name",
        )

    database.table("owned_games").update(
        {
            "achievements_total": len(schema) or None,
            "achievements_unlocked": len(unlocked) if schema else None,
            "achievements_synced_at": now,
            "updated_at": now,
        },
        returning="minimal",
    ).eq("player_id", player_id).eq("game_id", game_id).execute()
    _refresh_activity(database, player_id)
    return len(unlocked), len(schema)


def set_playtime(database: Client, player_id: str, game_id: int, playtime_minutes: int) -> None:
    if _source_of(database, player_id, game_id) == "steam":
        raise LibraryError("Steam から同期しているゲームのプレイ時間は変えられません")
    database.table("owned_games").update(
        {"playtime_minutes": max(playtime_minutes, 0), "updated_at": db.utcnow_iso()}, returning="minimal"
    ).eq("player_id", player_id).eq("game_id", game_id).execute()


# ---------------------------------------------------------------------------
# Both
# ---------------------------------------------------------------------------


def set_visibility(database: Client, player_id: str, game_id: int, is_visible: bool) -> None:
    _source_of(database, player_id, game_id)
    database.table("owned_games").update({"is_visible": is_visible}, returning="minimal").eq(
        "player_id", player_id
    ).eq("game_id", game_id).execute()
    _refresh_activity(database, player_id)


def remove_game(database: Client, player_id: str, game_id: int) -> None:
    source = _source_of(database, player_id, game_id)
    if source == "manual":
        # Only this player uses a hand-entered game; removing it removes the catalog row too.
        image = database.table("games").select("header_image_url").eq("id", game_id).execute().data[0]["header_image_url"]
        database.table("games").delete(returning="minimal").eq("id", game_id).execute()
        delete_game_image(database, image)
    elif source == "community":
        database.table("player_achievements").delete(returning="minimal").eq("player_id", player_id).eq(
            "game_id", game_id
        ).execute()
        database.table("owned_games").delete(returning="minimal").eq("player_id", player_id).eq(
            "game_id", game_id
        ).execute()
    else:
        raise LibraryError("Steam から同期しているゲームは管理画面から消せません")
    _refresh_activity(database, player_id)
