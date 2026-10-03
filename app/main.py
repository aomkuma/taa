"""Engine entry point: ``python -m app.main --mode paper [--fake] [--max-cycles N]``.

``--mode`` must repeat ``TRADING_MODE`` from the environment: the mode is never inferred, and a mismatch
between the command line and the configuration is refused rather than resolved.
"""

from __future__ import annotations

import argparse
import signal
import sys
from types import FrameType

from app.broker.factory import build_read_only
from app.config import load_settings
from app.core.clock import SystemClock
from app.core.errors import TaaError
from app.engine.orchestrator import Engine
from app.logging_config import configure_logging
from app.monitoring.alerts import EventBus, LocalLogSink
from app.storage.database import Database, resolve_db_url, upgrade_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.main", description="TAA engine (PAPER in Milestone 1)"
    )
    parser.add_argument("--mode", required=True, help="must equal TRADING_MODE (paper)")
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
        engine = Engine(settings, build_read_only(settings, fake=args.fake, clock=clock), db, clock, bus=bus)

        def _stop(signum: int, frame: FrameType | None) -> None:
            engine.stop()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
        engine.start()
        engine.run(args.max_cycles)
        return 0
    except TaaError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
