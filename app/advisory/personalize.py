"""Personalization: market opportunity × user → that user's view and alert decision (PLAN §A30; TAA-6B5).

Pure library (no broker, no database session): the cloud worker wires it up in TAA-8A4, and the engine can use
it for the local owner. Steps, in order:

1. **Entitlements:** asset class and detector families the user's plan allows (OWNER: everything).
2. **Theory subset:** setup strength over the user's enabled families (conflict policy applied), the win
   probability with disabled detectors neutrally imputed, and the number of distinct supporting families.
3. **Decision:** the user's metric ≥ x for the most permissive alerting watchlist that holds the symbol,
   minimum supporting families, the trading profile's minimum RR, higher-timeframe alignment and EV floor
   (break-even + 2 pp), pattern-strategy toggles and the conflict policy's block.
4. **Windows:** the market session (if the user respects it) and the user's own time windows; the user's
   ``valid_until`` is the earlier of the market window and the user window end.
5. **Rate limits:** no duplicate alert, a per-symbol cooldown, alerts per hour, the profile's signals per day
   and the plan's alerts per day.
6. **Payload:** TH/EN push with ``tag = opportunity_id``, the top-3 contributions, entry/SL/TP, lot and risk,
   "valid until HH:MM" in the user's timezone and the app-badge count; a silent same-tag replacement when the
   opportunity expires or is invalidated (R26).

Every reason that blocks an alert is collected (not only the first), so the UI can explain "why not".
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from app.advisory.confidence import (
    Explanation,
    Query,
    WinProbability,
    is_player,
    random_baseline,
    subset_setup_strength,
)
from app.advisory.explanations import Language
from app.advisory.preferences import (
    AdvisoryPreferences,
    AlertMetric,
    ConflictPolicy,
    Watchlist,
    WatchlistKind,
    required_win_probability,
)
from app.advisory.statuses import OPEN, OpportunityStatus
from app.config import ConfluenceConfig
from app.core.clock import ensure_utc
from app.evidence.confluence import Relation
from app.evidence.framework import Family
from app.storage.models import OpportunityRow
from app.strategy.signal_models import Signal

STRONG_CONFLICT_QUALITY = 0.6  # BLOCK policy: a conflicting item at least this strong blocks the alert
EXPIRING_SHARE = 0.2  # badge EXPIRING when less than 20% of the window remains


class NoAlert(StrEnum):
    ENTITLEMENT_ASSET_CLASS = "ENTITLEMENT_ASSET_CLASS"
    PATTERN_STRATEGY_OFF = "PATTERN_STRATEGY_OFF"
    NOT_WATCHED = "NOT_WATCHED"
    LIST_ALERTS_OFF = "LIST_ALERTS_OFF"
    BELOW_THRESHOLD = "BELOW_THRESHOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FEW_SUPPORTING_FAMILIES = "FEW_SUPPORTING_FAMILIES"
    STRONG_CONFLICT = "STRONG_CONFLICT"
    RR_BELOW_PROFILE = "RR_BELOW_PROFILE"
    HTF_NOT_ALIGNED = "HTF_NOT_ALIGNED"
    EV_NOT_POSITIVE = "EV_NOT_POSITIVE"
    MARKET_CLOSED = "MARKET_CLOSED"
    OUTSIDE_USER_WINDOW = "OUTSIDE_USER_WINDOW"
    WINDOW_PASSED = "WINDOW_PASSED"
    DUPLICATE = "DUPLICATE"
    SYMBOL_COOLDOWN = "SYMBOL_COOLDOWN"
    HOURLY_LIMIT = "HOURLY_LIMIT"
    DAILY_LIMIT = "DAILY_LIMIT"


class Badge(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRING = "EXPIRING"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"
    FOLLOWED = "FOLLOWED"


# --- inputs -------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MarketOpportunity:
    """The market facts of one opportunity, as the engine stored and replicated them."""

    opportunity_id: str
    strategy: str
    symbol: str
    asset_class: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float | None
    rr: float | None
    signal: Signal
    features: Mapping[str, float]
    created_at: datetime
    valid_until: datetime | None
    valid_reason: str
    status: str
    lot: float | None
    risk_money: float | None
    reward_money: float | None
    currency: str
    equity: float
    cost_r: float = 0.0

    @classmethod
    def from_row(cls, row: OpportunityRow) -> MarketOpportunity:
        return cls(
            opportunity_id=row.opportunity_id,
            strategy=row.strategy,
            symbol=row.symbol,
            asset_class=row.asset_class,
            side=row.side,
            entry=row.entry,
            stop_loss=row.stop_loss,
            take_profit=row.take_profit,
            rr=row.rr,
            signal=Signal.from_dict(row.signal),
            features=dict(row.features),
            created_at=ensure_utc(row.created_at),
            valid_until=None if row.valid_until is None else ensure_utc(row.valid_until),
            valid_reason=row.valid_reason,
            status=row.status,
            lot=row.lot,
            risk_money=row.risk_money,
            reward_money=row.reward_money,
            currency=row.currency,
            equity=row.equity,
        )


@dataclass(frozen=True, slots=True)
class Entitlements:
    """What the user's plan allows (``None``: unlimited). OWNER is :meth:`owner`."""

    asset_classes: frozenset[str] | None = None
    families: frozenset[Family] | None = None
    alerts_per_day: int | None = None

    @classmethod
    def owner(cls) -> Entitlements:
        return cls()


@dataclass(frozen=True, slots=True)
class SentAlert:
    opportunity_id: str
    symbol: str
    sent_at: datetime


@dataclass(frozen=True, slots=True)
class UserContext:
    """Per-user state the worker loads: alert history, active count, ranking membership, ownership."""

    preferences: AdvisoryPreferences
    entitlements: Entitlements = field(default_factory=Entitlements.owner)
    sent: Sequence[SentAlert] = ()
    active_alerts: int = 0  # for the app-icon badge
    ranked_top: Sequence[str] = ()  # the suitability ranking, best first (AUTO_TOP_N lists)
    is_owner: bool = True  # owner: the engine's exact MT5 sizing; others need their account profile (8A)
    pattern_strategies: Collection[str] = ()  # names of pattern setups (their toggles apply)
    core_families: Collection[Family] = ()  # the strategy's checklist families (no double counting)


# --- outputs ------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Personalized:
    opportunity_id: str
    alert: bool
    reasons: tuple[NoAlert, ...]
    metric: AlertMetric
    metric_value: float | None
    threshold: float
    setup_strength: float
    explanation: Explanation
    supporting_families: tuple[str, ...]
    watchlist: str | None  # the list that alerts
    valid_until: datetime | None  # the user's window end (earliest of market and user windows)
    window_reason: str
    badge: Badge | None
    payload: dict[str, Any] | None


# --- steps --------------------------------------------------------------------------------------------------


def enabled_families(user: UserContext) -> frozenset[Family]:
    families = user.preferences.theories.enabled_families()
    allowed = user.entitlements.families
    return families if allowed is None else families & allowed


def enabled_detectors(
    opportunity: MarketOpportunity, families: Collection[Family], user: UserContext
) -> set[str]:
    """Detector ids among the opportunity's evidence that the user (and plan) enabled."""
    toggles = user.preferences.theories.detectors
    out = set()
    for e in opportunity.signal.evidence:
        ev = e.item.evidence
        on = toggles.get(ev.detector_id, ev.family in families)
        if on and (user.entitlements.families is None or ev.family in user.entitlements.families):
            out.add(ev.detector_id)
    return out


def subset_signal(signal: Signal, detectors: Collection[str], policy: ConflictPolicy) -> Signal:
    """Only the enabled evidence; with IGNORE, conflicting evidence is dropped too."""
    kept = tuple(
        e
        for e in signal.evidence
        if e.item.evidence.detector_id in detectors
        and not (policy is ConflictPolicy.IGNORE and e.relation is Relation.CONFLICTS)
    )
    return Signal.from_dict(signal.to_dict() | {"evidence": [e.to_dict() for e in kept]})


def supporting(signal: Signal) -> tuple[str, ...]:
    return tuple(
        sorted({e.item.evidence.family.value for e in signal.evidence if e.relation is Relation.SUPPORTS})
    )


def strong_conflict(signal: Signal) -> bool:
    return any(
        e.relation is Relation.CONFLICTS and e.item.evidence.quality >= STRONG_CONFLICT_QUALITY
        for e in signal.evidence
    )


def alerting_list(
    prefs: AdvisoryPreferences, symbol: str, ranked_top: Sequence[str]
) -> tuple[Watchlist | None, bool]:
    """The most permissive list that holds the symbol and alerts; and whether any list holds it at all."""
    holding: list[Watchlist] = []
    for w in prefs.watchlists:
        if w.kind is WatchlistKind.AUTO_TOP_N:
            if symbol in list(ranked_top)[: w.size or 0]:
                holding.append(w)
        elif symbol in w.symbols:
            holding.append(w)
    alerting = [w for w in holding if w.alerts]
    if not alerting:
        return None, bool(holding)
    return min(alerting, key=lambda w: (prefs.alerts.effective_threshold(w), w.name)), True


def badge(status: str, start: datetime, valid_until: datetime | None, now: datetime) -> Badge | None:
    if status == OpportunityStatus.INVALIDATED.value:
        return Badge.INVALIDATED
    if status == OpportunityStatus.FOLLOWED.value:
        return Badge.FOLLOWED
    if status == OpportunityStatus.EXPIRED.value or (valid_until is not None and now >= valid_until):
        return Badge.EXPIRED
    if status not in OPEN:
        return None
    if valid_until is not None:
        total = (valid_until - start).total_seconds()
        if total > 0 and (valid_until - now).total_seconds() < EXPIRING_SHARE * total:
            return Badge.EXPIRING
    return Badge.ACTIVE


def rate_limits(user: UserContext, opportunity: MarketOpportunity, now: datetime) -> list[NoAlert]:
    limits = user.preferences.alerts.rate_limits
    reasons = []
    if any(s.opportunity_id == opportunity.opportunity_id for s in user.sent):
        reasons.append(NoAlert.DUPLICATE)
    cooldown = timedelta(minutes=limits.symbol_cooldown_minutes)
    if any(s.symbol == opportunity.symbol and now - ensure_utc(s.sent_at) < cooldown for s in user.sent):
        reasons.append(NoAlert.SYMBOL_COOLDOWN)
    last_hour = sum(now - ensure_utc(s.sent_at) < timedelta(hours=1) for s in user.sent)
    if last_hour >= limits.max_alerts_per_hour:
        reasons.append(NoAlert.HOURLY_LIMIT)
    today = sum(now - ensure_utc(s.sent_at) < timedelta(days=1) for s in user.sent)
    daily = user.preferences.trading_profile.max_signals_per_day
    if user.entitlements.alerts_per_day is not None:
        daily = min(daily, user.entitlements.alerts_per_day)
    if today >= daily:
        reasons.append(NoAlert.DAILY_LIMIT)
    return reasons


def personalize(
    opportunity: MarketOpportunity,
    user: UserContext,
    model: WinProbability,
    confluence: ConfluenceConfig,
    *,
    now: datetime,
    market_open: bool,
) -> Personalized:
    prefs = user.preferences
    profile = prefs.trading_profile.resolve()
    theories = prefs.theories
    policy = profile.conflict_policy if "conflict_policy" in profile.custom else theories.conflict_policy
    reasons: list[NoAlert] = []

    # 1. entitlements
    allowed_classes = user.entitlements.asset_classes
    if allowed_classes is not None and opportunity.asset_class not in allowed_classes:
        reasons.append(NoAlert.ENTITLEMENT_ASSET_CLASS)
    if opportunity.strategy in user.pattern_strategies and not theories.pattern_strategies.get(
        opportunity.strategy, True
    ):
        reasons.append(NoAlert.PATTERN_STRATEGY_OFF)

    # 2. theory subset
    families = enabled_families(user)
    detectors = enabled_detectors(opportunity, families, user)
    signal = subset_signal(opportunity.signal, detectors, policy)
    strength = subset_setup_strength(signal, families, confluence, user.core_families)
    query = Query(
        opportunity.strategy,
        opportunity.symbol,
        opportunity.asset_class,
        strength,
        opportunity.rr or 0.0,
        opportunity.cost_r,
        {
            k: v
            for k, v in opportunity.features.items()
            if not is_player(k) or k.split(":", 2)[2] in detectors
        },
    )
    explanation = model.explain(query, enabled_detectors=detectors)
    families_support = supporting(signal)

    # 3. the decision
    metric = prefs.alerts.metric
    watchlist, watched = alerting_list(prefs, opportunity.symbol, user.ranked_top)
    if watchlist is None:
        reasons.append(NoAlert.LIST_ALERTS_OFF if watched else NoAlert.NOT_WATCHED)
    threshold = prefs.alerts.effective_threshold(watchlist)
    rr = opportunity.rr or 0.0
    if metric is AlertMetric.WIN_PROBABILITY:
        threshold = max(threshold, required_win_probability(profile, rr, opportunity.cost_r))
        value: float | None = None if explanation.estimate.insufficient else explanation.estimate.p
        if value is None:
            reasons.append(NoAlert.INSUFFICIENT_DATA)
    else:
        value = strength
    if value is not None and value < threshold:
        reasons.append(NoAlert.BELOW_THRESHOLD)
    if explanation.ev_r <= 0 and not explanation.estimate.insufficient:
        reasons.append(NoAlert.EV_NOT_POSITIVE)
    if len(families_support) < max(theories.min_supporting_families, profile.min_supporting_families):
        reasons.append(NoAlert.FEW_SUPPORTING_FAMILIES)
    if policy is ConflictPolicy.BLOCK and strong_conflict(signal):
        reasons.append(NoAlert.STRONG_CONFLICT)
    if rr < profile.min_rr:
        reasons.append(NoAlert.RR_BELOW_PROFILE)
    if profile.require_htf_alignment and not opportunity.features.get("ctx:htf_aligned"):
        reasons.append(NoAlert.HTF_NOT_ALIGNED)

    # 4. windows
    if prefs.alerts.respect_market_sessions and not market_open:
        reasons.append(NoAlert.MARKET_CLOSED)
    user_end = prefs.alerts.window_end(now)
    valid_until, window_reason = opportunity.valid_until, opportunity.valid_reason
    if user_end is None:
        reasons.append(NoAlert.OUTSIDE_USER_WINDOW)
    elif user_end.year < 9999 and (valid_until is None or user_end < valid_until):
        valid_until, window_reason = user_end, "USER_WINDOW"
    if opportunity.status not in OPEN or (valid_until is not None and now >= valid_until):
        reasons.append(NoAlert.WINDOW_PASSED)

    # 5. rate limits
    reasons += rate_limits(user, opportunity, now)

    alert = not reasons
    payload = None
    if alert:
        payload = notification(
            opportunity, user, explanation, strength, valid_until, language=prefs.alerts.language
        )
    return Personalized(
        opportunity_id=opportunity.opportunity_id,
        alert=alert,
        reasons=tuple(dict.fromkeys(reasons)),
        metric=metric,
        metric_value=value,
        threshold=threshold,
        setup_strength=strength,
        explanation=explanation,
        supporting_families=families_support,
        watchlist=None if watchlist is None else watchlist.name,
        valid_until=valid_until,
        window_reason=window_reason,
        badge=badge(opportunity.status, opportunity.created_at, valid_until, now),
        payload=payload,
    )


# --- notifications ------------------------------------------------------------------------------------------

FAMILY_NAMES: dict[str, dict[Language, str]] = {
    "FIBONACCI": {"en": "Fibonacci", "th": "ฟีโบนัชชี"},
    "LEVELS": {"en": "Support/resistance", "th": "แนวรับแนวต้าน"},
    "TREND": {"en": "Trend", "th": "แนวโน้ม"},
    "CHART_PATTERN": {"en": "Chart pattern", "th": "รูปแบบกราฟ"},
    "CANDLESTICK": {"en": "Candlestick", "th": "แท่งเทียน"},
    "MOMENTUM": {"en": "Momentum", "th": "โมเมนตัม"},
    "VOLATILITY_VOLUME": {"en": "Volatility/volume", "th": "ความผันผวน/วอลุ่ม"},
    "ICHIMOKU": {"en": "Ichimoku", "th": "อิชิโมกุ"},
    "SMART_MONEY": {"en": "Smart money", "th": "สมาร์ทมันนี่"},
    "HARMONIC": {"en": "Harmonic", "th": "ฮาร์โมนิก"},
    "ELLIOTT": {"en": "Elliott wave", "th": "คลื่นเอลเลียต"},
    "SESSIONS": {"en": "Session", "th": "ช่วงเวลาตลาด"},
}
SIDE_NAMES: dict[str, dict[Language, str]] = {
    "BUY": {"en": "BUY", "th": "ซื้อ"},
    "SELL": {"en": "SELL", "th": "ขาย"},
}
TEXT: dict[str, dict[Language, str]] = {
    "probability": {"en": "Win probability", "th": "โอกาสชนะ"},
    "insufficient": {"en": "insufficient data", "th": "ข้อมูลยังไม่พอ"},
    "strength": {"en": "Setup strength", "th": "ความแข็งแรงของเซ็ตอัป"},
    "reasons": {"en": "Reasons", "th": "เหตุผล"},
    "lot": {"en": "Lot", "th": "ล็อต"},
    "risk": {"en": "risk", "th": "ความเสี่ยง"},
    "valid": {"en": "valid until", "th": "ใช้ได้ถึง"},
    "thai_time": {"en": "Thai time", "th": "เวลาไทย"},
    "passed": {"en": "suitable time has passed", "th": "หมดเวลาที่เหมาะสมแล้ว"},
    "invalidated": {"en": "conditions no longer hold", "th": "เงื่อนไขไม่เป็นจริงแล้ว"},
    "followed": {"en": "you opened a position", "th": "คุณเปิดออเดอร์แล้ว"},
    "baseline": {"en": "random", "th": "สุ่ม"},
}
REASON_TEXT: dict[str, dict[Language, str]] = {
    "SIGNAL_LIFETIME": {"en": "signal lifetime ended", "th": "สัญญาณหมดอายุ"},
    "SESSION_END": {"en": "market session ended", "th": "ช่วงตลาดปิด"},
    "NEWS_BLACKOUT": {"en": "news blackout", "th": "ช่วงงดเทรดเพราะข่าว"},
    "USER_WINDOW": {"en": "your alert window ended", "th": "หมดช่วงเวลาแจ้งเตือนของคุณ"},
    "PRICE_DRIFT": {"en": "price moved away from the entry", "th": "ราคาวิ่งห่างจากจุดเข้า"},
    "SL_TOUCHED": {"en": "price touched the stop before entry", "th": "ราคาแตะจุดตัดขาดทุนก่อนเข้า"},
    "SPREAD_SPIKE": {"en": "spread stayed too wide", "th": "สเปรดกว้างเกินไปนาน"},
    "OPPOSITE_SIGNAL": {"en": "an opposite signal appeared", "th": "มีสัญญาณฝั่งตรงข้าม"},
}


def _reason_text(reason: str, language: Language) -> str:
    key = reason.split(":", 1)[0]
    return REASON_TEXT.get(key, {}).get(language, reason)


def _local_time(at: datetime, timezone: str, language: Language) -> str:
    text = ensure_utc(at).astimezone(ZoneInfo(timezone)).strftime("%H:%M")
    zone = TEXT["thai_time"][language] if timezone == "Asia/Bangkok" else timezone
    return f"{text} ({zone})"


def _money(value: float | None, currency: str) -> str:
    return "-" if value is None else f"{value:,.2f} {currency}"


def notification(
    opportunity: MarketOpportunity,
    user: UserContext,
    explanation: Explanation,
    strength: float,
    valid_until: datetime | None,
    *,
    language: Language,
) -> dict[str, Any]:
    t = {k: v[language] for k, v in TEXT.items()}
    est = explanation.estimate
    p = (
        t["insufficient"]
        if est.insufficient
        else f"{est.p:.0f}% ({t['baseline']} {random_baseline(opportunity.rr or 0):.0f}%)"
    )
    lines = [f"{t['probability']} {p} · {t['strength']} {strength:.0f}"]
    tp = "-" if opportunity.take_profit is None else f"{opportunity.take_profit:g}"
    lines.append(f"Entry {opportunity.entry:g} · SL {opportunity.stop_loss:g} · TP {tp}")
    if user.is_owner and opportunity.lot is not None:
        risk = _money(opportunity.risk_money, opportunity.currency)
        lines.append(f"{t['lot']} {opportunity.lot:g} · {t['risk']} {risk}")
    top = explanation.top(3)
    if top:
        parts = [f"{FAMILY_NAMES.get(c.family, {}).get(language, c.family)} {c.points:+.0f}%" for c in top]
        lines.append(f"{t['reasons']}: " + " · ".join(parts))
    if valid_until is not None:
        lines.append(f"{t['valid']} {_local_time(valid_until, user.preferences.alerts.timezone, language)}")
    return {
        "tag": opportunity.opportunity_id,
        "title": f"{opportunity.symbol} {SIDE_NAMES[opportunity.side][language]}",
        "body": "\n".join(lines),
        "silent": False,
        "renotify": True,
        "badge": user.active_alerts + 1,
        "data": {"opportunity_id": opportunity.opportunity_id, "symbol": opportunity.symbol},
    }


def replacement(
    opportunity: MarketOpportunity, user: UserContext, *, status: str, reason: str
) -> dict[str, Any] | None:
    """The silent same-tag update when an alerted opportunity ends (``None`` if the user turned it off)."""
    if not user.preferences.alerts.expiry_updates:
        return None
    language = user.preferences.alerts.language
    t = {k: v[language] for k, v in TEXT.items()}
    head = {
        OpportunityStatus.EXPIRED.value: t["passed"],
        OpportunityStatus.INVALIDATED.value: t["invalidated"],
        OpportunityStatus.FOLLOWED.value: t["followed"],
    }.get(status, t["passed"])
    body = head if status == OpportunityStatus.FOLLOWED.value else f"{head}: {_reason_text(reason, language)}"
    return {
        "tag": opportunity.opportunity_id,
        "title": f"{opportunity.symbol} {SIDE_NAMES[opportunity.side][language]}",
        "body": body,
        "silent": True,
        "renotify": False,
        "badge": max(0, user.active_alerts - 1),
        "data": {"opportunity_id": opportunity.opportunity_id, "status": status},
    }
