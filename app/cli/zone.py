"""``python -m app.cli zone``: the run-zone runner on the broker account (eye/ZONE_LIVE.md L10).

* ``zone run --market XAUUSD --set default``: the mode from ``.env``; runs until stopped (Ctrl+C = a stop).
* ``zone status``: the pinned account, the hour's candidates, the setup, its orders and positions, the last
  requests, hands-off, any order or position of the magic that is not ours (read from the runner's status
  snapshot and the zone tables).
* ``zone stop [--now]``: writes a stop request and waits for the runner's acknowledgement.

LIVE is the owner's to turn on: ``ENABLE_LIVE_TRADING`` and ``LIVE_TRADING_CONFIRMATION`` in ``.env``
(CLAUDE.md).
"""

from __future__ import annotations

import argparse
import getpass
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings, load_settings
from app.core.clock import SystemClock
from app.core.errors import ConfigError, SafetyViolation
from app.zone.params import DEFAULT_DB, load_params
from app.zone.params import ConfigError as ZoneConfigError


def _settings(args: argparse.Namespace) -> Settings:
    return load_settings(env_file=args.env_file, config_file=args.config)


def _database(settings: Settings, *, migrate: bool = True) -> Any:
    from app.storage.database import Database, resolve_db_url, upgrade_schema

    url = resolve_db_url(settings.env.ENGINE_DB_URL)
    if migrate:
        upgrade_schema(url)
    return Database(url)


def build_runner(settings: Settings, args: argparse.Namespace) -> Any:
    """Everything the runner is given, from the settings; the real terminal unless ``--fake``."""
    from app.broker.execution import ExecutionGateway
    from app.broker.factory import build_trading
    from app.engine.magic_registry import MagicRegistry
    from app.risk.kill_switch import KillSwitch
    from app.zone.core import MARKET_DIRS, Bars, ZoneError, load_bars
    from app.zone.history_check import check_stored_history, required_frames
    from app.zone.trader import GatewayBarSource, ProcessLock, RunnerConfig, ZoneRunner

    clock = SystemClock()
    try:
        params, version = load_params(Path(args.db), args.market, args.set)
    except ZoneConfigError as exc:
        raise ConfigError(str(exc)) from exc
    if args.market not in MARKET_DIRS:
        raise ConfigError(f"no bars for {args.market}")
    zl = settings.config.zone_live
    cfg = RunnerConfig(
        lot=zl.lot,
        cycle_seconds=zl.cycle_seconds,
        stale_quote_seconds=zl.stale_quote_seconds,
        preclose_seconds=zl.preclose_seconds,
        epoch=pd.Timestamp(zl.epoch, tz="UTC"),
        symbol=zl.symbol,
        market=args.market,
        set_name=args.set,
        set_version=version,
        mode=settings.mode,
        env=settings.env,
    )
    bundle = build_trading(
        settings, fake=args.fake, clock=clock
    )  # refuses unless the gate's .env values are set
    bundle.client.connect()
    # L2: the stored bars of the pinned server (data/history/<server>/<market>), each frame cut to the
    # simulation's first bar of that frame; a missing or late series refuses the start
    server = bundle.gateway.account().server
    history_root = MARKET_DIRS[args.market].parent.parent
    try:
        # only the frames the exec frame needs (M5 is not read when it is M15): a store without M5 is valid
        need = required_frames(params.exec_tf)
        stored: Bars | None = load_bars(args.market, history_root / server / args.market, frames=need)
    except ZoneError:
        stored = None
    except OSError as exc:  # a required frame's file is missing or unreadable
        raise ConfigError(f"the stored history refuses the start: {exc}") from exc
    frames = None if stored is None else {tf: stored.frame(tf) for tf in need}
    check = check_stored_history(server, frames, params.exec_tf)
    if not check.ok or stored is None:
        raise ConfigError("the stored history refuses the start: " + "; ".join(check.reasons))
    f = check.frames
    bars = Bars(f["D1"], f["H4"], f["H1"], f["M15"], f.get("M5", stored.m5), stored.point)
    db = _database(settings)
    magic = MagicRegistry(db, settings.env.MAGIC_NUMBER_BASE, clock).zone_magic()
    kill = KillSwitch(settings.path(settings.env.KILL_SWITCH_FILE), db, None, clock)

    return ZoneRunner(
        cfg=cfg,
        params=params,
        clock=clock,
        gateway=bundle.gateway,
        execution=ExecutionGateway(bundle.client),
        bar_source=GatewayBarSource(bundle.gateway, zl.symbol, clock),
        db=db,
        bars=bars,
        kill_switch=kill,
        magic=magic,
        # L2: the live bars are kept in memory only - the runner never writes the stored history
        lock=ProcessLock(settings.path("data/zone_runner.lock")),
    )


def cmd_zone_run(args: argparse.Namespace) -> int:
    from app.logging_config import configure_logging
    from app.zone.trader import ZoneStartError

    settings = _settings(args)
    configure_logging("zone", settings.env.LOG_LEVEL, settings.path(settings.env.LOG_DIR))
    try:
        runner = build_runner(settings, args)
        runner.start()
    except (SafetyViolation, ZoneStartError, ConfigError) as exc:
        print(f"error: {exc}")
        return 1
    print(f"zone runner running ({settings.mode.value}); Ctrl+C or `zone stop` to stop")
    runner.run()
    return 0


def cmd_zone_status(args: argparse.Namespace) -> int:
    from app.zone.store import ZoneStore

    settings = _settings(args)
    db = _database(settings)
    probe = ZoneStore(db, 0, "")
    state = probe.all_state()
    if "status" not in state:
        print("no runner has written a status yet")
        return 0
    text, at = state["status"]
    status = json.loads(text)
    print(f"status of {at.isoformat()} (the runner's last write)")
    print(json.dumps(status, indent=2, default=str))
    store = ZoneStore(db, int(status.get("login", 0)), str(status.get("server", "")))
    print("\nlast requests:")
    for r in store.requests(limit=10, newest_first=True):
        print(
            f"  #{r.id} setup {r.setup_id} {r.kind} {r.name} {r.comment or ''} {r.state} {r.order_state}"
            f" {r.detail}"
        )
    print("\nlive setups:")
    for s in store.setups(states=("live",)):
        print(
            f"  #{s.id} {s.hour_open.isoformat()} {s.side} line {s.line} chosen={s.chosen}"
            f" outcome={s.outcome}"
        )
    if status.get("hands_off"):
        print(f"\nHANDS-OFF since {status.get('hands_off_since')}: {status['hands_off']}")
    if status.get("not_ours_orders") or status.get("not_ours_positions"):
        print(
            "\nNOT OURS (the owner's to close):",
            status.get("not_ours_orders"),
            status.get("not_ours_positions"),
        )
    return 0


def cmd_zone_stop(args: argparse.Namespace) -> int:
    from app.zone.store import ZoneStore

    settings = _settings(args)
    db = _database(settings)
    store = ZoneStore(db, 0, "")
    clock = SystemClock()
    sid = store.request_stop(clock.now_utc(), getpass.getuser(), now_flag=args.now)
    print(f"stop request {sid} written{' (now)' if args.now else ''}; waiting for the runner")
    deadline = time.monotonic() + args.wait
    while time.monotonic() < deadline:
        row = store.stop(sid)
        if row is not None and row.acknowledged_at is not None:
            print(f"acknowledged at {row.acknowledged_at.isoformat()}: {row.note}")
            return 0
        time.sleep(1.0)
    print("not acknowledged: no runner is reading the table (or it is busy); the request stays")
    return 2


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    zone = sub.add_parser("zone", help="the run-zone runner on the broker account (eye/ZONE_LIVE.md)")
    zsub = zone.add_subparsers(dest="zone_command", required=True)
    run = zsub.add_parser("run", help="run the zone runner until stopped (mode from .env)")
    run.add_argument("--market", default="XAUUSD")
    run.add_argument("--set", default="default")
    run.add_argument("--db", default=str(DEFAULT_DB), help="the zone parameter database")
    run.add_argument(
        "--fake", action="store_true", help="the in-memory FakeMT5 instead of a terminal (drills)"
    )
    run.set_defaults(func=cmd_zone_run)
    zsub.add_parser(
        "status", help="the runner's state, candidates, orders, positions, requests, hands-off"
    ).set_defaults(func=cmd_zone_status)
    stop = zsub.add_parser("stop", help="remove every unfilled order, place nothing new, exit when flat")
    stop.add_argument("--now", action="store_true", help="exit at once; open positions keep their SL / TP")
    stop.add_argument("--wait", type=float, default=60.0, help="seconds to wait for the acknowledgement")
    stop.set_defaults(func=cmd_zone_stop)
    return zone
