"""``python -m app.cli web ...``: user and engine management on the web database, and ``engine new-totp``
for the engine machine.

There is no public sign-up endpoint (PLAN §A14). Users are created here, locally or on Railway with
``railway ssh -s web -- python -m app.cli web create-user <name>``. TOTP is enrolled at creation: the secret
is shown once as a QR code and must be confirmed with a code before the user is saved.
"""

from __future__ import annotations

import argparse
import getpass
from collections.abc import Callable
from typing import TextIO

import qrcode

from app.config import WebSettings, load_web_settings
from app.core.clock import Clock, SystemClock
from app.security import passwords, web_totp
from app.storage.audit import AuditLog
from app.storage.database import Database, resolve_db_url, upgrade_schema
from app.sync.command_queue import CommandQueue
from app.web.app import engine_registry
from app.web.auth import AuthError, AuthKeys, AuthService, normalize_username
from app.web.deps import WEB_AUDIT_CHAIN
from app.web.engines import EngineError, EngineErrorCode, EngineRegistry, IssuedKey

ReadLine = Callable[[str], str]
CONFIRM_ATTEMPTS = 3


def auth_service(env_file: str | None) -> AuthService:
    settings = load_web_settings(env_file=env_file)
    url = resolve_db_url(settings.DATABASE_URL)
    upgrade_schema(url)
    db = Database(url)
    clock = SystemClock()
    keys = AuthKeys(settings.WEB_SESSION_SECRET.get_secret_value())
    return AuthService(db, clock, AuditLog(db, WEB_AUDIT_CHAIN, clock), keys)


def enroll_totp(service: AuthService, account: str, *, read_line: ReadLine, out: TextIO) -> str:
    """Show a new secret as a QR code and return it once a code from the app confirms it."""
    secret = web_totp.generate_secret()
    uri = web_totp.provisioning_uri(secret, account=account)
    out.write("\nScan this QR code with an authenticator app (Google Authenticator, 1Password, ...):\n\n")
    qr = qrcode.QRCode(border=2)
    qr.add_data(uri)
    qr.print_ascii(out=out, invert=True)
    out.write(f"\nOr enter the key manually: {secret}\n\n")
    for _ in range(CONFIRM_ATTEMPTS):
        code = read_line("6-digit code from the app: ")
        if web_totp.verify_totp(secret, code, at=service.clock.now_utc()) is not None:
            return secret
        out.write("That code does not match; check the app and the computer clock.\n")
    raise AuthError("TOTP confirmation failed; nothing was saved")


def create_user(
    service: AuthService,
    username: str,
    *,
    role: str,
    read_secret: ReadLine,
    read_line: ReadLine,
    out: TextIO,
) -> None:
    name = normalize_username(username)
    password = read_secret("Password: ")
    if read_secret("Repeat the password: ") != password:
        raise AuthError("the passwords do not match; nothing was saved")
    try:
        passwords.check_policy(password, username=name)
    except passwords.PasswordPolicyError as exc:
        raise AuthError(str(exc)) from exc
    secret = enroll_totp(service, name, read_line=read_line, out=out)
    service.create_user(name, password, secret, role=role)
    out.write(f"User {name!r} ({role}) created.\n")


def reset_totp(service: AuthService, username: str, *, read_line: ReadLine, out: TextIO) -> None:
    name = normalize_username(username)
    if name not in {u.username for u in service.list_users()}:
        raise AuthError(f"no user {name!r}")
    secret = enroll_totp(service, name, read_line=read_line, out=out)
    service.reset_totp(name, secret)
    out.write(f"TOTP for {name!r} replaced; all of their sessions were ended.\n")


def reset_password(service: AuthService, username: str, *, read_secret: ReadLine, out: TextIO) -> None:
    name = normalize_username(username)
    if name not in {u.username for u in service.list_users()}:
        raise AuthError(f"no user {name!r}")
    password = read_secret("New password: ")
    if read_secret("Repeat the password: ") != password:
        raise AuthError("the passwords do not match; nothing was saved")
    service.reset_password(name, password)
    out.write(
        f"Password for {name!r} replaced; all of their sessions were ended. The TOTP app stays the same.\n"
    )


def list_users(service: AuthService, *, out: TextIO) -> None:
    users = service.list_users()
    if not users:
        out.write("no users\n")
    for user in users:
        state = "disabled" if user.disabled else "active"
        out.write(
            f"{user.username:<24} {user.role:<10} {state:<8} created {user.created_at:%Y-%m-%d %H:%M}Z\n"
        )


def run(args: argparse.Namespace, *, out: TextIO, service: AuthService | None = None) -> int:
    service = service or auth_service(args.env_file)
    if args.web_command == "create-user":
        create_user(
            service, args.username, role=args.role, read_secret=getpass.getpass, read_line=input, out=out
        )
    elif args.web_command == "reset-totp":
        reset_totp(service, args.username, read_line=input, out=out)
    elif args.web_command == "reset-password":
        reset_password(service, args.username, read_secret=getpass.getpass, out=out)
    else:
        list_users(service, out=out)
    return 0


# --- engines (rev. 4, PLAN §A32) ----------------------------------------------------------------------------

CLI_ACTOR = "cli"


def engine_services(env_file: str | None) -> tuple[EngineRegistry, CommandQueue, WebSettings]:
    settings = load_web_settings(env_file=env_file)
    url = resolve_db_url(settings.DATABASE_URL)
    upgrade_schema(url)
    db = Database(url)
    clock = SystemClock()
    audit = AuditLog(db, WEB_AUDIT_CHAIN, clock)
    return engine_registry(settings, db, clock, audit), CommandQueue(db, clock), settings


def print_engine_env(issued: IssuedKey, settings: WebSettings, *, out: TextIO) -> None:
    origin = settings.WEB_PUBLIC_ORIGIN or "https://<your web service>"
    out.write(
        "\nPut these lines into the .env (or the keyring) on the engine machine.\n"
        "The secret is shown only now; if it is lost, rotate it.\n\n"
        f"CLOUD_BASE_URL={origin}\nENGINE_ID={issued.engine_id}\nENGINE_HMAC_SECRET={issued.secret}\n\n"
        "Then set sync.enabled: true in the config.yaml of the engine and create CONTROL_TOTP_SECRET on the\n"
        "engine machine with: python -m app.cli engine new-totp\n"
    )


def run_engine(
    args: argparse.Namespace,
    *,
    out: TextIO,
    services: tuple[EngineRegistry, CommandQueue, WebSettings] | None = None,
) -> int:
    registry, commands, settings = services or engine_services(args.env_file)
    command = args.engine_command
    if command == "add":
        issued = registry.register(registry.user(args.owner), args.label, actor=CLI_ACTOR)
        out.write(f"Engine {issued.engine_id} registered for {args.owner}.\n")
        print_engine_env(issued, settings, out=out)
    elif command == "rotate":
        issued = registry.rotate(args.engine_id, actor=CLI_ACTOR)
        out.write(
            f"New secret for {issued.engine_id}; the old one works until the engine uses the new one.\n"
        )
        print_engine_env(issued, settings, out=out)
    elif command == "rename":
        name = registry.rename(args.engine_id, args.label, actor=CLI_ACTOR)
        out.write(f"Engine {args.engine_id} is now labelled {name!r}.\n")
    elif command == "revoke":
        if args.confirm != args.engine_id:
            raise EngineError(
                EngineErrorCode.CONFIRMATION_MISMATCH, "repeat the engine id with --confirm to revoke it"
            )
        registry.revoke(args.engine_id, actor=CLI_ACTOR, commands=commands)
        out.write(f"Engine {args.engine_id} revoked (final); its open commands expired.\n")
    elif command == "import-env":
        if settings.ENGINE_ID is None or settings.ENGINE_HMAC_SECRET is None:
            raise EngineError(
                EngineErrorCode.NOTHING_TO_IMPORT, "ENGINE_ID and ENGINE_HMAC_SECRET are not set"
            )
        previous = settings.ENGINE_HMAC_SECRET_PREVIOUS
        info = registry.import_env(
            registry.user(args.owner),
            settings.ENGINE_ID,
            settings.ENGINE_HMAC_SECRET.get_secret_value(),
            previous.get_secret_value() if previous else None,
            actor=CLI_ACTOR,
        )
        out.write(
            f"Engine {info.engine_id} imported for {info.owner}. Now remove ENGINE_ID and "
            "ENGINE_HMAC_SECRET(_PREVIOUS) from the variables of the web service.\n"
        )
    else:
        engines = registry.list_engines()
        if not engines:
            out.write("no engines\n")
        for e in engines:
            seen = "never" if e.last_seen_at is None else f"{e.last_seen_at:%Y-%m-%d %H:%M}Z"
            out.write(f"{e.engine_id:<32} {e.owner:<16} {e.status:<8} last seen {seen:<18} {e.label}\n")
    return 0


def new_control_totp(*, read_line: ReadLine, out: TextIO, clock: Clock | None = None) -> str:
    """Engine side: a new CONTROL_TOTP_SECRET for remote close/flatten, confirmed with one code."""
    clock = clock or SystemClock()
    secret = web_totp.generate_secret()
    uri = web_totp.provisioning_uri(secret, account="engine control", issuer="TAA engine")
    out.write("\nScan this QR code with your authenticator app (it confirms remote close/flatten):\n\n")
    qr = qrcode.QRCode(border=2)
    qr.add_data(uri)
    qr.print_ascii(out=out, invert=True)
    out.write(f"\nOr enter the key manually: {secret}\n\n")
    for _ in range(CONFIRM_ATTEMPTS):
        code = read_line("6-digit code from the app: ")
        if web_totp.verify_totp(secret, code, at=clock.now_utc()) is not None:
            out.write(
                "\nPut this line into the .env (or the keyring) on the engine machine, then restart\n"
                f"the engine. It never goes to the cloud.\n\nCONTROL_TOTP_SECRET={secret}\n"
            )
            return secret
        out.write("That code does not match; check the app and the computer clock.\n")
    raise AuthError("TOTP confirmation failed; nothing to save")
