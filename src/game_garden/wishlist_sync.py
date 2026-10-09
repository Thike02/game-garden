"""Sync the Steam wishlist and record prices (daily Steam price + ITAD backfill)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from supabase import Client

from game_garden import db
from game_garden.config import Settings
from game_garden.itad import ItadClient, PricePoint
from game_garden.steam import SteamClient, StoreItem, WishlistItem
from game_garden.steam_sync import upsert_player

JOB = "wishlist"
SHOP = "steam"


@dataclass
class WishlistResult:
    items: int = 0
    removed: int = 0
    priced: int = 0
    backfilled: int = 0
    lows: int = 0


def daily_points(points: Iterable[PricePoint]) -> dict[date, PricePoint]:
    """Collapse price changes to one point per JST day: the last change of that day."""
    by_day: dict[date, PricePoint] = {}
    for point in points:
        day = point.at.astimezone(db.JST).date()
        if day not in by_day or point.at > by_day[day].at:
            by_day[day] = point
    return by_day


def _upsert_wishlist_games(
    database: Client, player_id: str, wishlist: list[WishlistItem], store_items: dict[int, StoreItem]
) -> dict[int, int]:
    """Store games and wishlist rows. Returns appid -> games.id."""
    now = db.utcnow_iso()
    game_rows = []
    for item in wishlist:
        store = store_items.get(item.appid)
        row = {"platform": "steam", "steam_appid": item.appid, "updated_at": now}
        row["name"] = store.name if store else f"App {item.appid}"
        if store:
            row["header_image_url"] = store.header_image_url
        game_rows.append(row)
    # Rows in one request must share keys, so split by whether we know the header image.
    with_image = [r for r in game_rows if "header_image_url" in r]
    without_image = [r for r in game_rows if "header_image_url" not in r]
    stored = db.upsert(database, "games", with_image, on_conflict="steam_appid", returning=True)
    # Not on the store any more: insert a placeholder, but never overwrite a name we already know.
    db.upsert(database, "games", without_image, on_conflict="steam_appid", ignore_duplicates=True)
    if without_image:
        appids = [r["steam_appid"] for r in without_image]
        stored += database.table("games").select("id, steam_appid").in_("steam_appid", appids).execute().data
    game_ids = {row["steam_appid"]: row["id"] for row in stored}

    db.upsert(
        database,
        "wishlist_items",
        [
            {
                "player_id": player_id,
                "game_id": game_ids[item.appid],
                "added_at": item.added_at.isoformat() if item.added_at else None,
                "priority": item.priority,
                "removed_at": None,  # re-added games become active again
            }
            for item in wishlist
        ],
        on_conflict="player_id,game_id",
    )
    return game_ids


def _mark_removed(database: Client, player_id: str, active_game_ids: set[int]) -> int:
    result = (
        database.table("wishlist_items")
        .select("game_id")
        .eq("player_id", player_id)
        .is_("removed_at", "null")
        .execute()
    )
    gone = [row["game_id"] for row in result.data if row["game_id"] not in active_game_ids]
    if gone:
        (
            database.table("wishlist_items")
            .update({"removed_at": db.utcnow_iso()}, returning="minimal")
            .eq("player_id", player_id)
            .in_("game_id", gone)
            .execute()
        )
    return len(gone)


def _record_today_prices(database: Client, game_ids: dict[int, int], store_items: dict[int, StoreItem]) -> int:
    today = db.today_jst().isoformat()
    rows = [
        {
            "game_id": game_ids[appid],
            "shop": SHOP,
            "recorded_on": today,
            "price": item.price.price,
            "regular_price": item.price.regular_price,
            "discount_pct": item.price.discount_pct,
            "currency": item.price.currency,
            "sale_ends_at": item.price.sale_ends_at.isoformat() if item.price.sale_ends_at else None,
            "source": "collector",
        }
        for appid, item in store_items.items()
        if item.price is not None and appid in game_ids
    ]
    # Our own daily observation wins over an ITAD backfill row for the same day.
    db.upsert(database, "price_history", rows, on_conflict="game_id,shop,recorded_on")
    return len(rows)


def _has_itad_history(database: Client, game_id: int) -> bool:
    result = (
        database.table("price_history")
        .select("game_id")
        .eq("game_id", game_id)
        .eq("source", "itad")
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _load_itad_ids(database: Client, game_ids: list[int]) -> dict[int, str]:
    """games.id -> itad_id for games already mapped."""
    games = database.table("games").select("id, itad_id").in_("id", game_ids).execute().data
    return {row["id"]: row["itad_id"] for row in games if row["itad_id"]}


def _sync_itad(
    database: Client, itad: ItadClient, game_ids: dict[int, int], country: str, result: WishlistResult
) -> None:
    itad_ids = _load_itad_ids(database, list(game_ids.values()))

    unmapped = [appid for appid, game_id in game_ids.items() if game_id not in itad_ids]
    if unmapped:
        for appid, itad_id in itad.lookup_steam_apps(unmapped).items():
            game_id = game_ids[appid]
            database.table("games").update({"itad_id": itad_id}, returning="minimal").eq("id", game_id).execute()
            itad_ids[game_id] = itad_id

    # Backfill full Steam price history once per game. Existing rows (e.g. today's) are kept.
    for game_id, itad_id in itad_ids.items():
        if _has_itad_history(database, game_id):
            continue
        points = daily_points(itad.get_price_history(itad_id, country=country))
        rows = [
            {
                "game_id": game_id,
                "shop": SHOP,
                "recorded_on": day.isoformat(),
                "price": p.price,
                "regular_price": p.regular_price,
                "discount_pct": p.discount_pct,
                "currency": p.currency,
                "source": "itad",
            }
            for day, p in points.items()
        ]
        db.upsert(database, "price_history", rows, on_conflict="game_id,shop,recorded_on", ignore_duplicates=True)
        if rows:
            result.backfilled += 1

    game_id_by_itad = {itad_id: game_id for game_id, itad_id in itad_ids.items()}
    lows = itad.get_steam_lows(list(itad_ids.values()), country=country)
    for itad_id, low in lows.items():
        (
            database.table("games")
            .update(
                {
                    "lowest_price": low.price,
                    "lowest_price_currency": low.currency,
                    "lowest_price_at": low.at.isoformat(),
                },
                returning="minimal",
            )
            .eq("id", game_id_by_itad[itad_id])
            .execute()
        )
    result.lows = len(lows)


def sync_wishlist(settings: Settings) -> WishlistResult:
    settings.require("steam_api_key", "steam_id", "itad_api_key")
    database = db.connect(settings)
    country = settings.steam_country_code.upper()
    result = WishlistResult()
    player_id: str | None = None

    with SteamClient(settings.steam_api_key) as steam, ItadClient(settings.itad_api_key) as itad:
        try:
            player_id = upsert_player(database, steam, settings.steam_id)
            wishlist = steam.get_wishlist(settings.steam_id)
            store_items = {
                item.appid: item
                for item in steam.get_store_items([w.appid for w in wishlist], country_code=country)
            }
            game_ids = _upsert_wishlist_games(database, player_id, wishlist, store_items)
            result.items = len(wishlist)
            result.removed = _mark_removed(database, player_id, set(game_ids.values()))
            result.priced = _record_today_prices(database, game_ids, store_items)
            print(f"Wishlist: {result.items} items, {result.removed} removed, {result.priced} priced today")

            for item in sorted(store_items.values(), key=lambda i: -(i.price.discount_pct if i.price else 0)):
                if item.price and item.price.discount_pct:
                    print(f"  -{item.price.discount_pct}% {item.name}: {item.price.price} {item.price.currency}")

            _sync_itad(database, itad, game_ids, country, result)
            print(f"ITAD: {result.backfilled} histories backfilled, {result.lows} historical lows")
        except Exception as e:
            if player_id is not None:
                db.record_failure(database, JOB, player_id, f"{type(e).__name__}: {e}")
            raise

    detail = f"items={result.items} removed={result.removed} priced={result.priced} backfilled={result.backfilled}"
    db.record_success(database, JOB, player_id, detail)
    return result
