"""Game Garden: track owned games, achievements and wishlist prices."""

from __future__ import annotations

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


def check_config() -> None:
    settings = load_settings()
    for name in SETTING_NAMES:
        mark = "ok" if getattr(settings, name) else "--"
        print(f"[{mark}] {name.upper()}")
    print(f"[ok] STEAM_COUNTRY_CODE={settings.steam_country_code}")
    try:
        settings.require(*SETTING_NAMES)
    except ConfigError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    commands = {"check-config": check_config}
    command = sys.argv[1] if len(sys.argv) > 1 else None
    if command not in commands:
        print(f"usage: game-garden {{{','.join(commands)}}}", file=sys.stderr)
        sys.exit(2)
    commands[command]()
