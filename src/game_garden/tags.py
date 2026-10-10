"""Player-made tags on games, edited from the local admin."""

from __future__ import annotations

from collections.abc import Iterable

from supabase import Client

# Palette names; the admin and the web page map each to a colour that reads well in both themes.
COLORS = ["blue", "green", "yellow", "orange", "red", "pink", "purple", "gray"]
COLOR_LABELS = {
    "blue": "青",
    "green": "緑",
    "yellow": "黄",
    "orange": "橙",
    "red": "赤",
    "pink": "桃",
    "purple": "紫",
    "gray": "灰",
}


class TagError(ValueError):
    pass


def _clean(name: str, color: str) -> tuple[str, str]:
    name = name.strip()
    if not name:
        raise TagError("タグの名前を入れてください")
    if len(name) > 30:
        raise TagError("タグの名前は30文字までにしてください")
    if color not in COLORS:
        raise TagError("色を選んでください")
    return name, color


def list_tags(database: Client, player_id: str) -> list[dict]:
    """Tags with how many games carry each, in display order."""
    tags = (
        database.table("tags")
        .select("id, name, color, is_public, sort_order")
        .eq("player_id", player_id)
        .order("sort_order")
        .order("name")
        .execute()
        .data
    )
    counts: dict[int, int] = {}
    for row in database.table("game_tags").select("tag_id").eq("player_id", player_id).execute().data:
        counts[row["tag_id"]] = counts.get(row["tag_id"], 0) + 1
    for tag in tags:
        tag["games"] = counts.get(tag["id"], 0)
    return tags


def get_tag(database: Client, player_id: str, tag_id: int) -> dict:
    rows = (
        database.table("tags")
        .select("id, name, color, is_public, sort_order")
        .eq("player_id", player_id)
        .eq("id", tag_id)
        .execute()
        .data
    )
    if not rows:
        raise TagError("そのタグは見つかりません")
    return rows[0]


def create_tag(database: Client, player_id: str, *, name: str, color: str, is_public: bool) -> int:
    name, color = _clean(name, color)
    if database.table("tags").select("id").eq("player_id", player_id).eq("name", name).execute().data:
        raise TagError(f"「{name}」はもうあります")
    count = len(database.table("tags").select("id").eq("player_id", player_id).execute().data)
    row = (
        database.table("tags")
        .insert(
            {"player_id": player_id, "name": name, "color": color, "is_public": is_public, "sort_order": count}
        )
        .execute()
        .data[0]
    )
    return row["id"]


def update_tag(
    database: Client, player_id: str, tag_id: int, *, name: str, color: str, is_public: bool, sort_order: int
) -> None:
    get_tag(database, player_id, tag_id)
    name, color = _clean(name, color)
    clash = database.table("tags").select("id").eq("player_id", player_id).eq("name", name).neq("id", tag_id).execute()
    if clash.data:
        raise TagError(f"「{name}」はもうあります")
    database.table("tags").update(
        {"name": name, "color": color, "is_public": is_public, "sort_order": sort_order}, returning="minimal"
    ).eq("id", tag_id).execute()


def delete_tag(database: Client, player_id: str, tag_id: int) -> str:
    tag = get_tag(database, player_id, tag_id)
    database.table("tags").delete(returning="minimal").eq("id", tag_id).execute()  # game_tags cascade
    return tag["name"]


def list_games(database: Client, player_id: str) -> list[dict]:
    """Every game the player has (Steam and not), for the tag checklist."""
    rows = (
        database.table("owned_games")
        .select("game_id, source, games(name, platform, header_image_url)")
        .eq("player_id", player_id)
        .execute()
        .data
    )
    return sorted(rows, key=lambda r: r["games"]["name"].lower())


def tagged_game_ids(database: Client, tag_id: int) -> set[int]:
    return {row["game_id"] for row in database.table("game_tags").select("game_id").eq("tag_id", tag_id).execute().data}


def set_tag_games(database: Client, player_id: str, tag_id: int, game_ids: Iterable[int]) -> tuple[int, int]:
    """Make exactly `game_ids` carry the tag. Returns (added, removed)."""
    get_tag(database, player_id, tag_id)
    wanted = set(game_ids)
    current = tagged_game_ids(database, tag_id)
    added, removed = wanted - current, current - wanted
    if removed:
        database.table("game_tags").delete(returning="minimal").eq("tag_id", tag_id).in_(
            "game_id", sorted(removed)
        ).execute()
    if added:
        database.table("game_tags").insert(
            [{"player_id": player_id, "game_id": g, "tag_id": tag_id} for g in sorted(added)], returning="minimal"
        ).execute()
    return len(added), len(removed)
