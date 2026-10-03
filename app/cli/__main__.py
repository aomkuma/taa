"""Operator command line: ``python -m app.cli <command>``."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import UTC, datetime

from app.config import REPO_ROOT, Settings, load_settings
from app.core.errors import ConfigError, TaaError


def _settings(args: argparse.Namespace) -> Settings:
    return load_settings(env_file=args.env_file, config_file=args.config)


def _engine_chain(settings: Settings) -> str:
    return f"engine:{settings.env.ENGINE_ID or 'local'}"


def _db_and_audit(settings: Settings):
    from app.storage.audit import AuditLog
    from app.storage.database import Database, resolve_db_url, upgrade_schema

    upgrade_schema(resolve_db_url(settings.env.ENGINE_DB_URL))
    db = Database(resolve_db_url(settings.env.ENGINE_DB_URL))
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
    bt.add_argument("--seed", type=int, default=None)
    bt.add_argument("--out", default=None, help="output folder (default: data/backtests/<hashes>)")
    bt.add_argument("--progress", action="store_true")
    bt.set_defaults(func=cmd_backtest)
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
