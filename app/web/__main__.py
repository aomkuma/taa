"""Run the web service: ``python -m app.web`` (locally) or as the Railway ``web`` start command.

Migrations are applied first (Railway also runs ``alembic upgrade head`` as its pre-deploy step).
"""

from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

from app.config import load_web_settings
from app.core.errors import TaaError
from app.logging_config import configure_logging
from app.storage.database import resolve_db_url, upgrade_schema
from app.web.app import create_app

log = logging.getLogger(__name__)

# Railway routes public traffic through its edge proxy to the container port.
ALL_INTERFACES = "0.0.0.0"  # noqa: S104  # nosec B104


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.web", description="TAA web service (API + PWA)")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--host", default=None, help="default: 0.0.0.0 in production, else 127.0.0.1")
    parser.add_argument("--port", type=int, default=None, help="default: PORT or 8000")
    parser.add_argument("--no-migrate", action="store_true", help="skip applying migrations at startup")
    args = parser.parse_args(argv)

    try:
        settings = load_web_settings(env_file=args.env_file)
        # Railway collects stdout/stderr; local runs also keep a rotating file in logs/.
        configure_logging("web", settings.LOG_LEVEL, log_dir=None if settings.is_production else "logs")
        if not args.no_migrate:
            upgrade_schema(resolve_db_url(settings.DATABASE_URL))
        app = create_app(settings)
    except TaaError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    host = args.host or (ALL_INTERFACES if settings.is_production else "127.0.0.1")
    log.info("web service starting on %s:%s (%s)", host, args.port or settings.PORT, settings.WEB_ENV)
    uvicorn.run(
        app,
        host=host,
        port=args.port or settings.PORT,
        # Behind Railway's edge proxy the client address comes from X-Forwarded-For;
        # locally only loopback is trusted.
        proxy_headers=True,
        forwarded_allow_ips="*" if settings.is_production else "127.0.0.1",
        server_header=False,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
