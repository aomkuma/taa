from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import WebSettings
from app.core.clock import ManualClock
from app.security import web_totp
from app.storage.database import Database
from app.storage.models import UserRow
from app.web.app import create_app
from app.web.auth import AuthService

SESSION_SECRET = "test-web-session-secret-0123456789abcdef"
DEV_ENV = {"WEB_ENV": "development", "WEB_SESSION_SECRET": SESSION_SECRET}
PROD_ENV = {
    "WEB_ENV": "production",
    "WEB_PUBLIC_ORIGIN": "https://taa.example.com",
    "WEB_SESSION_SECRET": SESSION_SECRET,
}
DEV_ORIGIN = "http://127.0.0.1:5173"
TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>TAA</title>", encoding="utf-8")
    (root / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (root / "manifest.webmanifest").write_text("{}", encoding="utf-8")
    (root / "sw.js").write_text("self.x=1", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside the static root", encoding="utf-8")
    return root


def make_app(
    db: Database, clock: ManualClock, static_dir: Path, env: dict[str, str] | None = None
) -> FastAPI:
    settings = WebSettings.model_validate(env or DEV_ENV)
    return create_app(settings, db=db, clock=clock, static_dir=static_dir)


@pytest.fixture
def app(db: Database, clock: ManualClock, static_dir: Path) -> FastAPI:
    return make_app(db, clock, static_dir)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # https: production session cookies are Secure, so the test client must look like a TLS origin.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def auth(app: FastAPI) -> AuthService:
    service: AuthService = app.state.ctx.auth
    return service


@pytest.fixture
def owner(auth: AuthService) -> UserRow:
    return auth.create_user("owner", PASSWORD, TOTP_SECRET)


def current_code(clock: ManualClock, secret: str = TOTP_SECRET) -> str:
    return web_totp.code_at(secret, web_totp.time_step(clock.now_utc()))


def login(
    client: TestClient,
    clock: ManualClock,
    *,
    username: str = "owner",
    password: str = PASSWORD,
    code: str | None = None,
    origin: str | None = DEV_ORIGIN,
) -> httpx.Response:
    headers = {"Origin": origin} if origin else {}
    body = {"username": username, "password": password, "code": code or current_code(clock)}
    return client.post("/api/v1/auth/login", json=body, headers=headers)


def mutation_headers(client: TestClient, origin: str = DEV_ORIGIN) -> dict[str, str]:
    """Origin + CSRF token of the client's current session."""
    token = client.get("/api/v1/auth/session").json()["csrf_token"]
    return {"Origin": origin, "X-CSRF-Token": token}


ENGINE_ID = "eng-1"
ENGINE_SECRET = "engine-hmac-secret-0123456789abcdef-xyz"


def pair_engine(
    app: FastAPI,
    engine_id: str = ENGINE_ID,
    secret: str = ENGINE_SECRET,
    previous: str | None = None,
    *,
    username: str = "owner",
) -> UserRow:
    """Register an engine in the app's registry (rev. 4: engine keys live in the database)."""
    ctx = app.state.ctx
    users = {u.username: u for u in ctx.auth.list_users()}
    user = users.get(username) or ctx.auth.create_user(username, PASSWORD, TOTP_SECRET)
    ctx.engine.registry.import_env(user, engine_id, secret, previous, actor="pytest")
    return user
