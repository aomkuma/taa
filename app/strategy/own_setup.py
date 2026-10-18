"""Setup OWN, F1 CONF-72: the owner's gold scalp on M1 (docs/OWN_SETUP.md; owner, 2026-10-18: "F1 + a stop
of at least 0.5 M15 ATR").

The rule exactly as frozen and tested in the research (research/2026-10-18-moments/agents/journal/build.py
and rules.py ``B0``, agents/portfolio/plib.py ``MENU`` C4 + C5, shadow/stop_floor.py; reference trades in
shadow/f1_port_ref.py), decided at the close of an M1 bar inside the windows (UTC 00-02, 07-12, 12-17):

- **Tide:** the last closed H1 bar's EMA(20) above its value three bars earlier and the close above the
  EMA(50) (a SELL mirrored).
- **At a level:** the nearest of six levels below the close (a SELL: above) - today's broker-day low and the
  Asian (UTC 00-07) low as of ``level_lag_bars`` bars earlier, yesterday's broker-day low, the round number,
  the M15 and H1 chart-read levels - lies within ``level_max_atr`` M1 ATR, and the last five bars came within
  one ATR of it.
- **Price action:** an M1 or M5 hammer, an M1 engulfing bar, or a sweep of the level reclaimed by the close.
- **Two of three M5 indicators:** RSI(14) rising under 50, the MACD(12, 26, 9) histogram rising, Stochastic
  %K(14, 3) crossing its %D(3) up (a SELL mirrored).
- **C4:** the 72-hour extreme in front (M1 bars -4320 .. -16) nearer than half the target, or behind.
- **C5:** not a fast tape: the M1 ATR under twice its median over the last day.
- **Plan:** the stop one M1 ATR beyond the level, 3-10 U from the entry (else no trade), then widened to at
  least 0.5 M15 ATR(14); the target 8 U (1 U = price / 4,100, the research's gold unit). The lane's position
  management adds the break-even at 0.6 of the target and the 60-bar time stop.

The M1 ATR keeps the research's bar range: the larger of high - low and |previous close - high|, averaged
over 14 bars. Every value comes from closed bars up to the decision bar (the H1 frame, the M1 window
resampled to M5 / M15, and the context map's chart reads at their last closed bar).
"""

from __future__ import annotations

import math
from datetime import datetime, time
from typing import ClassVar, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd
from pydantic import Field, field_validator, model_validator

from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.rules import entry_price, explain, hhmm, known, spread_price
from app.strategy.signal_models import (
    Condition,
    MarketContext,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)

ATHENS = ZoneInfo("Europe/Athens")  # FBS's broker day (EET/EEST), as the research's daily levels
ATR_BARS = 14
FloatArray = np.ndarray


class OwnConfParams(StrategyParams):
    windows: tuple[str, ...] = ("00:00-02:00", "07:00-12:00", "12:00-17:00")  # decision times, [start, end)
    window_zone: str = "UTC"  # the research measured the windows in UTC
    unit_price: float = Field(default=4100.0, gt=0, description="1 U = price / unit_price")
    target_u: float = Field(default=8.0, gt=0, le=100)
    stop_min_u: float = Field(default=3.0, gt=0, le=100)
    stop_max_u: float = Field(default=10.0, gt=0, le=200)
    stop_floor_m15_atr: float = Field(default=0.5, ge=0, le=5)
    level_max_atr: float = Field(default=3.0, gt=0, le=20)
    touch_atr: float = Field(default=1.0, gt=0, le=10)
    reclaim_atr: float = Field(default=0.1, ge=0, le=5)
    round_step: float = Field(default=50.0, gt=0)
    level_lag_bars: int = Field(default=15, ge=0, le=240)
    asia_end_hour_utc: int = Field(default=7, ge=1, le=12)
    room72_bars: int = Field(default=4305, ge=60, le=20_000)
    room72_lag: int = Field(default=16, ge=0, le=240)
    room72_share: float = Field(default=0.5, gt=0, le=5, description="of the target")
    atr_ratio_max: float = Field(default=2.0, gt=0, le=10)
    atr_median_bars: int = Field(default=1440, ge=100, le=10_000)
    min_indicators: int = Field(default=2, ge=0, le=3)
    # the round-number tilt (owner, 2026-10-18; agents/weapon4 Q3): F1's edge sits where its nearest level is
    # the round 50 (design +0.86 R v2 on 26 trades vs +0.19 R for all 139). Off the round 50 a trade is taken
    # at full size, at half the preset's risk, or skipped (F1R-b). At the minimum lot half is still 0.01.
    off_round: Literal["full", "half", "skip"] = "full"
    # v2 (owner, 2026-10-18; shadow/f1_improve.py X4, f1_v2_regime.py RM3): in a strong-volatility phase
    # (the M15 ATR >= ``regime_ratio`` x its median over ``regime_bars`` M15 bars) the trade runs: no 8 U
    # target, the break-even at ``runner_be_share`` of 8 U, a close beyond the level in front moves the stop
    # behind it (``runner_lock_atr`` M1 ATR) and from then on it trails one M15 ATR behind the best close;
    # else the fixed 8 U target, scratched after ``scratch_bars`` bars short of ``scratch_min_u`` U with the
    # close against it.
    exit_mode: Literal["fixed", "regime"] = "fixed"
    regime_ratio: float = Field(default=1.3, gt=0, le=10)
    regime_bars: int = Field(default=288, ge=100, le=1000)
    runner_be_share: float = Field(default=0.6, gt=0, le=2)
    runner_lock_atr: float = Field(default=0.5, ge=0, le=10)
    runner_cap_u: float = Field(
        default=40.0, gt=0, le=200, description="a runner's take-profit past the level"
    )
    fixed_hold_bars: int = Field(default=60, ge=1, le=1440)
    scratch_bars: int | None = Field(default=None, ge=1, le=240)
    scratch_min_u: float = Field(default=2.0, ge=0, le=50)

    @field_validator("windows")
    @classmethod
    def _check_windows(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("windows: at least one window")
        for w in value:
            start, sep, end = w.partition("-")
            if not sep or hhmm(start) >= hhmm(end):
                raise ValueError(f"windows: {w!r} is not 'HH:MM-HH:MM' with start < end")
        return value

    @field_validator("window_zone")
    @classmethod
    def _check_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"window_zone: unknown time zone {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _coherent(self) -> OwnConfParams:
        if self.stop_min_u >= self.stop_max_u:
            raise ValueError("stop_min_u must be < stop_max_u")
        if self.runner_cap_u <= self.target_u:
            raise ValueError("runner_cap_u must be beyond target_u (it tells a runner from a fixed target)")
        return self


def in_windows(at: datetime, windows: tuple[str, ...], zone: str) -> bool:
    """Weekday *at* (in *zone*) inside one of the ``HH:MM-HH:MM`` windows, start inclusive, end exclusive."""
    local = at.astimezone(ZoneInfo(zone))
    now = local.time()
    if local.weekday() > 4:
        return False
    for w in windows:
        start, _, end = w.partition("-")
        if hhmm(start) <= now < hhmm(end):
            return True
    return False


def m1_atr(high: FloatArray, low: FloatArray, close: FloatArray) -> FloatArray:
    """The research's M1 ATR (journal/build.py): the mean over 14 bars of max(high - low, |previous close -
    high|)."""
    prev = np.r_[np.nan, close[:-1]]
    rng = np.fmax(high - low, np.abs(prev - high))
    out = pd.Series(rng).rolling(ATR_BARS).mean().to_numpy()
    return np.asarray(out, dtype=float)


def hammer(o: float, h: float, lo: float, c: float, sign: int) -> bool:
    """A pin bar with the trade: the tail against it at least half the range, the close in the far third."""
    rng = max(h - lo, 1e-12)
    pos = (c - lo) / rng
    if sign > 0:
        return (min(o, c) - lo) / rng >= 0.5 and pos >= 2 / 3
    return (h - max(o, c)) / rng >= 0.5 and pos <= 1 / 3


def resample(m1: pd.DataFrame, minutes: int, at: datetime) -> pd.DataFrame:
    """The M1 window as *minutes* bars (bins by open time, as the research's ``resample(label="left")``), only
    the bins closed by *at*."""
    opens = pd.DatetimeIndex(m1["open_time"])
    key = opens.floor(f"{minutes}min")
    bars = (
        m1[["open", "high", "low", "close"]]
        .groupby(key)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    )
    closes = bars.index + pd.Timedelta(minutes=minutes)
    return bars[closes <= pd.Timestamp(at)]


def m5_votes(m5: pd.DataFrame, sign: int) -> tuple[bool, bool, bool, str] | None:
    """RSI(14) rising under 50, the MACD histogram rising, Stochastic %K crossing %D, all on the last closed
    M5 bar the trade's way (research formulas: Wilder RSI as ``ewm(alpha=1/14)``, %K smoothed over 3)."""
    if len(m5) < 40:
        return None
    c = m5["close"]
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14).mean()
    down = (-d.clip(upper=0)).ewm(alpha=1 / 14).mean()
    rsi = 100 - 100 / (1 + up / down)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    lo14, hi14 = m5["low"].rolling(14).min(), m5["high"].rolling(14).max()
    k = (100 * (c - lo14) / (hi14 - lo14)).rolling(3).mean()
    dk = k.rolling(3).mean()
    r, r0 = float(rsi.iloc[-1]), float(rsi.iloc[-2])
    h, h0 = float(hist.iloc[-1]), float(hist.iloc[-2])
    k1, k0, d1, d0 = float(k.iloc[-1]), float(k.iloc[-2]), float(dk.iloc[-1]), float(dk.iloc[-2])
    if sign > 0:
        rsi_ok = r - r0 > 0 and r < 50
        stoch_ok = k1 > d1 and k0 <= d0
    else:
        rsi_ok = r - r0 < 0 and r > 50
        stoch_ok = k1 < d1 and k0 >= d0
    macd_ok = (h - h0) * sign > 0
    return (
        rsi_ok,
        macd_ok,
        stoch_ok,
        f"RSI {r:.1f} ({r - r0:+.1f}), hist {h - h0:+.3g}, %K {k1:.0f} / %D {d1:.0f}",
    )


def m15_atr(m15: pd.DataFrame) -> float | None:
    """ATR(14) of the closed M15 bars: the mean true range (the stop floor's, shadow/stop_floor.py)."""
    series = m15_atrs(m15)
    if not len(series):
        return None
    value = float(series[-1])
    return value if math.isfinite(value) and value > 0 else None


def m15_atrs(m15: pd.DataFrame) -> FloatArray:
    """ATR(14) after every closed M15 bar that has 14 true ranges behind it."""
    if len(m15) < ATR_BARS + 1:
        return np.empty(0)
    h, lo, c = (m15[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    prev = c[:-1]
    tr = np.fmax(h[1:] - lo[1:], np.fmax(np.abs(h[1:] - prev), np.abs(lo[1:] - prev)))
    return np.convolve(tr, np.full(ATR_BARS, 1 / ATR_BARS), mode="valid")


def strong_phase(atrs: FloatArray, bars: int, ratio: float) -> bool | None:
    """The last M15 ATR at least *ratio* x the median of the last *bars* of them (None: under 100)."""
    tail = atrs[-bars:]
    if len(tail) < 100:
        return None
    return bool(tail[-1] >= ratio * float(np.median(tail)))


def h1_tide(h1: pd.DataFrame) -> int:
    """+1 / -1 when the last closed H1 bar's EMA(20) rose / fell over three bars with the close above / below
    the EMA(50); 0 otherwise (or not enough bars)."""
    if len(h1) < 60:
        return 0
    c = h1["close"].astype(float)
    e20 = c.ewm(span=20, adjust=False).mean().to_numpy()
    e50 = c.ewm(span=50, adjust=False).mean().to_numpy()
    rng = float((h1["high"] - h1["low"]).astype(float).iloc[-ATR_BARS:].mean())
    if not (math.isfinite(rng) and rng > 0):
        return 0
    slope, above = (e20[-1] - e20[-4]) / rng, (float(c.iloc[-1]) - e50[-1]) / rng
    if slope > 0 and above > 0:
        return 1
    if slope < 0 and above < 0:
        return -1
    return 0


def _day_start(at: pd.Timestamp, zone: ZoneInfo) -> pd.Timestamp:
    local = at.tz_convert(zone)
    midnight = datetime.combine(local.date(), time(0), tzinfo=zone)
    return pd.Timestamp(midnight).tz_convert("UTC")


def _extreme(values: FloatArray, sign: int) -> float:
    """The low (a BUY's level side) or the high (a SELL's) of *values*; NaN when empty."""
    if not len(values):
        return math.nan
    return float(values.min() if sign > 0 else values.max())


def daily_levels(
    opens: pd.DatetimeIndex, low: FloatArray, high: FloatArray, p: OwnConfParams, sign: int
) -> dict[str, float]:
    """Today's broker-day extreme and the Asian extreme as of ``level_lag_bars`` bars before the decision bar,
    and yesterday's broker-day extreme (the side the trade stands on: lows for a BUY)."""
    n = len(opens)
    last, q = n - 1, n - 1 - p.level_lag_bars
    side = low if sign > 0 else high
    out = {"today": math.nan, "yesterday": math.nan, "asia": math.nan}
    today = int(opens.searchsorted(_day_start(opens[last], ATHENS)))
    if q >= today:
        out["today"] = _extreme(side[today : q + 1], sign)
    if today > 0:
        start = int(opens.searchsorted(_day_start(opens[today - 1], ATHENS)))
        if start > 0:  # the window holds the whole previous broker day
            out["yesterday"] = _extreme(side[start:today], sign)
    if q >= 0:
        utc_day = opens[q].normalize()
        if utc_day == opens[last].normalize():
            first = int(opens.searchsorted(utc_day))
            asia_end = int(opens.searchsorted(utc_day + pd.Timedelta(hours=p.asia_end_hour_utc)))
            out["asia"] = _extreme(side[first : min(q + 1, asia_end)], sign)
    return out


def read_level(market: MarketContext, tf: str, close: float, sign: int) -> float:
    """The nearest chart-read level of the *tf* context map below (BUY) / above (SELL) *close*, else NaN."""
    m = None if market.htf is None else market.htf.frames.get(tf)
    if m is None or m.read is None:
        return math.nan
    prices = [lv.price for lv in m.read.levels if (close - lv.price) * sign > 0]
    if not prices:
        return math.nan
    return float(max(prices) if sign > 0 else min(prices))


class OwnConf72(BaseStrategy):
    name = "setup_own_conf72"
    version = "1.0.0"
    description = (
        "Setup OWN F1 CONF-72: H1 tide, a level, price action and two of three M5 indicators, near the "
        "72-hour extreme; M1 gold. Lane only. Unproven."
    )
    Params = OwnConfParams
    advised = False
    LEVEL_KINDS: ClassVar[tuple[str, ...]] = ("today", "yesterday", "asia", "round", "M15", "H1")

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.M1, Timeframe.H1)

    def warmup_bars(self) -> int:
        p: OwnConfParams = self.params
        need = max(p.room72_bars + p.room72_lag, p.atr_median_bars + ATR_BARS) + 1
        if p.exit_mode == "regime":
            need = max(need, (p.regime_bars + ATR_BARS + 1) * 15)
        return need

    def evaluate(self, ctx: StrategyContext) -> Signal:
        p: OwnConfParams = self.params
        market = ctx.market
        at = market.decision_time_utc
        if market.entry_timeframe is not Timeframe.M1:
            return self.hold(ctx, ReasonCode.DATA_QUALITY, explanation="the setup runs on an M1 lane")
        if not in_windows(at, p.windows, p.window_zone):
            return self.hold(ctx, ReasonCode.OUTSIDE_SESSION, explanation=f"{at:%a %H:%M} UTC")
        m1 = ctx.frame(Timeframe.M1)
        if len(m1) < self.warmup_bars():
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, explanation=f"{len(m1)} M1 bars")
        o, h, lo, c = (m1[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        atr = m1_atr(h, lo, c)
        atr1, close = float(atr[-1]), float(c[-1])
        median = float(np.nanmedian(atr[-p.atr_median_bars :]))
        if not known(atr1, median, close) or atr1 <= 0 or median <= 0:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, explanation="M1 ATR not ready")
        sign = h1_tide(ctx.frame(Timeframe.H1))
        if sign == 0:
            cond = Condition("h1_tide", False, 1.0, "H1 EMA(20) slope and close vs EMA(50) disagree")
            return self.hold(ctx, ReasonCode.NO_BIAS, conditions=[cond], explanation=explain([cond]))
        unit = close / p.unit_price
        conds = [Condition("h1_tide", True, 1.0, "BUY" if sign > 0 else "SELL")]
        ratio = atr1 / median
        conds.append(Condition("not_fast_tape", ratio < p.atr_ratio_max, 1.0, f"M1 ATR {ratio:.2f} x median"))
        conds.append(self._room72(h, lo, close, unit, sign))
        level, kind, level_cond = self._level(m1, market, h, lo, close, atr1, sign)
        conds.append(level_cond)
        if p.off_round == "skip" and kind != "round":
            conds.append(
                Condition("round_level", False, 1.0, f"the nearest level is {kind}, not the round 50")
            )
        if not all(x.passed for x in conds):
            return self.hold(ctx, ReasonCode.NO_SETUP, conditions=conds, explanation=explain(conds))
        m5 = resample(m1, 5, at)
        conds.append(self._price_action(o, h, lo, c, m5, level, atr1, sign))
        votes = m5_votes(m5, sign)
        if votes is None:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds, explanation="M5 not ready")
        count = sum(votes[:3])
        conds.append(Condition("m5_indicators", count >= p.min_indicators, 1.0, f"{count} of 3: {votes[3]}"))
        if not all(x.passed for x in conds):
            return self.hold(ctx, ReasonCode.NO_SETUP, conditions=conds, explanation=explain(conds))
        return self._plan(ctx, m1, conds, level, kind, atr1, unit, sign)

    def _room72(self, h: FloatArray, lo: FloatArray, close: float, unit: float, sign: int) -> Condition:
        p: OwnConfParams = self.params
        end = len(h) - p.room72_lag
        window = (h if sign > 0 else lo)[end - p.room72_bars : end]
        front = float(window.max() if sign > 0 else window.min())
        room = (front - close) * sign
        limit = p.room72_share * p.target_u * unit
        return Condition("room72", room < limit, 1.0, f"72-h extreme {room:+.2f} ahead (< {limit:.2f})")

    def _level(
        self,
        m1: pd.DataFrame,
        market: MarketContext,
        h: FloatArray,
        lo: FloatArray,
        close: float,
        atr1: float,
        sign: int,
    ) -> tuple[float, str, Condition]:
        p: OwnConfParams = self.params
        found = daily_levels(pd.DatetimeIndex(m1["open_time"]), lo, h, p, sign)
        step = p.round_step
        found["round"] = math.floor(close / step) * step if sign > 0 else math.ceil(close / step) * step
        found["M15"] = read_level(market, "M15", close, sign)
        found["H1"] = read_level(market, "H1", close, sign)
        best, kind = math.inf, ""
        for name in self.LEVEL_KINDS:  # the research's order breaks ties
            gap = (close - found[name]) * sign
            if math.isfinite(gap) and 0 < gap < best:
                best, kind = gap, name
        if not math.isfinite(best):
            return math.nan, "", Condition("at_level", False, 2.0, "no level on the trade's side")
        level = close - sign * best
        touch = float((lo[-5:].min() - level) if sign > 0 else (level - h[-5:].max()))
        ok = best <= p.level_max_atr * atr1 and touch <= p.touch_atr * atr1
        detail = (
            f"{kind} {level:.2f}, {best / atr1:.2f} ATR away, last 5 bars {touch / atr1:+.2f} ATR from it"
        )
        return level, kind, Condition("at_level", ok, 2.0, detail)

    def _price_action(
        self,
        o: FloatArray,
        h: FloatArray,
        lo: FloatArray,
        c: FloatArray,
        m5: pd.DataFrame,
        level: float,
        atr1: float,
        sign: int,
    ) -> Condition:
        p: OwnConfParams = self.params
        found = []
        if hammer(o[-1], h[-1], lo[-1], c[-1], sign):
            found.append("M1 hammer")
        if len(m5):
            b = m5.iloc[-1]
            if hammer(float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"]), sign):
                found.append("M5 hammer")
        if (c[-2] - o[-2]) * sign < 0 and (c[-1] - o[-2]) * sign > 0 and (c[-1] - o[-1]) * sign > 0:
            found.append("M1 engulfing")
        swept = float(lo[-3:].min() if sign > 0 else h[-3:].max())
        if (level - swept) * sign >= p.reclaim_atr * atr1 and (c[-1] - level) * sign > 0:
            found.append("sweep and reclaim")
        return Condition("price_action", bool(found), 1.0, ", ".join(found) or "none")

    def _plan(
        self,
        ctx: StrategyContext,
        m1: pd.DataFrame,
        conds: list[Condition],
        level: float,
        kind: str,
        atr1: float,
        unit: float,
        sign: int,
    ) -> Signal:
        p: OwnConfParams = self.params
        market = ctx.market
        costs = spread_price(ctx, m1.iloc[-1])
        if costs is None:
            return self.hold(ctx, ReasonCode.DATA_QUALITY, conditions=conds, explanation="no spread")
        entry = entry_price(market, float(m1["close"].iloc[-1]), costs[1], sign > 0)
        stop_dist = (entry - (level - sign * atr1)) * sign
        lo_u, hi_u = p.stop_min_u * unit, p.stop_max_u * unit
        sized = Condition(
            "stop_range", lo_u <= stop_dist <= hi_u, 1.0, f"{stop_dist:.2f} in {lo_u:.2f}..{hi_u:.2f}"
        )
        conds.append(sized)
        if not sized.passed:
            reason = ReasonCode.SL_TOO_FAR if stop_dist > hi_u else ReasonCode.NO_SETUP
            return self.hold(ctx, reason, conditions=conds, explanation=explain(conds))
        a15 = m15_atr(resample(m1, 15, market.decision_time_utc))
        if a15 is None:
            return self.hold(
                ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds, explanation="M15 ATR not ready"
            )
        stop_dist = max(stop_dist, p.stop_floor_m15_atr * a15)
        take_profit = entry + sign * p.target_u * unit
        note = f"{kind} level {level:.2f}; stop {stop_dist:.2f} (M15 ATR {a15:.2f}), target 8 U"
        if p.exit_mode == "regime":
            strong = strong_phase(
                m15_atrs(resample(m1, 15, market.decision_time_utc)), p.regime_bars, p.regime_ratio
            )
            if strong:
                front = self._front(m1, market, float(m1["close"].iloc[-1]), sign)
                anchor = front if (front - entry) * sign > 0 else entry
                take_profit = anchor + sign * p.runner_cap_u * (entry / p.unit_price)
                note = (
                    f"{kind} level {level:.2f}; stop {stop_dist:.2f}; strong phase: a runner past {front:.2f}"
                )
        scale = 0.5 if p.off_round == "half" and kind != "round" else 1.0
        if scale < 1.0:
            note += "; half size off the round 50"
        action = Action.BUY if sign > 0 else Action.SELL
        return self.entry(
            ctx,
            action,
            entry_price=entry,
            stop_loss=entry - sign * stop_dist,
            take_profit=take_profit,
            conditions=conds,
            score=60.0,
            explanation=f"{explain(conds)}; {note}",
            risk_scale=scale,
        )

    def _front(self, m1: pd.DataFrame, market: MarketContext, close: float, sign: int) -> float:
        """The nearest of the six level kinds in front of the trade (the research's ``room``), else NaN."""
        p: OwnConfParams = self.params
        lo, h = m1["low"].to_numpy(dtype=float), m1["high"].to_numpy(dtype=float)
        found = daily_levels(pd.DatetimeIndex(m1["open_time"]), lo, h, p, -sign)
        step = p.round_step
        found["round"] = math.ceil(close / step) * step if sign > 0 else math.floor(close / step) * step
        found["M15"] = read_level(market, "M15", close, -sign)
        found["H1"] = read_level(market, "H1", close, -sign)
        gaps = [(v - close) * sign for v in found.values()]
        room = min((g for g in gaps if math.isfinite(g) and g > 0), default=math.nan)
        return close + sign * room

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        """v2's exits, read back from the position alone (restart-safe): a take-profit past the 8 U target is
        a runner whose level in front sits ``runner_cap_u`` U inside it (none: the anchor is the entry)."""
        p: OwnConfParams = self.params
        if p.exit_mode == "fixed" and p.scratch_bars is None:
            return None  # v1: the lane's break-even and time stop do it all
        m1 = ctx.frames.get(Timeframe.M1)
        if m1 is None or pos.tp is None or ctx.spec is None:
            return None
        sign = 1 if pos.side is Side.BUY else -1
        unit = pos.entry / p.unit_price
        opens = pd.DatetimeIndex(m1["open_time"])
        start = int(opens.searchsorted(pd.Timestamp(pos.entry_time).floor("min")))
        held = len(m1) - start
        if held <= 0 or start < 15 * (ATR_BARS + 1):
            return None
        spread = m1["spread"].to_numpy(dtype=float)[start:] * ctx.spec.point
        h, lo, c = (m1[k].to_numpy(dtype=float)[start:] for k in ("high", "low", "close"))
        best = float(((h - pos.entry) if sign > 0 else (pos.entry - lo - spread)).max())
        marks = c + (spread if sign < 0 else 0.0)  # the price a position closes at: bid (BUY) / ask (SELL)
        if (pos.tp - pos.entry) * sign <= 0.5 * (p.target_u + p.runner_cap_u) * unit:
            return self._fixed(pos, sign, unit, held, best, float(marks[-1]))
        return self._runner(m1.iloc[:start], pos, pos.tp, sign, unit, best, marks)

    def _fixed(
        self, pos: OpenPosition, sign: int, unit: float, held: int, best: float, mark: float
    ) -> PositionAdvice | None:
        p: OwnConfParams = self.params
        if held >= p.fixed_hold_bars:
            return PositionAdvice(close=ExitReason.TIME_STOP, note=f"held {held} bars")
        if held == p.scratch_bars and best < p.scratch_min_u * unit and (mark - pos.entry) * sign < 0:
            return PositionAdvice(close=ExitReason.SIGNAL, note=f"scratch: best {best:.2f} after {held} bars")
        return None

    def _runner(
        self,
        before: pd.DataFrame,
        pos: OpenPosition,
        tp: float,
        sign: int,
        unit: float,
        best: float,
        marks: FloatArray,
    ) -> PositionAdvice | None:
        """Break-even at 0.6 of 8 U; once a close is beyond the level in front, the stop behind the level and
        then one M15 ATR (as of the entry) behind the best close since."""
        p: OwnConfParams = self.params
        h, lo, c = (before[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
        atr1 = float(m1_atr(h, lo, c)[-1])
        a15 = m15_atr(resample(before, 15, pd.Timestamp(before.index[-1]).to_pydatetime()))
        level = tp - sign * p.runner_cap_u * unit
        stops: list[tuple[float, ExitReason, str]] = []
        if best >= p.runner_be_share * p.target_u * unit:
            stops.append((pos.entry, ExitReason.BREAK_EVEN, "break-even"))
        has_level = (level - pos.entry) * sign > 1e-9
        beyond = np.flatnonzero((marks - level) * sign > 0) if has_level else np.empty(0, dtype=int)
        if len(beyond) and known(atr1):
            stops.append(
                (level - sign * p.runner_lock_atr * atr1, ExitReason.TRAILING_STOP, "behind the level")
            )
            if a15 is not None:
                tail = marks[int(beyond[0]) :]
                top = float(tail.max() if sign > 0 else tail.min())
                stops.append(
                    (top - sign * a15, ExitReason.TRAILING_STOP, "one M15 ATR behind the best close")
                )
        if not stops:
            return None
        price, kind, note = max(stops, key=lambda x: x[0] * sign)
        if (price - pos.sl) * sign <= 0:
            return None
        return PositionAdvice(new_sl=price, stop_kind=kind, note=note)
