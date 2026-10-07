"""Operator command line: ``python -m app.cli <command>``."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from app.cli.research import add_parser as add_research
from app.config import REPO_ROOT, Settings, load_settings
from app.core.errors import ConfigError, TaaError

if TYPE_CHECKING:
    from app.risk.circuit_breaker import BreakerBoard


def _settings(args: argparse.Namespace) -> Settings:
    return load_settings(env_file=args.env_file, config_file=args.config)


def _engine_chain(settings: Settings) -> str:
    return f"engine:{settings.env.ENGINE_ID or 'local'}"


def _db_and_audit(settings: Settings):
    from app.storage.audit import AuditLog
    from app.storage.database import Database, resolve_db_url, upgrade_schema

    upgrade_schema(resolve_db_url(settings.env.ENGINE_DB_URL))
    db = Database(resolve_db_url(settings.env.ENGINE_DB_URL))
    if settings.config.sync.enabled:  # CLI changes (kill switch, breaker resets) reach the cloud as well
        from app.core.clock import SystemClock
        from app.sync.replication import install_replication

        install_replication(db, SystemClock(), _engine_chain(settings))
    return db, AuditLog(db, _engine_chain(settings))


def cmd_config_show(args: argparse.Namespace) -> int:
    settings = _settings(args)
    print(json.dumps(settings.summary(), indent=2))
    return 0


def cmd_db_upgrade(args: argparse.Namespace) -> int:
    from app.storage.database import upgrade_schema

    url = args.url or _settings(args).env.ENGINE_DB_URL
    upgrade_schema(url)
    print("schema is up to date")
    return 0


def _engine_running(settings: Settings) -> bool:
    """Whether the engine answers on its health port (a restore needs it stopped)."""
    import socket

    engine = settings.config.engine
    try:
        with socket.create_connection((engine.health_host, engine.health_port), timeout=1.0):
            return True
    except OSError:
        return False


def cmd_db_backup(args: argparse.Namespace) -> int:
    from app.core.clock import SystemClock
    from app.storage.backup import BackupError, backup
    from app.storage.database import resolve_db_url

    settings = _settings(args)
    url = resolve_db_url(settings.env.ENGINE_DB_URL)
    stamp = SystemClock().now_utc().strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else settings.path(f"data/backups/engine-{stamp}.db")
    try:
        report = backup(url, out)
    except BackupError as exc:
        print(f"backup failed: {exc}")
        return 1
    print(f"backup written: {report.path} ({report.size} bytes, sha256 {report.sha256})")
    for chain, n in report.chains.items():
        print(f"  audit chain {chain}: {n} events verified")
    return 0


def cmd_db_restore(args: argparse.Namespace) -> int:
    from app.core.clock import SystemClock
    from app.storage.backup import BackupError, check, restore
    from app.storage.database import resolve_db_url

    settings = _settings(args)
    source = Path(args.source)
    if args.confirm != source.name:
        print(f"refused: repeat the backup's file name with --confirm {source.name}")
        return 2
    if _engine_running(settings):
        print("refused: the engine is running (its health port answers); stop it first")
        return 2
    try:
        report = check(source)
        aside = restore(resolve_db_url(settings.env.ENGINE_DB_URL), source, now=SystemClock().now_utc())
    except BackupError as exc:
        print(f"restore refused: {exc}")
        return 1
    print(f"restored {source} (sha256 {report.sha256}); the previous database is kept as {aside}")
    print("next: python -m app.cli audit verify, then start the engine (it reconciles with the broker first)")
    return 0


def cmd_audit_verify(args: argparse.Namespace) -> int:
    from app.storage.audit import verify_chain

    settings = _settings(args)
    db, _ = _db_and_audit(settings)
    report = verify_chain(db, args.chain or _engine_chain(settings))
    print(f"chain={report.chain} ok={report.ok} checked={report.events_checked} {report.detail}")
    return 0 if report.ok else 2


def cmd_kill(args: argparse.Namespace) -> int:
    from app.risk.kill_switch import KillMode, KillSwitch

    actor = args.actor or getpass.getuser()
    try:
        settings = _settings(args)
    except ConfigError as exc:
        # Fail-safe: activation must work even with broken configuration.
        if args.release or args.status:
            raise
        path = REPO_ROOT / "data" / "KILL_SWITCH"
        print(f"WARNING: configuration invalid ({exc}); writing default kill switch file {path}")
        KillSwitch(path).activate(args.reason or "manual (config invalid)", actor, "cli")
        return 0
    db, audit = _db_and_audit(settings)
    ks = KillSwitch(
        settings.path(settings.env.KILL_SWITCH_FILE),
        db,
        audit,
        flatten_allowed=settings.env.KILL_SWITCH_FLATTEN_ALLOWED,
    )
    if args.status:
        print(json.dumps(ks.state().__dict__, indent=2, default=str))
        return 0
    if not args.reason:
        print("--reason is required", file=sys.stderr)
        return 1
    if args.release:
        ks.release(args.reason, actor, "cli")
        print("kill switch released")
    else:
        state = ks.activate(args.reason, actor, "cli", KillMode(args.mode))
        print(f"kill switch ACTIVE ({state.mode}) at {ks.path}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from app.cli.doctor import run_doctor

    report = run_doctor(_settings(args), fake=args.fake, wait_seconds=args.wait)
    print("TAA doctor" + (" (FAKE broker)" if args.fake else ""))
    print("\n".join(report.lines))
    print(f"\n{report.failures} failure(s), {report.warnings} warning(s)")
    return 0 if report.failures == 0 else 2


def _date(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def cmd_ticks_probe(args: argparse.Namespace) -> int:
    """Read-only probe of the broker feed: depth of market, tick history depth, tick character (TAA-L001)."""
    import time

    from app.broker.factory import build_read_only
    from app.core.clock import SystemClock
    from app.market_data.feed_probe import format_report, probe

    settings = _settings(args)
    if not args.fake:  # the terminal caches every month the depth search touches (~40-60 MB per symbol)
        import shutil

        terminal = Path(settings.env.MT5_TERMINAL_PATH or ".").resolve()
        free_gb = shutil.disk_usage(terminal.anchor or ".").free / 1e9
        need_gb = 0.1 * len(args.symbols) * max(1, args.max_weeks // 4 + 1)
        if free_gb < 2 + need_gb:
            print(
                f"refused: {free_gb:.1f} GB free on {terminal.anchor}; the probe may need ~{need_gb:.1f} GB"
            )
            return 2
    clock = SystemClock()
    bundle = build_read_only(settings, fake=args.fake, clock=clock)
    bundle.client.connect()
    try:
        reports = probe(
            bundle.gateway,
            args.symbols,
            clock.now_utc(),
            book_samples=args.book_samples,
            book_interval=args.book_interval,
            max_weeks=args.max_weeks,
            sleep=time.sleep,
        )
    finally:
        bundle.client.shutdown()
    print("TAA feed probe" + (" (FAKE broker)" if args.fake else "") + " - read-only")
    for line in format_report(reports):
        print(line)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    from pathlib import Path

    from app.backtest.engine import Progress
    from app.backtest.metrics import compute_metrics
    from app.backtest.runner import load_history, run_and_write
    from app.market_data.history_store import ParquetHistoryStore

    settings = _settings(args)
    config = settings.config
    if args.seed is not None:
        config = config.model_copy(
            update={"backtest": config.backtest.model_copy(update={"seed": args.seed})}
        )
    server = args.server or settings.env.MT5_SERVER
    if not server:
        print("error: pass --server (the history store is organized by trade server)", file=sys.stderr)
        return 1
    symbols = args.symbols.split(",") if args.symbols else config.symbols.allowed
    start, end = _date(args.start), _date(args.end)
    store = ParquetHistoryStore(settings.path(args.data))
    loaded = load_history(
        store,
        server,
        symbols,
        config.timeframes.enabled,
        account_currency=config.backtest.account_currency,
        start=None,  # warm-up needs the bars before --start; the engine trades only inside the period
        end=end,
    )
    names = args.strategies.split(",") if args.strategies else None
    detectors: list[str] | Literal["all"] | None = None
    if args.detectors in ("all", "none"):
        detectors = "all" if args.detectors == "all" else []
    elif args.detectors is not None:
        detectors = args.detectors.split(",")
    out = (
        settings.path(args.out)
        if args.out
        else settings.path(
            f"data/backtests/{loaded.digest[:8]}-{settings.config_hash[:8]}-seed{config.backtest.seed}"
        )
    )

    def progress(p: Progress) -> None:
        print(f"  {p.fraction:6.1%}  {p.at:%Y-%m-%d %H:%M}  equity {p.equity:,.2f}", flush=True)

    result, paths = run_and_write(
        config,
        loaded,
        Path(out),
        config_hash=settings.config_hash,
        strategy_names=names,
        start=start,
        end=end,
        on_progress=progress if args.progress else None,
        detectors=detectors,
    )
    m = compute_metrics(result.trades, result.equity_curve, result.initial_balance)
    print(f"backtest {', '.join(symbols)}  {result.start} -> {result.end}")
    print(f"  data hash {loaded.digest}  config hash {settings.config_hash}  seed {config.backtest.seed}")
    print(f"  trades {m.trades}  win rate {m.win_rate}  profit factor {m.profit_factor}")
    print(f"  net {m.net_profit:,.2f}")
    print(f"  max drawdown {m.max_drawdown_percent:.2f}%  expectancy {m.expectancy_r} R")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    print("  (a bar-based simulation; past results do not predict future results)")
    return 0


def _board(settings: Settings) -> BreakerBoard:
    from app.core.clock import SystemClock
    from app.risk.circuit_breaker import default_specs

    db, audit = _db_and_audit(settings)
    cfg = settings.config
    specs = default_specs(
        cfg.breakers,
        consecutive_pause_hours=cfg.risk.consecutive_loss_pause_hours,
        symbol_pause_minutes=cfg.execution.symbol_pause_minutes,
    )
    from app.risk.circuit_breaker import BreakerBoard

    return BreakerBoard(
        db, specs, SystemClock(), mode=settings.mode, tz_name=settings.env.BROKER_TIMEZONE, audit=audit
    )


def cmd_breaker(args: argparse.Namespace) -> int:
    from app.risk.circuit_breaker import BreakerName

    board = _board(_settings(args))
    if args.action == "list":
        for s in board.statuses():
            latched = " (latched)" if s.latched else ""
            print(f"{s.name.value:22} {s.scope_key or '-':10} {s.state.value}{latched}  {s.reason}")
        return 0
    if not args.reason:
        print("--reason is required", file=sys.stderr)
        return 1
    actor = args.actor or getpass.getuser()
    board.reset(
        BreakerName(args.name.upper()),
        actor=f"cli:{actor}",
        reason=args.reason,
        scope_key=args.symbol or "",
        acknowledge=args.ack,
    )
    print(f"breaker {args.name.upper()} reset by {actor}")
    return 0


def cmd_demo_report(args: argparse.Namespace) -> int:
    from app.core.clock import SystemClock
    from app.engine.demo_report import build_report
    from app.storage.database import Database, resolve_db_url

    settings = _settings(args)
    db = Database(resolve_db_url(settings.env.ENGINE_DB_URL))
    report = build_report(db, SystemClock().now_utc(), args.days)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if all(report.checks.values()) else 3


def cmd_advisory_rank(args: argparse.Namespace) -> int:
    import tempfile
    from pathlib import Path

    from app.advisory.ranking_report import format_ranking
    from app.advisory.ranking_service import RankingService
    from app.advisory.universe import SymbolCatalog
    from app.broker.factory import build_read_only
    from app.core.clock import SystemClock
    from app.storage.database import Database, upgrade_schema

    if hasattr(sys.stdout, "reconfigure"):  # Thai text and symbols on a legacy Windows console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    settings = _settings(args)
    clock = SystemClock()
    bundle = build_read_only(settings, fake=args.fake, clock=clock)
    account = bundle.client.connect().account
    with tempfile.TemporaryDirectory() as tmp:
        if args.fake:  # never mix fake snapshots into the engine database
            url = f"sqlite:///{(Path(tmp) / 'advisory-fake.db').as_posix()}"
            upgrade_schema(url)
            db = Database(url)
        else:
            db, _ = _db_and_audit(settings)
        try:
            cfg = settings.config
            catalog = SymbolCatalog(db, bundle.gateway, cfg.advisory.universe, clock, server=account.server)
            service = RankingService(db, bundle.gateway, catalog, cfg, clock, server=account.server)
            run = service.rescan()
            print(format_ranking(run, top=args.top, language=args.lang))
        finally:
            db.engine.dispose()
            bundle.client.shutdown()
    return 0


def cmd_advisory_replay(args: argparse.Namespace) -> int:
    from datetime import timedelta

    import pandas as pd

    from app.advisory.replay import HistoricalReplay, load_resolution
    from app.advisory.requirements import local_requirements
    from app.advisory.scanner import strategy_set
    from app.backtest.runner import load_history
    from app.evidence.catalog import default_registry as evidence_registry
    from app.evidence.registry import EvidenceEngine
    from app.market_data.history_store import ParquetHistoryStore
    from app.strategy.catalog import default_registry as strategy_registry

    settings = _settings(args)
    config = settings.config
    server = args.server or settings.env.MT5_SERVER
    if not server:
        print("error: pass --server (the history store is organized by trade server)", file=sys.stderr)
        return 1
    symbols = args.symbols.split(",") if args.symbols else config.symbols.allowed
    start, end = _date(args.start), _date(args.end)
    store = ParquetHistoryStore(settings.path(args.data))
    loaded = load_history(
        store,
        server,
        symbols,
        config.timeframes.enabled,
        account_currency=config.backtest.account_currency,
        end=end,
    )
    if start is None:  # the last N months of the stored entry-timeframe history
        last = max(
            pd.Timestamp(d.frames[config.timeframes.entry]["close_time"].max()) for d in loaded.data.values()
        )
        start = last.to_pydatetime() - timedelta(days=round(30.44 * args.months))
    resolution = {s: load_resolution(store, server, s, start=start, end=end) for s in symbols}
    evidence, strategies = evidence_registry(), strategy_registry()
    req = local_requirements(config, ranked=[], evidence=evidence, strategies=strategies)
    names = args.strategies.split(",") if args.strategies else sorted(req.strategies)
    detectors = set(req.detectors)
    if args.detectors is not None:  # evidence costs ~1 s per bar with every detector: narrow it for long runs
        detectors = set() if args.detectors == "none" else set(args.detectors.split(","))
    plan = evidence.plan_from_config(config.evidence, only=detectors)
    replay = HistoricalReplay(
        config,
        loaded.data,
        resolution,
        loaded.rates,
        strategy_set(config, names, strategies),
        server=server,
        evidence=EvidenceEngine(evidence, plan) if plan.order else None,
        equity=args.equity,
        start=start,
        end=end,
        broker_tz=settings.env.BROKER_TIMEZONE,
        config_hash=settings.config_hash,
        on_symbol=(lambda s, n, total: print(f"  {s} {n}/{total}", flush=True)) if args.progress else None,
    )
    db, _ = _db_and_audit(settings)
    try:
        report = replay.run(db)
    finally:
        db.engine.dispose()
    print(f"replay {', '.join(report.symbols)}  {report.start} -> {report.end}  (source=REPLAY)")
    print(f"  resolution {report.resolution}  data hash {loaded.digest}  config hash {settings.config_hash}")
    print(
        f"  bars {report.bars}  signals {report.signals}  accepted {report.accepted}  hidden {report.hidden}"
    )
    print(
        f"  shadow rows stored {report.stored}  signals already stored {report.existing}"
        f"  unresolved {report.unresolved}"
    )
    print("  (hypothetical bar-based results; past results do not predict future results)")
    return 0


def cmd_advisory_calibrate(args: argparse.Namespace) -> int:
    from app.advisory.calibration import CalibrationService
    from app.core.clock import SystemClock

    settings = _settings(args)
    server = args.server or settings.env.MT5_SERVER
    if not server:
        print("error: pass --server (calibration is per trade server)", file=sys.stderr)
        return 1
    db, _ = _db_and_audit(settings)
    try:
        service = CalibrationService(
            db,
            settings.config.advisory.calibration,
            SystemClock(),
            server=server,
            executor=CalibrationService.inline(),
        )
        loaded = service.rebuild()
    finally:
        db.engine.dispose()
    report = loaded.model.report
    print(f"calibration {loaded.version}  server {server}")
    print(f"  outcomes: {loaded.n_live} live + {loaded.n_replay} replay (PLAN variant, CLOSED)")
    print(f"  evidence model: {'used' if loaded.model.uses_evidence else 'not used (bucket model only)'}")
    if report is not None and report.n_test:
        print(f"  walk-forward Brier: bucket {report.brier_bucket:.4f}  evidence {report.brier_evidence:.4f}")
    print("  (calibrated on hypothetical shadow results; not a prediction of future results)")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from app.cli.web import run

    return run(args, out=sys.stdout)


def cmd_sync_upload_history(args: argparse.Namespace) -> int:
    """Queue stored closed candles as ``candles`` events (TAA-706); ``--send`` delivers them right away."""
    from datetime import timedelta

    from app.core.clock import SystemClock
    from app.core.enums import Timeframe
    from app.market_data.history_store import ParquetHistoryStore
    from app.sync.candles import queue_history
    from app.sync.outbox import Outbox

    settings = _settings(args)
    server = args.server or settings.env.MT5_SERVER
    if not server:
        raise TaaError("--server is required when MT5_SERVER is not set")
    clock = SystemClock()
    db, _ = _db_and_audit(settings)
    start = None if args.days is None else clock.now_utc() - timedelta(days=args.days)
    events, bars = queue_history(
        Outbox(db, clock, settings.config.sync),
        ParquetHistoryStore(settings.path(args.history_dir)),
        server,
        symbols=[s.strip() for s in args.symbols.split(",")] if args.symbols else None,
        timeframes=[Timeframe(t.strip()) for t in args.timeframes.split(",")] if args.timeframes else None,
        start=start,
    )
    print(f"queued {bars} bars in {events} events for {server}")
    if not args.send:
        print("the engine sends them with its outbox (or run again with --send)")
        return 0
    from app.sync.runtime import SyncRuntime

    runtime = SyncRuntime.from_settings(settings, db, clock)
    sent = runtime.sender.drain()
    runtime.client.close()
    failed = runtime.sender.consecutive_failures > 0
    print(f"sent {sent} events" + (f"; stopped: {runtime.sender.last_error}" if failed else ""))
    return 1 if failed else 0


def cmd_web_engine(args: argparse.Namespace) -> int:
    from app.cli.web import run_engine

    return run_engine(args, out=sys.stdout)


def cmd_engine_new_totp(args: argparse.Namespace) -> int:
    from app.cli.web import new_control_totp

    new_control_totp(read_line=input, out=sys.stdout)
    return 0


def cmd_strategy(args: argparse.Namespace) -> int:
    """Strategies disabled by remote commands: list them, or re-enable one (local only, audited)."""
    from app.core.clock import SystemClock
    from app.engine.orchestrator import DISABLED_KEY
    from app.storage.repositories import EngineStateRepository

    settings = _settings(args)
    db, audit = _db_and_audit(settings)
    repo = EngineStateRepository(db, SystemClock())
    names = {str(n) for n in (repo.load(DISABLED_KEY) or {}).get("names", [])}
    if args.action == "list":
        print("disabled strategies: " + (", ".join(sorted(names)) or "(none)"))
        return 0
    if not args.reason:
        print("--reason is required", file=sys.stderr)
        return 1
    if args.name not in names:
        print(f"{args.name} is not disabled")
        return 0
    repo.save(DISABLED_KEY, {"names": sorted(names - {args.name})})
    actor = args.actor or getpass.getuser()
    audit.append("STRATEGY_ENABLE", actor, {"strategy": args.name, "reason": args.reason, "source": "cli"})
    print(f"{args.name} re-enabled (takes effect on the next bar)")
    return 0


def cmd_research_hypotheses(args: argparse.Namespace) -> int:
    from app.cli.research import cmd_research_hypotheses as run
    from app.storage.database import resolve_db_url

    data = Path(args.data)
    return run(
        args,
        lambda: resolve_db_url(_settings(args).env.ENGINE_DB_URL),
        data if data.is_absolute() else REPO_ROOT / data,
    )


def cmd_research_replay_family(args: argparse.Namespace) -> int:
    from app.cli.research import cmd_research_replay_family as run

    return run(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="TAA operator commands")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    cfg = sub.add_parser("config", help="configuration tools")
    cfg_sub = cfg.add_subparsers(dest="action", required=True)
    cfg_sub.add_parser("show", help="print effective configuration (secrets masked)").set_defaults(
        func=cmd_config_show
    )

    db = sub.add_parser("db", help="database tools")
    db_sub = db.add_subparsers(dest="action", required=True)
    up = db_sub.add_parser("upgrade", help="apply migrations")
    up.add_argument("--url", default=None, help="database URL (default: ENGINE_DB_URL)")
    up.set_defaults(func=cmd_db_upgrade)
    bk = db_sub.add_parser("backup", help="copy the engine database (online) and verify the copy")
    bk.add_argument("--out", default=None, help="file to write (default: data/backups/engine-<UTC time>.db)")
    bk.set_defaults(func=cmd_db_backup)
    rs = db_sub.add_parser(
        "restore", help="replace the engine database with a verified backup (engine stopped)"
    )
    rs.add_argument("--from", dest="source", required=True, help="the backup file")
    rs.add_argument("--confirm", required=True, help="the backup's file name again")
    rs.set_defaults(func=cmd_db_restore)

    audit = sub.add_parser("audit", help="audit trail tools")
    audit_sub = audit.add_subparsers(dest="action", required=True)
    ver = audit_sub.add_parser("verify", help="verify the audit hash chain")
    ver.add_argument("--chain", default=None)
    ver.set_defaults(func=cmd_audit_verify)

    doc = sub.add_parser("doctor", help="read-only diagnostics of terminal, account, server time and symbols")
    doc.add_argument("--fake", action="store_true", help="use the in-memory FakeMT5 instead of a terminal")
    doc.add_argument("--wait", type=float, default=10.0, help="seconds to wait for advancing ticks")
    doc.set_defaults(func=cmd_doctor)

    kill = sub.add_parser("kill", help="activate, release or inspect the kill switch")
    kill.add_argument("--reason", default=None)
    kill.add_argument("--actor", default=None)
    kill.add_argument("--mode", choices=["HALT", "FLATTEN"], default="HALT")
    kill.add_argument("--release", action="store_true", help="release (local CLI only)")
    kill.add_argument("--status", action="store_true")
    kill.set_defaults(func=cmd_kill)

    bt = sub.add_parser("backtest", help="run a backtest on stored history (data/history)")
    bt.add_argument("--symbols", default=None, help="comma-separated (default: symbols.allowed)")
    bt.add_argument("--server", default=None, help="trade server folder in the store (default: MT5_SERVER)")
    bt.add_argument("--data", default="data/history")
    bt.add_argument("--start", default=None, help="ISO date/time (UTC if no offset)")
    bt.add_argument("--end", default=None)
    bt.add_argument(
        "--strategies", default=None, help="comma-separated names from config.yaml (enabled for the run)"
    )
    bt.add_argument(
        "--detectors",
        default=None,
        help="comma-separated detector ids, 'all' (every enabled detector, as live; ~0.5-1 s per bar) or "
        "'none' (default: the detectors the selected strategies need to fire)",
    )
    bt.add_argument("--seed", type=int, default=None)
    bt.add_argument("--out", default=None, help="output folder (default: data/backtests/<hashes>)")
    bt.add_argument("--progress", action="store_true")
    bt.set_defaults(func=cmd_backtest)

    br = sub.add_parser("breaker", help="list or reset circuit breakers (local only, audited)")
    br_sub = br.add_subparsers(dest="action", required=True)
    br_sub.add_parser("list", help="every breaker with its state").set_defaults(func=cmd_breaker)
    reset = br_sub.add_parser("reset", help="manual reset with an actor and a reason")
    reset.add_argument("name", help="e.g. DUPLICATE_EXECUTION")
    reset.add_argument("--reason", default=None)
    reset.add_argument("--actor", default=None)
    reset.add_argument("--symbol", default=None, help="for symbol-scoped breakers")
    reset.add_argument("--ack", action="store_true", help="required for MAX_DRAWDOWN")
    reset.set_defaults(func=cmd_breaker)

    ticks = sub.add_parser("ticks", help="tick data tools (read-only)")
    ticks_sub = ticks.add_subparsers(dest="ticks_cmd", required=True)
    tp = ticks_sub.add_parser(
        "probe", help="depth of market, tick history depth and tick character (TAA-L001)"
    )
    tp.add_argument("--symbols", nargs="+", default=["EURUSD", "XAUUSD", "BTCUSD"])
    tp.add_argument("--book-samples", type=int, default=5)
    tp.add_argument("--book-interval", type=float, default=1.0, help="seconds between book samples")
    tp.add_argument(
        "--max-weeks",
        type=int,
        default=8,
        help="how far back to search tick history; each month touched costs ~40-60 MB of terminal cache",
    )
    tp.add_argument("--fake", action="store_true", help="use FakeMT5 instead of the real terminal")
    tp.set_defaults(func=cmd_ticks_probe)

    st = sub.add_parser("strategy", help="strategies disabled by remote commands (re-enable is local only)")
    st_sub = st.add_subparsers(dest="action", required=True)
    st_sub.add_parser("list", help="strategies disabled remotely").set_defaults(func=cmd_strategy)
    en = st_sub.add_parser("enable", help="re-enable a remotely disabled strategy (audited)")
    en.add_argument("name")
    en.add_argument("--reason", default=None)
    en.add_argument("--actor", default=None)
    en.set_defaults(func=cmd_strategy)

    rep = sub.add_parser("demo-report", help="DEMO soak report from the engine database")
    rep.add_argument("--days", type=float, default=14.0)
    rep.set_defaults(func=cmd_demo_report)

    adv = sub.add_parser("advisory", help="advisory tools (read-only; never changes what the bot trades)")
    adv_sub = adv.add_subparsers(dest="advisory_command", required=True)
    rank = adv_sub.add_parser("rank", help="rank every symbol by suitability for this account now")
    rank.add_argument("--fake", action="store_true", help="use the in-memory FakeMT5 instead of a terminal")
    rank.add_argument("--top", type=int, default=None, help="show only the first N rows")
    rank.add_argument("--lang", choices=["en", "th"], default="en")
    rank.set_defaults(func=cmd_advisory_rank)
    rp = adv_sub.add_parser("replay", help="replay the scanner over stored history into REPLAY shadow trades")
    rp.add_argument("--symbols", default=None, help="comma-separated (default: symbols.allowed)")
    rp.add_argument("--server", default=None, help="trade server folder in the store (default: MT5_SERVER)")
    rp.add_argument("--data", default="data/history")
    rp.add_argument("--start", default=None, help="ISO date/time (UTC if no offset); default: --months back")
    rp.add_argument("--end", default=None)
    rp.add_argument("--months", type=float, default=6.0, help="window when --start is not given")
    rp.add_argument("--equity", type=float, default=None, help="sizing equity (default: backtest balance)")
    rp.add_argument("--strategies", default=None, help="comma-separated (default: the advisory union)")
    rp.add_argument(
        "--detectors",
        default=None,
        help="comma-separated detector ids or 'none' (default: the advisory union)",
    )
    rp.add_argument("--progress", action="store_true")
    rp.set_defaults(func=cmd_advisory_replay)
    cal = adv_sub.add_parser("calibrate", help="rebuild the win-probability calibration from shadow trades")
    cal.add_argument("--server", default=None, help="trade server (default: MT5_SERVER)")
    cal.set_defaults(func=cmd_advisory_calibrate)

    web = sub.add_parser("web", help="web service users (there is no public sign-up; TOTP is enrolled here)")
    web_sub = web.add_subparsers(dest="web_command", required=True)
    cu = web_sub.add_parser("create-user", help="create a user: password prompt + TOTP enrollment")
    cu.add_argument("username")
    cu.add_argument("--role", choices=["OWNER", "ADMIN", "SUBSCRIBER"], default="OWNER")
    cu.set_defaults(func=cmd_web)
    rt = web_sub.add_parser("reset-totp", help="enroll a new TOTP secret and end the user's sessions")
    rt.add_argument("username")
    rt.set_defaults(func=cmd_web)
    rpw = web_sub.add_parser("reset-password", help="set a new password and end the user's sessions")
    rpw.add_argument("username")
    rpw.set_defaults(func=cmd_web)
    web_sub.add_parser("list-users", help="list web users").set_defaults(func=cmd_web)
    we = web_sub.add_parser("engine", help="engines paired with the web service (PLAN §A32)")
    we_sub = we.add_subparsers(dest="engine_command", required=True)
    ea = we_sub.add_parser("add", help="register an engine; prints ENGINE_ID and ENGINE_HMAC_SECRET once")
    ea.add_argument("--owner", required=True, help="username of the owner")
    ea.add_argument("--label", required=True)
    er = we_sub.add_parser("rotate", help="issue a new secret (the old one works until the engine switches)")
    er.add_argument("engine_id")
    en = we_sub.add_parser("rename", help="give an engine a new label (shown in the PWA)")
    en.add_argument("engine_id")
    en.add_argument("--label", required=True)
    ev = we_sub.add_parser("revoke", help="revoke an engine for good")
    ev.add_argument("engine_id")
    ev.add_argument("--confirm", required=True, help="the engine id again")
    ei = we_sub.add_parser(
        "import-env", help="move ENGINE_ID/ENGINE_HMAC_SECRET from the env into the database"
    )
    ei.add_argument("--owner", required=True, help="username of the owner")
    el = we_sub.add_parser("list", help="list engines (never secrets)")
    for p in (ea, er, en, ev, ei, el):
        p.set_defaults(func=cmd_web_engine)

    syn = sub.add_parser("sync", help="cloud sync tools (PLAN §A13)")
    syn_sub = syn.add_subparsers(dest="sync_command", required=True)
    uh = syn_sub.add_parser(
        "upload-history", help="queue local Parquet history for the cloud (charts, backtests)"
    )
    uh.add_argument("--server", default=None, help="trade server (default: MT5_SERVER)")
    uh.add_argument("--symbols", default=None, help="comma list (default: every stored symbol)")
    uh.add_argument("--timeframes", default=None, help="comma list (default: every stored timeframe)")
    uh.add_argument("--days", type=int, default=None, help="only the last N days (default: everything)")
    uh.add_argument("--history-dir", default="data/history")
    uh.add_argument("--send", action="store_true", help="also send now (else the running engine sends it)")
    uh.set_defaults(func=cmd_sync_upload_history)

    eng = sub.add_parser("engine", help="engine machine helpers")
    eng_sub = eng.add_subparsers(dest="engine_tool", required=True)
    eng_sub.add_parser(
        "new-totp",
        help="create CONTROL_TOTP_SECRET (QR code, confirmed with one code; never sent to the cloud)",
    ).set_defaults(func=cmd_engine_new_totp)

    add_research(sub, hypotheses=cmd_research_hypotheses, replay_family=cmd_research_replay_family)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except TaaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
