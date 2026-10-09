"""Game Garden: track owned games, achievements and wishlist prices."""

from __future__ import annotations

import argparse
import sys

from game_garden.config import ConfigError, load_settings

SETTING_NAMES = (
    "steam_api_key",
    "steam_id",
    "itad_api_key",
    "discord_webhook_url",
    "supabase_url",
    "supabase_anon_key",
    "supabase_service_role_key",
)


def check_config(args: argparse.Namespace) -> None:
    settings = load_settings()
    for name in SETTING_NAMES:
        mark = "ok" if getattr(settings, name) else "--"
        print(f"[{mark}] {name.upper()}")
    print(f"[ok] STEAM_COUNTRY_CODE={settings.steam_country_code}")
    settings.require(*SETTING_NAMES)


def sync_steam(args: argparse.Namespace) -> None:
    from game_garden.steam_sync import sync_steam as run

    result = run(load_settings(), full=args.full, limit=args.limit)
    print(
        f"Done: {result.owned_games} owned, {result.achievement_games} achievement syncs, {result.failed} failed"
    )


def sync_wishlist(args: argparse.Namespace) -> None:
    from game_garden.wishlist_sync import sync_wishlist as run

    run(load_settings())


def notify_sales(args: argparse.Namespace) -> None:
    from game_garden.notify import notify_sales as run

    run(load_settings(), dry_run=args.dry_run)


def notify_failure(args: argparse.Namespace) -> None:
    from game_garden.notify import notify_failure as run

    run(load_settings(), args.failed, args.run_url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="game-garden")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("check-config", help="show which settings are present").set_defaults(func=check_config)

    steam = commands.add_parser("sync-steam", help="sync owned games and achievements from Steam")
    steam.add_argument("--full", action="store_true", help="refetch achievements for every owned game")
    steam.add_argument("--limit", type=int, help="sync achievements for at most N games")
    steam.set_defaults(func=sync_steam)

    commands.add_parser(
        "sync-wishlist", help="sync the Steam wishlist, record today's prices and backfill history from ITAD"
    ).set_defaults(func=sync_wishlist)

    notify = commands.add_parser("notify-sales", help="send today's wishlist sales to Discord")
    notify.add_argument("--dry-run", action="store_true", help="print what would be sent without sending")
    notify.set_defaults(func=notify_sales)

    failure = commands.add_parser("notify-failure", help="tell Discord that scheduled jobs failed")
    failure.add_argument("--failed", action="append", required=True, help="failed command name (repeatable)")
    failure.add_argument("--run-url", help="link to the CI run log")
    failure.set_defaults(func=notify_failure)
    return parser


def main() -> None:
    # Game names can contain characters the Windows console code page (cp932) cannot encode.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args()
    try:
        args.func(args)
    except ConfigError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
