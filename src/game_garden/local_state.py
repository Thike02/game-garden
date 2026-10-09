"""Small per-PC state for the local admin (not shared, not committed)."""

from __future__ import annotations

import json
from pathlib import Path

STATE_FILE = Path(".game-garden-local.json")


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ignored_appids(path: Path = STATE_FILE) -> set[int]:
    return set(_load(path).get("ignored_appids", []))


def ignore_appid(appid: int, path: Path = STATE_FILE) -> None:
    state = _load(path)
    state["ignored_appids"] = sorted(set(state.get("ignored_appids", [])) | {appid})
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def unignore_appid(appid: int, path: Path = STATE_FILE) -> None:
    state = _load(path)
    state["ignored_appids"] = sorted(set(state.get("ignored_appids", [])) - {appid})
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
