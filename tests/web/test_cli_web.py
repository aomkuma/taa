"""``python -m app.cli web`` (TAA-802): user bootstrap with TOTP enrollment, TOTP reset, listing."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cli.__main__ import build_parser
from app.cli.web import create_user, list_users, reset_totp, run
from app.core.clock import ManualClock
from app.security import web_totp
from app.storage.database import Database
from app.storage.models import SessionRow, UserRow
from app.web.auth import AuthError, AuthService
from tests.web.conftest import PASSWORD, login


def answers(*values: str) -> Iterator[str]:
    yield from values


class AppCodes:
    """Reads the secret the CLI prints and answers with the current code, like an authenticator app."""

    def __init__(self, out: io.StringIO, clock: ManualClock, wrong: int = 0) -> None:
        self.out = out
        self.clock = clock
        self.wrong = wrong

    def __call__(self, _prompt: str) -> str:
        if self.wrong:
            self.wrong -= 1
            return "000000"
        secret = self.out.getvalue().split("enter the key manually: ")[-1].split()[0]
        return web_totp.code_at(secret, web_totp.time_step(self.clock.now_utc()))


def printed_secret(out: io.StringIO) -> str:
    return out.getvalue().split("enter the key manually: ")[-1].split()[0]


def test_create_user_enrolls_totp_and_can_log_in(
    auth: AuthService, client: TestClient, clock: ManualClock
) -> None:
    out = io.StringIO()
    secrets_ = answers(PASSWORD, PASSWORD)
    create_user(
        auth,
        "Alice",
        role="OWNER",
        read_secret=lambda _p: next(secrets_),
        read_line=AppCodes(out, clock, wrong=1),
        out=out,
    )
    text = out.getvalue()
    assert "Scan this QR code" in text
    assert "does not match" in text
    assert "User 'alice' (OWNER) created." in text
    clock.advance(web_totp.INTERVAL)
    assert (
        login(
            client,
            clock,
            username="alice",
            code=web_totp.code_at(printed_secret(out), web_totp.time_step(clock.now_utc())),
        ).status_code
        == 200
    )


def test_password_mismatch_saves_nothing(auth: AuthService, clock: ManualClock) -> None:
    out = io.StringIO()
    secrets_ = answers(PASSWORD, PASSWORD + "x")
    with pytest.raises(AuthError, match="do not match"):
        create_user(
            auth,
            "alice",
            role="OWNER",
            read_secret=lambda _p: next(secrets_),
            read_line=AppCodes(out, clock),
            out=out,
        )
    assert auth.list_users() == []


def test_weak_password_is_refused_before_enrollment(auth: AuthService, clock: ManualClock) -> None:
    out = io.StringIO()
    with pytest.raises(AuthError, match="at least"):
        create_user(
            auth,
            "alice",
            role="OWNER",
            read_secret=lambda _p: "short",
            read_line=AppCodes(out, clock),
            out=out,
        )
    assert "QR" not in out.getvalue()


def test_three_wrong_codes_save_nothing(auth: AuthService, clock: ManualClock) -> None:
    out = io.StringIO()
    secrets_ = answers(PASSWORD, PASSWORD)
    with pytest.raises(AuthError, match="nothing was saved"):
        create_user(
            auth,
            "alice",
            role="OWNER",
            read_secret=lambda _p: next(secrets_),
            read_line=AppCodes(out, clock, wrong=3),
            out=out,
        )
    assert auth.list_users() == []


@pytest.mark.usefixtures("owner")
def test_reset_totp_replaces_the_secret_and_ends_sessions(
    auth: AuthService, client: TestClient, clock: ManualClock, db: Database
) -> None:
    assert login(client, clock).status_code == 200
    clock.advance(web_totp.INTERVAL)
    out = io.StringIO()
    reset_totp(auth, "owner", read_line=AppCodes(out, clock), out=out)
    assert "all of their sessions were ended" in out.getvalue()
    assert client.get("/api/v1/auth/session").status_code == 401
    with db.session() as sess:
        assert all(row.revoked_at is not None for row in sess.scalars(select(SessionRow)))
    clock.advance(web_totp.INTERVAL)
    code = web_totp.code_at(printed_secret(out), web_totp.time_step(clock.now_utc()))
    assert login(client, clock, code=code).status_code == 200


def test_reset_totp_for_an_unknown_user(auth: AuthService, clock: ManualClock) -> None:
    with pytest.raises(AuthError, match="no user"):
        reset_totp(auth, "ghost", read_line=AppCodes(io.StringIO(), clock), out=io.StringIO())


@pytest.mark.usefixtures("owner")
def test_list_users(auth: AuthService, db: Database) -> None:
    out = io.StringIO()
    list_users(auth, out=out)
    assert out.getvalue().startswith("owner")
    assert "OWNER" in out.getvalue()
    with db.session() as sess:
        assert sess.scalars(select(UserRow)).one().username == "owner"


def test_parser_and_dispatch(auth: AuthService) -> None:
    args = build_parser().parse_args(["web", "list-users"])
    out = io.StringIO()
    assert run(args, out=out, service=auth) == 0
    assert out.getvalue() == "no users\n"
    args = build_parser().parse_args(["web", "create-user", "bob", "--role", "SUBSCRIBER"])
    assert (args.username, args.role) == ("bob", "SUBSCRIBER")
    with pytest.raises(SystemExit):
        build_parser().parse_args(["web", "create-user", "bob", "--role", "ROOT"])
