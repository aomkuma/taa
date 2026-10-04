"""FastAPI application factory for the cloud web service (PLAN §A14).

The web service is a replica reader and command writer: it never imports broker code (enforced by
tests/unit/test_architecture.py) and holds no MT5 credentials. Middleware order, outermost first:
security headers → internal-error guard → body-size limit → routes, so every response carries the headers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI

from app import __version__
from app.config import REPO_ROOT, WebSettings
from app.core.clock import Clock, SystemClock
from app.security.hmac_auth import Verifier
from app.storage.audit import AuditLog
from app.storage.database import Database, resolve_db_url
from app.sync.command_queue import CommandQueue
from app.sync.ingest import IngestService
from app.sync.nonces import SqlNonceStore
from app.web.auth import AuthKeys, AuthService
from app.web.deps import WEB_AUDIT_CHAIN, EngineLink, WebContext
from app.web.errors import InternalErrorMiddleware, install_error_handlers
from app.web.routers import auth, engine, health, ingest
from app.web.security_headers import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.web.static import mount_pwa

API_PREFIX = "/api/v1"


def static_root(settings: WebSettings) -> Path:
    path = Path(settings.WEB_STATIC_DIR)
    return path if path.is_absolute() else REPO_ROOT / path


def engine_link(settings: WebSettings, db: Database, clock: Clock, audit: AuditLog) -> EngineLink | None:
    if settings.ENGINE_ID is None or settings.ENGINE_HMAC_SECRET is None:
        return None
    previous = settings.ENGINE_HMAC_SECRET_PREVIOUS
    verifier = Verifier.single(
        settings.ENGINE_ID,
        settings.ENGINE_HMAC_SECRET.get_secret_value(),
        clock,
        previous=previous.get_secret_value() if previous else None,
        nonces=SqlNonceStore(db),  # shared by every web process
    )
    commands = CommandQueue(db, clock)
    return EngineLink(settings.ENGINE_ID, verifier, IngestService(db, clock, commands, audit=audit), commands)


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
    app.include_router(api)
    mount_pwa(app, static_dir or static_root(settings))

    app.add_middleware(
        BodySizeLimitMiddleware, path_limits={ingest.INGEST_PATH: ingest.INGEST_MAX_BODY_BYTES}
    )
    app.add_middleware(InternalErrorMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, production=settings.is_production)
    return app
