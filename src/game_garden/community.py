"""Read unlocked achievements from a Steam Community profile page.

Used for Steam games that GetOwnedGames leaves out (e.g. free games never launched), so
their achievements are not synced daily. The profile's achievements page still lists them.
This is scraping, not an API, so it may break when Steam changes the page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

PAGE_URL = "https://steamcommunity.com/profiles/{steam_id}/stats/{appid}/achievements/?l=english"
# The page shows unlock times in US Pacific time (with DST) to logged-out visitors.
PAGE_TZ = ZoneInfo("America/Los_Angeles")

_ROW = re.compile(r'class="achieveRow[^"]*">(.*?)(?=class="achieveRow|<div id="footer|\Z)', re.S)
_ICON = re.compile(r'<img src="[^"]*/apps/\d+/([0-9a-f]+)\.(?:jpg|png)"')
_UNLOCK = re.compile(r'class="achieveUnlockTime">\s*Unlocked\s+(.*?)\s*<br', re.S)
_WHEN = re.compile(r"(\d{1,2}) (\w{3})(?:, (\d{4}))? @ (\d{1,2}):(\d{2})(am|pm)")
_MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}


class CommunityPageError(RuntimeError):
    pass


@dataclass(frozen=True)
class PageRow:
    icon_hash: str  # file name of the icon; matches the colour or grey icon in the API schema
    unlocked_at: datetime | None  # None when locked


def icon_hash(url: str | None) -> str | None:
    """'.../apps/123/abcd.jpg' -> 'abcd'"""
    if not url:
        return None
    return url.rsplit("/", 1)[-1].split(".", 1)[0]


def parse_unlock_time(text: str, now: datetime) -> datetime | None:
    """'4 Mar, 2022 @ 1:23am' or '4 Oct @ 4:23am' (current year omitted), Pacific time -> UTC."""
    m = _WHEN.search(text)
    if not m:
        return None
    day, month, year, hour, minute, ampm = m.groups()
    hour_24 = int(hour) % 12 + (12 if ampm == "pm" else 0)
    local_year = int(year) if year else now.astimezone(PAGE_TZ).year
    local = datetime(local_year, _MONTHS[month], int(day), hour_24, int(minute), tzinfo=PAGE_TZ)
    return local.astimezone(UTC)


def parse_page(page: str, now: datetime) -> list[PageRow]:
    if "achieveRow" not in page:
        raise CommunityPageError("No achievements on the page (private profile, wrong app, or layout changed)")
    rows = []
    for block in _ROW.findall(page):
        icon = _ICON.search(block)
        if not icon:
            continue
        unlock = _UNLOCK.search(block)
        rows.append(PageRow(icon_hash=icon.group(1), unlocked_at=parse_unlock_time(unlock.group(1), now) if unlock else None))
    return rows


def fetch_page_rows(steam_id: str, appid: int, *, http: httpx.Client | None = None) -> list[PageRow]:
    client = http or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        response = client.get(PAGE_URL.format(steam_id=steam_id, appid=appid))
        response.raise_for_status()
        return parse_page(response.text, datetime.now(UTC))
    finally:
        if http is None:
            client.close()
