"""Send messages to a Discord channel webhook."""

from __future__ import annotations

import time
from collections.abc import Sequence

import httpx

MAX_EMBEDS_PER_MESSAGE = 10


class DiscordError(RuntimeError):
    pass


def send_embeds(
    webhook_url: str,
    embeds: Sequence[dict],
    *,
    content: str | None = None,
    http: httpx.Client | None = None,
    max_retries: int = 3,
) -> None:
    """Post embeds, 10 per message (Discord's limit). `content` goes on the first message only."""
    client = http or httpx.Client(timeout=30.0)
    try:
        for start in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            payload: dict = {"embeds": list(embeds[start : start + MAX_EMBEDS_PER_MESSAGE])}
            if content and start == 0:
                payload["content"] = content
            _post(client, webhook_url, payload, max_retries)
    finally:
        if http is None:
            client.close()


def _post(client: httpx.Client, url: str, payload: dict, max_retries: int) -> None:
    for attempt in range(max_retries + 1):
        response = client.post(url, json=payload)
        if response.status_code == 429 and attempt < max_retries:
            time.sleep(float(response.json().get("retry_after", 1)))
            continue
        if response.status_code >= 400:
            # Don't echo the URL: it contains the webhook token.
            raise DiscordError(f"Discord webhook returned {response.status_code}: {response.text[:200]}")
        return
