"""The run-zone runner's state (eye/ZONE_LIVE.md L8): one row per live candidate, one row per request to the
broker (written before it is sent), the visit records of each closed H1 bar, the stop request and the runner's
status snapshot. Engine-local, not replicated."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base
from app.storage.types import UTCDateTime


class ZoneLiveSetupRow(Base):
    """A live candidate of an hour: its prices (unrounded and as sent), whether it was visited, what it
    filled,
    the break-even, the exit, its outcome and where its reservation ends."""

    __tablename__ = "zone_live_setup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_login: Mapped[int] = mapped_column(BigInteger, index=True)
    account_server: Mapped[str] = mapped_column(String(64))
    market: Mapped[str] = mapped_column(String(16))
    zone_set: Mapped[str] = mapped_column(String(32))
    set_version: Mapped[int] = mapped_column(Integer)
    hour_open: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    side: Mapped[str] = mapped_column(String(4))
    line: Mapped[float] = mapped_column(Float)
    step: Mapped[float] = mapped_column(Float)
    p1: Mapped[float] = mapped_column(Float)
    p2: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    tp: Mapped[float] = mapped_column(Float)
    p1_sent: Mapped[float] = mapped_column(Float)
    p2_sent: Mapped[float] = mapped_column(Float)
    sl_sent: Mapped[float] = mapped_column(Float)
    tp_sent: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(10), index=True)  # live | ended | dropped
    chosen: Mapped[bool] = mapped_column(Boolean, default=False)
    visited_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    touch_bar_open: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    fills_json: Mapped[str] = mapped_column(Text, default="[]")
    be_on: Mapped[bool] = mapped_column(Boolean, default=False)
    be_sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    be_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    exit_how: Mapped[str | None] = mapped_column(String(8), nullable=True)  # SL | TP | BE | close
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_broker_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(12), nullable=True)
    end_close_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ZoneLiveRequestRow(Base):
    """A request to the broker, written ``intent`` before ``order_send``, then ``sent`` or ``refused``.
    ``comment``
    (place requests only) is unique: the key that ties a broker order, deal or position to its row."""

    __tablename__ = "zone_live_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setup_id: Mapped[int] = mapped_column(Integer, index=True)
    account_login: Mapped[int] = mapped_column(BigInteger)
    account_server: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(8))  # place | remove | modify | close
    name: Mapped[str] = mapped_column(String(4), default="")  # P1 | P2 | ""
    comment: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    state: Mapped[str] = mapped_column(String(8), index=True)  # intent | sent | refused | unknown | moot
    order_state: Mapped[str] = mapped_column(
        String(10), default=""
    )  # place: open | filled | cancelled | expired | refused | unfollowed
    order_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    position_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deal_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    retcode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market: Mapped[bool] = mapped_column(Boolean, default=False)  # a place request sent as a market order
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    detail: Mapped[str] = mapped_column(Text, default="")
    intent_at: Mapped[datetime] = mapped_column(UTCDateTime())
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ZoneLiveVisitRow(Base):
    """A visit of a closed H1 bar (every line it visited), classified in the simulation's order."""

    __tablename__ = "zone_live_visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_login: Mapped[int] = mapped_column(BigInteger)
    account_server: Mapped[str] = mapped_column(String(64))
    hour_open: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    side: Mapped[str] = mapped_column(String(4))
    line: Mapped[float] = mapped_column(Float)
    classification: Mapped[str] = mapped_column(
        String(12)
    )  # momentum | busy | abnormal | trend | setup | undecided
    setup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(12), nullable=True)  # the setup's, once it ended
    agreed: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ZoneLiveStopRow(Base):
    """``zone stop``: a row the runner reads every cycle and acknowledges."""

    __tablename__ = "zone_live_stop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime())
    requested_by: Mapped[str] = mapped_column(String(64), default="")
    now: Mapped[bool] = mapped_column(Boolean, default=False)  # exit at once, positions left to their SL / TP
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class ZoneLiveStateRow(Base):
    """Key / value status of the runner (``zone status`` reads it): the pinned account, the hour, the
    strays."""

    __tablename__ = "zone_live_state"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
