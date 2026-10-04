"""Cloud-only tables of the web service: users, sessions, login throttling, engines and advisory preferences.

PLAN §A14, §A18, §A32.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, utcnow
from app.storage.types import JSONType, UTCDateTime


class UserRow(Base):
    """A web user. TOTP is mandatory: every user is created with an enrolled secret.

    Users are created only with ``app.cli web create-user``. ``role`` is OWNER for now; Phase 8A adds ADMIN
    and SUBSCRIBER scoping.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)  # normalized: lowercase
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="OWNER")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # TOTP secrets are encrypted with a key derived from WEB_SESSION_SECRET (app.security.crypto).
    totp_secret_enc: Mapped[str] = mapped_column(Text)
    totp_pending_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_last_step: Mapped[int] = mapped_column(BigInteger, default=0)  # replay protection
    locale: Mapped[str] = mapped_column(String(8), default="th")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Bangkok")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    totp_enrolled_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SessionRow(Base):
    """A server-side session. Only a keyed hash of the cookie token is stored."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())  # absolute limit
    step_up_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(256), default="")


class LoginThrottleRow(Base):
    """Failed-login counter per key (``user:<name>`` or ``ip:<address>``) with an exponential lockout."""

    __tablename__ = "login_throttle"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class EngineRow(Base):
    """A paired engine (PLAN §A32, TAA-708): its owner and its HMAC secrets, encrypted with a key derived from
    WEB_SESSION_SECRET (HMAC is symmetric, so the verifier needs the secret itself, not a hash).

    ``status`` ACTIVE or REVOKED (final; the secrets are erased). ``previous_secret_enc`` is accepted until
    ``previous_until`` or the first request signed with the new secret, whichever comes first."""

    __tablename__ = "engines"

    engine_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(64))
    secret_enc: Mapped[str] = mapped_column(Text)
    previous_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(8), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    rotated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class UserAdvisoryPrefsRow(Base):
    """A user's advisory preferences (PLAN §A26, §A29–§A31; TAA-809): watchlists, alert rules, theory
    selection, trading profile and entry plan, as one validated ``AdvisoryPreferences`` document. No row:
    the defaults."""

    __tablename__ = "user_advisory_prefs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    prefs: Mapped[dict[str, Any]] = mapped_column(JSONType)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
