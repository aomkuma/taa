"""Engine entry point: ``python -m app.main --mode paper [--fake] [--max-cycles N]``.

``--mode`` must repeat ``TRADING_MODE`` from the environment: the mode is never inferred, and a mismatch
between the command line and the configuration is refused rather than resolved.
"""

from __future__ import annotations

import argparse
import signal
import sys
from types import FrameType

from app.broker.factory import build_read_only, build_trading
from app.config import load_settings
from app.core.clock import SystemClock
from app.core.enums import TradingMode
from app.core.errors import TaaError
from app.engine.orchestrator import Engine
from app.logging_config import configure_logging
from app.monitoring.alerts import EventBus, LocalLogSink
from app.monitoring.health_check import HealthServer
from app.storage.database import Database, resolve_db_url, upgrade_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.main", description="TAA engine (PAPER, or DEMO broker orders)"
    )
    parser.add_argument("--mode", required=True, help="must equal TRADING_MODE (paper | demo)")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--config", default=None)
    parser.add_argument("--fake", action="store_true", help="use the in-memory FakeMT5 (development)")
    parser.add_argument("--max-cycles", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(env_file=args.env_file, config_file=args.config)
        if args.mode.strip().upper() != settings.mode.value:
            mode = settings.mode.value
            sys.stderr.write(f"error: --mode {args.mode} does not match TRADING_MODE={mode}\n")
            return 2
        env = settings.env
        configure_logging("engine", env.LOG_LEVEL, settings.path(env.LOG_DIR))
        url = resolve_db_url(env.ENGINE_DB_URL)
        upgrade_schema(url)
        db = Database(url)
        clock = SystemClock()
        bus = EventBus(clock, [LocalLogSink(settings.path(env.LOG_DIR) / "events.jsonl")])
        # DEMO gets a trading client (refused unless ENABLE_DEMO_TRADING); PAPER stays read-only
        build = build_trading if settings.mode is TradingMode.DEMO else build_read_only
        engine = Engine(settings, build(settings, fake=args.fake, clock=clock), db, clock, bus=bus)

        def _stop(signum: int, frame: FrameType | None) -> None:
            engine.stop()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
        loop = settings.config.engine
        health = HealthServer(engine.status, loop.health_host, loop.health_port)
        health.start()
        try:
            engine.start()
            engine.run(args.max_cycles)
        finally:
            health.stop()
        return 0
    except TaaError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
