"""Sync owned Steam games and achievements into Supabase."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from supabase import Client

from game_garden import db
from game_garden.config import Settings
from game_garden.steam import OwnedGame, SteamClient, SteamPrivateProfileError

JOB = "steam"
PRIVATE_CHECK_MIN_GAMES = 3


@dataclass
class SyncResult:
    owned_games: int = 0
    achievement_games: int = 0
    failed: int = 0


def select_achievement_targets(
    owned: Iterable[OwnedGame], synced_at: dict[int, datetime | None], *, full: bool
) -> list[OwnedGame]:
    """Pick games whose achievements need (re)fetching.

    Never-synced games are always included, so the first run covers everything.
    After that only games played since their last sync are refreshed.
    """
    targets = []
    for game in owned:
        last_sync = synced_at.get(game.appid)
        if full or last_sync is None or (game.last_played_at and game.last_played_at > last_sync):
            targets.append(game)
    # Most recently played first, so a partial run still covers what matters.
    targets.sort(key=lambda g: (g.last_played_at is not None, g.last_played_at), reverse=True)
    return targets


def upsert_player(database: Client, steam: SteamClient, steam_id: str) -> str:
    summary = steam.get_player_summary(steam_id)
    rows = db.upsert(
        database,
        "players",
        [{"steam_id": summary.steam_id, "display_name": summary.display_name, "avatar_url": summary.avatar_url}],
        on_conflict="steam_id",
        returning=True,
    )
    return rows[0]["id"]


def _load_header_images(steam: SteamClient, owned: list[OwnedGame], country_code: str) -> dict[int, str]:
    """Exact header image URLs from the store; games missing here fall back to the guessed URL."""
    try:
        items = steam.get_store_items([g.appid for g in owned], country_code=country_code)
    except Exception as e:  # images are cosmetic; never fail the sync over them
        print(f"Header images unavailable ({e}); using fallback URLs")
        return {}
    return {item.appid: item.header_image_url for item in items}


def _upsert_owned_games(
    database: Client, player_id: str, owned: list[OwnedGame], header_images: dict[int, str]
) -> dict[int, int]:
    """Store games and ownership rows. Returns appid -> games.id."""
    now = db.utcnow_iso()
    game_rows = [
        {
            "platform": "steam",
            "steam_appid": g.appid,
            "name": g.name,
            "header_image_url": header_images.get(g.appid, g.header_image_url),
            "updated_at": now,
        }
        for g in owned
    ]
    stored = db.upsert(database, "games", game_rows, on_conflict="steam_appid", returning=True)
    game_ids = {row["steam_appid"]: row["id"] for row in stored}

    owned_rows = [
        {
            "player_id": player_id,
            "game_id": game_ids[g.appid],
            "source": "steam",
            "playtime_minutes": g.playtime_minutes,
            "last_played_at": g.last_played_at.isoformat() if g.last_played_at else None,
            "updated_at": now,
        }
        for g in owned
    ]
    db.upsert(database, "owned_games", owned_rows, on_conflict="player_id,game_id")
    return game_ids


def _record_playtime_snapshots(
    database: Client, player_id: str, owned: list[OwnedGame], game_ids: dict[int, int]
) -> None:
    """Store today's lifetime playtime per game; day-to-day increases become the activity grid."""
    today = db.today_jst().isoformat()
    rows = [
        {
            "player_id": player_id,
            "game_id": game_ids[g.appid],
            "snapshot_date": today,
            "playtime_minutes": g.playtime_minutes,
            "last_played_at": g.last_played_at.isoformat() if g.last_played_at else None,
        }
        for g in owned
    ]
    db.upsert(database, "playtime_snapshots", rows, on_conflict="player_id,game_id,snapshot_date")


def _load_synced_at(database: Client, player_id: str, game_ids: dict[int, int]) -> dict[int, datetime | None]:
    appid_by_game_id = {game_id: appid for appid, game_id in game_ids.items()}
    synced_at: dict[int, datetime | None] = {}
    page_size = 1000
    start = 0
    while True:
        result = (
            database.table("owned_games")
            .select("game_id, achievements_synced_at")
            .eq("player_id", player_id)
            .range(start, start + page_size - 1)
            .execute()
        )
        for row in result.data:
            appid = appid_by_game_id.get(row["game_id"])
            if appid is not None and row["achievements_synced_at"]:
                synced_at[appid] = datetime.fromisoformat(row["achievements_synced_at"])
        if len(result.data) < page_size:
            return synced_at
        start += page_size


def _sync_game_achievements(
    database: Client, steam: SteamClient, steam_id: str, player_id: str, game_id: int, appid: int
) -> tuple[int, int]:
    """Fetch one game's achievements. Returns (unlocked, total)."""
    now = db.utcnow_iso()
    schema = steam.get_achievement_schema(appid)
    unlocked_count = 0

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
        known = {a.api_name for a in schema}
        unlocked = [a for a in steam.get_player_achievements(steam_id, appid) if a.api_name in known]
        unlocked_count = len(unlocked)
        db.upsert(
            database,
            "player_achievements",
            [
                {
                    "player_id": player_id,
                    "game_id": game_id,
                    "api_name": a.api_name,
                    "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None,
                }
                for a in unlocked
            ],
            on_conflict="player_id,game_id,api_name",
        )

    (
        database.table("owned_games")
        .update(
            {
                # null total means "this game has no achievements"
                "achievements_total": len(schema) or None,
                "achievements_unlocked": unlocked_count if schema else None,
                "achievements_synced_at": now,
            },
            returning="minimal",
        )
        .eq("player_id", player_id)
        .eq("game_id", game_id)
        .execute()
    )
    return unlocked_count, len(schema)


def sync_steam(settings: Settings, *, full: bool = False, limit: int | None = None) -> SyncResult:
    settings.require("steam_api_key", "steam_id")
    database = db.connect(settings)
    result = SyncResult()
    player_id: str | None = None

    with SteamClient(settings.steam_api_key) as steam:
        try:
            player_id = upsert_player(database, steam, settings.steam_id)
            owned = steam.get_owned_games(settings.steam_id)
            header_images = _load_header_images(steam, owned, settings.steam_country_code)
            game_ids = _upsert_owned_games(database, player_id, owned, header_images)
            _record_playtime_snapshots(database, player_id, owned, game_ids)
            result.owned_games = len(owned)
            print(f"Owned games: {len(owned)}")

            synced_at = _load_synced_at(database, player_id, game_ids)
            targets = select_achievement_targets(owned, synced_at, full=full)
            if limit is not None:
                targets = targets[:limit]
            print(f"Achievements to sync: {len(targets)}")

            private_failures = 0
            for i, game in enumerate(targets, start=1):
                try:
                    unlocked, total = _sync_game_achievements(
                        database, steam, settings.steam_id, player_id, game_ids[game.appid], game.appid
                    )
                except SteamPrivateProfileError:
                    # The owned games list was readable, so the profile itself is public. Steam also
                    # answers "Profile is not public" for single apps it won't serve stats for.
                    private_failures += 1
                    result.failed += 1
                    print(f"  [{i}/{len(targets)}] {game.name}: skipped (Steam refused its achievements)")
                    continue
                except Exception as e:  # keep going; one broken app must not stop the run
                    result.failed += 1
                    print(f"  [{i}/{len(targets)}] {game.name}: failed ({e})")
                    continue
                result.achievement_games += 1
                progress = f"{unlocked}/{total}" if total else "no achievements"
                print(f"  [{i}/{len(targets)}] {game.name}: {progress}")

            # Refused for every one of several games: achievements really are hidden. One or two
            # refusals alone can just be odd apps, so they don't fail the whole run.
            if len(targets) >= PRIVATE_CHECK_MIN_GAMES and private_failures == len(targets):
                raise SteamPrivateProfileError(
                    "Achievements are not visible. Set Steam profile > Privacy > Game details to Public."
                )

            # Rebuilt from snapshots and unlock times, so it also picks up achievements synced above.
            database.rpc("refresh_daily_activity", {"p_player_id": player_id}).execute()
        except Exception as e:
            if player_id is not None:
                db.record_failure(database, JOB, player_id, f"{type(e).__name__}: {e}")
            raise

    detail = f"owned={result.owned_games} synced={result.achievement_games} failed={result.failed}"
    db.record_success(database, JOB, player_id, detail)
    return result
