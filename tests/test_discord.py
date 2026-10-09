import json

import httpx
import pytest

from game_garden.discord import DiscordError, send_embeds


def test_splits_into_messages_of_ten():
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(204)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    send_embeds("https://discord.test/hook", [{"title": str(i)} for i in range(23)], content="hi", http=http)
    assert [len(m["embeds"]) for m in sent] == [10, 10, 3]
    assert sent[0]["content"] == "hi"
    assert "content" not in sent[1]


def test_error_does_not_leak_webhook_url():
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404, text="Unknown Webhook")))
    with pytest.raises(DiscordError) as e:
        send_embeds("https://discord.test/hook/secret-token", [{"title": "x"}], http=http)
    assert "secret-token" not in str(e.value)
