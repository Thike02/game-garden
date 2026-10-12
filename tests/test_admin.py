from fastapi.testclient import TestClient

from game_garden.admin import create_app

BASE = "http://127.0.0.1:8765"


def test_rejects_other_hosts():
    client = TestClient(create_app(), base_url="http://evil.example:8765")
    assert client.get("/setup").status_code == 403


def test_post_without_token_is_rejected():
    client = TestClient(create_app(), base_url=BASE)
    response = client.post("/games/1/delete", data={"csrf": "wrong"})
    assert response.status_code == 403


def test_setup_page_renders():
    client = TestClient(create_app(), base_url=BASE)
    response = client.get("/setup")
    assert response.status_code == 200
    assert "STEAM_API_KEY" in response.text


def test_csrf_token_survives_a_restart(monkeypatch):
    # serve() sets this once; reloaded app instances must reuse it so open pages keep working
    from game_garden.admin import CSRF_ENV, templates

    monkeypatch.setenv(CSRF_ENV, "fixed-token")
    create_app()
    assert templates.env.globals["csrf"] == "fixed-token"
    client = TestClient(create_app(), base_url=BASE)
    assert client.post("/games/1/delete", data={"csrf": "other"}).status_code == 403
