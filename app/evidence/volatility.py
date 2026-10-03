"""Volatility and volume detectors (PLAN §A29, family VOLATILITY_VOLUME, tier T1).

Volume is MT5 *tick* volume: relative measures only (see docs/INDICATORS.md, "Volume"). Detectors that need
volume skip bars where it is missing.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
from pydantic import Field

from app.evidence.common import period_keys
from app.evidence.framework import (
    Detector,
    DetectorParams,
    Direction,
    Evidence,
    EvidenceContext,
    Family,
    KeyLevel,
    Tier,
)
from app.indicators.common import FloatArray
from app.indicators.volatility import atr, bollinger, true_range
from app.indicators.volume import volume_ratio


def _sign_dir(sign: int) -> Direction:
    return Direction.BULL if sign > 0 else Direction.BEAR


def _first_close_beyond(c: FloatArray, level: FloatArray, t: int, sign: int) -> bool:
    """Bar *t* closes beyond *level* in direction *sign* and bar ``t - 1`` did not."""
    now, before = (c[t] - level[t]) * sign, (c[t - 1] - level[t - 1]) * sign
    return bool(np.isfinite(now) and np.isfinite(before) and now > 0 >= before)


# --- Bollinger squeeze ------------------------------------------------------------------------------------


class SqueezeParams(DetectorParams):
    n: int = Field(default=20, ge=2, le=500)
    k: float = Field(default=2.0, gt=0, le=5)
    lookback: int = Field(default=120, ge=20, le=5000)  # bars over which the width is ranked
    squeeze_pct: float = Field(default=0.1, gt=0, lt=1)  # width in its lowest decile = squeeze
    window: int = Field(default=20, ge=1, le=500)  # a breakout must follow within this many bars


class BollingerSqueeze(Detector):
    """Bollinger band width in the lowest ``squeeze_pct`` of its last ``lookback`` values (a squeeze),
    followed within ``window`` bars by the first close outside a band: a volatility breakout in that
    direction. Once per squeeze episode."""

    id = "volatility.bollinger_squeeze"
    name = "Bollinger squeeze breakout"
    family = Family.VOLATILITY_VOLUME
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = SqueezeParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        bb = ctx.memo(("bollinger", params.n, params.k), lambda: bollinger(ctx.close, params.n, params.k))
        width, upper, lower, mid = (bb[k].to_numpy() for k in ("width", "upper", "lower", "mid"))
        ranked = _rank(width, params.lookback)
        out: list[Evidence] = []
        # an episode is a run of squeeze bars (gaps up to ``window`` allowed); the breakout bar itself may
        # still rank as a squeeze, since one wide bar barely moves a 20-bar width
        last_squeeze, episode, used = -(10**9), 0, -1
        for t in range(1, ctx.n):
            if np.isfinite(ranked[t]) and ranked[t] <= params.squeeze_pct:
                if t - last_squeeze > params.window:
                    episode += 1
                last_squeeze = t
            if t - last_squeeze > params.window or used == episode:
                continue
            for sign, band in ((1, upper), (-1, lower)):
                if _first_close_beyond(ctx.c, band, t, sign):
                    used = episode
                    out.append(
                        self.make(
                            ctx,
                            t,
                            _sign_dir(sign),
                            0.6 + 0.4 * (1.0 - (t - last_squeeze) / params.window),
                            key_levels=[KeyLevel("band", float(band[t]))],
                            invalidation=float(mid[t]),
                            details={"bars_since_squeeze": t - last_squeeze},
                        )
                    )
                    break
        return out


def _rank(values: FloatArray, lookback: int) -> FloatArray:
    """Share of the last *lookback* values (including the current) that are ≤ the current value."""
    out = np.full(len(values), np.nan)
    for t in range(lookback - 1, len(values)):
        window = values[t - lookback + 1 : t + 1]
        if np.isfinite(window).all():
            out[t] = float(np.mean(window <= values[t]))
    return out


# --- Keltner and Donchian ---------------------------------------------------------------------------------


class KeltnerParams(DetectorParams):
    n: int = Field(default=20, ge=2, le=500)
    atr_n: int = Field(default=10, ge=2, le=500)
    mult: float = Field(default=2.0, gt=0, le=10)


class KeltnerBreakout(Detector):
    """First close outside the Keltner channel: EMA(``n``) ± ``mult`` × ATR(``atr_n``)."""

    id = "volatility.keltner"
    name = "Keltner channel breakout"
    family = Family.VOLATILITY_VOLUME
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = KeltnerParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        mid = ctx.ema_array(params.n)
        a = atr(ctx.high, ctx.low, ctx.close, params.atr_n).to_numpy()
        upper, lower = mid + params.mult * a, mid - params.mult * a
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            for sign, band in ((1, upper), (-1, lower)):
                if _first_close_beyond(ctx.c, band, t, sign):
                    beyond = abs(ctx.c[t] - band[t]) / max(float(a[t]), 1e-12)
                    out.append(
                        self.make(
                            ctx,
                            t,
                            _sign_dir(sign),
                            min(1.0, 0.5 + beyond),
                            key_levels=[KeyLevel("channel", float(band[t])), KeyLevel("mid", float(mid[t]))],
                            invalidation=float(mid[t]),
                        )
                    )
        return out


class DonchianParams(DetectorParams):
    n: int = Field(default=20, ge=2, le=1000)


class DonchianBreakout(Detector):
    """First close above the highest high (below the lowest low) of the previous ``n`` bars."""

    id = "volatility.donchian"
    name = "Donchian breakout"
    family = Family.VOLATILITY_VOLUME
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = DonchianParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        n = params.n
        hh = ctx.high.rolling(n, min_periods=n).max().shift(1).to_numpy()
        ll = ctx.low.rolling(n, min_periods=n).min().shift(1).to_numpy()
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            for sign, level, other in ((1, hh, ll), (-1, ll, hh)):
                if _first_close_beyond(ctx.c, level, t, sign):
                    out.append(
                        self.make(
                            ctx,
                            t,
                            _sign_dir(sign),
                            0.7,
                            key_levels=[KeyLevel(f"channel_{n}", float(level[t]))],
                            invalidation=float((level[t] + other[t]) / 2),
                            variant=f"n{n}",
                        )
                    )
        return out


# --- range expansion --------------------------------------------------------------------------------------


class ExpansionParams(DetectorParams):
    mult: float = Field(default=2.0, gt=1, le=10)  # true range vs the previous ATR
    close_zone: float = Field(default=0.3, gt=0, le=0.5)  # close within this share of the range's end


class AtrExpansion(Detector):
    """A range-expansion bar: true range ≥ ``mult`` × the previous bar's ATR, closing in the top (bullish) or
    bottom (bearish) ``close_zone`` of its range."""

    id = "volatility.atr_expansion"
    name = "Range expansion"
    family = Family.VOLATILITY_VOLUME
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = ExpansionParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        tr = ctx.memo(("true_range",), lambda: true_range(ctx.high, ctx.low, ctx.close).to_numpy())
        a = ctx.atr_array()
        out: list[Evidence] = []
        for t in range(1, ctx.n):
            rng = ctx.h[t] - ctx.l[t]
            if (
                not (np.isfinite(a[t - 1]) and np.isfinite(tr[t]) and rng > 0)
                or tr[t] < params.mult * a[t - 1]
            ):
                continue
            pos = (ctx.c[t] - ctx.l[t]) / rng
            sign = 1 if pos >= 1 - params.close_zone else (-1 if pos <= params.close_zone else 0)
            if sign == 0:
                continue
            out.append(
                self.make(
                    ctx,
                    t,
                    _sign_dir(sign),
                    min(1.0, tr[t] / (params.mult * a[t - 1]) * 0.6),
                    invalidation=float((ctx.h[t] + ctx.l[t]) / 2),
                    details={"tr_atr": round(float(tr[t] / a[t - 1]), 3)},
                )
            )
        return out


# --- tick volume ------------------------------------------------------------------------------------------


class VolumeParams(DetectorParams):
    n: int = Field(default=20, ge=2, le=500)
    spike: float = Field(default=2.5, gt=1, le=50)  # tick volume vs the mean of the previous n bars
    climax_move_atr: float = Field(default=3.0, gt=0, le=50)  # prior move for a climax
    climax_bars: int = Field(default=10, ge=2, le=200)


class TickVolumeSpike(Detector):
    """A tick-volume spike (≥ ``spike`` × the previous ``n`` bars' mean).

    ``climax``: the spike ends an extended move (≥ ``climax_move_atr`` × ATR over ``climax_bars``) and the bar
    closes off its extreme, in its far half (a selling climax after a decline is bullish). Otherwise
    ``spike``, in the direction of a bar that closes in its outer 30 %.
    """

    id = "volume.tick_spike"
    name = "Tick-volume spike/climax"
    family = Family.VOLATILITY_VOLUME
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = VolumeParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        ratio = ctx.memo(("volume_ratio", params.n), lambda: volume_ratio(ctx.volume, params.n).to_numpy())
        a = ctx.atr_array()
        out: list[Evidence] = []
        for t in range(params.climax_bars, ctx.n):
            rng = ctx.h[t] - ctx.l[t]
            if not (np.isfinite(ratio[t]) and ratio[t] >= params.spike and rng > 0 and np.isfinite(a[t])):
                continue
            pos = (ctx.c[t] - ctx.l[t]) / rng
            move = ctx.c[t - 1] - ctx.c[t - params.climax_bars]
            q = min(1.0, 0.4 + 0.2 * ratio[t] / params.spike)
            if move <= -params.climax_move_atr * a[t] and pos >= 0.5:
                sign, kind = 1, "climax"  # selling climax: heavy volume, closed off the lows
            elif move >= params.climax_move_atr * a[t] and pos <= 0.5:
                sign, kind = -1, "climax"
            elif pos >= 0.7:
                sign, kind = 1, "spike"
            elif pos <= 0.3:
                sign, kind = -1, "spike"
            else:
                continue
            out.append(
                self.make(
                    ctx,
                    t,
                    _sign_dir(sign),
                    q,
                    invalidation=float(ctx.l[t] if sign > 0 else ctx.h[t]),
                    details={"volume_ratio": round(float(ratio[t]), 3)},
                    variant=kind,
                )
            )
        return out


# --- session VWAP -----------------------------------------------------------------------------------------


class VwapParams(DetectorParams):
    min_bars: int = Field(default=3, ge=1, le=500)  # VWAP is unstable at the start of a session


def session_vwap(ctx: EvidenceContext) -> FloatArray:
    """Tick-volume-weighted typical price, reset at each trading day (``evidence.session_timezone``)."""

    def compute() -> FloatArray:
        keys = period_keys(ctx, "day")
        tp = (ctx.h + ctx.l + ctx.c) / 3
        v = np.where(np.isfinite(ctx.v), ctx.v, np.nan)
        out = np.full(ctx.n, np.nan)
        start = 0
        for t in range(ctx.n):
            if t > 0 and keys[t] != keys[t - 1]:
                start = t
            vol = v[start : t + 1]
            if np.isfinite(vol).all() and vol.sum() > 0:
                out[t] = float(np.dot(tp[start : t + 1], vol) / vol.sum())
        return out

    return ctx.memo(("session_vwap",), compute)


class SessionVwap(Detector):
    """The close crossing the session VWAP: ``reclaim`` (back above, bullish) or ``loss`` (below, bearish).
    Ignored in the first ``min_bars`` bars of a session."""

    id = "volume.session_vwap"
    name = "Session VWAP cross"
    family = Family.VOLATILITY_VOLUME
    tier = Tier.T1
    Params: ClassVar[type[DetectorParams]] = VwapParams

    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        vwap = session_vwap(ctx)
        keys = period_keys(ctx, "day")
        out: list[Evidence] = []
        start = 0
        for t in range(1, ctx.n):
            if keys[t] != keys[t - 1]:
                start = t
                continue
            if t - start < params.min_bars:
                continue
            for sign in (1, -1):
                if _first_close_beyond(ctx.c, vwap, t, sign):
                    out.append(
                        self.make(
                            ctx,
                            t,
                            _sign_dir(sign),
                            0.6,
                            key_levels=[KeyLevel("vwap", float(vwap[t]))],
                            invalidation=float(vwap[t]),
                            variant="reclaim" if sign > 0 else "loss",
                        )
                    )
        return out
