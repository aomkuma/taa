"""Engine registry: issuing, limits, verification, rotation, revocation, import and CLI (PLAN §A32; TAA-708)."""

from __future__ import annotations

import argparse
import io
import logging
from pathlib import Path
from typing import Any

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import WebSettings
from app.core.clock import ManualClock
from app.core.errors import ConfigError
from app.security.hmac_auth import AuthError, AuthFailure, Signer, Verifier
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import AuditEvent, EngineCommandRow, EngineRow, UserRow
from app.sync.command_queue import CommandQueue
from app.sync.commands import COMMANDS_PATH
from app.web.app import check_engine_env, engine_registry
from app.web.auth import AuthKeys, AuthService
from app.web.deps import WEB_AUDIT_CHAIN
from app.web.engines import CACHE_SECONDS, PREVIOUS_GRACE, EngineError, EngineRegistry
from tests.web.conftest import DEV_ENV, PASSWORD, PROD_ENV, SESSION_SECRET, TOTP_SECRET, make_app

TARGET = COMMANDS_PATH


def settings(**env: Any) -> WebSettings:
    return WebSettings.model_validate(DEV_ENV | {k: str(v) for k, v in env.items()})


def registry(db: Database, clock: ManualClock, **env: Any) -> EngineRegistry:
    return engine_registry(settings(**env), db, clock, AuditLog(db, WEB_AUDIT_CHAIN, clock))


def user(db: Database, clock: ManualClock, name: str, role: str = "OWNER") -> UserRow:
    audit = AuditLog(db, WEB_AUDIT_CHAIN, clock)
    return AuthService(db, clock, audit, AuthKeys(SESSION_SECRET)).create_user(
        name, PASSWORD, TOTP_SECRET, role=role
    )


def verify(reg: EngineRegistry, clock: ManualClock, engine_id: str, secret: str) -> Any:
    headers = Signer(engine_id, secret.encode(), clock).headers("GET", TARGET)
    return Verifier(reg, clock).verify("GET", TARGET, headers, b"")


def audit_events(db: Database) -> list[AuditEvent]:
    with db.session() as sess:
        return list(sess.execute(select(AuditEvent).where(AuditEvent.chain == WEB_AUDIT_CHAIN)).scalars())


class TestIssuing:
    def test_register_issues_an_unguessable_id_and_a_secret_once(
        self, db: Database, clock: ManualClock
    ) -> None:
        reg = registry(db, clock)
        owner = user(db, clock, "owner")
        issued = reg.register(owner, "  home   pc ", actor="owner")
        assert issued.engine_id.startswith("eng_") and len(issued.engine_id) == 30
        assert len(issued.secret) >= 43 and issued.secret not in repr(issued)
        [info] = reg.list_engines()
        assert (info.label, info.status, info.owner, info.first_seen_at) == (
            "home pc",
            "ACTIVE",
            "owner",
            None,
        )
        assert issued.secret not in repr(info)
        with db.session() as sess:
            row = sess.get(EngineRow, issued.engine_id)
            assert row is not None and issued.secret not in row.secret_enc  # encrypted at rest
        [event] = [e for e in audit_events(db) if e.event_type == "ENGINE_REGISTERED"]
        assert event.payload == {"engine_id": issued.engine_id, "owner": "owner", "label": "home pc"}
        assert verify(reg, clock, issued.engine_id, issued.secret).engine_id == issued.engine_id
        assert reg.owner_of(issued.engine_id) == owner.id

    def test_labels_are_bounded(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        owner = user(db, clock, "owner")
        for bad in ("", "   ", "x" * 65):
            with pytest.raises(EngineError, match="label"):
                reg.register(owner, bad, actor="owner")


class TestLimits:
    def test_several_engines_once_replicas_are_engine_scoped(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock, MULTI_ENGINE_ENABLED=True)  # TAA-709 lifted the one-engine limit
        a = reg.register(user(db, clock, "owner"), "a", actor="owner")
        b = reg.register(user(db, clock, "other", "SUBSCRIBER"), "b", actor="other")
        assert {e.engine_id for e in reg.list_engines()} == {a.engine_id, b.engine_id}
        reg.one_active_engine = True  # the pre-709 switch still refuses a second engine
        with pytest.raises(EngineError) as exc:
            reg.register(user(db, clock, "third", "SUBSCRIBER"), "c", actor="third")
        assert exc.value.code == "engine_limit_reached"

    def test_a_revoked_engine_frees_the_slot(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        owner = user(db, clock, "owner")
        first = reg.register(owner, "a", actor="owner")
        reg.revoke(first.engine_id, actor="owner")
        assert reg.register(owner, "b", actor="owner").engine_id != first.engine_id

    def test_only_owners_link_engines_unless_enabled(self, db: Database, clock: ManualClock) -> None:
        sub = user(db, clock, "subscriber", "SUBSCRIBER")
        with pytest.raises(EngineError) as exc:
            registry(db, clock).register(sub, "a", actor="subscriber")
        assert exc.value.code == "engine_linking_disabled"
        assert registry(db, clock, MULTI_ENGINE_ENABLED=True).register(sub, "a", actor="subscriber")

    def test_per_user_limit(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock, WEB_MAX_ENGINES_PER_USER=2)
        reg.one_active_engine = False  # as after TAA-709
        owner = user(db, clock, "owner")
        reg.register(owner, "a", actor="owner")
        reg.register(owner, "b", actor="owner")
        with pytest.raises(EngineError, match="per user"):
            reg.register(owner, "c", actor="owner")

    def test_disabled_or_unknown_owners(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        with pytest.raises(EngineError) as exc:
            reg.user("nobody")
        assert exc.value.code == "owner_not_found"


class TestVerification:
    def test_unknown_and_malformed_ids_are_unknown_engines(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        for engine_id in ("eng_nothere", "../etc", "x" * 65):
            with pytest.raises(AuthError) as exc:
                verify(reg, clock, engine_id, "s" * 43)
            assert exc.value.reason is AuthFailure.UNKNOWN_ENGINE

    def test_revocation_is_immediate_here_and_within_5_s_elsewhere(
        self, db: Database, clock: ManualClock
    ) -> None:
        here, elsewhere = registry(db, clock), registry(db, clock)  # two web processes
        issued = here.register(user(db, clock, "owner"), "a", actor="owner")
        verify(elsewhere, clock, issued.engine_id, issued.secret)  # warms the other process's cache
        commands = CommandQueue(db, clock)
        open_cmd = commands.enqueue(issued.engine_id, "RESYNC", created_by="owner")
        here.revoke(issued.engine_id, actor="owner", commands=commands)
        with pytest.raises(AuthError):
            verify(here, clock, issued.engine_id, issued.secret)
        verify(elsewhere, clock, issued.engine_id, issued.secret)  # still cached
        clock.advance(CACHE_SECONDS)
        with pytest.raises(AuthError):
            verify(elsewhere, clock, issued.engine_id, issued.secret)
        with db.session() as sess:
            row = sess.get(EngineRow, issued.engine_id)
            assert row is not None and row.secret_enc == "" and row.revoked_at is not None
            cmd = sess.get(EngineCommandRow, open_cmd["id"])
            assert cmd is not None and cmd.status == "EXPIRED"
        with pytest.raises(EngineError) as exc:
            here.rotate(issued.engine_id, actor="owner")
        assert exc.value.code == "engine_revoked"

    def test_rotation_hand_over(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        first = reg.register(user(db, clock, "owner"), "a", actor="owner")
        second = reg.rotate(first.engine_id, actor="owner")
        assert verify(reg, clock, first.engine_id, first.secret).previous_secret  # old one still works
        verified = verify(reg, clock, first.engine_id, second.secret)
        reg.seen(first.engine_id, previous_secret=verified.previous_secret)  # the engine switched
        with pytest.raises(AuthError):
            verify(reg, clock, first.engine_id, first.secret)
        third = reg.rotate(first.engine_id, actor="owner")
        clock.advance(PREVIOUS_GRACE.total_seconds() + 1)  # the engine never switched: 7 days, then gone
        with pytest.raises(AuthError):
            verify(reg, clock, first.engine_id, second.secret)
        assert verify(reg, clock, first.engine_id, third.secret)
        assert [e.payload for e in audit_events(db) if e.event_type == "ENGINE_KEY_ROTATED"] == [
            {"engine_id": first.engine_id, "owner": "owner"}
        ] * 2

    def test_contact_is_recorded_at_most_every_minute(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        issued = reg.register(user(db, clock, "owner"), "a", actor="owner")
        first = clock.now_utc()
        reg.seen(issued.engine_id, previous_secret=False)
        clock.advance(30)
        reg.seen(issued.engine_id, previous_secret=False)
        info = reg.get(issued.engine_id)
        assert info is not None and info.first_seen_at == first and info.last_seen_at == first
        clock.advance(30)
        reg.seen(issued.engine_id, previous_secret=False)
        info = reg.get(issued.engine_id)
        assert info is not None and info.first_seen_at == first and info.last_seen_at == clock.now_utc()

    def test_a_changed_session_secret_fails_closed(self, db: Database, clock: ManualClock) -> None:
        issued = registry(db, clock).register(user(db, clock, "owner"), "a", actor="owner")
        other = registry(db, clock, WEB_SESSION_SECRET="another-session-secret-0123456789abcdef")
        with pytest.raises(AuthError):
            verify(other, clock, issued.engine_id, issued.secret)


class TestSecretsStayHidden:
    def test_no_secret_in_logs_audit_or_listings(
        self, db: Database, clock: ManualClock, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        reg = registry(db, clock)
        issued = reg.register(user(db, clock, "owner"), "a", actor="owner")
        rotated = reg.rotate(issued.engine_id, actor="owner")
        verify(reg, clock, issued.engine_id, rotated.secret)
        reg.revoke(issued.engine_id, actor="owner")
        text = caplog.text + repr([e.payload for e in audit_events(db)]) + repr(reg.list_engines())
        for secret in (issued.secret, rotated.secret):
            assert secret not in text


class TestImport:
    SECRET = "engine-hmac-secret-0123456789abcdef-xyz"
    OLD = "engine-hmac-secret-previous-0123456789ab"

    def test_import_once_with_the_previous_secret(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        owner = user(db, clock, "owner")
        info = reg.import_env(owner, "eng-1", self.SECRET, self.OLD, actor="cli")
        assert info.has_previous_secret and info.label == "imported"
        assert verify(reg, clock, "eng-1", self.OLD).previous_secret
        with pytest.raises(EngineError) as exc:
            reg.import_env(owner, "eng-1", self.SECRET, None, actor="cli")
        assert exc.value.code == "engine_exists"
        [event] = [e for e in audit_events(db) if e.event_type == "ENGINE_IMPORTED"]
        assert event.payload == {"engine_id": "eng-1", "owner": "owner", "with_previous": True}

    def test_bad_imports_are_refused(self, db: Database, clock: ManualClock) -> None:
        reg = registry(db, clock)
        owner = user(db, clock, "owner")
        with pytest.raises(EngineError):
            reg.import_env(owner, "bad id!", self.SECRET, None, actor="cli")
        with pytest.raises(ConfigError):
            reg.import_env(owner, "eng-1", "short", None, actor="cli")

    def test_production_refuses_engine_variables(self, db: Database, clock: ManualClock) -> None:
        env = {"ENGINE_ID": "eng-1", "ENGINE_HMAC_SECRET": self.SECRET}
        prod = WebSettings.model_validate(PROD_ENV | env)
        reg = registry(db, clock)
        with pytest.raises(ConfigError, match="import-env"):
            check_engine_env(prod, reg)
        reg.import_env(user(db, clock, "owner"), "eng-1", self.SECRET, None, actor="cli")
        with pytest.raises(ConfigError, match="remove"):
            check_engine_env(prod, reg)
        check_engine_env(WebSettings.model_validate(PROD_ENV), reg)  # unset: fine

    def test_development_only_warns(
        self, db: Database, clock: ManualClock, static_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        env = DEV_ENV | {"ENGINE_ID": "eng-1", "ENGINE_HMAC_SECRET": self.SECRET}
        app = make_app(db, clock, static_dir, env)  # the local .env is shared with the engine
        assert "ignored by the web service" in caplog.text
        with TestClient(app, base_url="https://testserver") as client:  # and the env keys do not work
            headers = Signer("eng-1", self.SECRET.encode(), clock).headers("GET", TARGET)
            assert client.get(TARGET, headers=headers).status_code == 401


class TestCli:
    def services(self, db: Database, clock: ManualClock) -> tuple[EngineRegistry, CommandQueue, WebSettings]:
        env = {"ENGINE_ID": "eng-1", "ENGINE_HMAC_SECRET": TestImport.SECRET}
        web = settings(**env)
        return (
            engine_registry(web, db, clock, AuditLog(db, WEB_AUDIT_CHAIN, clock)),
            CommandQueue(db, clock),
            web,
        )

    def run(self, services: Any, command: str, **kw: Any) -> str:
        from app.cli.web import run_engine

        out = io.StringIO()
        run_engine(argparse.Namespace(engine_command=command, **kw), out=out, services=services)
        return out.getvalue()

    def test_add_list_rotate_revoke(self, db: Database, clock: ManualClock) -> None:
        user(db, clock, "owner")
        services = self.services(db, clock)
        added = self.run(services, "add", owner="owner", label="vps")
        engine_id = next(
            line.split("=", 1)[1] for line in added.splitlines() if line.startswith("ENGINE_ID=")
        )
        secret = next(
            line.split("=", 1)[1] for line in added.splitlines() if line.startswith("ENGINE_HMAC_SECRET=")
        )
        assert "CLOUD_BASE_URL=" in added and "new-totp" in added
        listing = self.run(services, "list")
        assert engine_id in listing and secret not in listing and "never" in listing
        rotated = self.run(services, "rotate", engine_id=engine_id)
        assert "ENGINE_HMAC_SECRET=" in rotated and secret not in rotated
        assert "'mt5 demo'" in self.run(services, "rename", engine_id=engine_id, label="  mt5   demo ")
        assert "mt5 demo" in self.run(services, "list")
        with pytest.raises(EngineError, match="1-64"):
            self.run(services, "rename", engine_id=engine_id, label=" ")
        assert [e.payload for e in audit_events(db) if e.event_type == "ENGINE_RENAMED"] == [
            {"engine_id": engine_id, "from": "vps", "to": "mt5 demo"}
        ]
        with pytest.raises(EngineError, match="confirm"):
            self.run(services, "revoke", engine_id=engine_id, confirm="other")
        assert "revoked" in self.run(services, "revoke", engine_id=engine_id, confirm=engine_id)

    def test_import_env(self, db: Database, clock: ManualClock) -> None:
        user(db, clock, "owner")
        out = self.run(self.services(db, clock), "import-env", owner="owner")
        assert "eng-1 imported" in out and TestImport.SECRET not in out

    def test_new_control_totp(self, monkeypatch: pytest.MonkeyPatch, clock: ManualClock) -> None:
        from app.cli import web as cli_web

        monkeypatch.setattr(cli_web.web_totp, "generate_secret", lambda: TOTP_SECRET)
        codes = iter(["000000", pyotp.TOTP(TOTP_SECRET).at(clock.now_utc().timestamp())])
        out = io.StringIO()
        assert cli_web.new_control_totp(read_line=lambda _p: next(codes), out=out, clock=clock) == TOTP_SECRET
        assert f"CONTROL_TOTP_SECRET={TOTP_SECRET}" in out.getvalue() and "does not match" in out.getvalue()
