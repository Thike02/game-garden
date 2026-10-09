"""Update KEY=value lines in a .env file without touching anything else."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

_LINE = re.compile(r"^\s*([A-Z0-9_]+)\s*=")


def _format(value: str) -> str:
    # Quote only when needed so the file stays readable.
    if value == "" or re.fullmatch(r"[\w@:/.,+\-%?&=~]+", value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_env(existing: str, values: Mapping[str, str]) -> str:
    """Replace the given keys in place, append new ones, keep comments and other lines."""
    remaining = dict(values)
    lines = []
    for line in existing.splitlines():
        m = _LINE.match(line)
        if m and m.group(1) in remaining:
            key = m.group(1)
            lines.append(f"{key}={_format(remaining.pop(key))}")
        else:
            lines.append(line)
    if remaining:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(f"{key}={_format(value)}" for key, value in remaining.items())
    return "\n".join(lines) + "\n"


def update_env_file(path: Path, values: Mapping[str, str], *, template: Path | None = None) -> None:
    """Write `values` into `path`, starting from `template` (e.g. .env.example) if `path` is missing."""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    elif template and template.exists():
        existing = template.read_text(encoding="utf-8")
    else:
        existing = ""
    path.write_text(render_env(existing, values), encoding="utf-8")
