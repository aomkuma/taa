"""Builds the :class:`StrategyContext` for one symbol at one decision bar (PLAN §A5, §A7).

- **Per-timeframe retrieval:** every enabled timeframe is fetched on its own (closed candles only) and
  analyzed by :func:`analyze_frame` into a frame of indicator columns plus confirmed swings.
- **Close-time alignment:** the decision time is the close of the newest entry-timeframe bar. Every timeframe
  is cut to bars with ``close_time <= decision_time`` (the ``merge_asof`` rule): a higher-timeframe bar that
  is still forming at the decision time is never seen. All indicators are causal, so slicing a frame analyzed
  once equals analyzing the cut frame (the look-ahead tests check exactly that), which lets backtests analyze
  each frame once and call :func:`context_at` per bar.
- **Logs:** :meth:`ContextBuilder.build` logs one analysis line per timeframe (trend, regime, volatility,
  ADX, ATR percentile and the bar used), so every decision can be traced to what each timeframe said.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.config import AppConfig, IndicatorParams, RegimeConfig
from app.core.clock import Clock, ensure_utc
from app.core.enums import Regime, Session, Timeframe, Trend, VolatilityState
from app.core.errors import DataQualityError, InsufficientDataError
from app.evidence.framework import EvidenceContext, EvidenceSnapshot
from app.evidence.registry import EvidenceEngine
from app.indicators.momentum import rsi
from app.indicators.price_action import Swing, find_swings, market_structure, sr_zones
from app.indicators.trend import adx, ema
from app.indicators.volatility import atr, atr_percentile
from app.market_data.data_models import CandleFrame, Quote, SymbolSpec
from app.strategy.regime_detector import regime_series, trend_series, volatility_series
from app.strategy.signal_models import MarketContext, StrategyContext, TimeframeState

log = logging.getLogger(__name__)

# columns of every analyzed frame (indexed by bar close time, UTC)
FRAME_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "ema_fast",
    "ema_mid",
    "ema_slow",
    "rsi",
    "atr",
    "atr_pct",
    "adx",
    "plus_di",
    "minus_di",
    "structure",
    "trend",
    "regime",
    "volatility",
    "valid",  # finite prices, low > 0 and consistent OHLC (a negative print, e.g. WTI in April 2020, is not)
)
MAX_LEVELS = 3  # nearest S/R zone centres kept on each side of the close


class CandleSource(Protocol):
    """Closed candles per symbol/timeframe (``CandleService`` in production, history replays in backtests)."""

    def closed_candles(self, symbol: str, tf: Timeframe, count: int) -> CandleFrame: ...


class QuoteSource(Protocol):
    def quote(self, spec: SymbolSpec) -> Quote: ...


@dataclass(frozen=True, eq=False)
class AnalyzedFrame:
    timeframe: Timeframe
    df: pd.DataFrame  # FRAME_COLUMNS, indexed by close time
    swings: tuple[Swing, ...]  # confirmed pivots (positions refer to ``df``)
    quality_flags: tuple[str, ...] = ()

    def count_upto(self, at: datetime) -> int:
        """Number of bars that closed at or before *at*."""
        return int(self.df.index.searchsorted(pd.Timestamp(ensure_utc(at)), side="right"))


def analyze_frame(
    candles: pd.DataFrame,
    tf: Timeframe,
    params: IndicatorParams,
    regime: RegimeConfig,
    quality_flags: Sequence[str] = (),
) -> AnalyzedFrame:
    """Indicators, states and swings for one timeframe of closed candles (``CANDLE_COLUMNS`` input)."""
    if "close_time" not in candles.columns:
        raise DataQualityError("candles need a close_time column")
    index = pd.DatetimeIndex(candles["close_time"])
    if index.tz is None:
        raise DataQualityError("close_time must be timezone-aware UTC")
    index = index.tz_convert("UTC")
    if not (index.is_monotonic_increasing and index.is_unique):
        raise DataQualityError(f"{tf} candles are not in strictly increasing close-time order")
    src = candles.reset_index(drop=True)
    df = pd.DataFrame(index=index)
    df["open_time"] = (
        pd.DatetimeIndex(src["open_time"]).tz_convert("UTC")
        if "open_time" in src
        else index - pd.Timedelta(seconds=tf.seconds)
    )
    for col in ("open", "high", "low", "close"):
        df[col] = src[col].to_numpy(dtype=float)
    for col in ("tick_volume", "spread"):
        df[col] = src[col].to_numpy(dtype=float) if col in src else np.nan
    high, low, close = df["high"], df["low"], df["close"]
    df["ema_fast"] = ema(close, params.ema_fast)
    df["ema_mid"] = ema(close, params.ema_mid)
    df["ema_slow"] = ema(close, params.ema_slow)
    df["rsi"] = rsi(close, params.rsi_period)
    df["atr"] = atr(high, low, close, params.atr_period)
    df["atr_pct"] = atr_percentile(df["atr"], params.atr_percentile_lookback)
    dmi = adx(high, low, close, params.adx_period)
    df["adx"], df["plus_di"], df["minus_di"] = dmi["adx"], dmi["plus_di"], dmi["minus_di"]
    df["structure"] = market_structure(high, low, params.swing_k)["trend"]
    c, mid, slow = close.to_numpy(), df["ema_mid"].to_numpy(), df["ema_slow"].to_numpy()
    df["trend"] = trend_series(c, mid, slow)
    df["regime"] = regime_series(df["adx"].to_numpy(), df["atr_pct"].to_numpy(), regime)
    df["volatility"] = volatility_series(df["atr_pct"].to_numpy(), regime)
    o, h, lo = df["open"].to_numpy(), high.to_numpy(), low.to_numpy()
    finite = np.isfinite(o) & np.isfinite(h) & np.isfinite(lo) & np.isfinite(c)
    with np.errstate(invalid="ignore"):
        consistent = (lo > 0) & (lo <= np.minimum(o, c)) & (h >= np.maximum(o, c))
    df["valid"] = finite & consistent
    swings = tuple(find_swings(high, low, params.swing_k))
    return AnalyzedFrame(tf, df, swings, tuple(quality_flags))


def trading_session(at_utc: datetime) -> Session:
    """Main FX session at *at_utc*, from each centre's local business hours (zoneinfo handles DST)."""
    at = ensure_utc(at_utc)
    active = {s for s, tz, start, end in _SESSION_HOURS if _within(at, tz, start, end)}
    if {Session.LONDON, Session.NEW_YORK} <= active:
        return Session.LONDON_NY_OVERLAP
    for session in (Session.LONDON, Session.NEW_YORK, Session.ASIA):
        if session in active:
            return session
    return Session.OFF


_SESSION_HOURS = (
    (Session.ASIA, "Asia/Tokyo", time(9), time(18)),
    (Session.LONDON, "Europe/London", time(8), time(17)),
    (Session.NEW_YORK, "America/New_York", time(8), time(17)),
)


def _within(at: datetime, tz: str, start: time, end: time) -> bool:
    local = at.astimezone(ZoneInfo(tz))
    return local.weekday() < 5 and start <= local.time() < end


def _opt(value: float | None) -> float | None:
    if value is None:
        return None
    f = float(value)
    return f if math.isfinite(f) else None


def _state(frame: AnalyzedFrame, pos: int) -> TimeframeState:
    row = frame.df.iloc[pos]
    structure = row["structure"]
    return TimeframeState(
        timeframe=frame.timeframe,
        bar_close_utc=pd.Timestamp(frame.df.index[pos]).to_pydatetime(),
        close=float(row["close"]),
        trend=Trend(row["trend"]),
        regime=Regime(row["regime"]),
        volatility=VolatilityState(row["volatility"]),
        structure=None if pd.isna(structure) else str(structure),
        atr=_opt(row["atr"]),
        atr_percentile=_opt(row["atr_pct"]),
        adx=_opt(row["adx"]),
        plus_di=_opt(row["plus_di"]),
        minus_di=_opt(row["minus_di"]),
        rsi=_opt(row["rsi"]),
        ema_fast=_opt(row["ema_fast"]),
        ema_mid=_opt(row["ema_mid"]),
        ema_slow=_opt(row["ema_slow"]),
    )


def _levels(
    frame: AnalyzedFrame, pos: int, tolerance_atr: float
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    atr_value = _opt(frame.df["atr"].iloc[pos])
    if atr_value is None or atr_value <= 0:
        return (), ()
    close = float(frame.df["close"].iloc[pos])
    zones = sr_zones(frame.swings, as_of_pos=pos, atr_value=atr_value, tolerance_atr=tolerance_atr)
    support = sorted((z.center for z in zones if z.role(close) == "SUPPORT"), reverse=True)
    resistance = sorted(z.center for z in zones if z.role(close) == "RESISTANCE")
    return tuple(support[:MAX_LEVELS]), tuple(resistance[:MAX_LEVELS])


def context_at(
    frames: Mapping[Timeframe, AnalyzedFrame],
    *,
    symbol: str,
    entry_timeframe: Timeframe,
    higher_timeframe: Timeframe,
    decision_time: datetime,
    now_utc: datetime,
    params: IndicatorParams,
    quote: Quote | None = None,
    spec: SymbolSpec | None = None,
    evidence: Mapping[Timeframe, EvidenceSnapshot] | None = None,
    window: int | None = None,
) -> StrategyContext:
    """The strategy context at *decision_time* (an entry-timeframe bar close) from pre-analyzed frames.

    *window* limits each frame handed to strategies to its last *window* bars (backtests pass the warm-up
    size, so a long history is not copied at every bar); indicators were computed on the full frame.
    """
    decision_time = ensure_utc(decision_time)
    entry = frames[entry_timeframe]
    n_entry = entry.count_upto(decision_time)
    if n_entry == 0 or pd.Timestamp(entry.df.index[n_entry - 1]) != pd.Timestamp(decision_time):
        raise DataQualityError(f"no {entry_timeframe} bar of {symbol} closes at {decision_time.isoformat()}")
    states: list[TimeframeState] = []
    cut: dict[Timeframe, pd.DataFrame] = {}
    flags: list[str] = []
    for tf, frame in frames.items():
        n = frame.count_upto(decision_time)
        if n == 0:
            raise InsufficientDataError(f"no closed {tf} bar of {symbol} at {decision_time.isoformat()}")
        cut[tf] = frame.df.iloc[0 if window is None else max(0, n - window) : n].copy()
        bad = int((~cut[tf]["valid"].astype(bool)).sum())
        if bad:
            # indicators computed through a bad print stay contaminated: hold while it is in the window
            flags.append(f"{tf.value}:INVALID_OHLC:{bad}")
        states.append(_state(frame, n - 1))
        flags.extend(f"{tf.value}:{flag}" for flag in frame.quality_flags)
        lag = (decision_time - states[-1].bar_close_utc).total_seconds()
        if lag >= 2 * tf.seconds:
            flags.append(f"{tf.value}:ALIGNMENT_LAG:{int(lag // tf.seconds)}")
    support, resistance = _levels(entry, n_entry - 1, params.sr_tolerance_atr)
    spread = None if quote is None or not quote.valid else quote.spread_points
    market = MarketContext(
        symbol=symbol,
        decision_time_utc=decision_time,
        entry_timeframe=entry_timeframe,
        higher_timeframe=higher_timeframe,
        states=tuple(states),
        session=trading_session(decision_time),
        bid=None if quote is None or not quote.valid else quote.bid,
        ask=None if quote is None or not quote.valid else quote.ask,
        spread_points=spread,
        quote_time_utc=None if quote is None else quote.time_utc,
        quality_flags=tuple(flags),
        support_levels=support,
        resistance_levels=resistance,
    )
    return StrategyContext(market, cut, now_utc, spec, evidence or {})


class ContextBuilder:
    """Fetches, analyzes and aligns every enabled timeframe of a symbol (live engine and scanner)."""

    def __init__(
        self,
        candles: CandleSource,
        config: AppConfig,
        clock: Clock,
        quotes: QuoteSource | None = None,
        evidence: EvidenceEngine | None = None,
    ) -> None:
        self.candles = candles
        self.config = config
        self.clock = clock
        self.quotes = quotes
        self.evidence = evidence

    def analyze(self, symbol: str) -> dict[Timeframe, AnalyzedFrame]:
        tfs = self.config.timeframes
        out: dict[Timeframe, AnalyzedFrame] = {}
        for tf in tfs.enabled:
            frame = self.candles.closed_candles(symbol, tf, tfs.warmup_bars)
            if frame.df.empty:
                raise InsufficientDataError(f"no closed {tf} bars for {symbol}")
            out[tf] = analyze_frame(
                frame.df, tf, self.config.indicators, self.config.regime, frame.quality.flags
            )
        return out

    def build(self, symbol: str, spec: SymbolSpec | None = None) -> StrategyContext:
        frames = self.analyze(symbol)
        entry_tf = self.config.timeframes.entry
        decision_time = pd.Timestamp(frames[entry_tf].df.index[-1]).to_pydatetime()
        quote = self.quotes.quote(spec) if self.quotes is not None and spec is not None else None
        snapshots = self.evaluate_evidence(symbol, frames, decision_time)
        ctx = context_at(
            frames,
            symbol=symbol,
            entry_timeframe=entry_tf,
            higher_timeframe=self.config.timeframes.higher,
            decision_time=decision_time,
            now_utc=self.clock.now_utc(),
            params=self.config.indicators,
            quote=quote,
            spec=spec,
            evidence=snapshots,
        )
        log_analysis(ctx.market)
        return ctx

    def evaluate_evidence(
        self, symbol: str, frames: Mapping[Timeframe, AnalyzedFrame], decision_time: datetime
    ) -> dict[Timeframe, EvidenceSnapshot]:
        """Active evidence per timeframe at *decision_time*, each from that timeframe's closed bars only."""
        if self.evidence is None:
            return {}
        out: dict[Timeframe, EvidenceSnapshot] = {}
        for tf, frame in frames.items():
            n = frame.count_upto(decision_time)
            if n == 0:
                continue
            candles = frame.df.iloc[:n].reset_index(names="close_time")
            out[tf] = self.evidence.evaluate(EvidenceContext(symbol, tf, candles, self.config.evidence))
        return out


def log_analysis(market: MarketContext) -> None:
    for s in market.states:
        log.info(
            "analysis symbol=%s tf=%s bar=%s trend=%s regime=%s volatility=%s structure=%s adx=%s atr_pct=%s",
            market.symbol,
            s.timeframe.value,
            s.bar_close_utc.isoformat(),
            s.trend.value,
            s.regime.value,
            s.volatility.value,
            s.structure,
            _fmt(s.adx),
            _fmt(s.atr_percentile),
        )
    if market.quality_flags:
        log.warning("analysis symbol=%s quality_flags=%s", market.symbol, ",".join(market.quality_flags))


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"
