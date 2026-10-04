"""Run the cloud worker (TAA-808): ``python -m app.worker`` locally, or the Railway ``worker`` start command.

``python -m app.worker check`` exits 0 when a worker beat within the last minute, else 1 (for scripts and the
operator). The worker does not migrate the database by default: the web service and Railway's pre-deploy step
do, and two processes migrating at once could collide. ``--migrate`` applies migrations first (local use).
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
from typing import Any

from app.config import load_worker_settings
from app.core.clock import SystemClock
from app.core.errors import TaaError
from app.logging_config import configure_logging
from app.storage.database import Database, resolve_db_url, upgrade_schema
from app.web.entitlements import seed_plans
from app.worker.backtests import BacktestService
from app.worker.backtests import handlers as backtest_handlers
from app.worker.jobs import JobQueue
from app.worker.push import PushDispatcher, WebPushSender
from app.worker.push import handlers as push_handlers
from app.worker.service import Handler, Worker, default_tasks, default_worker_id, worker_health

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker", description="TAA cloud worker")
    parser.add_argument("command", nargs="?", choices=("run", "check"), default="run")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--migrate", action="store_true", help="apply migrations before starting")
    args = parser.parse_args(argv)

    try:
        settings = load_worker_settings(env_file=args.env_file)
        configure_logging("worker", settings.LOG_LEVEL, log_dir=None if settings.is_production else "logs")
        url = resolve_db_url(settings.DATABASE_URL)
        if args.migrate:
            upgrade_schema(url)
        db = Database(url)
    except TaaError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    clock = SystemClock()
    if args.command == "check":
        health = worker_health(db, clock)
        print(json.dumps(health, indent=2))  # noqa: T201 - a command-line report
        db.dispose()
        return 0 if health["status"] == "ok" else 1

    seed_plans(db, clock.now_utc())
    stop = threading.Event()

    def request_stop(signum: int, _frame: Any) -> None:
        log.info("signal %s: stopping after the current pass", signum)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)
    handlers: dict[str, Handler] = dict(backtest_handlers(BacktestService(db, clock, JobQueue(db, clock))))
    push = None
    if settings.VAPID_PRIVATE_KEY is not None and settings.VAPID_SUBJECT is not None:
        sender = WebPushSender(settings.VAPID_PRIVATE_KEY.get_secret_value(), settings.VAPID_SUBJECT)
        push = PushDispatcher(db, clock, JobQueue(db, clock), sender)
        handlers |= push_handlers(push)
    else:
        log.warning("Web Push is off: VAPID_PRIVATE_KEY and VAPID_SUBJECT are not set")
    worker = Worker(
        db,
        clock,
        handlers=handlers,
        tasks=default_tasks(db, clock, push=push),
        worker_id=settings.WORKER_ID or default_worker_id(),
        poll_seconds=settings.WORKER_POLL_SECONDS,
    )
    try:
        worker.run(stop)
    finally:
        db.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
