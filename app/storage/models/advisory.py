"""Advisory tables (PLAN §A25-A27): symbol catalog, suitability snapshots, market opportunities and shadow
trades."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.models.base import Base, EngineKeyed, EngineTagged
from app.storage.types import JSONType, UTCDateTime


class SymbolCatalogRow(EngineKeyed, Base):
    """Every symbol the broker offers, classified; refreshed daily from ``symbols_get``."""

    __tablename__ = "symbol_catalog"

    server: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    asset_class: Mapped[str] = mapped_column(String(16), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text, default="")
    path: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(String(128), default="")
    spec: Mapped[dict[str, Any]] = mapped_column(JSONType)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    refreshed_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    present: Mapped[bool] = mapped_column(Boolean, default=True)  # still offered by the broker


class SuitabilitySnapshotRow(EngineTagged, Base):
    """The ranking per symbol: one row per symbol and UTC hour, rewritten by every run within that hour.

    The rows of the newest ``computed_at`` are the latest ranking; older hours are the history (90-day
    retention).
    """

    __tablename__ = "suitability_snapshots"
    __table_args__ = (
        UniqueConstraint("engine_id", "server", "symbol", "hour", name="uq_suitability_symbol_hour"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32))
    hour: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    asset_class: Mapped[str] = mapped_column(String(16))
    rank: Mapped[int] = mapped_column(Integer)
    eligible: Mapped[bool] = mapped_column(Boolean)
    overall: Mapped[float] = mapped_column(Float)
    now_score: Mapped[float] = mapped_column(Float)
    failed_gates: Mapped[list[str]] = mapped_column(JSONType)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)  # scores, gates, metrics, session


class OpportunityRow(EngineKeyed, Base):
    """A market opportunity: one strategy's entry signal on one symbol and bar that passed the ADVISORY hard
    checks. Idempotent per strategy/symbol/bar/side (the signal's idempotency key). Never an alert by itself:
    the personalizer decides who is alerted (§A30)."""

    __tablename__ = "opportunities"

    opportunity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    server: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_class: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(8))
    side: Mapped[str] = mapped_column(String(4))
    bar_close_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    signal_expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    setup_strength: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    # lifecycle (TAA-6B4)
    status: Mapped[str] = mapped_column(String(16), index=True, default="CANDIDATE")
    status_reason: Mapped[str] = mapped_column(Text, default="")
    status_at: Mapped[datetime] = mapped_column(UTCDateTime())
    valid_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    valid_reason: Mapped[str] = mapped_column(String(64), default="")
    alerted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)  # first alert, if any
    # the owner account at signal time
    decision_id: Mapped[str] = mapped_column(String(64))
    warnings: Mapped[list[str]] = mapped_column(JSONType)
    lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    # market facts and model inputs
    session: Mapped[str] = mapped_column(String(24))
    regime: Mapped[str] = mapped_column(String(16))
    atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)  # the quote the decision used
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    quote_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    requirements_version: Mapped[str] = mapped_column(String(16))
    calibration_version: Mapped[str | None] = mapped_column(String(48), nullable=True)  # win probability used
    features: Mapped[dict[str, float]] = mapped_column(JSONType)
    signal: Mapped[dict[str, Any]] = mapped_column(JSONType)  # conditions, evidence, confluence


class ShadowTradeRow(EngineKeyed, Base):
    """A hypothetical trade of one opportunity in one variant (PLAN §A27): PLAN (fixed SL/TP) or MANAGED
    (break-even/trailing per ``position_management``). ``source`` is LIVE (engine) or REPLAY (history).

    Signal facts (strength, RR, features, session) are copied from the opportunity so outcomes stand on their
    own, also for replay trades that have no opportunity row. Money fields are None when the opportunity had
    no lot ("not tradable at your capital"); R results are always set once CLOSED.
    """

    __tablename__ = "shadow_trades"

    shadow_id: Mapped[str] = mapped_column(String(96), primary_key=True)  # <opportunity_id>:<variant>
    opportunity_id: Mapped[str] = mapped_column(String(80), index=True)
    variant: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(8), index=True)
    server: Mapped[str] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    asset_class: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(8))
    side: Mapped[str] = mapped_column(String(4))
    session: Mapped[str] = mapped_column(String(24))
    setup_strength: Mapped[float] = mapped_column(Float)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)  # planned, from the signal
    features: Mapped[dict[str, float]] = mapped_column(JSONType)
    atr: Mapped[float | None] = mapped_column(Float, nullable=True)  # entry TF at signal (MANAGED trailing)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    followed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(8), index=True)  # PENDING / OPEN / CLOSED / VOID / MISSED
    signal_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)  # the signal bar's close
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    # entry
    entry_at: Mapped[datetime] = mapped_column(
        UTCDateTime()
    )  # PENDING: the signal's entry time until the fill
    entry_price: Mapped[float] = mapped_column(Float)  # PENDING: the limit price
    # entry modes (TAA-L702): a limit not filled before this instant is MISSED; None for market entries
    entry_window_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    slippage_points: Mapped[float] = mapped_column(Float)
    initial_sl: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)  # current stop (MANAGED moves it)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_kind: Mapped[str] = mapped_column(String(8))  # how a stop-out is labelled: SL / BE / TRAIL
    deadline: Mapped[datetime] = mapped_column(UTCDateTime())  # time stop
    cursor: Mapped[datetime] = mapped_column(UTCDateTime())  # open time of the next M1 bar to resolve
    # sizing snapshot
    lot: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    # result
    mae: Mapped[float] = mapped_column(Float, default=0.0)  # price units, >= 0
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    exit_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)
    win: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # TP first
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)  # gross, price-based
    r_net: Mapped[float | None] = mapped_column(Float, nullable=True)  # after commission and swap
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float | None] = mapped_column(Float, nullable=True)  # <= 0
    swap: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    swap_days: Mapped[int] = mapped_column(Integer, default=0)
    flags: Mapped[list[str]] = mapped_column(JSONType)
    note: Mapped[str] = mapped_column(Text, default="")


class CalibrationTableRow(EngineKeyed, Base):
    """One versioned build of the win-probability bucket model (PLAN §A27 "Calibration").

    ``cells`` holds every hierarchy cell's LIVE and REPLAY counts; ``cv`` the walk-forward verdict between the
    bucket and evidence models; ``reliability`` predicted vs observed per probability bin (out of sample).
    """

    __tablename__ = "calibration_tables"

    version: Mapped[str] = mapped_column(String(48), primary_key=True)  # <UTC timestamp>-<content hash>
    server: Mapped[str] = mapped_column(String(64), index=True)
    built_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    variant: Mapped[str] = mapped_column(String(8))
    n_live: Mapped[int] = mapped_column(Integer)
    n_replay: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType)
    cells: Mapped[list[Any]] = mapped_column(JSONType)
    cv: Mapped[dict[str, Any]] = mapped_column(JSONType)
    uses_evidence: Mapped[bool] = mapped_column(Boolean)
    brier: Mapped[float | None] = mapped_column(Float, nullable=True)  # of the selected model, out of sample
    reliability: Mapped[list[Any]] = mapped_column(JSONType)


class EvidenceModelVersionRow(EngineTagged, Base):
    """One logistic evidence model of a calibration version: per strategy x asset class, or the pooled one."""

    __tablename__ = "evidence_model_versions"
    __table_args__ = (UniqueConstraint("engine_id", "source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # the engine's own id of this row (the cloud's ``id`` is its own; TAA-709)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    version: Mapped[str] = mapped_column(String(48), index=True)
    server: Mapped[str] = mapped_column(String(64))
    built_at: Mapped[datetime] = mapped_column(UTCDateTime())
    pooled: Mapped[bool] = mapped_column(Boolean)
    group_key: Mapped[list[str]] = mapped_column(JSONType)  # [strategy, asset_class]; [] when pooled
    names: Mapped[list[str]] = mapped_column(JSONType)
    coef: Mapped[list[float]] = mapped_column(JSONType)
    intercept: Mapped[float] = mapped_column(Float)
    means: Mapped[list[float]] = mapped_column(JSONType)
    active: Mapped[list[float]] = mapped_column(JSONType)  # share of training rows with the feature > 0
    l2: Mapped[float] = mapped_column(Float)
    n: Mapped[int] = mapped_column(Integer)


class ManualTradeLinkRow(EngineKeyed, Base):
    """Which signal a manual MT5 position followed (PLAN §A34, TAA-1006), matched by the engine when it
    first sees the position and never rewritten. ``confidence`` HIGH / LIKELY / UNMATCHED; the owner's
    override lives in the cloud (``manual_trade_overrides``)."""

    __tablename__ = "manual_trade_links"

    position_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ticket: Mapped[int] = mapped_column(BigInteger)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(4))
    volume: Mapped[float] = mapped_column(Float)
    price_open: Mapped[float] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    confidence: Mapped[str] = mapped_column(String(16))
    signal_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidates: Mapped[int] = mapped_column(Integer, default=0)
    rule_version: Mapped[str] = mapped_column(String(8))
    matched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    # the trade itself (TAA-1006 part 2): the stop when first seen (1R), then the close from the MT5 deals
    sl_initial: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(8), default="OPEN", server_default="OPEN")  # OPEN | CLOSED
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)  # profit + commission + swap + fee
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)  # (close − open) / initial risk
    # every later stop change as {"at": iso, "sl": price or None when removed} (TAA-L808); None: not recorded
    # (links made before the history was kept)
    stop_history: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)


class ManualTradeOverrideRow(EngineKeyed, Base):
    """The owner's correction of a manual-trade link (TAA-1006), cloud-only: ``CONFIRMED`` (the engine's link
    is right), ``OWN_IDEA`` (no signal) or ``SIGNAL`` (this other signal). Audited on the web chain."""

    __tablename__ = "manual_trade_overrides"

    position_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    choice: Mapped[str] = mapped_column(String(16))
    signal_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class AIAssessmentRow(EngineKeyed, Base):
    """One AI review of a proposed entry (TAA-1303), recorded whether it answered or not; replicated for the
    PWA's assessments page (agreement and cost, TAA-1304). ``effect``: VETOED / PASSED in veto mode,
    ADVISORY in advisory mode."""

    __tablename__ = "ai_assessments"

    assessment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    signal_key: Mapped[str] = mapped_column(String(80), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    strategy: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(4))
    bar_close_utc: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12), index=True)
    verdict: Mapped[str | None] = mapped_column(String(10), nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasons: Mapped[list[str]] = mapped_column(JSONType, default=list)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    effect: Mapped[str] = mapped_column(String(10))
    detail: Mapped[str] = mapped_column(Text, default="")


class AINoteRow(EngineKeyed, Base):
    """An AI note on advisory (TAA-1305, TAA-1304), written on the engine and replicated: an OPPORTUNITY
    opinion (verdict, confidence, reasons and a TH/EN narrative), a RANKING narrative of one snapshot or an
    ANALYTICS narrative of recent shadow results. One per kind and subject (``note_id`` = ``KIND:subject``),
    recorded whether it answered or not; descriptive only, it never changes a score, alert or trade."""

    __tablename__ = "ai_notes"

    note_id: Mapped[str] = mapped_column(String(140), primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    subject: Mapped[str] = mapped_column(
        String(120), index=True
    )  # the opportunity id, snapshot hour or period
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    status: Mapped[str] = mapped_column(String(12), index=True)
    verdict: Mapped[str | None] = mapped_column(String(10), nullable=True)  # OPPORTUNITY only
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasons: Mapped[list[str]] = mapped_column(JSONType, default=list)
    text_en: Mapped[str] = mapped_column(Text, default="")
    text_th: Mapped[str] = mapped_column(Text, default="")
    facts: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # the input, for audit
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
