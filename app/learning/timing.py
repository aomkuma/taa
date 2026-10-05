"""Timing diagnostics: why trades that read the direction right still lose (PLAN_LEARNING §L19; TAA-L701).

Pure functions over analytics :class:`~app.analytics.trade_builder.Trade` records and bid-based candle frames
(``open_time`` UTC, ``high``, ``low``, ``close``). Nothing here changes the analytics, the recommendations or
the attribution it reads (§L0.2).

**Price path rules** (the backtester's, §A17): bars are Bid. A BUY exits at the bid, so a level above the
entry is reached when ``high >= level`` and one below when ``low <= level``. A SELL exits at the ask, so the
recorded spread (``context.spread``, 0 when unknown) is added to the bar before comparing. When one bar
reaches both levels the pessimistic one counts (no claim the trade was right).

**Follow-up after a stop-loss exit** looks at bars that open at or after the exit (the exit bar itself also
holds prices from before the exit) up to the look-ahead ``H``:

- ``VINDICATED``: the original take-profit is reached before price goes a further 1R beyond the stop;
- ``NOT_VINDICATED``: the further 1R comes first (or both in one bar);
- ``UNKNOWN``: neither within the data; the data ending before ``H`` is censoring, not evidence.

**Failure modes** (losers only; a WIN or a break-even/trailing scratch is not a failure):

1. ``STALL``: a time-stop exit, or a manual/signal close that never got +0.5R in its favour;
2. ``EARLY``: a stop-loss exit that was ``VINDICATED``;
3. ``LATE``: a stop-loss exit after price had already run ``late_run_atr`` × ATR in the trade's direction over
   the ``pre_bars`` entry-timeframe bars before the entry (chasing);
4. ``TF_MISMATCH``: a stop-loss exit with the higher-timeframe trend on the trade's side at entry and at the
   exit, while the entry timeframe was trending the other way (close below/above its ``pre_trend_bars`` mean);
5. ``WRONG``: a stop-loss exit that was ``NOT_VINDICATED`` and none of the above;
6. ``OTHER`` / ``UNKNOWN``: any other losing exit / a stop-loss exit without enough facts.

**Random-walk baseline (first passage).** For a driftless walk, a take-profit ``a`` above and a stop ``b``
below the entry (price distances), P(TP first) = b / (a + b) and the expected exit time is a·b / σ² bars, with
σ the per-bar standard deviation. After a stop-out, reaching the TP before a further 1R (= b) has probability
b / (a + 2b). σ is estimated from the entry-timeframe ATR as ATR / √(8/π) (the expected range of a Brownian
bar), an approximation that ignores gaps. Observed rates are only evidence where they differ from this
baseline.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

import numpy as np
import pandas as pd

from app.advisory.stats_math import wilson_interval
from app.analytics.trade_builder import Alignment, Outcome, Trade
from app.core.clock import ensure_utc
from app.core.enums import ExitReason, Side
from app.core.errors import TaaError

# Defaults (PLAN_LEARNING §L19.2; `learning.timing` config later).
STALL_MFE_R = 0.5
LATE_RUN_ATR = 1.5
PRE_BARS = 10
PRE_TREND_BARS = 50
MIN_QUANTILE_N = 10
QUANTILES = (0.25, 0.5, 0.75, 0.8)
RANGE_PER_SIGMA = math.sqrt(8 / math.pi)  # E[high - low] of one Brownian bar, in σ

STOP_LOSS_EXITS = frozenset({ExitReason.STOP_LOSS, ExitReason.STOP_OUT})
STALL_EXITS = frozenset({ExitReason.MANUAL, ExitReason.SIGNAL})


class TimingError(TaaError):
    pass


class Vindication(StrEnum):
    VINDICATED = "VINDICATED"
    NOT_VINDICATED = "NOT_VINDICATED"
    UNKNOWN = "UNKNOWN"


class FailureMode(StrEnum):
    EARLY = "EARLY"
    LATE = "LATE"
    STALL = "STALL"
    TF_MISMATCH = "TF_MISMATCH"
    WRONG = "WRONG"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class TimingParams:
    lookahead: timedelta = timedelta(hours=72)  # PLAN_LEARNING §L19.2: the strategy's time stop by default
    stall_mfe_r: float = STALL_MFE_R
    late_run_atr: float = LATE_RUN_ATR
    pre_bars: int = PRE_BARS
    pre_trend_bars: int = PRE_TREND_BARS


@dataclass(frozen=True, slots=True)
class Diagnosis:
    trade_id: str
    mode: FailureMode | None  # None: not a losing trade
    vindication: Vindication | None  # stop-loss exits only
    pre_run_atr: float | None  # run in the trade's direction before entry, in ATR
    baseline_p_tp: float | None  # random-walk P(TP before SL) at entry
    baseline_vindication: float | None  # random-walk P(TP before a further 1R) after the stop
    baseline_bars: float | None  # random-walk expected bars to TP or SL


def _side_prices(side: Side, bars: pd.DataFrame, spread: float) -> tuple[np.ndarray, np.ndarray]:
    """(high, low) of the price the position exits at: the bid for a BUY, the ask for a SELL."""
    add = 0.0 if side is Side.BUY else spread
    return bars["high"].to_numpy(dtype=float) + add, bars["low"].to_numpy(dtype=float) + add


def _window(bars: pd.DataFrame, start: datetime, end: datetime | None = None) -> pd.DataFrame:
    times = bars["open_time"]
    mask = times >= start if end is None else (times >= start) & (times < end)
    return bars.loc[mask]


def _risk(trade: Trade) -> float | None:
    return trade.risk_distance


class Touch(StrEnum):
    TARGET = "TARGET"
    ADVERSE = "ADVERSE"
    NEITHER = "NEITHER"


def first_touch(
    side: Side,
    bars: pd.DataFrame,
    start: datetime,
    lookahead: timedelta,
    *,
    target: float,
    adverse: float,
    spread: float = 0.0,
) -> Touch:
    """Which level a position on ``side`` reaches first in the bars opening in [start, start + lookahead):
    ``target`` in its favour or ``adverse`` against it. Both in one bar counts as ``ADVERSE`` (pessimistic).
    """
    start = ensure_utc(start)
    after = _window(bars, start, start + lookahead)
    sign = side.sign
    high, low = _side_prices(side, after, spread)
    for hi, lo in zip(high, low, strict=True):
        if (lo <= adverse) if sign > 0 else (hi >= adverse):
            return Touch.ADVERSE
        if (hi >= target) if sign > 0 else (lo <= target):
            return Touch.TARGET
    return Touch.NEITHER


def follow_up(trade: Trade, bars: pd.DataFrame, lookahead: timedelta) -> Vindication:
    """After a stop-loss exit: was the original take-profit reached before a further 1R against the trade?"""
    risk = _risk(trade)
    if trade.exit_reason not in STOP_LOSS_EXITS or risk is None or trade.initial_tp is None:
        return Vindication.UNKNOWN
    stop = trade.initial_sl if trade.initial_sl is not None else trade.exit_price
    touch = first_touch(
        trade.side,
        bars,
        trade.exit_time,
        lookahead,
        target=trade.initial_tp,
        adverse=stop - trade.side.sign * risk,
        spread=trade.context.spread or 0.0,
    )
    if touch is Touch.TARGET:
        return Vindication.VINDICATED
    return Vindication.NOT_VINDICATED if touch is Touch.ADVERSE else Vindication.UNKNOWN


def pre_entry_run_atr(trade: Trade, bars: pd.DataFrame, pre_bars: int) -> float | None:
    """How far price ran in the trade's direction over the ``pre_bars`` bars before the entry, in ATR."""
    atr = trade.context.atr
    if atr is None or atr <= 0:
        return None
    before = bars.loc[bars["open_time"] < ensure_utc(trade.entry_time)].tail(pre_bars + 1)
    if len(before) < pre_bars + 1:
        return None
    closes = before["close"].to_numpy(dtype=float)
    return float((trade.entry_price - closes[0]) * trade.side.sign / atr)


def entry_tf_against(trade: Trade, bars: pd.DataFrame, trend_bars: int) -> bool | None:
    """True when the entry timeframe closed on the far side of its ``trend_bars`` mean, against the trade."""
    before = bars.loc[bars["open_time"] < ensure_utc(trade.entry_time)].tail(trend_bars)
    if len(before) < trend_bars:
        return None
    closes = before["close"].to_numpy(dtype=float)
    return bool((closes[-1] - closes.mean()) * trade.side.sign < 0)


def sigma_from_atr(atr: float) -> float:
    return atr / RANGE_PER_SIGMA


def first_passage(
    tp_distance: float, sl_distance: float, sigma: float | None = None
) -> tuple[float, float | None]:
    """Driftless random walk: (P(TP first), expected bars to either level; None without σ)."""
    if tp_distance <= 0 or sl_distance <= 0:
        raise TimingError("barrier distances must be positive")
    p_tp = sl_distance / (tp_distance + sl_distance)
    bars = tp_distance * sl_distance / sigma**2 if sigma is not None and sigma > 0 else None
    return p_tp, bars


def _baseline(trade: Trade) -> tuple[float | None, float | None, float | None]:
    risk = _risk(trade)
    if risk is None or trade.initial_tp is None:
        return None, None, None
    reward = (trade.initial_tp - trade.entry_price) * trade.side.sign
    if reward <= 0:
        return None, None, None
    atr = trade.context.atr
    sigma = sigma_from_atr(atr) if atr is not None and atr > 0 else None
    p_tp, bars = first_passage(reward, risk, sigma)
    return p_tp, risk / (reward + 2 * risk), bars


def classify(trade: Trade, bars: pd.DataFrame | None, params: TimingParams | None = None) -> Diagnosis:
    """The failure mode of one trade, from its record and the entry-timeframe bars around it."""
    params = params or TimingParams()
    p_tp, p_vind, rw_bars = _baseline(trade)
    frame = bars if bars is not None else pd.DataFrame(columns=["open_time", "high", "low", "close"])
    vindication = follow_up(trade, frame, params.lookahead) if trade.exit_reason in STOP_LOSS_EXITS else None
    run = pre_entry_run_atr(trade, frame, params.pre_bars)

    def done(mode: FailureMode | None) -> Diagnosis:
        return Diagnosis(trade.trade_id, mode, vindication, run, p_tp, p_vind, rw_bars)

    if trade.outcome is Outcome.WIN:
        return done(None)
    mfe_r = trade.mfe_r
    if trade.exit_reason is ExitReason.TIME_STOP or (
        trade.exit_reason in STALL_EXITS and mfe_r is not None and mfe_r < params.stall_mfe_r
    ):
        return done(FailureMode.STALL)
    if trade.outcome is not Outcome.LOSS:
        return done(None)
    if trade.exit_reason not in STOP_LOSS_EXITS:
        return done(FailureMode.OTHER)
    if vindication is Vindication.VINDICATED:
        return done(FailureMode.EARLY)
    if run is not None and run >= params.late_run_atr:
        return done(FailureMode.LATE)
    against = entry_tf_against(trade, frame, params.pre_trend_bars)
    if trade.alignment is Alignment.WITH and trade.alignment_at_exit is Alignment.WITH and against:
        return done(FailureMode.TF_MISMATCH)
    if vindication is Vindication.NOT_VINDICATED:
        return done(FailureMode.WRONG)
    return done(FailureMode.UNKNOWN)


# --- aggregation -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Share:
    count: int
    n: int
    share: float
    low: float  # Wilson 90 % interval
    high: float


@dataclass(frozen=True, slots=True)
class TimingReport:
    key: Hashable
    trades: int
    losers: int  # trades with a failure mode
    modes: Mapping[FailureMode, Share]
    winner_mae_r: Mapping[float, float] | None  # quantile → MAE in R of winners before their TP
    winner_mae_atr: Mapping[float, float] | None
    winner_bars_to_tp: Mapping[float, float] | None
    hit_rate: Share | None  # TP-first among TP/SL-resolved trades
    baseline_hit_rate: float | None  # mean random-walk P(TP first) of the same trades
    vindicated: Share | None  # among stop-loss exits with a known follow-up
    baseline_vindicated: float | None


def _share(count: int, n: int) -> Share:
    low, high = wilson_interval(count, n)
    return Share(count, n, count / n if n else 0.0, low, high)


def _quantiles(values: Sequence[float], min_n: int) -> Mapping[float, float] | None:
    if len(values) < min_n:
        return None
    arr = np.asarray(values, dtype=float)
    return {q: float(np.quantile(arr, q)) for q in QUANTILES}


def _mean(values: Sequence[float]) -> float | None:
    return float(sum(values) / len(values)) if values else None


def default_key(trade: Trade) -> Hashable:
    session = trade.context.session.value if trade.context.session is not None else "UNKNOWN"
    return (trade.symbol, trade.strategy, session)


def report(
    trades: Iterable[Trade],
    bars_for: Callable[[Trade], pd.DataFrame | None],
    *,
    key: Callable[[Trade], Hashable] = default_key,
    params: TimingParams | None = None,
    min_quantile_n: int = MIN_QUANTILE_N,
) -> list[TimingReport]:
    """One :class:`TimingReport` per group. ``bars_for`` returns the entry-timeframe bars around a trade (from
    ``pre_trend_bars`` before the entry to the look-ahead after the exit), or None when there are none."""
    params = params or TimingParams()
    groups: dict[Hashable, list[tuple[Trade, Diagnosis]]] = defaultdict(list)
    for trade in trades:
        groups[key(trade)].append((trade, classify(trade, bars_for(trade), params)))
    out = []
    for group_key, rows in sorted(groups.items(), key=lambda kv: str(kv[0])):
        failed = [d for _, d in rows if d.mode is not None]
        counts = Counter(d.mode for d in failed)
        winners = [t for t, _ in rows if t.outcome is Outcome.WIN and t.exit_reason is ExitReason.TAKE_PROFIT]
        mae_r = [t.mae_r for t in winners if t.mae_r is not None]
        mae_atr = [t.mae / t.context.atr for t in winners if t.context.atr]
        to_tp = [float(t.bars_held) for t in winners if t.bars_held is not None]
        resolved = [(t, d) for t, d in rows if t.exit_reason in STOP_LOSS_EXITS | {ExitReason.TAKE_PROFIT}]
        tp_first = sum(1 for t, _ in resolved if t.exit_reason is ExitReason.TAKE_PROFIT)
        base_hit = [d.baseline_p_tp for _, d in resolved if d.baseline_p_tp is not None]
        followed = [
            d for _, d in rows if d.vindication in (Vindication.VINDICATED, Vindication.NOT_VINDICATED)
        ]
        vindicated = sum(1 for d in followed if d.vindication is Vindication.VINDICATED)
        base_vind = [d.baseline_vindication for d in followed if d.baseline_vindication is not None]
        out.append(
            TimingReport(
                key=group_key,
                trades=len(rows),
                losers=len(failed),
                modes={mode: _share(counts.get(mode, 0), len(failed)) for mode in FailureMode},
                winner_mae_r=_quantiles(mae_r, min_quantile_n),
                winner_mae_atr=_quantiles(mae_atr, min_quantile_n),
                winner_bars_to_tp=_quantiles(to_tp, min_quantile_n),
                hit_rate=_share(tp_first, len(resolved)) if resolved else None,
                baseline_hit_rate=_mean(base_hit),
                vindicated=_share(vindicated, len(followed)) if followed else None,
                baseline_vindicated=_mean(base_vind),
            )
        )
    return out
