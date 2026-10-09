"""Notify Discord about wishlist games on sale."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from supabase import Client

from game_garden import db
from game_garden.config import Settings
from game_garden.discord import send_embeds
from game_garden.pricing import time_weighted_average

JOB = "notify"
AVERAGE_DAYS = 365
COLOR_LOW = 0xF1C40F  # gold
COLOR_SALE = 0x2ECC71  # green
COLOR_ERROR = 0xE74C3C  # red
JOB_LABELS = {
    "sync-steam": "所有ゲームと実績",
    "sync-wishlist": "ウィッシュリストと価格",
    "notify-sales": "セール通知",
}
STORE_URL = "https://store.steampowered.com/app/{appid}/"


@dataclass(frozen=True)
class SaleCandidate:
    game_id: int
    appid: int
    name: str
    header_image_url: str | None
    price: int
    regular_price: int
    discount_pct: int
    currency: str
    sale_ends_at: datetime | None
    lowest_price: int | None
    average: float | None

    @property
    def is_historical_low(self) -> bool:
        # A game never on sale has its regular price as its "low"; only count real sales.
        return self.discount_pct > 0 and self.lowest_price is not None and self.price <= self.lowest_price

    @property
    def below_average_pct(self) -> float | None:
        if not self.average:
            return None
        return (1 - self.price / self.average) * 100


def should_notify(candidate: SaleCandidate, min_discount: int) -> bool:
    return candidate.discount_pct >= min_discount or candidate.is_historical_low


def sort_key(candidate: SaleCandidate) -> tuple:
    return (not candidate.is_historical_low, -candidate.discount_pct, candidate.name)


def sale_started_on(history: Sequence[tuple[date, int]], today: date) -> date | None:
    """First day of the current sale: the day after the last regular-price day before today.

    `history` is (day, discount_pct) pairs. None if the game was never seen at regular price.
    """
    regular_days = [day for day, discount in history if discount == 0 and day < today]
    return max(regular_days) + timedelta(days=1) if regular_days else None


def already_notified(previous: Sequence[tuple[datetime, int]], sale_start: date | None, price: int) -> bool:
    """True if this sale was already announced at the same or a lower price."""
    since = datetime.combine(sale_start, time.min, tzinfo=db.JST) if sale_start else None
    return any(price >= old_price and (since is None or at >= since) for at, old_price in previous)


def format_price(amount: int, currency: str) -> str:
    if currency == "JPY":
        return f"¥{amount:,}"
    return f"{amount / 100:,.2f} {currency}"


def build_embed(c: SaleCandidate) -> dict:
    lines = [
        f"~~{format_price(c.regular_price, c.currency)}~~ → "
        f"**{format_price(c.price, c.currency)}（-{c.discount_pct}%）**"
    ]

    notes = []
    if c.is_historical_low:
        notes.append("過去最安値を更新！" if c.price < c.lowest_price else "過去最安値！")
    elif c.lowest_price is not None:
        notes.append(f"最安値 {format_price(c.lowest_price, c.currency)}")
    if c.average:
        average = format_price(round(c.average), c.currency)
        below = c.below_average_pct
        notes.append(f"1年の平均 {average} より{below:.0f}%安い" if below >= 1 else f"1年の平均 {average}")
    if notes:
        lines.append(" ｜ ".join(notes))

    if c.sale_ends_at:
        ends = c.sale_ends_at.astimezone(db.JST)
        lines.append(f"セール終了：{ends.month}/{ends.day} {ends:%H:%M}")

    embed = {
        "title": f"🏆 {c.name}" if c.is_historical_low else c.name,
        "url": STORE_URL.format(appid=c.appid),
        "description": "\n".join(lines),
        "color": COLOR_LOW if c.is_historical_low else COLOR_SALE,
    }
    if c.header_image_url:
        embed["thumbnail"] = {"url": c.header_image_url}
    return embed


def _get_player_id(database: Client, steam_id: str) -> str:
    result = database.table("players").select("id").eq("steam_id", steam_id).limit(1).execute()
    if not result.data:
        raise RuntimeError("Player not found. Run sync-steam or sync-wishlist first.")
    return result.data[0]["id"]


def _load_today_candidates(database: Client, player_id: str, today: date) -> list[dict]:
    wishlist = (
        database.table("wishlist_items")
        .select("game_id, games(name, steam_appid, header_image_url, lowest_price)")
        .eq("player_id", player_id)
        .is_("removed_at", "null")
        .execute()
        .data
    )
    games = {row["game_id"]: row["games"] for row in wishlist}
    if not games:
        return []
    prices = (
        database.table("price_history")
        .select("game_id, price, regular_price, discount_pct, currency, sale_ends_at")
        .eq("recorded_on", today.isoformat())
        .eq("source", "collector")
        .in_("game_id", list(games))
        .execute()
        .data
    )
    return [{**row, **games[row["game_id"]]} for row in prices if row["discount_pct"] > 0]


def _load_history(database: Client, game_id: int) -> list[dict]:
    return (
        database.table("price_history")
        .select("recorded_on, price, discount_pct")
        .eq("game_id", game_id)
        .order("recorded_on")
        .limit(10_000)
        .execute()
        .data
    )


def _load_previous_notifications(database: Client, player_id: str, game_id: int) -> list[tuple[datetime, int]]:
    rows = (
        database.table("sale_notifications")
        .select("notified_at, price")
        .eq("player_id", player_id)
        .eq("game_id", game_id)
        .order("notified_at", desc=True)
        .limit(50)
        .execute()
        .data
    )
    return [(datetime.fromisoformat(r["notified_at"]), r["price"]) for r in rows]


def notify_sales(settings: Settings, *, dry_run: bool = False) -> list[SaleCandidate]:
    settings.require("steam_id", *(() if dry_run else ("discord_webhook_url",)))
    database = db.connect(settings)
    today = db.today_jst()
    player_id = _get_player_id(database, settings.steam_id)

    rows = _load_today_candidates(database, player_id, today)
    if not rows:
        print("No wishlist games on sale today (did sync-wishlist run today?)")

    to_send: list[SaleCandidate] = []
    for row in rows:
        history = _load_history(database, row["game_id"])
        points = [(date.fromisoformat(h["recorded_on"]), h["price"]) for h in history]
        candidate = SaleCandidate(
            game_id=row["game_id"],
            appid=row["steam_appid"],
            name=row["name"],
            header_image_url=row["header_image_url"],
            price=row["price"],
            regular_price=row["regular_price"],
            discount_pct=row["discount_pct"],
            currency=row["currency"],
            sale_ends_at=datetime.fromisoformat(row["sale_ends_at"]) if row["sale_ends_at"] else None,
            lowest_price=row["lowest_price"],
            average=time_weighted_average(points, today=today, days=AVERAGE_DAYS),
        )
        if not should_notify(candidate, settings.notify_min_discount):
            continue
        sale_start = sale_started_on(
            [(date.fromisoformat(h["recorded_on"]), h["discount_pct"]) for h in history], today
        )
        previous = _load_previous_notifications(database, player_id, candidate.game_id)
        if already_notified(previous, sale_start, candidate.price):
            print(f"  already notified: {candidate.name}")
            continue
        to_send.append(candidate)

    to_send.sort(key=sort_key)
    for c in to_send:
        mark = "LOW " if c.is_historical_low else ""
        print(f"  {mark}-{c.discount_pct}% {c.name}: {format_price(c.price, c.currency)}")

    if dry_run or not to_send:
        print(f"{len(to_send)} to notify" + (" (dry run, nothing sent)" if dry_run else ""))
        return to_send

    send_embeds(
        settings.discord_webhook_url,
        [build_embed(c) for c in to_send],
        content=f"🛒 ウィッシュリストのセール情報（{len(to_send)}本）",
    )
    database.table("sale_notifications").insert(
        [
            {
                "player_id": player_id,
                "game_id": c.game_id,
                "price": c.price,
                "discount_pct": c.discount_pct,
                "score": round(c.below_average_pct, 3) if c.below_average_pct is not None else None,
            }
            for c in to_send
        ],
        returning="minimal",
    ).execute()
    db.record_success(database, JOB, player_id, f"sent={len(to_send)}")
    print(f"Sent {len(to_send)} to Discord")
    return to_send


def build_failure_embed(failed_jobs: Sequence[str], run_url: str | None) -> dict:
    labels = [f"・{JOB_LABELS.get(job, job)}（`{job}`）" for job in failed_jobs]
    description = "\n".join(["次の取得に失敗しました。", *labels])
    if run_url:
        description += f"\n\n[実行ログを見る]({run_url})"
    return {"title": "⚠️ 毎日の更新に失敗しました", "description": description, "color": COLOR_ERROR}


def notify_failure(settings: Settings, failed_jobs: Sequence[str], run_url: str | None) -> None:
    settings.require("discord_webhook_url")
    send_embeds(settings.discord_webhook_url, [build_failure_embed(failed_jobs, run_url)])
