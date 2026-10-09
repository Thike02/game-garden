"""Find Steam apps this PC has played, from the local Steam client's files.

The Web API leaves some owned games out (titles with mature content), so the local
client is the only place that lists them. Read-only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_STEAM_DIR = Path(r"C:\Program Files (x86)\Steam")
_STATS_FILE = re.compile(r"UserGameStats_(\d+)_(\d+)\.bin$")
# localconfig.vdf: "Software" > "Valve" > "Steam" > "apps" > "<appid>" { ... }
_APPS_SECTION = re.compile(r'\n(\t+)"apps"\n\1\{\n(.*?)\n\1\}', re.S)


def steam_dir() -> Path:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                return Path(winreg.QueryValueEx(key, "SteamPath")[0])
        except OSError:
            pass
    return DEFAULT_STEAM_DIR


def account_id(steam_id64: str) -> int:
    """SteamID64 -> the 32-bit account id used in local folder names."""
    return int(steam_id64) - 76561197960265728


def played_appids(steam_path: Path, steam_id64: str) -> set[int]:
    """Apps with local stats files or an entry in this account's localconfig.vdf."""
    account = account_id(steam_id64)
    apps: set[int] = set()

    stats_dir = steam_path / "appcache" / "stats"
    if stats_dir.is_dir():
        for f in stats_dir.iterdir():
            m = _STATS_FILE.match(f.name)
            if m and int(m.group(1)) == account:
                apps.add(int(m.group(2)))

    config = steam_path / "userdata" / str(account) / "config" / "localconfig.vdf"
    if config.is_file():
        text = config.read_text(encoding="utf-8", errors="ignore")
        section = _APPS_SECTION.search(text)
        if section:
            indent = section.group(1) + "\t"
            apps.update(int(a) for a in re.findall(rf'^{indent}"(\d+)"$', section.group(2), re.M))
    return apps
