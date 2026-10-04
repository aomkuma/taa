from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import WebSettings
from app.core.clock import ManualClock
from app.storage.database import Database
from app.web.app import create_app

DEV_ENV = {"WEB_ENV": "development"}
PROD_ENV = {"WEB_ENV": "production", "WEB_PUBLIC_ORIGIN": "https://taa.example.com"}


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
    # https: session cookies are Secure, so the test client must look like a TLS origin.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
