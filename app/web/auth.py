"""Authentication for the web service (PLAN §A14).

- Passwords: argon2id. TOTP is mandatory for every login; a code's time step can be used only once.
- Sessions live server-side. The cookie holds a random token; the table stores only its keyed hash. A session
  ends after 30 minutes without requests or 12 hours after login, whichever comes first.
- CSRF: mutations need ``X-CSRF-Token`` (an HMAC of the session id) and an allowed ``Origin``, on top of the
  ``SameSite=Strict`` cookie.
- Failed logins count per username and per client address, with an exponential lockout. Responses never say
  which factor failed; the audit log does.
- Step-up: control actions need a fresh TOTP code (valid for 5 minutes on that session).
- Self-service security (TAA-913): change the password (current password + step-up; the user's other
  sessions end), list the user's live sessions and end any of the others.
- Every login, failure, lockout, logout, step-up, enrollment, password change and session revocation is
  appended to the ``web`` audit chain.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import TaaError
from app.core.ids import new_id, short_id
from app.security import passwords, web_totp
from app.security.crypto import SecretBox, derive_key, keyed_digest
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import LoginThrottleRow, SessionRow, UserRow

IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=12)
STEP_UP_WINDOW = timedelta(minutes=5)
# last_seen_at is written at most this often; idle expiry is therefore exact to within this interval.
TOUCH_INTERVAL = timedelta(seconds=60)

USER_LOCK_THRESHOLD = 5
IP_LOCK_THRESHOLD = 20
BASE_LOCK = timedelta(minutes=1)
MAX_LOCK = timedelta(hours=1)
# Failures older than this are forgotten.
THROTTLE_MEMORY = timedelta(hours=24)


class Role(StrEnum):
    """PLAN §A30. Control rights come from owning an engine (§A32), never from the role alone."""

    OWNER = "OWNER"  # the deployment's owner: everything, administers users and engines
    ADMIN = "ADMIN"  # support: user administration views, never trading controls or trading data
    SUBSCRIBER = "SUBSCRIBER"  # advisory features; controls only an engine it owns (when linking is enabled)


ROLES = tuple(r.value for r in Role)
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
MAX_TOKEN_LENGTH = 128


class AuthError(TaaError):
    """A user-management request is invalid (bad username, duplicate, policy)."""


class AuthFailure(TaaError):
    """Login or code verification failed. ``code`` is safe to show; details are only in the audit log."""

    def __init__(self, code: str, *, retry_after: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class AuthSession:
    session_id: str
    user_id: str
    username: str
    role: str
    locale: str
    timezone: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    step_up_until: datetime | None

    @property
    def idle_expires_at(self) -> datetime:
        return min(self.last_seen_at + IDLE_TIMEOUT, self.expires_at)


@dataclass(frozen=True)
class SessionInfo:
    """One of the user's live sessions, as the Settings page lists it."""

    session_id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime  # whichever comes first: idle or absolute expiry
    ip: str
    user_agent: str
    current: bool


@dataclass(frozen=True)
class TotpEnrollment:
    secret: str
    uri: str


class AuthKeys:
    """Purpose-specific keys derived from WEB_SESSION_SECRET."""

    def __init__(self, secret: str) -> None:
        self.session = derive_key(secret, "session-token")
        self.csrf = derive_key(secret, "csrf")
        self.totp = SecretBox(derive_key(secret, "totp-secret"))


def normalize_username(raw: str) -> str:
    return raw.strip().lower()


def lock_duration(failures: int, threshold: int) -> timedelta | None:
    """None below the threshold; then 1, 2, 4, ... minutes, capped at one hour."""
    if failures < threshold:
        return None
    return min(BASE_LOCK * 2 ** min(failures - threshold, 16), MAX_LOCK)


class AuthService:
    def __init__(self, db: Database, clock: Clock, audit: AuditLog, keys: AuthKeys) -> None:
        self.db = db
        self.clock = clock
        self.audit = audit
        self.keys = keys

    # ------------------------------------------------------------------------------------------ users
    def create_user(self, username: str, password: str, totp_secret: str, *, role: str = "OWNER") -> UserRow:
        name = normalize_username(username)
        if not USERNAME_RE.fullmatch(name):
            raise AuthError(
                "username: 3-64 characters of a-z, 0-9, '.', '_' or '-', starting with a letter or digit"
            )
        if role not in ROLES:
            raise AuthError(f"role must be one of {', '.join(ROLES)}")
        try:
            passwords.check_policy(password, username=name)
        except passwords.PasswordPolicyError as exc:
            raise AuthError(str(exc)) from exc
        now = self.clock.now_utc()
        with self.db.session() as sess:
            if sess.scalar(select(UserRow.id).where(UserRow.username == name)) is not None:
                raise AuthError(f"user {name!r} already exists")
            if role == "OWNER" and sess.scalar(select(UserRow.id).where(UserRow.role == "OWNER")) is not None:
                raise AuthError("an OWNER already exists (single owner)")
            user = UserRow(
                id=new_id(),
                username=name,
                password_hash=passwords.hash_password(password),
                role=role,
                disabled=False,
                totp_secret_enc=self.keys.totp.encrypt(totp_secret),
                totp_last_step=0,
                created_at=now,
                password_changed_at=now,
                totp_enrolled_at=now,
            )
            sess.add(user)
        self.audit.append("user.created", "cli", {"username": name, "role": role})
        return user

    def reset_totp(self, username: str, totp_secret: str) -> None:
        """Replace a user's TOTP secret (local CLI) and end all of their sessions."""
        name = normalize_username(username)
        now = self.clock.now_utc()
        with self.db.session() as sess:
            user = sess.scalar(select(UserRow).where(UserRow.username == name))
            if user is None:
                raise AuthError(f"no user {name!r}")
            user.totp_secret_enc = self.keys.totp.encrypt(totp_secret)
            user.totp_pending_enc = None
            user.totp_last_step = 0
            user.totp_enrolled_at = now
            revoked = self._revoke_user_sessions(sess, user.id, now)
        self.audit.append("user.totp_reset", "cli", {"username": name, "sessions_revoked": revoked})

    def reset_password(self, username: str, password: str) -> None:
        """Set a new password (local CLI; the old one cannot be recovered), lift the user's login lockout
        and end all of their sessions. The TOTP enrollment stays."""
        name = normalize_username(username)
        try:
            passwords.check_policy(password, username=name)
        except passwords.PasswordPolicyError as exc:
            raise AuthError(str(exc)) from exc
        now = self.clock.now_utc()
        with self.db.session() as sess:
            user = sess.scalar(select(UserRow).where(UserRow.username == name))
            if user is None:
                raise AuthError(f"no user {name!r}")
            user.password_hash = passwords.hash_password(password)
            user.password_changed_at = now
            self._clear_throttle(sess, {f"user:{name}": USER_LOCK_THRESHOLD})
            revoked = self._revoke_user_sessions(sess, user.id, now)
        self.audit.append("user.password_reset", "cli", {"username": name, "sessions_revoked": revoked})

    def list_users(self) -> list[UserRow]:
        with self.db.session() as sess:
            return list(sess.scalars(select(UserRow).order_by(UserRow.created_at)))

    # ------------------------------------------------------------------------------------------ login
    def login(
        self, username: str, password: str, code: str, *, ip: str, user_agent: str
    ) -> tuple[AuthSession, str]:
        """Returns the new session and its cookie token, or raises :class:`AuthFailure`."""
        now = self.clock.now_utc()
        name = normalize_username(username)[:64]
        throttle_keys = {f"user:{name}": USER_LOCK_THRESHOLD, f"ip:{ip}": IP_LOCK_THRESHOLD}
        retry_after = self._lock_remaining(throttle_keys, now)
        if retry_after:
            self.audit.append("auth.login_failed", name or "?", {"reason": "locked", "ip": ip})
            raise AuthFailure("too_many_attempts", retry_after=retry_after)

        with self.db.session() as sess:
            user = sess.scalar(select(UserRow).where(UserRow.username == name))
        password_ok = passwords.verify_password(user.password_hash if user else None, password)
        reason: str | None = None
        if user is None:
            reason = "unknown_user"
        elif not password_ok:
            reason = "bad_password"
        elif user.disabled:
            reason = "disabled"
        elif not self._consume_code(user, code, now):
            reason = "bad_code"

        if reason is not None or user is None:
            locked = self._record_failures(throttle_keys, now)
            self.audit.append(
                "auth.login_failed", name or "?", {"reason": reason, "ip": ip, "locked": sorted(locked)}
            )
            raise AuthFailure("invalid_credentials")

        token = secrets.token_urlsafe(32)
        with self.db.session() as sess:
            self._clear_throttle(sess, throttle_keys)
            if passwords.needs_rehash(user.password_hash):
                sess.execute(
                    update(UserRow)
                    .where(UserRow.id == user.id)
                    .values(password_hash=passwords.hash_password(password))
                )
            row = SessionRow(
                id=new_id(),
                token_hash=keyed_digest(self.keys.session, token),
                user_id=user.id,
                created_at=now,
                last_seen_at=now,
                expires_at=now + ABSOLUTE_TIMEOUT,
                ip=ip[:64],
                user_agent=user_agent[:256],
            )
            sess.add(row)
        self.audit.append("auth.login", name, {"session": short_id(row.id), "ip": ip})
        return self._session(row, user), token

    def authenticate(self, token: str | None, *, touch: bool = True) -> AuthSession | None:
        """The live session for a cookie token, or None. Refreshes the idle timer unless *touch* is false
        (live streams: the EventSource reconnects by itself, which must not keep an idle session alive)."""
        if not token or len(token) > MAX_TOKEN_LENGTH:
            return None
        now = self.clock.now_utc()
        digest = keyed_digest(self.keys.session, token)
        with self.db.session() as sess:
            row = sess.scalar(select(SessionRow).where(SessionRow.token_hash == digest))
            if row is None or row.revoked_at is not None:
                return None
            user = sess.get(UserRow, row.user_id)
            if user is None or user.disabled:
                return None
            if now >= row.expires_at or now >= row.last_seen_at + IDLE_TIMEOUT:
                return None
            if touch and now - row.last_seen_at >= TOUCH_INTERVAL:
                row.last_seen_at = now
            return self._session(row, user)

    def is_live(self, session: AuthSession) -> bool:
        """Whether *session* is still valid, without refreshing its idle timer (for long-lived streams,
        which must not keep an unattended session alive)."""
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = sess.get(SessionRow, session.session_id)
            if row is None or row.revoked_at is not None:
                return False
            user = sess.get(UserRow, row.user_id)
            if user is None or user.disabled:
                return False
            return now < row.expires_at and now < row.last_seen_at + IDLE_TIMEOUT

    def update_profile(self, session: AuthSession, *, locale: str, timezone: str) -> None:
        """The user's language and display timezone (push texts, alert times; TAA-809)."""
        with self.db.session() as sess:
            user = sess.get(UserRow, session.user_id)
            if user is not None:
                user.locale, user.timezone = locale, timezone
        self.audit.append("auth.profile", session.username, {"locale": locale, "timezone": timezone})

    def logout(self, session: AuthSession) -> None:
        with self.db.session() as sess:
            row = sess.get(SessionRow, session.session_id)
            if row is not None and row.revoked_at is None:
                row.revoked_at = self.clock.now_utc()
        self.audit.append("auth.logout", session.username, {"session": short_id(session.session_id)})

    # ------------------------------------------------------------------------------------------ CSRF
    def csrf_token(self, session: AuthSession) -> str:
        return keyed_digest(self.keys.csrf, session.session_id)

    def check_csrf(self, session: AuthSession, value: str | None) -> bool:
        return value is not None and secrets.compare_digest(self.csrf_token(session), value)

    # ------------------------------------------------------------------------------------------ step-up
    def step_up(self, session: AuthSession, code: str) -> datetime:
        """Verify a fresh TOTP code; control actions are allowed until the returned time."""
        now = self.clock.now_utc()
        keys = {f"user:{session.username}": USER_LOCK_THRESHOLD}
        retry_after = self._lock_remaining(keys, now)
        if retry_after:
            raise AuthFailure("too_many_attempts", retry_after=retry_after)
        user = self._user(session.user_id)
        if not self._consume_code(user, code, now):
            self._record_failures(keys, now)
            self.audit.append(
                "auth.step_up_failed", session.username, {"session": short_id(session.session_id)}
            )
            raise AuthFailure("invalid_code")
        until = min(now + STEP_UP_WINDOW, session.expires_at)
        with self.db.session() as sess:
            self._clear_throttle(sess, keys)
            row = sess.get(SessionRow, session.session_id)
            if row is not None:
                row.step_up_until = until
        self.audit.append("auth.step_up", session.username, {"session": short_id(session.session_id)})
        return until

    def has_step_up(self, session: AuthSession) -> bool:
        return session.step_up_until is not None and self.clock.now_utc() < session.step_up_until

    # ------------------------------------------------------------------------------------------ TOTP
    def start_totp_enrollment(self, session: AuthSession, password: str) -> TotpEnrollment:
        """A new secret, kept pending until a code from it is confirmed. Needs the password again."""
        user = self._user(session.user_id)
        if not passwords.verify_password(user.password_hash, password):
            self.audit.append("auth.totp_enroll_failed", session.username, {"reason": "bad_password"})
            raise AuthFailure("invalid_password")
        secret = web_totp.generate_secret()
        with self.db.session() as sess:
            sess.execute(
                update(UserRow)
                .where(UserRow.id == user.id)
                .values(totp_pending_enc=self.keys.totp.encrypt(secret))
            )
        self.audit.append("auth.totp_enroll_started", session.username, {})
        return TotpEnrollment(secret, web_totp.provisioning_uri(secret, account=user.username))

    def confirm_totp_enrollment(self, session: AuthSession, code: str) -> None:
        """Activate the pending secret and end every other session of the user."""
        now = self.clock.now_utc()
        user = self._user(session.user_id)
        if user.totp_pending_enc is None:
            raise AuthFailure("no_pending_enrollment")
        pending = self.keys.totp.decrypt(user.totp_pending_enc)
        step = web_totp.verify_totp(pending, code, at=now)
        if step is None:
            self.audit.append("auth.totp_enroll_failed", session.username, {"reason": "bad_code"})
            raise AuthFailure("invalid_code")
        with self.db.session() as sess:
            row = sess.get(UserRow, user.id)
            if row is None:  # pragma: no cover - deleted concurrently
                raise AuthFailure("invalid_code")
            row.totp_secret_enc = user.totp_pending_enc
            row.totp_pending_enc = None
            row.totp_last_step = step
            row.totp_enrolled_at = now
            revoked = self._revoke_user_sessions(sess, user.id, now, keep=session.session_id)
        self.audit.append("auth.totp_enrolled", session.username, {"other_sessions_revoked": revoked})

    # ------------------------------------------------------------------------------------------ self-service
    def change_password(self, session: AuthSession, current: str, new: str) -> int:
        """Replace the password (the current one is required again) and end the user's other sessions.
        Returns how many sessions ended. Raises ``invalid_password`` or ``weak_password``."""
        user = self._user(session.user_id)
        if not passwords.verify_password(user.password_hash, current):
            self.audit.append("auth.password_change_failed", session.username, {"reason": "bad_password"})
            raise AuthFailure("invalid_password")
        try:
            passwords.check_policy(new, username=user.username)
        except passwords.PasswordPolicyError as exc:
            raise AuthFailure("weak_password") from exc
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = sess.get(UserRow, user.id)
            if row is None:  # pragma: no cover - deleted concurrently
                raise AuthFailure("invalid_password")
            row.password_hash = passwords.hash_password(new)
            row.password_changed_at = now
            revoked = self._revoke_user_sessions(sess, user.id, now, keep=session.session_id)
        self.audit.append("auth.password_changed", session.username, {"other_sessions_revoked": revoked})
        return revoked

    def list_sessions(self, session: AuthSession) -> list[SessionInfo]:
        """The user's live sessions, newest first."""
        now = self.clock.now_utc()
        with self.db.session() as sess:
            rows = sess.scalars(
                select(SessionRow)
                .where(
                    SessionRow.user_id == session.user_id,
                    SessionRow.revoked_at.is_(None),
                    SessionRow.expires_at > now,
                    SessionRow.last_seen_at > now - IDLE_TIMEOUT,
                )
                .order_by(SessionRow.created_at.desc())
            ).all()
        return [
            SessionInfo(
                session_id=r.id,
                created_at=r.created_at,
                last_seen_at=r.last_seen_at,
                expires_at=min(r.last_seen_at + IDLE_TIMEOUT, r.expires_at),
                ip=r.ip,
                user_agent=r.user_agent,
                current=r.id == session.session_id,
            )
            for r in rows
        ]

    def revoke_session(self, session: AuthSession, session_id: str) -> bool:
        """End one of the user's *other* sessions; False when it is not theirs, not live or the current one
        (that one signs out with logout)."""
        if session_id == session.session_id:
            return False
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = sess.get(SessionRow, session_id)
            if row is None or row.user_id != session.user_id or row.revoked_at is not None:
                return False
            row.revoked_at = now
        self.audit.append("auth.session_revoked", session.username, {"session": short_id(session_id)})
        return True

    def revoke_other_sessions(self, session: AuthSession) -> int:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            revoked = self._revoke_user_sessions(sess, session.user_id, now, keep=session.session_id)
        self.audit.append("auth.sessions_revoked", session.username, {"other_sessions_revoked": revoked})
        return revoked

    # ------------------------------------------------------------------------------------------ internals
    def _user(self, user_id: str) -> UserRow:
        with self.db.session() as sess:
            user = sess.get(UserRow, user_id)
        if user is None:
            raise AuthFailure("invalid_credentials")
        return user

    def _session(self, row: SessionRow, user: UserRow) -> AuthSession:
        return AuthSession(
            session_id=row.id,
            user_id=user.id,
            username=user.username,
            role=user.role,
            locale=user.locale,
            timezone=user.timezone,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            step_up_until=row.step_up_until,
        )

    def _consume_code(self, user: UserRow, code: str, now: datetime) -> bool:
        """Verify *code* and claim its time step atomically, so the same code cannot be used twice."""
        secret = self.keys.totp.decrypt(user.totp_secret_enc)
        step = web_totp.verify_totp(secret, code, at=now, after_step=user.totp_last_step)
        if step is None:
            return False
        with self.db.session() as sess:
            result = sess.execute(
                update(UserRow)
                .where(UserRow.id == user.id, UserRow.totp_last_step < step)
                .values(totp_last_step=step)
            )
            return bool(getattr(result, "rowcount", 0) == 1)

    def _lock_remaining(self, keys: dict[str, int], now: datetime) -> int:
        with self.db.session() as sess:
            rows = sess.scalars(select(LoginThrottleRow).where(LoginThrottleRow.key.in_(keys))).all()
        remaining = [
            (row.locked_until - now).total_seconds()
            for row in rows
            if row.locked_until is not None and row.locked_until > now
        ]
        return int(max(remaining)) + 1 if remaining else 0

    def _record_failures(self, keys: dict[str, int], now: datetime) -> set[str]:
        """Count a failure for every key; returns the keys that are now locked."""
        locked: set[str] = set()
        with self.db.session() as sess:
            for key, threshold in keys.items():
                row = sess.get(LoginThrottleRow, key)
                if row is None:
                    row = LoginThrottleRow(key=key, failures=0, updated_at=now)
                    sess.add(row)
                elif now - row.updated_at > THROTTLE_MEMORY:
                    row.failures = 0
                row.failures += 1
                row.updated_at = now
                duration = lock_duration(row.failures, threshold)
                if duration is not None:
                    row.locked_until = now + duration
                    locked.add(key)
        for key in sorted(locked):
            self.audit.append("auth.lockout", "system", {"key": key})
        return locked

    @staticmethod
    def _clear_throttle(sess: Session, keys: dict[str, int]) -> None:
        for key in keys:
            row = sess.get(LoginThrottleRow, key)
            if row is not None:
                sess.delete(row)

    @staticmethod
    def _revoke_user_sessions(sess: Session, user_id: str, now: datetime, keep: str | None = None) -> int:
        stmt = (
            update(SessionRow)
            .where(SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        if keep is not None:
            stmt = stmt.where(SessionRow.id != keep)
        return int(getattr(sess.execute(stmt), "rowcount", 0))
