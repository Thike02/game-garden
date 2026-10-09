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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="game-garden")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("check-config", help="show which settings are present").set_defaults(func=check_config)

    steam = commands.add_parser("sync-steam", help="sync owned games and achievements from Steam")
    steam.add_argument("--full", action="store_true", help="refetch achievements for every owned game")
    steam.add_argument("--limit", type=int, help="sync achievements for at most N games")
    steam.set_defaults(func=sync_steam)
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
