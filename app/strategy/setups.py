"""Pattern-based setup generators (PLAN §A29 use 2, TAA-306). DEMONSTRATION ONLY: unproven, no profit claim.

Each setup turns one *trigger* detector's evidence on the entry timeframe into an explicit trade plan:

- **Trigger:** an active, directional evidence item of the setup's detectors, fired on the decision
  bar (``trigger_max_age_bars`` 0 by default), at or above ``min_quality``. Triggers in both directions on
  the same bar mean HOLD ``CONFLICT``. Among same-direction triggers the best quality wins.
- **Entry:** market, at the live ask/bid (or the bid-based close plus the spread for a BUY).
- **Stop** (``stop_mode``):
  - ``invalidation``: beyond the trigger's invalidation level (or the setup's own reference, e.g. the
    sweep extreme for SMC) by ``stop_buffer_atr`` × ATR;
  - ``atr``: ``sl_atr_multiple`` × ATR from the entry;
  - ``nearer``: whichever of the two is closer to the entry;
  - ``zone``: beyond the nearest demand (BUY) / supply (SELL) zone behind the entry on the
    ``zone_stop_frame`` market map, by ``stop_buffer_atr`` x ATR (no such zone: the ATR stop).

  An invalidation on the wrong side of the entry falls back to the ATR stop. The spread is added as a
  buffer in every mode.
- **Target** (``target_mode``):
  - ``measured``: the nearest of the trigger's targets beyond the entry that gives at least ``min_rr``
    (else the farthest, which then fails the RR check);
  - ``level``: the nearest opposing S/R zone of the context, under the same rule;
  - ``rr``: ``rr_target`` × the risk. Measured or level modes without a usable price fall back to it;
  - ``zone``: the near edge of the nearest opposing zone (supply for a BUY) on the ``zone_scope`` maps.
- **Triple screen and demand/supply (owner, 2026-10-13; SETUP_REVIEW §16, CONFLUENCE_DIRECTION §3.1):** every
  setup may gate on the higher-timeframe market map (``MarketContext.htf``, ``timeframes.context``). The first
  screen ``screen_h4`` (the tide) and the second ``screen_h1`` (the wave) read the map's state relative to the
  trade (with / against / range / transition); the setup's trigger is the third screen. ``zone_gate:
  clear_to_target`` refuses a plan whose path to the target meets an opposing zone (one starting ahead of the
  entry).
  A gate whose map is missing holds (fail closed). All are off by default.
- **Screen timeframes** (owner, 2026-10-14): ``screen_tide_tf`` / ``screen_wave_tf`` (H4 / H1) follow
  the entry timeframe (Elder: each screen about 4-6 times the next); they must be in ``timeframes.context``.
- **Counter-trend fade** (``fade_counter_trend``, owner 2026-10-14, SETUP_REVIEW §16): a trigger running
  against both the H4 and the H1 trend is a trap more often than a move; it is traded the other way, with the
  trend, at the plan's prices swapped (the stop at the plan's target, the target at the plan's stop; the entry
  on the other side of the spread). Every rule except the screens still applies to the plan; the entry carries
  ``FADE`` so the decision engine applies ``risk.fade`` (its R:R is the plan's inverse). Off by default.
- **Regime fit** (owner, 2026-10-14: a setup trades less, not never, in a phase that does not suit it):
  ``quiet_h4_atr_pct`` marks a quiet phase (the H4 map's ATR percentile below it; a missing map counts as
  quiet: fail closed), in which ``quiet_rule`` adds a stricter condition: ``m15_not_range`` refuses triggers
  while the entry timeframe's own market-map state is RANGE (a break out of a narrow M15 box). Off by default.
- **Trend-entry window** (``trend_entry_window_ny``, "HH:MM-HH:MM" New York time, DST-aware; §16):
  entries in the trigger's own direction only inside it (breaks fail less at the New York session, §14);
  counter-trend fades are not limited by it. Off by default.
- **Trend entries** (§16; entries in the trigger's direction, not fades): ``trend_stop_scale`` widens their
  stop and target by the same factor (the same R multiple; the stop out of the hunted noise band);
  ``trend_structure`` needs the swing structure (HH+HL for a BUY, LH+LL for a SELL) on the entry timeframe
  (``entry``) or on it and the higher one (``entry_and_higher``).
  ``trend_entries: false`` keeps only the fades (wait for a counter-trend break, then trade with the trend).
- **Broadening** (``skip_broadening: higher``, owner 2026-10-14: "gold often makes an inverted triangle"): no
  entry, trend or fade, while the higher timeframe's last swings are a higher high and a lower low (false
  breaks on both sides before the real run).
- **Scalping on small timeframes** (owner, 2026-10-14): ``atr_bars`` measures the stop/target ATR over that
  many entry bars instead of the frame's ATR(14) (M1: 60 bars = one hour, the scale the behaviour was
  measured on); ``skip_window_ny`` ("HH:MM-HH:MM" New York time) takes no entry inside it (gold scalps lose
  around the US releases, 08:00-12:00 New York). Both off by default.
- **Chart read gates** (TAA-L813, docs/CHART_READ.md §7; each off by default, chosen per setup only after
  its backtests hold). They read the chart read of ``structure_tf`` (a context timeframe; the MT5 ZigZag
  swings) relative to the trade actually taken (the fade's side for a fade), at the plan's entry; a missing
  read holds (fail closed):
  - ``screen_source: swings``: the two screens (and the fade's "against both") read the swing structure
    instead of the map state; CONTRACTING / BROADENING / FLAT count as a range;
  - ``structure_gate`` (``not_against`` / ``with``): the swing structure must not oppose (must follow) the
    trade; a mixed phase is not against;
  - ``mixed_rule`` in a CONTRACTING / BROADENING / FLAT phase: ``any`` trades as usual, ``surest`` needs the
    next-higher context timeframe's swing trend with the trade **and** the entry at a supportive or flipped
    level, ``skip`` takes nothing (the system principle: ``surest`` before ``skip``);
  - ``level_gate: at_level``: the entry within the read's tolerance of a supportive or flipped level;
  - ``room_min_r``: at least this many R to the nearest opposing level of the read;
  - ``structure_stop``: the trade's stop beyond the last swing pivot behind the entry (the low for a BUY) by
    ``stop_buffer_atr`` × ATR, at most ``max_sl_atr`` ATR; the target keeps its R multiple. A separate switch
    rather than a ``stop_mode`` because a fade mirrors the trigger plan, whose stop becomes the fade's target.
- **Rules:** the shared checks of :mod:`app.strategy.rules` (SL ≤ ``max_sl_atr`` ATR, RR ≥ ``min_rr``,
  spread ≤ ``max_spread_to_sl`` of the SL, session window, Friday cutoff), plus each setup's confirmations.

Score (ranking only, **not a probability**): ``setup_strength × (0.5 + 0.5 × trigger quality)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import ClassVar, Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pydantic import Field, field_validator

from app.core.enums import Action, Timeframe, Trend
from app.evidence.framework import ActiveEvidence, Direction, Evidence, Family
from app.indicators.chart_read import MIXED, ChartRead, Structure
from app.indicators.market_map import MapParams, MapState, MapZone, TimeframeMap, ZoneKind, state_frame
from app.indicators.price_action import SwingKind, market_structure
from app.strategy.base_strategy import BaseStrategy
from app.strategy.rules import (
    EntryRuleParams,
    entry_price,
    explain,
    failed_reasons,
    hhmm,
    known,
    risk_conditions,
    spread_price,
    time_conditions,
)
from app.strategy.signal_models import Condition, MarketContext, ReasonCode, Signal, StrategyContext

NEW_YORK = ZoneInfo("America/New_York")
StopMode = Literal["invalidation", "atr", "nearer", "zone"]
TargetMode = Literal["measured", "level", "rr", "zone"]
ScreenFrame = Literal["M5", "M15", "M30", "H1", "H4", "D1"]
ScreenGate = Literal["any", "with", "with_or_range", "not_against", "against", "against_or_range"]
ZoneGate = Literal["none", "clear_to_target"]
ZoneScope = Literal["H4", "H4_D1"]
ZoneStopFrame = Literal["H1", "H4"]
QuietRule = Literal["none", "m15_not_range"]
TrendStructure = Literal["any", "entry", "entry_and_higher"]
SkipBroadening = Literal["none", "higher"]
ScreenSource = Literal["map", "swings"]
StructureGate = Literal["off", "not_against", "with"]
MixedRule = Literal["any", "surest", "skip"]
LevelGate = Literal["off", "at_level"]

# the trade-relative map states each screen gate lets through
_SCREEN_OK: dict[str, frozenset[str]] = {
    "with": frozenset({"WITH"}),
    "with_or_range": frozenset({"WITH", "RANGE"}),
    "not_against": frozenset({"WITH", "RANGE", "TRANSITION"}),
    "against": frozenset({"AGAINST"}),
    "against_or_range": frozenset({"AGAINST", "RANGE"}),
}


class SetupParams(EntryRuleParams):
    trigger_max_age_bars: int = Field(default=0, ge=0, le=20, description="0: fired on the decision bar")
    min_quality: float = Field(default=0.0, ge=0, le=1)
    stop_mode: StopMode = "invalidation"
    target_mode: TargetMode = "measured"
    stop_buffer_atr: float = Field(default=0.1, ge=0, le=2)
    sl_atr_multiple: float = Field(default=1.5, gt=0, le=10)
    require_htf_alignment: bool = False
    confirm_window_bars: int = Field(default=30, ge=1, le=200)
    max_rr: float | None = Field(
        default=None, gt=0, le=20, description="refuse plans whose target is farther than this many R"
    )
    screen_h4: ScreenGate = "any"  # the first screen (the tide) on ``screen_tide_tf``
    screen_h1: ScreenGate = "any"  # the second screen (the wave) on ``screen_wave_tf``
    screen_tide_tf: ScreenFrame = "H4"  # Elder: each screen ~4-6x the next (M15 -> H1 -> H4; M1 -> M5 -> M30)
    screen_wave_tf: ScreenFrame = "H1"
    zone_gate: ZoneGate = "none"
    zone_scope: ZoneScope = "H4_D1"
    zone_stop_frame: ZoneStopFrame = "H1"
    fade_counter_trend: bool = False
    quiet_h4_atr_pct: float | None = Field(
        default=None, gt=0, lt=100, description="H4 ATR percentile below which the phase counts as quiet"
    )
    quiet_rule: QuietRule = "none"
    trend_stop_scale: float = Field(default=1.0, ge=1.0, le=4.0)
    trend_entries: bool = True  # False: only fades (owner, 2026-10-14: wait, then trade with the big trend)
    trend_structure: TrendStructure = "any"
    skip_broadening: SkipBroadening = "none"
    atr_bars: int | None = Field(default=None, ge=2, le=1000)
    skip_window_ny: str | None = Field(default=None, description="HH:MM-HH:MM New York time with no entries")
    trend_entry_window_ny: str | None = Field(
        default=None, description="HH:MM-HH:MM New York time for entries in the trigger's direction"
    )
    screen_source: ScreenSource = "map"
    structure_tf: ScreenFrame = "H1"  # the chart read the gates below use (a context timeframe)
    structure_gate: StructureGate = "off"
    mixed_rule: MixedRule = "any"
    level_gate: LevelGate = "off"
    room_min_r: float | None = Field(default=None, gt=0, le=10, description="R to the nearest opposing level")
    structure_stop: bool = False

    @field_validator("trend_entry_window_ny", "skip_window_ny")
    @classmethod
    def _check_window(cls, value: str | None) -> str | None:
        if value is not None:
            start, sep, end = value.partition("-")
            if not sep or hhmm(start) >= hhmm(end):
                raise ValueError("a New York window must be HH:MM-HH:MM with start before end")
        return value


def variant(ev: Evidence) -> str:
    """The variant suffix of an evidence record (``evidence.<detector>.<variant>``), or ``""``."""
    prefix = f"evidence.{ev.detector_id}"
    return ev.i18n_key[len(prefix) + 1 :] if ev.i18n_key.startswith(prefix + ".") else ""


def _sign(direction: Direction) -> int:
    return direction.sign


class EvidenceSetup(BaseStrategy):
    """A strategy driven by one family of trigger detectors. Subclasses set the class attributes."""

    triggers: ClassVar[frozenset[str]]
    confirming: ClassVar[frozenset[str]] = frozenset()  # other detectors the confirmations read
    setup_code: ClassVar[str]  # the entry's reason code, e.g. NECKLINE_BREAK
    Params = SetupParams
    demo_only = True

    def required_detectors(self) -> frozenset[str]:
        return self.triggers | self.confirming

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return ()

    def warmup_bars(self) -> int:
        return 120  # zigzag pivots and the evidence detectors' own windows

    # hooks ---------------------------------------------------------------------------------------------

    def accepts(self, ev: Evidence) -> bool:
        """Extra trigger filter (variants, primary counts, ...)."""
        return True

    def confirmations(
        self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence], ctx: StrategyContext
    ) -> list[Condition]:
        return []

    def stop_reference(self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence]) -> float | None:
        return trigger.evidence.invalidation

    # evaluation ----------------------------------------------------------------------------------------

    def evaluate(self, ctx: StrategyContext) -> Signal:
        p: SetupParams = self.params
        market = ctx.market
        snapshot = ctx.evidence.get(market.entry_timeframe)
        if snapshot is None:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, explanation="evidence was not computed")
        items = snapshot.items
        found = [
            a
            for a in items
            if a.evidence.detector_id in self.triggers
            and a.age_bars <= p.trigger_max_age_bars
            and a.evidence.direction is not Direction.NEUTRAL
            and a.evidence.quality >= p.min_quality
            and self.accepts(a.evidence)
        ]
        if not found:
            cond = Condition("trigger", False, 2.0, f"no {self.setup_code} trigger")
            return self.hold(ctx, ReasonCode.NO_SETUP, conditions=[cond], explanation=explain([cond]))
        if len({a.evidence.direction for a in found}) > 1:
            cond = Condition("trigger", False, 2.0, "triggers in both directions")
            return self.hold(ctx, ReasonCode.CONFLICT, conditions=[cond], explanation=explain([cond]))
        trigger = min(found, key=lambda a: (-a.evidence.quality, a.age_bars, a.evidence.detector_id))
        ev = trigger.evidence
        buy = ev.direction is Direction.BULL
        sign = _sign(ev.direction)
        conds = [Condition("trigger", True, 2.0, f"{ev.name} (quality {ev.quality:.2f})")]
        if p.require_htf_alignment:
            opposed = Trend.BEARISH if buy else Trend.BULLISH
            h = market.higher
            conds.append(
                Condition(
                    "htf_not_opposed", h.trend is not opposed, 1.0, f"{h.timeframe.value} {h.trend.value}"
                )
            )
        conds += self.confirmations(trigger, items, ctx)
        conds += _screens(market, p, buy)
        conds += _quiet_phase(ctx, p)

        frame = ctx.frame(market.entry_timeframe)
        if frame.empty:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds)
        last = frame.iloc[-1]
        close, atr_v = float(last["close"]), float(last["atr"])
        if p.atr_bars is not None:
            atr_v = _atr_over(frame, p.atr_bars)
        costs = spread_price(ctx, last)
        if not known(close, atr_v) or atr_v <= 0 or costs is None:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds, explanation=explain(conds))
        spread_points, spread = costs
        entry = entry_price(market, close, spread, buy)
        stop, stop_note = self._stop(trigger, items, market, entry, atr_v, sign)
        stop -= sign * spread
        risk = abs(entry - stop)
        take_profit, target_note = self._target(ev, market, entry, risk, sign)
        fade = p.fade_counter_trend and _against_both(market, p, buy)
        if not fade and p.trend_stop_scale != 1.0:
            # a trend entry's stop out of the noise band, the target at the same R multiple (SETUP_REVIEW §16)
            stop = entry - sign * risk * p.trend_stop_scale
            take_profit = entry + (take_profit - entry) * p.trend_stop_scale
            risk *= p.trend_stop_scale
            stop_note += f", x{p.trend_stop_scale:g}"
        if p.structure_stop:
            stop, take_profit, risk, stop_note = self._structure_stop(
                market, entry, stop, take_profit, atr_v, spread, -sign if fade else sign, fade, stop_note
            )
        conds += risk_conditions(
            entry=entry,
            stop=stop,
            take_profit=take_profit,
            atr=atr_v,
            spread=spread,
            spread_points=spread_points,
            p=p,
        )
        conds += time_conditions(market.decision_time_utc, p)
        if p.max_rr is not None and risk > 0:
            rr = abs(take_profit - entry) / risk
            conds.append(Condition("rr_not_too_far", rr <= p.max_rr, 1.0, f"RR {rr:.2f} vs max {p.max_rr:g}"))
        if p.zone_gate == "clear_to_target":
            conds.append(_zone_clear(market, p, entry, take_profit, sign))
        conds.append(Condition("plan", True, 1.0, f"stop {stop_note}; target {target_note}"))

        if p.skip_broadening == "higher":
            conds.append(_not_broadening(ctx))
        if p.skip_window_ny is not None:
            inside = _ny_window(market.decision_time_utc, p.skip_window_ny)
            conds.append(Condition("outside_skip_window", not inside.passed, 1.0, inside.detail))
        if fade:
            conds = [c for c in conds if c.name not in ("screen_h4", "screen_h1")]
            conds.append(
                Condition("counter_trend_fade", True, 1.0, "against H4 and H1: traded with the trend")
            )
        else:
            if not p.trend_entries:
                conds.append(
                    Condition("trend_entry", False, 1.0, "entries in the trigger's direction are off")
                )
            if p.trend_entry_window_ny is not None:
                conds.append(_ny_window(market.decision_time_utc, p.trend_entry_window_ny))
            if p.trend_structure != "any":
                frames = [market.entry_timeframe]
                if p.trend_structure == "entry_and_higher":
                    frames.append(market.higher_timeframe)
                conds += [_structure_with(ctx, tf, buy) for tf in frames]
        trade_buy = buy is not fade
        trade_risk = abs(take_profit - entry) if fade else risk
        conds += _read_gates(market, p, trade_buy, entry, trade_risk)
        if not all(c.passed for c in conds):
            reasons = failed_reasons(conds, {"htf_not_opposed": ReasonCode.CONFLICT})
            return self.hold(ctx, *reasons, conditions=conds, explanation=explain(conds))
        total = sum(c.weight for c in conds)
        score = 100.0 * sum(c.weight for c in conds if c.passed) / total * (0.5 + 0.5 * ev.quality)
        if fade:
            # the plan the other way: its target becomes the stop, its stop the target (owner, 2026-10-14)
            quoted = market.bid if buy else market.ask
            fade_entry = (
                quoted if quoted is not None and market.bid is not None and market.ask is not None else entry
            )
            return self.entry(
                ctx,
                Action.SELL if buy else Action.BUY,
                entry_price=fade_entry,
                stop_loss=take_profit,
                take_profit=stop,
                conditions=conds,
                score=score,
                reasons=(self.setup_code, ReasonCode.FADE),
                explanation=f"fade: {explain(conds)}",
            )
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=entry,
            stop_loss=stop,
            take_profit=take_profit,
            conditions=conds,
            score=score,
            reasons=(self.setup_code,),
            explanation=explain(conds),
        )

    def _stop(
        self,
        trigger: ActiveEvidence,
        items: Sequence[ActiveEvidence],
        market: MarketContext,
        entry: float,
        atr_v: float,
        sign: int,
    ) -> tuple[float, str]:
        p: SetupParams = self.params
        atr_stop = entry - sign * p.sl_atr_multiple * atr_v
        if p.stop_mode == "zone":
            own = ZoneKind.DEMAND if sign > 0 else ZoneKind.SUPPLY
            behind = [
                edge
                for z in _zones(market, (p.zone_stop_frame,), own)
                if ((edge := z.low if sign > 0 else z.high) - entry) * sign < 0
            ]
            if not behind:
                return atr_stop, f"{p.sl_atr_multiple:g} ATR (no {p.zone_stop_frame} zone behind the entry)"
            edge = max(behind) if sign > 0 else min(behind)
            return edge - sign * p.stop_buffer_atr * atr_v, f"beyond the {p.zone_stop_frame} zone {edge:.5g}"
        ref = self.stop_reference(trigger, items)
        usable = ref is not None and (entry - ref) * sign > 0
        if p.stop_mode == "atr" or not usable or ref is None:
            note = f"{p.sl_atr_multiple:g} ATR" + (
                "" if p.stop_mode == "atr" else " (no usable invalidation)"
            )
            return atr_stop, note
        inv_stop = ref - sign * p.stop_buffer_atr * atr_v
        if p.stop_mode == "nearer" and (atr_stop - inv_stop) * sign > 0:
            return atr_stop, f"{p.sl_atr_multiple:g} ATR (nearer than the invalidation {ref:.5g})"
        return inv_stop, f"beyond the invalidation {ref:.5g}"

    def _structure_stop(
        self,
        market: MarketContext,
        entry: float,
        stop: float,
        take_profit: float,
        atr_v: float,
        spread: float,
        side: int,
        fade: bool,
        note: str,
    ) -> tuple[float, float, float, str]:
        """``structure_stop``: the stop of the trade taken (*side*) beyond the last swing pivot behind the
        entry, the target at the same R multiple. A fade's trade stop is the plan's target (and its target the
        plan's stop), so for a fade the plan's two prices move. Returns the plan's (stop, take_profit, risk,
        note)."""
        p: SetupParams = self.params
        read = _read(market, p.structure_tf)
        kind = SwingKind.LOW if side > 0 else SwingKind.HIGH
        pivots = () if read is None else read.pivots
        pivot = next(
            (q.price for q in reversed(pivots) if q.kind is kind and (entry - q.price) * side > 0), None
        )
        if pivot is None:
            return (
                stop,
                take_profit,
                abs(entry - stop),
                note + f" (no {p.structure_tf} swing behind the entry)",
            )
        dist = min((entry - pivot) * side + p.stop_buffer_atr * atr_v + spread, p.max_sl_atr * atr_v)
        trade_stop = entry - side * dist
        where = f"the {p.structure_tf} swing {pivot:.5g}"
        if fade:  # the trade's stop is the plan's target; the trade's target (the plan's stop) keeps its R
            old = abs(take_profit - entry)
            stop = entry + (stop - entry) * (dist / old) if old > 0 else stop
            return stop, trade_stop, abs(entry - stop), note + f"; the fade's stop beyond {where}"
        old = abs(entry - stop)
        take_profit = entry + (take_profit - entry) * (dist / old) if old > 0 else take_profit
        return trade_stop, take_profit, dist, f"beyond {where}"

    def _target(
        self, ev: Evidence, market: MarketContext, entry: float, risk: float, sign: int
    ) -> tuple[float, str]:
        p: SetupParams = self.params
        rr_tp = entry + sign * p.rr_target * risk
        if p.target_mode == "rr" or risk <= 0:
            return rr_tp, f"{p.rr_target:g}R"
        if p.target_mode == "zone":
            ahead_zones = sorted(
                (e for e in _opposing_edges(market, p, sign) if (e - entry) * sign > 0),
                key=lambda e: abs(e - entry),
            )
            if not ahead_zones:
                return rr_tp, f"{p.rr_target:g}R (no opposing zone ahead)"
            return ahead_zones[0], f"opposing zone {ahead_zones[0]:.5g}"
        if p.target_mode == "measured":
            prices, label = list(ev.targets), "measured target"
        else:
            prices = list(market.resistance_levels if sign > 0 else market.support_levels)
            label = "next opposing level"
        ahead = sorted((t for t in prices if (t - entry) * sign > 0), key=lambda t: abs(t - entry))
        if not ahead:
            return rr_tp, f"{p.rr_target:g}R (no {label} ahead)"
        for t in ahead:
            if abs(t - entry) / risk >= p.min_rr:
                return t, f"{label} {t:.5g}"
        return ahead[-1], f"{label} {ahead[-1]:.5g}"


def _relative(state: MapState | None, buy: bool) -> str:
    """A map state relative to the trade: WITH, AGAINST, RANGE, TRANSITION, or NONE (unknown / no map)."""
    if state is None or state is MapState.UNKNOWN:
        return "NONE"
    if state in (MapState.UP, MapState.DOWN):
        return "WITH" if (state is MapState.UP) == buy else "AGAINST"
    return state.value


def _swings(ctx: StrategyContext, tf: Timeframe) -> tuple[str | None, str | None] | None:
    """The last confirmed swing labels (HH/LH/EQH, HL/LL/EQL) of *tf*; None without a frame."""
    frame = ctx.frames.get(tf)
    if frame is None or frame.empty or not {"high", "low"} <= set(frame.columns):
        return None
    ms = market_structure(frame["high"].astype(float), frame["low"].astype(float), 3)
    high, low = ms["last_high_label"].iloc[-1], ms["last_low_label"].iloc[-1]
    return (None if high is None else str(high)), (None if low is None else str(low))


def _structure_with(ctx: StrategyContext, tf: Timeframe, buy: bool) -> Condition:
    """The swing structure of *tf* trends the trade's way: HH+HL for a BUY, LH+LL for a SELL."""
    labels = _swings(ctx, tf)
    if labels is None:
        return Condition(f"structure_{tf.value.lower()}", False, 1.0, f"no {tf.value} frame")
    want = ("HH", "HL") if buy else ("LH", "LL")
    return Condition(
        f"structure_{tf.value.lower()}", labels == want, 1.0, f"{tf.value} {labels[0]}+{labels[1]}"
    )


def _not_broadening(ctx: StrategyContext) -> Condition:
    """The higher timeframe is not a broadening swing (HH + LL: false breaks on both sides)."""
    tf = ctx.market.higher_timeframe
    labels = _swings(ctx, tf)
    if labels is None:
        return Condition("not_broadening", False, 1.0, f"no {tf.value} frame")
    return Condition("not_broadening", labels != ("HH", "LL"), 1.0, f"{tf.value} {labels[0]}+{labels[1]}")


def _atr_over(frame: pd.DataFrame, bars: int) -> float:
    """Mean true range of the last *bars* closed bars (NaN with fewer bars or no high/low)."""
    if len(frame) < bars + 1 or not {"high", "low", "close"} <= set(frame.columns):
        return float("nan")
    tail = frame.iloc[-(bars + 1) :]
    high, low = tail["high"].to_numpy(dtype=float), tail["low"].to_numpy(dtype=float)
    prev = tail["close"].to_numpy(dtype=float)[:-1]
    tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - prev), np.abs(low[1:] - prev)))
    return float(tr.mean())


def _ny_window(at: datetime, window: str) -> Condition:
    """The decision bar's close inside *window* (HH:MM-HH:MM, New York local time, DST-aware)."""
    start, _, end = window.partition("-")
    local = at.astimezone(NEW_YORK).time()
    inside = hhmm(start) <= local < hhmm(end)
    return Condition("trend_entry_window", inside, 1.0, f"{local:%H:%M} New York vs {window}")


def _swing_relative(read: ChartRead | None, buy: bool) -> str:
    """A chart read's structure relative to the trade: WITH, AGAINST, RANGE (a mixed phase) or NONE."""
    if read is None or read.structure is Structure.NONE:
        return "NONE"
    if read.structure in MIXED:
        return "RANGE"
    return "WITH" if (read.structure is Structure.UP) == buy else "AGAINST"


def _screen_relative(m: TimeframeMap | None, p: SetupParams, buy: bool) -> str:
    if m is None:
        return "NONE"
    return _swing_relative(m.read, buy) if p.screen_source == "swings" else _relative(m.state, buy)


def _read(market: MarketContext, tf: str) -> ChartRead | None:
    m = None if market.htf is None else market.htf.frames.get(tf)
    return None if m is None else m.read


def _against_both(market: MarketContext, p: SetupParams, buy: bool) -> bool:
    """The trigger runs against both the tide and the wave trend (H4/H1 by default; a missing map: no)."""
    if market.htf is None:
        return False
    frames = [market.htf.frames.get(f) for f in (p.screen_tide_tf, p.screen_wave_tf)]
    return all(m is not None and _screen_relative(m, p, buy) == "AGAINST" for m in frames)


def _screens(market: MarketContext, p: SetupParams, buy: bool) -> list[Condition]:
    """Elder's first (the tide) and second (the wave) screens on the market map (H4 and H1 by default)."""
    out = []
    for name, frame, gate in (
        ("screen_h4", p.screen_tide_tf, p.screen_h4),
        ("screen_h1", p.screen_wave_tf, p.screen_h1),
    ):
        if gate == "any":
            continue
        m = None if market.htf is None else market.htf.frames.get(frame)
        rel = _screen_relative(m, p, buy)
        src = " swings" if p.screen_source == "swings" else ""
        out.append(
            Condition(name, rel in _SCREEN_OK[gate], 1.0, f"{frame}{src} {rel.lower()} (needs {gate})")
        )
    return out


def _at_level(read: ChartRead, buy: bool, entry: float) -> tuple[bool, str]:
    """The entry within the read's tolerance of a level that supports the trade (a support or a flipped level
    below for a BUY, a resistance or a flipped level above for a SELL)."""
    tol = read.tol_atr * read.atr
    hits = [lv for lv in read.levels if lv.above is not buy and abs(entry - lv.price) <= tol]
    if not hits:
        return False, f"{read.timeframe} no supportive level within {read.tol_atr:g} ATR"
    lv = min(hits, key=lambda x: abs(entry - x.price))
    return True, f"{read.timeframe} {lv.role.value.lower()} {lv.price:.5g}"


def _higher_read(market: MarketContext, tf: str) -> ChartRead | None:
    """The chart read of the next-higher context timeframe than *tf*."""
    if market.htf is None:
        return None
    base = Timeframe(tf).seconds
    above = sorted(
        (Timeframe(k) for k in market.htf.frames if Timeframe(k).seconds > base), key=lambda t: t.seconds
    )
    return None if not above else _read(market, above[0].value)


def _read_gates(
    market: MarketContext, p: SetupParams, buy: bool, entry: float, risk: float
) -> list[Condition]:
    """The chart read gates of the trade actually taken (*buy* is its side; CHART_READ.md §7)."""
    on = (
        p.structure_gate != "off"
        or p.mixed_rule != "any"
        or p.level_gate != "off"
        or p.room_min_r is not None
    )
    if not on:
        return []
    tf = p.structure_tf
    read = _read(market, tf)
    if read is None:
        return [Condition("chart_read", False, 1.0, f"no {tf} chart read")]
    out: list[Condition] = []
    rel = _swing_relative(read, buy)
    if p.structure_gate != "off":
        ok = rel == "WITH" or (p.structure_gate == "not_against" and rel == "RANGE")
        detail = f"{tf} {read.structure.value} {rel.lower()} (needs {p.structure_gate})"
        out.append(Condition("structure_gate", ok, 1.0, detail))
    if p.mixed_rule != "any" and read.structure in MIXED:
        if p.mixed_rule == "skip":
            out.append(Condition("mixed_phase", False, 1.0, f"{tf} {read.structure.value}: skipped"))
        else:
            higher = _higher_read(market, tf)
            trend = _swing_relative(higher, buy)
            at, where = _at_level(read, buy, entry)
            name = "-" if higher is None else higher.timeframe
            detail = f"{tf} {read.structure.value}: surest: {name} {trend.lower()}, {where}"
            out.append(Condition("mixed_phase", trend == "WITH" and at, 1.0, detail))
    if p.level_gate == "at_level":
        at, where = _at_level(read, buy, entry)
        out.append(Condition("at_read_level", at, 1.0, where))
    if p.room_min_r is not None:
        sign = 1 if buy else -1
        ahead = [(lv.price - entry) * sign for lv in read.levels if (lv.price - entry) * sign > 0]
        if not ahead or risk <= 0:
            out.append(Condition("room_to_level", risk > 0, 1.0, f"{tf} no opposing level ahead"))
        else:
            room = min(ahead) / risk
            detail = f"{room:.2f} R to the {tf} level (needs {p.room_min_r:g})"
            out.append(Condition("room_to_level", room >= p.room_min_r, 1.0, detail))
    return out


def _quiet_phase(ctx: StrategyContext, p: SetupParams) -> list[Condition]:
    """Regime fit: in a quiet H4 phase the setup takes only the signals that pass ``quiet_rule``."""
    if p.quiet_h4_atr_pct is None or p.quiet_rule == "none":
        return []
    h4 = None if ctx.market.htf is None else ctx.market.htf.frames.get("H4")
    pct = None if h4 is None else h4.atr_pct
    if pct is not None and pct >= p.quiet_h4_atr_pct:
        return []
    note = "no H4 volatility" if pct is None else f"H4 ATR percentile {pct:.0f} < {p.quiet_h4_atr_pct:g}"
    frame = ctx.frame(ctx.market.entry_timeframe)
    if frame.empty or not {"high", "low", "close"} <= set(frame.columns):
        return [Condition("quiet_phase_rule", False, 1.0, f"{note}; no entry frame")]
    state = str(state_frame(frame[["high", "low", "close"]], MapParams())["state"].iloc[-1])
    return [Condition("quiet_phase_rule", state != MapState.RANGE.value, 1.0, f"{note}; entry frame {state}")]


def _zones(market: MarketContext, frames: Sequence[str], kind: ZoneKind) -> list[MapZone]:
    if market.htf is None:
        return []
    maps = [m for f in frames if (m := market.htf.frames.get(f)) is not None]
    return [z for m in maps for z in m.zones if z.kind is kind]


def _scope(p: SetupParams) -> tuple[str, ...]:
    return ("H4",) if p.zone_scope == "H4" else ("H4", "D1")


def _opposing_edges(market: MarketContext, p: SetupParams, sign: int) -> list[float]:
    """Near edges of the opposing zones (a supply zone's low for a BUY, a demand zone's high for a SELL)."""
    kind = ZoneKind.SUPPLY if sign > 0 else ZoneKind.DEMAND
    return [z.low if sign > 0 else z.high for z in _zones(market, _scope(p), kind)]


def _zone_clear(market: MarketContext, p: SetupParams, entry: float, target: float, sign: int) -> Condition:
    """No opposing zone starts between the entry and the target (a zone the entry is breaking through does not
    count: a breakout enters inside the zone of the level it breaks)."""
    frames = _scope(p)
    if market.htf is None or not any(f in market.htf.frames for f in frames):
        return Condition("zone_clear", False, 1.0, "no market map")
    kind = ZoneKind.SUPPLY if sign > 0 else ZoneKind.DEMAND
    span = (target - entry) * sign
    for z in _zones(market, frames, kind):
        near = ((z.low if sign > 0 else z.high) - entry) * sign
        if 0 < near < span:
            note = f"{kind.value.lower()} zone {z.low:.5g}-{z.high:.5g} in the way"
            return Condition("zone_clear", False, 1.0, note)
    return Condition("zone_clear", True, 1.0, "no opposing zone before the target")


def _confirmed_by(
    items: Sequence[ActiveEvidence],
    detector: str,
    direction: Direction,
    window: int,
    variant_name: str | None = None,
) -> ActiveEvidence | None:
    """The most recent same-direction item of *detector* within *window* bars, if any."""
    matches = [
        a
        for a in items
        if a.evidence.detector_id == detector
        and a.evidence.direction is direction
        and a.age_bars <= window
        and (variant_name is None or variant(a.evidence) == variant_name)
    ]
    return min(matches, key=lambda a: a.age_bars) if matches else None


# --- the setups (PLAN §A29 table) -------------------------------------------------------------------------


class NecklineParams(SetupParams):
    # beyond the pattern extreme a measured move gives RR < 1, so the default takes the nearer stop
    stop_mode: StopMode = "nearer"


class NecklineBreak(EvidenceSetup):
    name = "setup_neckline_break"
    description = "M/W, triple tops/bottoms and head & shoulders: neckline-break close. Unproven."
    setup_code = "NECKLINE_BREAK"
    triggers = frozenset({"chart.double", "chart.triple", "chart.head_shoulders"})
    core_families = frozenset({Family.CHART_PATTERN})
    Params = NecklineParams


class PatternBreakout(EvidenceSetup):
    name = "setup_pattern_breakout"
    description = "Triangle, wedge, rectangle, flag/pennant and cup & handle boundary breaks. Unproven."
    setup_code = "PATTERN_BREAKOUT"
    triggers = frozenset(
        {"chart.triangle", "chart.wedge", "chart.rectangle", "chart.flag", "chart.cup_handle"}
    )
    core_families = frozenset({Family.CHART_PATTERN})
    Params = NecklineParams


class FibPullbackParams(SetupParams):
    require_htf_alignment: bool = True  # a continuation trade needs a trend that is at least not against it


class FibPullback(EvidenceSetup):
    name = "setup_fib_pullback"
    description = "Fibonacci golden-zone (50–61.8 %) rejection in the impulse direction. Unproven."
    setup_code = "FIB_PULLBACK"
    triggers = frozenset({"fib.golden_zone"})
    core_families = frozenset({Family.FIBONACCI})
    Params = FibPullbackParams


class HarmonicParams(SetupParams):
    """SETUP_REVIEW §15 (2026-10-11): harmonic is a reversal at the end of a move or inside a range.

    - ``phase_gate``: ``h4_against_or_range`` trades only while the H4 market map (``MarketContext.htf``)
      trends against the trade or ranges (a missing map holds: fail closed);
    - ``confirm``: ``prior_bar_break`` waits after the PRZ completion (``trigger_max_age_bars`` bars at most)
      for the first entry-timeframe close beyond the previous bar's high (BUY) / low (SELL), Elder's third
      screen; a close through the pattern's invalidation before that cancels it.
    """

    phase_gate: Literal["none", "h4_against_or_range"] = "none"
    confirm: Literal["none", "prior_bar_break"] = "none"


class HarmonicPrz(EvidenceSetup):
    name = "setup_harmonic_prz"
    description = "Harmonic XABCD completion: reversal at the PRZ, targets 38.2/61.8 % of AD. Unproven."
    setup_code = "HARMONIC_PRZ"
    triggers = frozenset(
        {
            "harmonic.gartley",
            "harmonic.bat",
            "harmonic.butterfly",
            "harmonic.crab",
            "harmonic.cypher",
            "harmonic.shark",
            "harmonic.abcd",
        }
    )
    core_families = frozenset({Family.HARMONIC})
    Params = HarmonicParams

    def confirmations(
        self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence], ctx: StrategyContext
    ) -> list[Condition]:
        p: HarmonicParams = self.params
        buy = trigger.evidence.direction is Direction.BULL
        out: list[Condition] = []
        if p.phase_gate == "h4_against_or_range":
            h4 = None if ctx.market.htf is None else ctx.market.htf.frames.get("H4")
            state = "none" if h4 is None else h4.state.value
            against = "DOWN" if buy else "UP"
            out.append(Condition("h4_phase", state in (against, "RANGE"), 1.0, f"H4 {state}"))
        if p.confirm == "prior_bar_break":
            out.append(self._prior_bar_break(trigger, ctx, buy))
        return out

    def _prior_bar_break(self, trigger: ActiveEvidence, ctx: StrategyContext, buy: bool) -> Condition:
        frame = ctx.frame(ctx.market.entry_timeframe)
        age = trigger.age_bars
        if age < 1 or len(frame) < age + 2:
            return Condition(
                "prz_confirmed", False, 1.0, f"waiting for a close beyond the previous bar ({age})"
            )
        high = frame["high"].to_numpy(dtype=float)[-(age + 2) :]
        low = frame["low"].to_numpy(dtype=float)[-(age + 2) :]
        close = frame["close"].to_numpy(dtype=float)[-(age + 2) :]
        # positions: [-age-1] the PRZ bar's predecessor... [-1] the decision bar; bars after the PRZ: 2..end
        breaks = [close[i] > high[i - 1] if buy else close[i] < low[i - 1] for i in range(2, len(close))]
        inv = trigger.evidence.invalidation
        failed = inv is not None and any(
            (c < inv) if buy else (c > inv) for c in close[1:]
        )  # from the PRZ bar
        if failed:
            return Condition("prz_confirmed", False, 1.0, "closed through the invalidation")
        if not breaks[-1] or any(breaks[:-1]):
            return Condition("prz_confirmed", False, 1.0, "no fresh close beyond the previous bar")
        return Condition(
            "prz_confirmed", True, 1.0, f"close beyond the previous bar, {age} bar(s) after the PRZ"
        )


class ElliottWave(EvidenceSetup):
    name = "setup_elliott_wave"
    description = "Possible wave 3 / wave 5 start of the primary (heuristic) count. Unproven."
    setup_code = "ELLIOTT_WAVE"
    triggers = frozenset({"elliott.wave"})
    core_families = frozenset({Family.ELLIOTT})

    def accepts(self, ev: Evidence) -> bool:
        return variant(ev) in {"wave3", "wave5"} and ev.detail("count") == "primary"


class SmcParams(SetupParams):
    target_mode: TargetMode = "level"  # the opposite liquidity: the nearest opposing zone


class SmcReversal(EvidenceSetup):
    """Liquidity sweep, then a change of character, then a fair-value-gap retest, all the same way."""

    name = "setup_smc_reversal"
    description = "Smart money: sweep + CHoCH + FVG retest; stop beyond the sweep extreme. Unproven."
    setup_code = "SMC_REVERSAL"
    triggers = frozenset({"smc.fvg"})
    confirming = frozenset({"smc.liquidity_sweep", "structure.bos_choch"})
    core_families = frozenset({Family.SMART_MONEY, Family.TREND})
    Params = SmcParams

    def confirmations(
        self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence], ctx: StrategyContext
    ) -> list[Condition]:
        window = self.params.confirm_window_bars
        direction = trigger.evidence.direction
        sweep = _confirmed_by(items, "smc.liquidity_sweep", direction, window)
        choch = _confirmed_by(items, "structure.bos_choch", direction, window, "choch")
        return [
            Condition(
                "liquidity_sweep",
                sweep is not None,
                1.0,
                "no sweep" if sweep is None else f"swept {sweep.age_bars} bars ago",
            ),
            Condition(
                "change_of_character",
                choch is not None,
                1.0,
                "no CHoCH" if choch is None else f"CHoCH {choch.age_bars} bars ago",
            ),
        ]

    def stop_reference(self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence]) -> float | None:
        sweep = _confirmed_by(
            items, "smc.liquidity_sweep", trigger.evidence.direction, self.params.confirm_window_bars
        )
        return None if sweep is None else sweep.evidence.invalidation


class BreakoutParams(SetupParams):
    stop_mode: StopMode = "nearer"  # Donchian's invalidation is the channel middle, often far away


class RangeBreakout(EvidenceSetup):
    name = "setup_breakout"
    description = "Donchian channel and Asian / London / New York opening-range breakouts. Unproven."
    setup_code = "RANGE_BREAKOUT"
    triggers = frozenset({"volatility.donchian", "sessions.asian_breakout", "sessions.open_breakout"})
    core_families = frozenset({Family.VOLATILITY_VOLUME, Family.SESSIONS})
    Params = BreakoutParams


class CandleParams(SetupParams):
    target_mode: TargetMode = "level"  # the next level


class CandleReversal(EvidenceSetup):
    """A directional reversal candle that sits on a level (``at_level``), stop beyond the candle extreme."""

    name = "setup_candle_reversal"
    description = "Reversal candlestick at a level (S/R, Fibonacci, pivots, trendline). Unproven."
    setup_code = "CANDLE_REVERSAL"
    triggers = frozenset(
        {
            "candle.engulfing",
            "candle.hammer",
            "candle.shooting_star",
            "candle.doji",
            "candle.inside_outside",
            "candle.star",
            "candle.harami",
            "candle.tweezer",
        }
    )
    core_families = frozenset({Family.CANDLESTICK})
    Params = CandleParams

    def confirmations(
        self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence], ctx: StrategyContext
    ) -> list[Condition]:
        levels = str(trigger.evidence.detail("at_levels", "") or "")
        at_level = bool(trigger.evidence.detail("at_level", False))
        return [
            Condition("at_level", at_level, 1.0, levels.replace(",", ", ") if at_level else "not at a level")
        ]


SETUPS: tuple[type[EvidenceSetup], ...] = (
    NecklineBreak,
    PatternBreakout,
    FibPullback,
    HarmonicPrz,
    ElliottWave,
    SmcReversal,
    RangeBreakout,
    CandleReversal,
)
