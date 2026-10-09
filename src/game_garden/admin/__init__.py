"""Local admin: first-run setup, hand-entered games, and Steam games missing from the owned list.

Runs on 127.0.0.1 only and uses the service_role key from .env.
"""

from __future__ import annotations

import secrets
import webbrowser
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from game_garden import db, library
from game_garden.config import Settings, load_settings
from game_garden.env_file import update_env_file
from game_garden.images import ImageError, upload_game_image
from game_garden.local_state import ignore_appid
from game_garden.setup_checks import GITHUB_SECRETS, run_checks, set_github_secrets
from game_garden.steam import SteamClient

HOST = "127.0.0.1"
PORT = 8765
ENV_PATH = Path(".env")
ENV_TEMPLATE = Path(".env.example")
REQUIRED = ("steam_api_key", "steam_id", "supabase_url", "supabase_service_role_key")
STORE_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _settings() -> Settings:
    return load_settings(prefer_env_file=True)


def _missing(settings: Settings) -> list[str]:
    return [name for name in REQUIRED if not getattr(settings, name)]


def _back(path: str, message: str | None = None, error: str | None = None) -> RedirectResponse:
    query = []
    if message:
        query.append(f"msg={quote(message)}")
    if error:
        query.append(f"err={quote(error)}")
    return RedirectResponse(path + ("?" + "&".join(query) if query else ""), status_code=303)


def _minutes(hours: str | None) -> int | None:
    if not hours or not hours.strip():
        return None
    return round(float(hours) * 60)


def _int(value: str | None) -> int | None:
    return int(value) if value and value.strip() else None


async def _image_url(database, image_url: str, image_file: UploadFile | None) -> str:
    """An uploaded file wins over a typed URL."""
    if image_file is not None and image_file.filename:
        return upload_game_image(database, await image_file.read())
    return image_url.strip()


def create_app() -> FastAPI:
    app = FastAPI(title="Game Garden admin", docs_url=None, redoc_url=None, openapi_url=None)
    # Any web page could POST to localhost, so every form carries this per-process token.
    csrf_token = secrets.token_urlsafe(32)
    templates.env.globals["csrf"] = csrf_token
    templates.env.globals["platforms"] = library.PLATFORMS

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # Reject other Host headers (DNS rebinding) even though we only listen on 127.0.0.1.
        if request.headers.get("host") not in {f"{HOST}:{PORT}", f"localhost:{PORT}"}:
            return HTMLResponse("Forbidden", status_code=403)
        return await call_next(request)

    def check_csrf(csrf: str = Form(...)) -> None:
        if not secrets.compare_digest(csrf, csrf_token):
            raise HTTPException(status_code=403, detail="invalid form token")

    def page(request: Request, name: str, **context) -> HTMLResponse:
        context.setdefault("msg", request.query_params.get("msg"))
        context.setdefault("err", request.query_params.get("err"))
        return templates.TemplateResponse(request, name, context)

    def clients(settings: Settings):
        database = db.connect(settings)
        steam = SteamClient(settings.steam_api_key)
        return database, steam

    # ---------------------------------------------------------------- setup

    @app.get("/setup", response_class=HTMLResponse)
    def setup_form(request: Request):
        settings = _settings()
        values = {name: getattr(settings, name.lower()) or "" for name in GITHUB_SECRETS}
        return page(request, "setup.html", values=values, missing=_missing(settings), results=None)

    @app.post("/setup", response_class=HTMLResponse, dependencies=[Depends(check_csrf)])
    async def setup_submit(request: Request):
        form = await request.form()
        action = form.get("action")
        values = {name: str(form.get(name, "")).strip() for name in GITHUB_SECRETS}
        if action == "secrets":
            results = set_github_secrets(values)
            return page(request, "setup.html", values=values, missing=[], results=results, title="GitHub Secrets")
        results = run_checks(values, send_discord_test=form.get("discord_test") == "on")
        if action == "save":
            update_env_file(ENV_PATH, values, template=ENV_TEMPLATE)
            return page(
                request, "setup.html", values=values, missing=_missing(_settings()), results=results,
                title="確認結果", msg=".env に保存しました",
            )
        return page(request, "setup.html", values=values, missing=_missing(_settings()), results=results, title="確認結果")

    # ---------------------------------------------------------------- library

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, q: str | None = None):
        settings = _settings()
        if _missing(settings):
            return RedirectResponse("/setup", status_code=303)
        database, steam = clients(settings)
        with steam:
            player_id = library.get_player_id(database, steam, settings)
        games = library.list_managed_games(database, player_id)
        search = []
        if q and q.strip():
            if q.strip().isdigit():
                search = [{"id": int(q), "name": f"App {q.strip()}（ID で追加）"}]
            else:
                response = httpx.get(STORE_SEARCH_URL, params={"term": q, "cc": "jp", "l": "japanese"}, timeout=15)
                search = response.json().get("items", [])[:10]
        return page(
            request, "index.html",
            manual=[g for g in games if g["source"] == "manual"],
            hidden=[g for g in games if g["source"] == "community"],
            q=q or "", search=search,
        )

    @app.post("/manual", dependencies=[Depends(check_csrf)])
    async def add_manual(
        name: str = Form(...), platform: str = Form(...), image_url: str = Form(""),
        image_file: UploadFile | None = File(None),
        achievements_total: str = Form(""), achievements_unlocked: str = Form(""),
        playtime_hours: str = Form(""), is_visible: str | None = Form(None),
    ):
        settings = _settings()
        database, steam = clients(settings)
        try:
            with steam:
                player_id = library.get_player_id(database, steam, settings)
            image = await _image_url(database, image_url, image_file)
            library.add_manual_game(
                database, player_id, name=name, platform=platform, image_url=image,
                achievements_total=_int(achievements_total), achievements_unlocked=_int(achievements_unlocked),
                playtime_minutes=_minutes(playtime_hours), is_visible=is_visible == "on",
            )
        except (library.LibraryError, ImageError, ValueError) as e:
            return _back("/", error=str(e))
        return _back("/", f"{name} を登録しました")

    @app.post("/manual/{game_id}", dependencies=[Depends(check_csrf)])
    async def update_manual(
        game_id: int, name: str = Form(...), platform: str = Form(...), image_url: str = Form(""),
        image_file: UploadFile | None = File(None),
        achievements_total: str = Form(""), achievements_unlocked: str = Form(""), playtime_hours: str = Form(""),
    ):
        settings = _settings()
        database, steam = clients(settings)
        try:
            with steam:
                player_id = library.get_player_id(database, steam, settings)
            image = await _image_url(database, image_url, image_file)
            library.update_manual_game(
                database, player_id, game_id, name=name, platform=platform, image_url=image,
                achievements_total=_int(achievements_total), achievements_unlocked=_int(achievements_unlocked),
                playtime_minutes=_minutes(playtime_hours),
            )
        except (library.LibraryError, ImageError, ValueError) as e:
            return _back("/", error=str(e))
        return _back("/", f"{name} を更新しました")

    @app.post("/hidden", dependencies=[Depends(check_csrf)])
    def add_hidden(appid: int = Form(...), is_visible: str | None = Form(None)):
        settings = _settings()
        database, steam = clients(settings)
        try:
            with steam:
                game_id = library.add_hidden_steam_game(database, steam, settings, appid, is_visible=is_visible == "on")
        except library.LibraryError as e:
            return _back("/", error=str(e))
        name = database.table("games").select("name").eq("id", game_id).execute().data[0]["name"]
        return _back("/", f"{name} を追加しました")

    @app.post("/hidden/{game_id}/refresh", dependencies=[Depends(check_csrf)])
    def refresh_hidden(game_id: int):
        settings = _settings()
        database, steam = clients(settings)
        try:
            with steam:
                unlocked, total = library.sync_hidden_steam_game(database, steam, settings, game_id)
        except library.LibraryError as e:
            return _back("/", error=str(e))
        return _back("/", f"実績を更新しました（{unlocked}/{total}）" if total else "このゲームに実績はありません")

    @app.post("/games/{game_id}/visibility", dependencies=[Depends(check_csrf)])
    def visibility(game_id: int, is_visible: str = Form(...)):
        settings = _settings()
        database, steam = clients(settings)
        with steam:
            player_id = library.get_player_id(database, steam, settings)
        library.set_visibility(database, player_id, game_id, is_visible == "true")
        return _back("/", "公開ページに出すようにしました" if is_visible == "true" else "公開ページから隠しました")

    @app.post("/games/{game_id}/playtime", dependencies=[Depends(check_csrf)])
    def playtime(game_id: int, playtime_hours: str = Form("")):
        settings = _settings()
        database, steam = clients(settings)
        try:
            with steam:
                player_id = library.get_player_id(database, steam, settings)
            library.set_playtime(database, player_id, game_id, _minutes(playtime_hours) or 0)
        except (library.LibraryError, ValueError) as e:
            return _back("/", error=str(e))
        return _back("/", "プレイ時間を更新しました")

    @app.post("/games/{game_id}/delete", dependencies=[Depends(check_csrf)])
    def delete(game_id: int):
        settings = _settings()
        database, steam = clients(settings)
        try:
            with steam:
                player_id = library.get_player_id(database, steam, settings)
            library.remove_game(database, player_id, game_id)
        except library.LibraryError as e:
            return _back("/", error=str(e))
        return _back("/", "削除しました")

    # ---------------------------------------------------------------- candidates

    @app.get("/candidates", response_class=HTMLResponse)
    def candidates(request: Request):
        settings = _settings()
        if _missing(settings):
            return RedirectResponse("/setup", status_code=303)
        database, steam = clients(settings)
        with steam:
            found = library.find_candidates(database, steam, settings)
        return page(request, "candidates.html", candidates=found)

    @app.post("/candidates/{appid}/ignore", dependencies=[Depends(check_csrf)])
    def ignore(appid: int):
        ignore_appid(appid)
        return _back("/candidates", "候補から外しました")

    return app


def serve(*, open_browser: bool = True) -> None:
    import uvicorn

    url = f"http://{HOST}:{PORT}/"
    print(f"Game Garden admin: {url}  (Ctrl+C で終了)")
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(create_app(), host=HOST, port=PORT, log_level="warning")
