"""Settings loaded from environment variables (and .env for local runs)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    steam_api_key: str | None
    steam_id: str | None
    itad_api_key: str | None
    discord_webhook_url: str | None
    supabase_url: str | None
    supabase_anon_key: str | None
    supabase_service_role_key: str | None
    steam_country_code: str
    notify_min_discount: int

    def require(self, *names: str) -> None:
        """Raise ConfigError listing every missing setting among `names`."""
        missing = [name for name in names if not getattr(self, name)]
        if missing:
            env_names = ", ".join(name.upper() for name in missing)
            raise ConfigError(f"Missing required settings: {env_names} (see .env.example)")


def _get(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def load_settings(*, prefer_env_file: bool = False) -> Settings:
    # Real environment variables (e.g. GitHub Actions secrets) take precedence over .env,
    # except in the local admin, which edits .env and must see its own changes.
    load_dotenv(override=prefer_env_file)
    return Settings(
        steam_api_key=_get("STEAM_API_KEY"),
        steam_id=_get("STEAM_ID"),
        itad_api_key=_get("ITAD_API_KEY"),
        discord_webhook_url=_get("DISCORD_WEBHOOK_URL"),
        supabase_url=_get("SUPABASE_URL"),
        supabase_anon_key=_get("SUPABASE_ANON_KEY"),
        supabase_service_role_key=_get("SUPABASE_SERVICE_ROLE_KEY"),
        steam_country_code=_get("STEAM_COUNTRY_CODE") or "JP",
        notify_min_discount=int(_get("NOTIFY_MIN_DISCOUNT") or 20),
    )
