"""Checks run by the admin's setup page before keys are saved."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass

import httpx
from supabase import create_client

from game_garden.itad import ItadClient
from game_garden.steam import SteamClient, SteamPrivateProfileError

# Secrets the GitHub Actions workflows read (daily.yml and pages.yml).
GITHUB_SECRETS = (
    "STEAM_API_KEY",
    "STEAM_ID",
    "ITAD_API_KEY",
    "DISCORD_WEBHOOK_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
)
SAMPLE_APPID = 1456880  # any public Steam app works for the ITAD check


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    message: str


def _run(name: str, check) -> CheckResult:
    try:
        return CheckResult(name, True, check())
    except Exception as e:  # report every failure on the page instead of crashing
        return CheckResult(name, False, f"{type(e).__name__}: {e}")


def check_steam(api_key: str, steam_id: str) -> str:
    with SteamClient(api_key) as steam:
        player = steam.get_player_summary(steam_id)
        try:
            owned = steam.get_owned_games(steam_id)
        except SteamPrivateProfileError:
            raise RuntimeError(
                f"{player.display_name} さんのゲームが見えません。Steam のプライバシー設定で「ゲームの詳細」を公開にしてください"
            ) from None
    return f"{player.display_name} さん・{len(owned)} 本のゲームが見えます"


def check_itad(api_key: str) -> str:
    with ItadClient(api_key) as itad:
        if not itad.lookup_steam_apps([SAMPLE_APPID]):
            raise RuntimeError("ゲームを1本も調べられませんでした")
    return "価格の履歴を取得できます"


def check_supabase(url: str, key: str, label: str) -> str:
    create_client(url, key).table("games").select("id", count="exact", head=True).execute()
    return f"{label}でテーブルを読めます"


def check_discord(webhook_url: str, *, send_test: bool) -> str:
    # GET on a webhook URL returns its info without posting anything.
    response = httpx.get(webhook_url, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"Webhook が見つかりません（{response.status_code}）")
    channel = response.json().get("name", "webhook")
    if send_test:
        httpx.post(webhook_url, json={"content": "🌱 Game Garden の設定画面からのテストメッセージです"}, timeout=15).raise_for_status()
        return f"「{channel}」にテストメッセージを送りました"
    return f"「{channel}」に送れます"


def run_checks(values: Mapping[str, str], *, send_discord_test: bool) -> list[CheckResult]:
    v = {k: (values.get(k) or "").strip() for k in GITHUB_SECRETS}
    results = [
        _run("Steam", lambda: check_steam(v["STEAM_API_KEY"], v["STEAM_ID"])),
        _run("IsThereAnyDeal", lambda: check_itad(v["ITAD_API_KEY"])),
        _run("Supabase（service_role）", lambda: check_supabase(v["SUPABASE_URL"], v["SUPABASE_SERVICE_ROLE_KEY"], "service_role キー")),
        _run("Supabase（anon）", lambda: check_supabase(v["SUPABASE_URL"], v["SUPABASE_ANON_KEY"], "公開キー")),
        _run("Discord", lambda: check_discord(v["DISCORD_WEBHOOK_URL"], send_test=send_discord_test)),
    ]
    return results


def set_github_secrets(values: Mapping[str, str]) -> list[CheckResult]:
    """`gh secret set` for each workflow secret in the current repository. Values go over stdin."""
    results = []
    for name in GITHUB_SECRETS:
        value = (values.get(name) or "").strip()
        if not value:
            results.append(CheckResult(name, False, "値が空なので登録しませんでした"))
            continue
        proc = subprocess.run(["gh", "secret", "set", name], input=value, text=True, capture_output=True)
        results.append(
            CheckResult(name, proc.returncode == 0, "登録しました" if proc.returncode == 0 else proc.stderr.strip()[:200])
        )
    return results
