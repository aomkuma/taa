"""FastAPI skeleton (TAA-801): health, security headers, error shape, size limits, PWA serving."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import WEB_DEV_ORIGINS, WebSettings, load_web_settings, unknown_env_file_keys
from app.core.clock import ManualClock
from app.core.errors import ConfigError
from app.storage.database import Database
from app.web.security_headers import CONTENT_SECURITY_POLICY, DEFAULT_MAX_BODY_BYTES
from tests.web.conftest import DEV_ENV, PROD_ENV, SESSION_SECRET, make_app


class TestSettings:
    def test_production_is_the_default_and_needs_an_https_origin(self) -> None:
        with pytest.raises(ConfigError, match="WEB_PUBLIC_ORIGIN"):
            load_web_settings(env_file=None, environ={"WEB_SESSION_SECRET": SESSION_SECRET})
        with pytest.raises(ConfigError, match="WEB_PUBLIC_ORIGIN"):
            load_web_settings(
                env_file=None,
                environ={"WEB_PUBLIC_ORIGIN": "http://taa.example.com", "WEB_SESSION_SECRET": SESSION_SECRET},
            )

    def test_production_accepts_only_its_origin(self) -> None:
        settings = load_web_settings(env_file=None, environ=PROD_ENV)
        assert settings.is_production
        assert settings.allowed_origins == frozenset({"https://taa.example.com"})

    def test_development_adds_the_local_dev_origins(self) -> None:
        settings = load_web_settings(env_file=None, environ=DEV_ENV)
        assert settings.allowed_origins == frozenset(WEB_DEV_ORIGINS)

    @pytest.mark.parametrize("origin", ["https://taa.example.com/app", "taa.example.com", "ftp://x.y"])
    def test_origin_must_be_scheme_and_host(self, origin: str) -> None:
        with pytest.raises(ConfigError):
            load_web_settings(env_file=None, environ={**DEV_ENV, "WEB_PUBLIC_ORIGIN": origin})

    def test_trailing_slash_is_dropped(self) -> None:
        settings = load_web_settings(
            env_file=None, environ={**PROD_ENV, "WEB_PUBLIC_ORIGIN": "https://taa.example.com/"}
        )
        assert settings.WEB_PUBLIC_ORIGIN == "https://taa.example.com"

    def test_web_keys_in_a_shared_env_file_are_not_typos(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "TRADING_MODE=PAPER\nWEB_ENV=development\nPORT=9000\nWEB_TYPO=1\n", encoding="utf-8"
        )
        assert unknown_env_file_keys(env_file) == ["WEB_TYPO"]

    def test_session_secret_is_required(self) -> None:
        with pytest.raises(ConfigError, match="WEB_SESSION_SECRET"):
            load_web_settings(env_file=None, environ={"WEB_ENV": "development"})

    def test_session_secret_must_be_long(self) -> None:
        with pytest.raises(ConfigError, match="at least 32"):
            load_web_settings(env_file=None, environ={**DEV_ENV, "WEB_SESSION_SECRET": "short-secret"})

    def test_session_secret_is_never_shown(self) -> None:
        settings = load_web_settings(env_file=None, environ=DEV_ENV)
        assert SESSION_SECRET not in repr(settings)


class TestHealth:
    def test_ok(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"] == {"database": True}
        assert body["time"] == "2026-10-01T12:00:00+00:00"

    def test_database_down_is_503(
        self, client: TestClient, db: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(db, "healthcheck", lambda: False)
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"


class TestSecurityHeaders:
    @pytest.mark.parametrize("path", ["/api/v1/health", "/", "/api/v1/nope", "/assets/index-abc123.js"])
    def test_every_response_carries_the_headers(self, client: TestClient, path: str) -> None:
        headers = client.get(path).headers
        assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "no-referrer"
        assert "camera=()" in headers["permissions-policy"]

    def test_csp_forbids_inline_code_and_framing(self) -> None:
        assert "'unsafe-inline'" not in CONTENT_SECURITY_POLICY
        assert "'unsafe-eval'" not in CONTENT_SECURITY_POLICY
        assert "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY

    def test_api_responses_are_never_cached(self, client: TestClient) -> None:
        assert client.get("/api/v1/health").headers["cache-control"] == "no-store"

    def test_hsts_only_in_production(
        self, client: TestClient, db: Database, clock: ManualClock, static_dir: Path
    ) -> None:
        assert "strict-transport-security" not in client.get("/api/v1/health").headers
        with TestClient(make_app(db, clock, static_dir, PROD_ENV), base_url="https://testserver") as prod:
            assert prod.get("/api/v1/health").headers["strict-transport-security"].startswith("max-age=")

    def test_no_server_banner_or_docs(self, client: TestClient) -> None:
        assert (
            client.get("/docs").headers["content-type"].startswith("text/html")
        )  # SPA fallback, not Swagger
        assert "swagger" not in client.get("/docs").text.lower()
        assert client.get("/api/v1/openapi.json").status_code == 200  # development only

    def test_openapi_is_hidden_in_production(
        self, db: Database, clock: ManualClock, static_dir: Path
    ) -> None:
        with TestClient(make_app(db, clock, static_dir, PROD_ENV), base_url="https://testserver") as prod:
            assert prod.get("/api/v1/openapi.json").status_code == 404


class Echo(BaseModel):
    name: str


@pytest.fixture
def probe_client(app: FastAPI) -> Iterator[TestClient]:
    @app.post("/api/v1/_test/echo")
    def echo(body: Echo) -> dict[str, str]:
        return {"name": body.name}

    @app.get("/api/v1/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internals: password=hunter2")

    # Routes added after the catch-all PWA route must be moved in front of it.
    app.router.routes.sort(key=lambda r: getattr(r, "path", "") == "/{path:path}")
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


class TestErrors:
    def test_unknown_api_route_is_json_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        assert response.json() == {"error": {"code": "not_found", "message": "Not found"}}

    def test_wrong_method(self, client: TestClient) -> None:
        response = client.post("/api/v1/health")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"

    def test_validation_error_hides_the_input(self, probe_client: TestClient) -> None:
        response = probe_client.post("/api/v1/_test/echo", json={"name": 123, "password": "hunter2"})
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "invalid_request"
        assert body["error"]["fields"][0]["loc"] == ["body", "name"]
        assert "hunter2" not in response.text
        assert "123" not in response.text

    def test_unexpected_exception_is_a_generic_500_with_headers(
        self, probe_client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        response = probe_client.get("/api/v1/_test/boom")
        assert response.status_code == 500
        assert response.json() == {"error": {"code": "internal_error", "message": "Internal error"}}
        assert "hunter2" not in response.text
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert "unhandled error" in caplog.text

    def test_declared_oversized_body_is_413(self, probe_client: TestClient) -> None:
        big = "x" * (DEFAULT_MAX_BODY_BYTES + 1)
        response = probe_client.post(
            "/api/v1/_test/echo", content=big, headers={"content-type": "application/json"}
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "request_too_large"

    def test_streamed_oversized_body_is_413(self, probe_client: TestClient) -> None:
        def chunks() -> Iterator[bytes]:
            for _ in range(DEFAULT_MAX_BODY_BYTES // 1024 + 2):
                yield b"x" * 1024

        response = probe_client.post(
            "/api/v1/_test/echo", content=chunks(), headers={"content-type": "application/json"}
        )
        assert response.status_code == 413

    def test_small_body_passes(self, probe_client: TestClient) -> None:
        assert probe_client.post("/api/v1/_test/echo", json={"name": "ok"}).json() == {"name": "ok"}


class TestStaticPwa:
    def test_index_at_root(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "<title>TAA</title>" in response.text
        assert response.headers["cache-control"] == "no-cache"

    def test_client_routes_deep_link_to_index(self, client: TestClient) -> None:
        response = client.get("/settings/security")
        assert response.status_code == 200
        assert "<title>TAA</title>" in response.text

    def test_hashed_assets_are_immutable_with_a_js_type(self, client: TestClient) -> None:
        response = client.get("/assets/index-abc123.js")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert response.headers["content-type"].startswith("text/javascript")

    def test_service_worker_and_manifest_revalidate(self, client: TestClient) -> None:
        assert client.get("/sw.js").headers["cache-control"] == "no-cache"
        manifest = client.get("/manifest.webmanifest")
        assert manifest.headers["content-type"].startswith("application/manifest+json")

    def test_missing_asset_is_404_not_index(self, client: TestClient) -> None:
        response = client.get("/assets/missing-123.js")
        assert response.status_code == 404
        assert "<title>" not in response.text

    @pytest.mark.parametrize("path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"])
    def test_no_path_traversal(self, client: TestClient, path: str) -> None:
        assert "outside the static root" not in client.get(path).text

    def test_api_paths_never_fall_back_to_the_shell(self, client: TestClient) -> None:
        response = client.get("/api/v2/anything")
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/json"

    def test_missing_build_is_reported(self, db: Database, clock: ManualClock, tmp_path: Path) -> None:
        settings = WebSettings.model_validate(DEV_ENV)
        from app.web.app import create_app

        app = create_app(settings, db=db, clock=clock, static_dir=tmp_path / "nowhere")
        with TestClient(app, base_url="https://testserver") as test_client:
            response = test_client.get("/")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "pwa_not_built"
