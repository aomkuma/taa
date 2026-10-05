"""FastAPI application factory for the cloud web service (PLAN §A14).

The web service is a replica reader and command writer: it never imports broker code (enforced by
tests/unit/test_architecture.py) and holds no MT5 credentials. Middleware order, outermost first:
security headers → internal-error guard → body-size limit → routes, so every response carries the headers.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app import __version__
from app.config import REPO_ROOT, WebSettings
from app.core.clock import Clock, SystemClock
from app.core.errors import ConfigError
from app.security.hmac_auth import Verifier
from app.storage.audit import AuditLog
from app.storage.database import Database, resolve_db_url
from app.sync.command_queue import CommandQueue
from app.sync.ingest import IngestService
from app.sync.nonces import SqlNonceStore
from app.web.auth import AuthKeys, AuthService
from app.web.deps import WEB_AUDIT_CHAIN, EngineLink, WebContext
from app.web.engines import EngineRegistry
from app.web.entitlements import seed_plans
from app.web.errors import InternalErrorMiddleware, install_error_handlers
from app.web.routers import (
    advisory,
    analytics,
    auth,
    backtests,
    billing,
    control,
    data,
    engine,
    engines,
    health,
    ingest,
    learning,
    manual,
    me,
    notifications,
    stream,
)
from app.web.security_headers import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.web.static import mount_pwa

API_PREFIX = "/api/v1"

log = logging.getLogger(__name__)


def static_root(settings: WebSettings) -> Path:
    path = Path(settings.WEB_STATIC_DIR)
    return path if path.is_absolute() else REPO_ROOT / path


def engine_registry(settings: WebSettings, db: Database, clock: Clock, audit: AuditLog) -> EngineRegistry:
    return EngineRegistry(
        db,
        clock,
        audit,
        settings.WEB_SESSION_SECRET.get_secret_value(),
        max_per_user=settings.WEB_MAX_ENGINES_PER_USER,
        multi_engine=settings.MULTI_ENGINE_ENABLED,
    )


def engine_link(settings: WebSettings, db: Database, clock: Clock, audit: AuditLog) -> EngineLink:
    registry = engine_registry(settings, db, clock, audit)
    verifier = Verifier(registry, clock, SqlNonceStore(db))  # nonces shared by every web process
    commands = CommandQueue(db, clock)
    return EngineLink(registry, verifier, IngestService(db, clock, commands, audit=audit), commands)


def check_engine_env(settings: WebSettings, registry: EngineRegistry) -> None:
    """(rev. 4) Engine keys live in the database. Production refuses ``ENGINE_*`` in the web env, so the env
    and the registry can never disagree. Development only warns: the local ``.env`` is shared with the engine,
    which needs those variables."""
    if settings.ENGINE_ID is None and settings.ENGINE_HMAC_SECRET is None:
        return
    imported = settings.ENGINE_ID is not None and registry.get(settings.ENGINE_ID) is not None
    hint = (
        "remove ENGINE_ID / ENGINE_HMAC_SECRET(_PREVIOUS) from the web service"
        if imported
        else "import them once with `python -m app.cli web engine import-env --owner NAME`, then remove them"
    )
    if settings.is_production:
        raise ConfigError(f"engine keys are kept in the database (PLAN §A32): {hint}")
    log.warning("ENGINE_* variables are ignored by the web service (engines are registered in the database)")


def create_app(
    settings: WebSettings,
    *,
    db: Database | None = None,
    clock: Clock | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Build the app. Tests inject *db*, *clock* and *static_dir*; production derives them from *settings*."""
    database = db or Database(resolve_db_url(settings.DATABASE_URL))
    clock = clock or SystemClock()
    audit = AuditLog(database, WEB_AUDIT_CHAIN, clock)
    keys = AuthKeys(settings.WEB_SESSION_SECRET.get_secret_value())
    ctx = WebContext(
        settings=settings,
        db=database,
        clock=clock,
        audit=audit,
        auth=AuthService(database, clock, audit, keys),
        engine=engine_link(settings, database, clock, audit),
    )
    check_engine_env(settings, ctx.engine.registry)
    seed_plans(database, clock.now_utc())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if db is None:  # only dispose what the factory created
            database.dispose()

    app = FastAPI(
        title="TAA",
        version=__version__,
        lifespan=lifespan,
        # Swagger/ReDoc pages load scripts from a CDN, which the CSP forbids; the schema stays available in
        # development for tooling.
        docs_url=None,
        redoc_url=None,
        openapi_url=None if settings.is_production else f"{API_PREFIX}/openapi.json",
    )
    app.state.ctx = ctx
    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(ingest.router)
    api.include_router(engine.router)
    api.include_router(data.router)
    api.include_router(manual.router)
    api.include_router(analytics.router)
    api.include_router(learning.router)
    api.include_router(stream.router)
    api.include_router(control.router)
    api.include_router(engines.router)
    api.include_router(notifications.router)
    api.include_router(backtests.router)
    api.include_router(advisory.router)
    api.include_router(me.router)
    api.include_router(billing.router)
    app.include_router(api)
    mount_pwa(app, static_dir or static_root(settings))

    app.add_middleware(
        BodySizeLimitMiddleware, path_limits={ingest.INGEST_PATH: ingest.INGEST_MAX_BODY_BYTES}
    )
    app.add_middleware(InternalErrorMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, production=settings.is_production)
    app.add_middleware(StaticGZipMiddleware)
    return app


class StaticGZipMiddleware:
    """Gzip for the PWA's static files only (TAA-914: the app shell was sent uncompressed, ~800 KB).

    ``/api/`` is left alone: its responses carry session data and once-shown secrets, and compressing secrets
    next to request-controlled text leaks them through the response length (BREACH); the live stream must not
    be buffered either."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=1024)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not str(scope.get("path", "")).startswith("/api/"):
            await self.gzip(scope, receive, send)
        else:
            await self.app(scope, receive, send)
