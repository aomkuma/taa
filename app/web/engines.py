"""Engine registry: paired engines, their owners and HMAC secrets (PLAN §A32; TAA-708).

The cloud no longer reads engine keys from its environment. Each engine is a row in ``engines``, owned by
one user, with its secrets encrypted by a key derived from ``WEB_SESSION_SECRET`` (purpose
``engine-hmac-secret``).

- **Issuing:** the server generates the id (``eng_`` + 26 base32 characters, so ids cannot be guessed or
  chosen) and a 32-byte URL-safe secret. The secret is returned once and never logged, audited or listed.
- **Verification:** :meth:`EngineRegistry.keys` implements :class:`app.security.hmac_auth.KeyLookup`. Only
  ACTIVE engines have keys. Decrypted keys are cached for at most ``CACHE_SECONDS`` (5 s), so a revocation
  takes effect in every web process within 5 s (at once in the process that revoked).
- **Rotation:** the new secret becomes current and the old one previous. The previous secret is dropped on
  the first request signed with the new one, or after 7 days.
- **Revocation** is final: the secrets are erased and the engine's open commands expire. Replicated rows stay
  for audit.
- **Limits (fail-closed):** only OWNER users may register engines unless ``MULTI_ENGINE_ENABLED``; at most
  ``WEB_MAX_ENGINES_PER_USER`` ACTIVE engines per user; and at most one ACTIVE engine per deployment until the
  replicated tables are engine-scoped (TAA-709).
- **Audit** (web chain): ENGINE_REGISTERED, ENGINE_KEY_ROTATED, ENGINE_REVOKED, ENGINE_IMPORTED, each with
  the actor, the engine id and the owner, never key material.
"""

from __future__ import annotations

import base64
import logging
import re
import secrets
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.clock import Clock, ensure_utc
from app.core.errors import TaaError
from app.security.crypto import DecryptionError, SecretBox, derive_key
from app.security.hmac_auth import check_secret
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import EngineRow, UserRow
from app.sync.command_queue import CommandQueue

log = logging.getLogger(__name__)

KEY_PURPOSE = "engine-hmac-secret"
CACHE_SECONDS = 5.0
SEEN_WRITE_SECONDS = 60.0
PREVIOUS_GRACE = timedelta(days=7)
ENGINE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
OWNER_ROLE = "OWNER"
ERASED = ""  # the stored secret of a revoked engine


class EngineStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class EngineError(TaaError):
    """``code`` is the API error code (TAA-811 maps it to an HTTP status and an i18n key)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class IssuedKey:
    """A new engine secret, shown once."""

    engine_id: str
    secret: str = field(repr=False)


@dataclass(frozen=True)
class EngineInfo:
    """What may be listed about an engine: never key material."""

    engine_id: str
    owner_user_id: str
    owner: str
    label: str
    status: str
    created_at: datetime
    rotated_at: datetime | None
    revoked_at: datetime | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    has_previous_secret: bool


@dataclass(frozen=True)
class _Entry:
    until: float  # monotonic
    keys: tuple[bytes, ...] | None
    owner_user_id: str | None
    has_previous: bool


def new_engine_id() -> str:
    return "eng_" + base64.b32encode(secrets.token_bytes(16)).decode("ascii").rstrip("=").lower()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


class EngineRegistry:
    def __init__(
        self,
        db: Database,
        clock: Clock,
        audit: AuditLog,
        session_secret: str,
        *,
        max_per_user: int = 1,
        multi_engine: bool = False,
        one_active_engine: bool = True,
    ) -> None:
        self.db = db
        self.clock = clock
        self.audit = audit
        self.box = SecretBox(derive_key(session_secret, KEY_PURPOSE))
        self.max_per_user = max_per_user
        self.multi_engine = multi_engine
        self.one_active_engine = one_active_engine  # lifted by TAA-709 (engine-scoped replicas)
        self._cache: dict[str, _Entry] = {}
        self._seen_written: dict[str, float] = {}
        self._lock = threading.Lock()

    # --- verification (KeyLookup) ---------------------------------------------------------------------------

    def keys(self, engine_id: str) -> Sequence[bytes] | None:
        return self._entry(engine_id).keys

    def owner_of(self, engine_id: str) -> str | None:
        """The owner of an ACTIVE engine (None when unknown or revoked)."""
        entry = self._entry(engine_id)
        return entry.owner_user_id if entry.keys else None

    def invalidate(self, engine_id: str | None = None) -> None:
        with self._lock:
            if engine_id is None:
                self._cache.clear()
            else:
                self._cache.pop(engine_id, None)

    def _entry(self, engine_id: str) -> _Entry:
        now = self.clock.monotonic()
        with self._lock:
            cached = self._cache.get(engine_id)
        if cached is not None and cached.until > now:
            return cached
        entry = self._load(engine_id, now)
        with self._lock:
            self._cache[engine_id] = entry
        return entry

    def _load(self, engine_id: str, now: float) -> _Entry:
        until = now + CACHE_SECONDS
        if not ENGINE_ID_RE.fullmatch(engine_id):
            return _Entry(until, None, None, False)
        with self.db.session() as sess:
            row = sess.get(EngineRow, engine_id)
        if row is None or row.status != EngineStatus.ACTIVE.value:
            return _Entry(until, None, None, False)
        try:
            keys = [self.box.decrypt(row.secret_enc).encode("utf-8")]
            previous = row.previous_secret_enc is not None and (
                row.previous_until is not None and ensure_utc(row.previous_until) > self.clock.now_utc()
            )
            if previous and row.previous_secret_enc is not None:
                keys.append(self.box.decrypt(row.previous_secret_enc).encode("utf-8"))
        except DecryptionError:  # WEB_SESSION_SECRET changed: the engine must be re-keyed (fail closed)
            log.error(
                "engine %s: stored secret cannot be decrypted; rotate it with the current key", engine_id
            )
            return _Entry(until, None, None, False)
        return _Entry(until, tuple(keys), row.owner_user_id, previous)

    def seen(self, engine_id: str, *, previous_secret: bool) -> None:
        """Record contact after a verified request: first/last seen (at most every 60 s) and the end of a
        rotation hand-over (the first request signed with the new secret drops the previous one)."""
        now_mono = self.clock.monotonic()
        entry = self._entry(engine_id)
        with self._lock:
            written = self._seen_written.get(engine_id)
        write_seen = written is None or now_mono - written >= SEEN_WRITE_SECONDS
        drop_previous = entry.has_previous and not previous_secret
        if not write_seen and not drop_previous:
            return
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = sess.get(EngineRow, engine_id)
            if row is None or row.status != EngineStatus.ACTIVE.value:
                return
            if write_seen:
                row.first_seen_at = row.first_seen_at or now
                row.last_seen_at = now
            if drop_previous and row.previous_secret_enc is not None:
                row.previous_secret_enc = None
                row.previous_until = None
                log.info("engine %s signed with its new secret; the previous secret is retired", engine_id)
        with self._lock:
            self._seen_written[engine_id] = now_mono
        if drop_previous:
            self.invalidate(engine_id)

    # --- administration -------------------------------------------------------------------------------------

    def user(self, username: str) -> UserRow:
        with self.db.session() as sess:
            row = sess.execute(
                select(UserRow).where(UserRow.username == username.strip().lower())
            ).scalar_one_or_none()
        if row is None or row.disabled:
            raise EngineError("owner_not_found", f"no active user {username!r}")
        return row

    def _check_limits(self, owner: UserRow) -> None:
        if owner.role != OWNER_ROLE and not self.multi_engine:
            raise EngineError(
                "engine_linking_disabled", "only the owner may connect engines (MULTI_ENGINE_ENABLED)"
            )
        with self.db.session() as sess:
            active = EngineRow.status == EngineStatus.ACTIVE.value
            mine = sess.execute(
                select(func.count()).select_from(EngineRow).where(active, EngineRow.owner_user_id == owner.id)
            ).scalar_one()
            total = sess.execute(select(func.count()).select_from(EngineRow).where(active)).scalar_one()
        if mine >= self.max_per_user:
            raise EngineError("engine_limit_reached", f"at most {self.max_per_user} engine(s) per user")
        if self.one_active_engine and total >= 1:
            raise EngineError(
                "engine_limit_reached", "one active engine per deployment until replicas are engine-scoped"
            )

    @staticmethod
    def _label(label: str) -> str:
        cleaned = " ".join(label.split())
        if not 1 <= len(cleaned) <= 64:
            raise EngineError("invalid_label", "the label must have 1-64 characters")
        return cleaned

    def register(self, owner: UserRow, label: str, *, actor: str) -> IssuedKey:
        name = self._label(label)
        self._check_limits(owner)
        engine_id, secret = new_engine_id(), new_secret()
        self._insert(owner, engine_id, name, secret, None)
        self.audit.append(
            "ENGINE_REGISTERED", actor, {"engine_id": engine_id, "owner": owner.username, "label": name}
        )
        log.info("engine %s registered for %s", engine_id, owner.username)
        return IssuedKey(engine_id, secret)

    def import_env(
        self, owner: UserRow, engine_id: str, secret: str, previous: str | None, *, actor: str
    ) -> EngineInfo:
        """Move the pre-rev. 4 ``ENGINE_*`` variables of the web service into the registry (once)."""
        if not ENGINE_ID_RE.fullmatch(engine_id):
            raise EngineError(
                "invalid_engine_id", "ENGINE_ID: 1-64 characters of A-Z, a-z, 0-9, '.', '_', '-'"
            )
        check_secret(secret)
        if previous is not None:
            check_secret(previous, "ENGINE_HMAC_SECRET_PREVIOUS")
        with self.db.session() as sess:
            if sess.get(EngineRow, engine_id) is not None:
                raise EngineError("engine_exists", f"engine {engine_id} is already registered")
        self._check_limits(owner)
        self._insert(owner, engine_id, "imported", secret, previous)
        self.audit.append(
            "ENGINE_IMPORTED",
            actor,
            {"engine_id": engine_id, "owner": owner.username, "with_previous": previous is not None},
        )
        info = self.get(engine_id)
        if info is None:  # pragma: no cover - just inserted
            raise EngineError("engine_not_found", engine_id)
        return info

    def _insert(self, owner: UserRow, engine_id: str, label: str, secret: str, previous: str | None) -> None:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            sess.add(
                EngineRow(
                    engine_id=engine_id,
                    owner_user_id=owner.id,
                    label=label,
                    secret_enc=self.box.encrypt(secret),
                    previous_secret_enc=None if previous is None else self.box.encrypt(previous),
                    previous_until=None if previous is None else now + PREVIOUS_GRACE,
                    status=EngineStatus.ACTIVE.value,
                    created_at=now,
                )
            )
        self.invalidate(engine_id)

    @staticmethod
    def _active_row(sess: Session, engine_id: str) -> EngineRow:
        row = sess.get(EngineRow, engine_id)
        if row is None:
            raise EngineError("engine_not_found", f"no engine {engine_id}")
        if row.status != EngineStatus.ACTIVE.value:
            raise EngineError("engine_revoked", f"engine {engine_id} is revoked")
        return row

    def rotate(self, engine_id: str, *, actor: str) -> IssuedKey:
        secret = new_secret()
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = self._active_row(sess, engine_id)
            row.previous_secret_enc = row.secret_enc
            row.previous_until = now + PREVIOUS_GRACE
            row.secret_enc = self.box.encrypt(secret)
            row.rotated_at = now
            owner = sess.get(UserRow, row.owner_user_id)
        self.invalidate(engine_id)
        self.audit.append(
            "ENGINE_KEY_ROTATED", actor, {"engine_id": engine_id, "owner": owner.username if owner else ""}
        )
        return IssuedKey(engine_id, secret)

    def revoke(self, engine_id: str, *, actor: str, commands: CommandQueue | None = None) -> None:
        now = self.clock.now_utc()
        with self.db.session() as sess:
            row = self._active_row(sess, engine_id)
            row.status = EngineStatus.REVOKED.value
            row.revoked_at = now
            row.secret_enc = ERASED  # a revoked engine can never sign again
            row.previous_secret_enc = None
            row.previous_until = None
            owner = sess.get(UserRow, row.owner_user_id)
        self.invalidate(engine_id)
        expired = commands.expire_engine(engine_id) if commands is not None else 0
        self.audit.append(
            "ENGINE_REVOKED",
            actor,
            {"engine_id": engine_id, "owner": owner.username if owner else "", "expired_commands": expired},
        )
        log.warning("engine %s revoked by %s", engine_id, actor)

    def get(self, engine_id: str) -> EngineInfo | None:
        infos = self._infos(EngineRow.engine_id == engine_id)
        return infos[0] if infos else None

    def list_engines(self, owner_user_id: str | None = None) -> list[EngineInfo]:
        return self._infos(None if owner_user_id is None else EngineRow.owner_user_id == owner_user_id)

    def _infos(self, where: ColumnElement[bool] | None) -> list[EngineInfo]:
        query = select(EngineRow, UserRow.username).join(UserRow, UserRow.id == EngineRow.owner_user_id)
        if where is not None:
            query = query.where(where)
        with self.db.session() as sess:
            rows = sess.execute(query.order_by(EngineRow.created_at)).all()
        return [
            EngineInfo(
                engine_id=r.engine_id,
                owner_user_id=r.owner_user_id,
                owner=username,
                label=r.label,
                status=r.status,
                created_at=ensure_utc(r.created_at),
                rotated_at=None if r.rotated_at is None else ensure_utc(r.rotated_at),
                revoked_at=None if r.revoked_at is None else ensure_utc(r.revoked_at),
                first_seen_at=None if r.first_seen_at is None else ensure_utc(r.first_seen_at),
                last_seen_at=None if r.last_seen_at is None else ensure_utc(r.last_seen_at),
                has_previous_secret=r.previous_secret_enc is not None,
            )
            for r, username in rows
        ]
