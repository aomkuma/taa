"""``python -m app.cli web ...``: user management on the web database.

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

from app.config import load_web_settings
from app.core.clock import SystemClock
from app.security import passwords, web_totp
from app.storage.audit import AuditLog
from app.storage.database import Database, resolve_db_url, upgrade_schema
from app.web.auth import AuthError, AuthKeys, AuthService, normalize_username
from app.web.deps import WEB_AUDIT_CHAIN

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
    else:
        list_users(service, out=out)
    return 0
