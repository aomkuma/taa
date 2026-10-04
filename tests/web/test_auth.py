"""Authentication (TAA-802): login + TOTP, sessions, CSRF, lockout, step-up, TOTP re-enrollment, audit."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.clock import ManualClock
from app.security import web_totp
from app.storage.audit import verify_chain
from app.storage.database import Database
from app.storage.models import AuditEvent, LoginThrottleRow, SessionRow, UserRow
from app.web.auth import (
    ABSOLUTE_TIMEOUT,
    IDLE_TIMEOUT,
    IP_LOCK_THRESHOLD,
    STEP_UP_WINDOW,
    USER_LOCK_THRESHOLD,
    AuthError,
    AuthService,
)
from tests.web.conftest import (
    DEV_ORIGIN,
    PASSWORD,
    PROD_ENV,
    TOTP_SECRET,
    current_code,
    login,
    make_app,
    mutation_headers,
)

pytestmark = pytest.mark.usefixtures("owner")


def audit_events(db: Database, event_type: str) -> list[AuditEvent]:
    with db.session() as sess:
        return list(sess.scalars(select(AuditEvent).where(AuditEvent.event_type == event_type)))


def next_step(clock: ManualClock) -> None:
    """Move to the next TOTP time step (a code can be used only once)."""
    clock.advance(web_totp.INTERVAL)


class TestLogin:
    def test_success_sets_a_strict_http_only_cookie(self, client: TestClient, clock: ManualClock) -> None:
        response = login(client, clock)
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["username"] == "owner"
        assert body["user"]["role"] == "OWNER"
        assert body["user"]["locale"] == "th"
        assert body["idle_timeout_seconds"] == 1800
        assert body["csrf_token"]
        cookie = response.headers["set-cookie"]
        assert cookie.startswith("taa_session=")
        for attribute in ("HttpOnly", "SameSite=strict", "Path=/", "Max-Age=43200"):
            assert attribute.lower() in cookie.lower()

    def test_production_cookie_is_host_prefixed_and_secure(
        self, db: Database, clock: ManualClock, static_dir: Path
    ) -> None:
        app = make_app(db, clock, static_dir, PROD_ENV)
        with TestClient(app, base_url="https://testserver") as prod:
            response = login(prod, clock, origin="https://taa.example.com")
            assert response.status_code == 200
            cookie = response.headers["set-cookie"]
            assert cookie.startswith("__Host-taa_session=")
            assert "secure" in cookie.lower()
            assert prod.get("/api/v1/auth/session").status_code == 200

    def test_username_is_case_insensitive(self, client: TestClient, clock: ManualClock) -> None:
        assert login(client, clock, username="  OWNER ").status_code == 200

    @pytest.mark.parametrize(
        ("field", "value", "reason"),
        [
            ("username", "nobody", "unknown_user"),
            ("password", "wrong password here", "bad_password"),
            ("code", "000000", "bad_code"),
        ],
    )
    def test_every_failure_looks_the_same(
        self, client: TestClient, clock: ManualClock, db: Database, field: str, value: str, reason: str
    ) -> None:
        response = login(client, clock, **{field: value})  # type: ignore[arg-type]
        assert response.status_code == 401
        assert response.json() == {
            "error": {"code": "invalid_credentials", "message": "Invalid username, password or code"}
        }
        assert "set-cookie" not in response.headers
        assert audit_events(db, "auth.login_failed")[-1].payload["reason"] == reason

    def test_disabled_user_cannot_log_in(self, client: TestClient, clock: ManualClock, db: Database) -> None:
        with db.session() as sess:
            sess.execute(update(UserRow).values(disabled=True))
        assert login(client, clock).status_code == 401
        assert audit_events(db, "auth.login_failed")[-1].payload["reason"] == "disabled"

    def test_a_code_works_only_once(self, client: TestClient, clock: ManualClock) -> None:
        code = current_code(clock)
        assert login(client, clock, code=code).status_code == 200
        assert login(client, clock, code=code).status_code == 401
        next_step(clock)
        assert login(client, clock).status_code == 200

    @pytest.mark.parametrize("origin", [None, "https://evil.example.com", "null"])
    def test_foreign_or_missing_origin_is_rejected(
        self, client: TestClient, clock: ManualClock, origin: str | None
    ) -> None:
        response = login(client, clock, origin=origin)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "origin_not_allowed"

    def test_unknown_fields_are_rejected(self, client: TestClient, clock: ManualClock) -> None:
        body = {"username": "owner", "password": PASSWORD, "code": current_code(clock), "role": "OWNER"}
        response = client.post("/api/v1/auth/login", json=body, headers={"Origin": DEV_ORIGIN})
        assert response.status_code == 422

    def test_session_token_is_stored_only_as_a_hash(
        self, client: TestClient, clock: ManualClock, db: Database
    ) -> None:
        login(client, clock)
        token = client.cookies["taa_session"]
        with db.session() as sess:
            row = sess.scalars(select(SessionRow)).one()
        assert token not in row.token_hash
        assert len(row.token_hash) == 64

    def test_totp_secret_is_encrypted_at_rest(self, db: Database) -> None:
        with db.session() as sess:
            user = sess.scalars(select(UserRow)).one()
        assert TOTP_SECRET not in user.totp_secret_enc
        assert user.password_hash.startswith("$argon2id$")


class TestLockout:
    def test_user_lockout_is_exponential(self, client: TestClient, clock: ManualClock, db: Database) -> None:
        for _ in range(USER_LOCK_THRESHOLD):
            assert login(client, clock, password="wrong password here").status_code == 401
        locked = login(client, clock)  # even the right password is refused while locked
        assert locked.status_code == 429
        assert locked.json()["error"]["code"] == "too_many_attempts"
        assert int(locked.headers["retry-after"]) == 61
        assert audit_events(db, "auth.lockout")

        clock.advance(61)
        assert login(client, clock, password="wrong password here").status_code == 401  # 6th failure
        assert int(login(client, clock).headers["retry-after"]) == 121  # now 2 minutes

        clock.advance(121)
        assert login(client, clock).status_code == 200
        with db.session() as sess:
            assert sess.get(LoginThrottleRow, "user:owner") is None  # success clears the counter

    def test_unknown_usernames_are_throttled_too(self, client: TestClient, clock: ManualClock) -> None:
        for _ in range(USER_LOCK_THRESHOLD):
            login(client, clock, username="ghost")
        assert login(client, clock, username="ghost").status_code == 429

    def test_client_address_lockout_across_usernames(self, client: TestClient, clock: ManualClock) -> None:
        for i in range(IP_LOCK_THRESHOLD):
            assert login(client, clock, username=f"guess{i}").status_code == 401
        assert login(client, clock).status_code == 429

    def test_old_failures_are_forgotten(self, client: TestClient, clock: ManualClock) -> None:
        for _ in range(USER_LOCK_THRESHOLD - 1):
            login(client, clock, password="wrong password here")
        clock.advance(25 * 3600)
        login(client, clock, password="wrong password here")
        assert login(client, clock).status_code == 200


class TestSession:
    def test_requires_a_cookie(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/session")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_returns_the_session(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        body = client.get("/api/v1/auth/session").json()
        assert body["user"]["username"] == "owner"
        assert body["expires_at"] == (clock.now_utc() + IDLE_TIMEOUT).isoformat()
        assert body["step_up_until"] is None

    def test_tampered_token_is_rejected(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        client.cookies.set("taa_session", client.cookies["taa_session"][:-2] + "xx")
        assert client.get("/api/v1/auth/session").status_code == 401

    def test_idle_timeout(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        clock.advance(IDLE_TIMEOUT.total_seconds() - 1)
        assert client.get("/api/v1/auth/session").status_code == 200  # activity refreshes the timer
        clock.advance(IDLE_TIMEOUT.total_seconds() - 1)
        assert client.get("/api/v1/auth/session").status_code == 200
        clock.advance(IDLE_TIMEOUT.total_seconds())
        assert client.get("/api/v1/auth/session").status_code == 401

    def test_absolute_timeout_despite_activity(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        elapsed = timedelta()
        while elapsed < ABSOLUTE_TIMEOUT - timedelta(minutes=20):
            clock.advance(20 * 60)
            elapsed += timedelta(minutes=20)
            assert client.get("/api/v1/auth/session").status_code == 200
        clock.advance(20 * 60)
        assert client.get("/api/v1/auth/session").status_code == 401

    def test_disabling_a_user_ends_their_sessions(
        self, client: TestClient, clock: ManualClock, db: Database
    ) -> None:
        login(client, clock)
        with db.session() as sess:
            sess.execute(update(UserRow).values(disabled=True))
        assert client.get("/api/v1/auth/session").status_code == 401


class TestCsrfAndLogout:
    def test_logout_needs_the_csrf_token(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        response = client.post("/api/v1/auth/logout", headers={"Origin": DEV_ORIGIN})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_failed"
        assert client.get("/api/v1/auth/session").status_code == 200

    def test_logout_needs_an_allowed_origin(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        headers = mutation_headers(client, origin="https://evil.example.com")
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 403

    def test_logout_ends_the_session(self, client: TestClient, clock: ManualClock, db: Database) -> None:
        login(client, clock)
        token = client.cookies["taa_session"]
        response = client.post("/api/v1/auth/logout", headers=mutation_headers(client))
        assert response.status_code == 204
        assert (
            'taa_session=""' in response.headers["set-cookie"]
            or "Max-Age=0" in response.headers["set-cookie"]
        )
        client.cookies.set("taa_session", token)  # replaying the old cookie does not help
        assert client.get("/api/v1/auth/session").status_code == 401
        assert audit_events(db, "auth.logout")

    def test_csrf_token_is_bound_to_its_session(self, app: object, clock: ManualClock) -> None:
        with (
            TestClient(app, base_url="https://testserver") as first,  # type: ignore[arg-type]
            TestClient(app, base_url="https://testserver") as second,  # type: ignore[arg-type]
        ):
            login(first, clock)
            next_step(clock)
            login(second, clock)
            stolen = mutation_headers(first)
            assert second.post("/api/v1/auth/logout", headers=stolen).status_code == 403


class TestStepUp:
    def test_control_actions_need_a_fresh_code(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        headers = mutation_headers(client)
        response = client.post("/api/v1/auth/totp/enroll", json={"password": PASSWORD}, headers=headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "step_up_required"

        next_step(clock)
        step = client.post("/api/v1/auth/step-up", json={"code": current_code(clock)}, headers=headers)
        assert step.status_code == 200
        assert step.json()["step_up_until"] == (clock.now_utc() + STEP_UP_WINDOW).isoformat()
        assert (
            client.post("/api/v1/auth/totp/enroll", json={"password": PASSWORD}, headers=headers).status_code
            == 200
        )

        clock.advance(STEP_UP_WINDOW.total_seconds())
        response = client.post("/api/v1/auth/totp/enroll", json={"password": PASSWORD}, headers=headers)
        assert response.json()["error"]["code"] == "step_up_required"

    def test_wrong_code_is_400_not_401(self, client: TestClient, clock: ManualClock, db: Database) -> None:
        login(client, clock)
        response = client.post(
            "/api/v1/auth/step-up", json={"code": "000000"}, headers=mutation_headers(client)
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_code"
        assert audit_events(db, "auth.step_up_failed")

    def test_the_login_code_cannot_be_reused_for_step_up(
        self, client: TestClient, clock: ManualClock
    ) -> None:
        code = current_code(clock)
        login(client, clock, code=code)
        response = client.post("/api/v1/auth/step-up", json={"code": code}, headers=mutation_headers(client))
        assert response.status_code == 400

    def test_step_up_is_throttled(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        headers = mutation_headers(client)
        for _ in range(USER_LOCK_THRESHOLD):
            client.post("/api/v1/auth/step-up", json={"code": "000000"}, headers=headers)
        next_step(clock)
        response = client.post("/api/v1/auth/step-up", json={"code": current_code(clock)}, headers=headers)
        assert response.status_code == 429


class TestTotpEnrollment:
    def _stepped_up(self, client: TestClient, clock: ManualClock) -> dict[str, str]:
        login(client, clock)
        headers = mutation_headers(client)
        next_step(clock)
        client.post("/api/v1/auth/step-up", json={"code": current_code(clock)}, headers=headers)
        return headers

    def test_re_enrollment_replaces_the_secret_and_ends_other_sessions(
        self, app: object, client: TestClient, clock: ManualClock, db: Database
    ) -> None:
        with TestClient(app, base_url="https://testserver") as other:  # type: ignore[arg-type]
            login(other, clock)
            next_step(clock)
            headers = self._stepped_up(client, clock)

            started = client.post("/api/v1/auth/totp/enroll", json={"password": PASSWORD}, headers=headers)
            assert started.status_code == 200
            body = started.json()
            new_secret = body["secret"]
            assert body["otpauth_uri"].startswith("otpauth://totp/TAA:owner?")
            assert body["qr_svg"].startswith("data:image/svg+xml;base64,")

            wrong = client.post("/api/v1/auth/totp/confirm", json={"code": "000000"}, headers=headers)
            assert wrong.status_code == 400
            next_step(clock)
            confirm = client.post(
                "/api/v1/auth/totp/confirm", json={"code": current_code(clock, new_secret)}, headers=headers
            )
            assert confirm.status_code == 204

            assert client.get("/api/v1/auth/session").status_code == 200
            assert other.get("/api/v1/auth/session").status_code == 401

        next_step(clock)
        fresh = TestClient(app, base_url="https://testserver")  # type: ignore[arg-type]
        assert login(fresh, clock).status_code == 401  # the old secret is gone
        assert login(fresh, clock, code=current_code(clock, new_secret)).status_code == 200
        assert audit_events(db, "auth.totp_enrolled")

    def test_enrollment_needs_the_password(self, client: TestClient, clock: ManualClock) -> None:
        headers = self._stepped_up(client, clock)
        response = client.post(
            "/api/v1/auth/totp/enroll", json={"password": "not my password"}, headers=headers
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_password"

    def test_confirm_without_a_pending_secret(self, client: TestClient, clock: ManualClock) -> None:
        login(client, clock)
        response = client.post(
            "/api/v1/auth/totp/confirm", json={"code": "123456"}, headers=mutation_headers(client)
        )
        assert response.status_code == 409


class TestUsers:
    def test_single_owner(self, auth: AuthService) -> None:
        with pytest.raises(AuthError, match="OWNER already exists"):
            auth.create_user("second", PASSWORD, TOTP_SECRET)
        auth.create_user("viewer", PASSWORD, TOTP_SECRET, role="SUBSCRIBER")

    @pytest.mark.parametrize("username", ["ab", "-dash", "has space", "x" * 65, "ไทย"])
    def test_username_rules(self, auth: AuthService, username: str) -> None:
        with pytest.raises(AuthError, match="username"):
            auth.create_user(username, PASSWORD, TOTP_SECRET, role="SUBSCRIBER")

    def test_duplicate_and_policy(self, auth: AuthService) -> None:
        with pytest.raises(AuthError, match="already exists"):
            auth.create_user("OWNER", PASSWORD, TOTP_SECRET, role="ADMIN")
        with pytest.raises(AuthError, match="at least"):
            auth.create_user("viewer", "short", TOTP_SECRET, role="SUBSCRIBER")
        with pytest.raises(AuthError, match="role"):
            auth.create_user("viewer", PASSWORD, TOTP_SECRET, role="ROOT")


def test_audit_chain_stays_valid(client: TestClient, clock: ManualClock, db: Database) -> None:
    login(client, clock, password="wrong password here")
    next_step(clock)
    login(client, clock)
    client.post("/api/v1/auth/logout", headers=mutation_headers(client))
    report = verify_chain(db, "web")
    assert report.ok
    assert report.events_checked >= 4
    types = {e.event_type for e in audit_events(db, "auth.login")} | {
        e.event_type for e in audit_events(db, "user.created")
    }
    assert types == {"auth.login", "user.created"}
