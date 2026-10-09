"""Supabase access for the collector (service_role, bypasses RLS)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

from supabase import Client, create_client

from game_garden.config import Settings

CHUNK_SIZE = 500


def connect(settings: Settings) -> Client:
    settings.require("supabase_url", "supabase_service_role_key")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def chunks(rows: Sequence[Any], size: int = CHUNK_SIZE) -> Iterator[Sequence[Any]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def upsert(
    db: Client, table: str, rows: Sequence[dict], on_conflict: str, *, returning: bool = False
) -> list[dict]:
    """Upsert in chunks. Returns the stored rows only when `returning` is set."""
    stored: list[dict] = []
    for chunk in chunks(rows):
        query = db.table(table).upsert(
            list(chunk), on_conflict=on_conflict, returning="representation" if returning else "minimal"
        )
        result = query.execute()
        if returning:
            stored.extend(result.data)
    return stored


# job_runs.last_run_at always means "last successful run"; a failure only flips status/detail.


def get_last_run(db: Client, job: str, player_id: str) -> datetime | None:
    result = (
        db.table("job_runs").select("last_run_at").eq("job", job).eq("player_id", player_id).limit(1).execute()
    )
    if not result.data:
        return None
    return datetime.fromisoformat(result.data[0]["last_run_at"])


def record_success(db: Client, job: str, player_id: str, detail: str | None = None) -> None:
    row = {"job": job, "player_id": player_id, "last_run_at": utcnow_iso(), "status": "ok", "detail": detail}
    db.table("job_runs").upsert(row, on_conflict="job,player_id", returning="minimal").execute()


def record_failure(db: Client, job: str, player_id: str, detail: str) -> None:
    (
        db.table("job_runs")
        .update({"status": "error", "detail": detail[:1000]}, returning="minimal")
        .eq("job", job)
        .eq("player_id", player_id)
        .execute()
    )
