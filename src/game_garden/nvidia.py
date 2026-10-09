"""Last launch times NVIDIA App records for the games it detects. Read-only, local."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

STORAGE = Path(os.path.expandvars(r"%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA App\NvBackend\ApplicationStorage.json"))
_NEVER = "1601-01-01"  # NVIDIA's value for "not launched yet"


@dataclass(frozen=True)
class NvidiaApp:
    short_name: str  # e.g. 'arknights_endfield'
    display_name: str
    last_launch: datetime | None


def detected_apps(path: Path = STORAGE) -> list[NvidiaApp]:
    """Apps NVIDIA App knows about; empty when it isn't installed."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    apps = []
    for entry in data.get("Applications", []):
        app = entry.get("Application", {})
        if not app.get("ShortName"):
            continue
        raw = app.get("LastLaunchTimeISO") or ""
        last = None if not raw or raw.startswith(_NEVER) else datetime.fromisoformat(raw.replace("Z", "+00:00"))
        apps.append(NvidiaApp(app["ShortName"], app.get("DisplayName") or app["ShortName"], last))
    return sorted(apps, key=lambda a: a.display_name.lower())
