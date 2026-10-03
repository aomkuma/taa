"""Operator command line: ``python -m app.cli <command>``."""

from __future__ import annotations

import argparse
import getpass
import json
import sys

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
