"""Setup OWN PLAN-1, Asia B2: a chart pattern at the owner's H1 level, confirmed by a pullback and a new
close, in the Asia window 07:00-09:00 Thai (docs/PLAN1_LANE.md; ported 1:1 from
research/2026-10-18-moments/agents/dev: patterns.py, p2_trades.py ``confirm_b`` / ``structure_exit_time``,
p3_trades.py setting ``B2``, p4_trades.py ``window_of``; precursors/zones.py ``levels_at``;
journal/rules_week.py's week-6 rule).

Per entry timeframe (M1: :class:`Plan1B2`, M5: :class:`Plan1B2M5` - two strategies so that a position's own
timeframe is known from its magic number after a restart), at the close of each of its bars:

1. **Swings:** a causal ATR ZigZag (a swing = 2 x the TF's MT5 ATR(14)) on the TF's bars built from M1.
2. **Patterns** breaking out at bar d (both sides, sells by the mirror): inverse H&S / H&S, W / M (and the one
   whose second low swept the first), the sweep then the higher low / lower high, a base then its break; no
   taller than 4 x ATR; the stop 0.2 ATR beyond the pattern's extreme.
3. **At a level:** the owner's H1 levels known at d's close (zones of 3+ or flipped H1 fractal swings, of 2
   swings, the five-day high / low, the previous server day's high / low, the latest swing top above / low
   below), the extreme within 0.1 H1 ATR of a level, or past it by at most 0.5 H1 ATR with the close back (a
   sweep; the sweep-turn needs it), or the base overlapping the zone; the nearest level wins.
4. **Confirmation (B):** after bar d, a pullback of 1 ATR from the post-breakout high, then the first close
   above that high, within 30 bars; none if a low reaches the extreme first. The entry is at that close,
   inside the Asia window; the candidate with the smallest risk (close to stop) wins.
5. **Week 6:** a second B2 trade of the Thai morning only in the first one's direction. The day's B2 entries
   are handed over by the engine from its stored decisions (:meth:`attach_entries`), so the rule survives a
   restart.
6. **Exits:** the target is the next level beyond the entry if it is more than one risk away (else only a far
   cap); the structure exit at the first TF bar closing beyond the last confirmed swing low (a buy) / high (a
   sell); out after 60 TF bars.

Every value comes from bars closed by the decision. The ZigZag starts at the window's start: on P1 / P2 its
structure equals the full-history one at every one of 600 sampled bars (dev/plan1_b2_parity.py).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd
from pydantic import Field, field_validator

from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy.base_strategy import BaseStrategy, PastEntry, StrategyParams
from app.strategy.plan1 import (
    atr_detail,
    h1_atr_at,
    h4_change_at,
    pools,
    pools_detail,
    regime,
    spread_detail,
)
from app.strategy.rules import explain, hhmm
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)

FloatArray = np.ndarray
NS_MIN = 60 * 10**9
ATHENS = ZoneInfo("Europe/Athens")

# patterns.py (frozen)
ZZ_K = 2.0
HEAD_ATR, SHOULDER_H, NECK_H = 0.5, 0.5, 0.5
EQ_ATR, EQ_H = 0.5, 0.15
SWEEP_W_H = 0.35
SPAN = {"ihs": 60, "w": 40, "st": 40}
BASE_MIN, BASE_MAX, BASE_W = 8, 40, 1.5
STOP_ATR = 0.2
ZONE_H1, SWEEP_H1 = 0.1, 0.5
HEIGHT_ATR = 4.0
SELL_NAMES = {
    "W": "M",
    "W, the 2nd low swept the 1st": "M, the 2nd high swept the 1st",
    "inverse H&S": "H&S",
    "sweep, higher low": "sweep, lower high",
}
SELL_LABELS = {"L1": "H1", "L2": "H2", "P": "T", "HL": "LH"}
NAMES = {
    ("ihs", 1): "inverse H&S",
    ("ihs", -1): "H&S",
    ("w", 1): "W",
    ("w", -1): "M",
    ("st", 1): "sweep, higher low",
    ("st", -1): "sweep, lower high",
    ("base", 1): "base, break up",
    ("base", -1): "base, break down",
}
# zones.py (frozen)
H1_K, WIN, TOL_ATR = 2, 120, 0.25
ORDER = ("x3+ / flip", "x2", "5d high", "5d low", "PDH", "PDL", "last top", "last low")


# --- bars, ATR, ZigZag --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Bars:
    t_open: np.ndarray  # int64 ns
    avail: np.ndarray  # int64 ns: when the bar is complete
    o: FloatArray
    h: FloatArray
    lo: FloatArray
    c: FloatArray


def tf_bars(
    opens: pd.DatetimeIndex,
    o: FloatArray,
    h: FloatArray,
    lo: FloatArray,
    c: FloatArray,
    minutes: int,
    t: pd.Timestamp,
) -> Bars:
    """patterns.tf_bars: bars of *minutes* from M1 on the clock (avail = open + minutes), only those
    complete by *t*."""
    if minutes == 1:
        key = opens
        df = pd.DataFrame({"o": o, "h": h, "lo": lo, "c": c}, index=opens)
    else:
        key = opens.floor(f"{minutes}min")
        g = pd.DataFrame({"o": o, "h": h, "lo": lo, "c": c}, index=opens).groupby(key, sort=True)
        df = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "lo": g.lo.min(), "c": g.c.last()})
    idx = pd.DatetimeIndex(df.index)
    t_open = idx.as_unit("ns").to_numpy(dtype="datetime64[ns]").astype(np.int64)
    avail = t_open + minutes * NS_MIN
    keep = avail <= pd.Timestamp(t).as_unit("ns").value
    return Bars(
        t_open[keep],
        avail[keep],
        df.o.to_numpy(float)[keep],
        df.h.to_numpy(float)[keep],
        df.lo.to_numpy(float)[keep],
        df.c.to_numpy(float)[keep],
    )


def mt5_atr(h: FloatArray, lo: FloatArray, c: FloatArray, n: int = 14) -> FloatArray:
    """foundation.atr: the simple average of n true ranges; bar 0 has no previous close (NaN)."""
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(lo, pc)
    if len(tr):
        tr[0] = np.nan
    return np.asarray(pd.Series(tr).rolling(n).mean().to_numpy(), float)


@dataclass(frozen=True)
class Pivots:
    b: np.ndarray  # bar
    p: FloatArray  # price
    k: np.ndarray  # +1 peak, -1 trough
    conf: np.ndarray  # the bar that confirmed it

    def mirror(self) -> Pivots:
        return Pivots(self.b, -self.p, -self.k, self.conf)


def zigzag(h: FloatArray, lo: FloatArray, atr: FloatArray, k: float = ZZ_K) -> Pivots:
    """patterns.zigzag: the causal ATR ZigZag (each bar reads bars <= it)."""
    piv: list[tuple[int, float, int, int]] = []
    fin = np.isfinite(atr)
    if not fin.any():
        e = np.empty(0, int)
        return Pivots(e, np.empty(0), e, e)
    i0 = int(np.argmax(fin))
    hi_i = lo_i = ext = i0
    direction = 0
    for i in range(i0, len(h)):
        thr = k * atr[i]
        if not np.isfinite(thr):
            continue
        if direction == 0:
            if h[i] > h[hi_i]:
                hi_i = i
            if lo[i] < lo[lo_i]:
                lo_i = i
            if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr:
                if lo_i < hi_i:
                    piv.append((lo_i, float(lo[lo_i]), -1, i))
                    direction, ext = 1, hi_i
                else:
                    piv.append((hi_i, float(h[hi_i]), 1, i))
                    direction, ext = -1, lo_i
        elif direction == 1:
            if h[i] >= h[ext]:
                ext = i
            elif h[ext] - lo[i] >= thr:
                piv.append((ext, float(h[ext]), 1, i))
                direction, ext = -1, i
        else:
            if lo[i] <= lo[ext]:
                ext = i
            elif h[i] - lo[ext] >= thr:
                piv.append((ext, float(lo[ext]), -1, i))
                direction, ext = 1, i
    a = np.array(piv, dtype=float).reshape(-1, 4)
    return Pivots(a[:, 0].astype(int), a[:, 1], a[:, 2].astype(int), a[:, 3].astype(int))


Swing = tuple[int, float, int, bool]


def structure(piv: Pivots, h: FloatArray, lo: FloatArray, d: int, keep: int = 6) -> list[Swing]:
    """patterns.structure: the last *keep* pivots confirmed by d, then the running extreme since the last
    one."""
    n = int(np.searchsorted(piv.conf, d, side="right"))
    out: list[Swing] = [
        (int(piv.b[j]), float(piv.p[j]), int(piv.k[j]), False) for j in range(max(n - keep, 0), n)
    ]
    if n:
        last_b, last_k = int(piv.b[n - 1]), int(piv.k[n - 1])
        if last_b < d:
            if last_k == 1:
                j = last_b + 1 + int(np.argmin(lo[last_b + 1 : d + 1]))
                out.append((j, float(lo[j]), -1, True))
            else:
                j = last_b + 1 + int(np.argmax(h[last_b + 1 : d + 1]))
                out.append((j, float(h[j]), 1, True))
    return out


def m_structure(piv: Pivots, d: int) -> str:
    """patterns.m_structure: up / down / mixed from the last two confirmed troughs and peaks ('none' if
    fewer)."""
    n = int(np.searchsorted(piv.conf, d, side="right"))
    tr = piv.p[:n][piv.k[:n] == -1][-2:]
    pk = piv.p[:n][piv.k[:n] == 1][-2:]
    if len(tr) < 2 or len(pk) < 2:
        return "none"
    if tr[1] > tr[0] and pk[1] > pk[0]:
        return "up"
    if tr[1] < tr[0] and pk[1] < pk[0]:
        return "down"
    return "mixed"


def last_swing(piv: Pivots, b: int, kind: int) -> float:
    """p2_trades.last_pivot_prices at bar b: the price of the last pivot of *kind* confirmed by b (NaN if
    none)."""
    n = int(np.searchsorted(piv.conf, b, side="right"))
    x = piv.p[:n][piv.k[:n] == kind]
    return float(x[-1]) if len(x) else math.nan


# --- patterns -----------------------------------------------------------------------------------------------


def first_close_above(c: FloatArray, line: FloatArray, a: int, d: int) -> bool:
    return bool(c[d] > line[-1] and np.all(c[a:d] <= line[:-1]))


def find_buy(
    h: FloatArray, lo: FloatArray, c: FloatArray, atr: float, seq: list[Swing], d: int
) -> list[dict[str, Any]]:
    """patterns.find_buy: inverse H&S, W, the sweep then the higher low, breaking out at bar d."""
    if len(seq) < 3 or not np.isfinite(atr):
        return []
    k3 = len(seq) - 1 if seq[-1][2] == -1 else len(seq) - 2
    if k3 < 2 or seq[k3][2] != -1:
        return []
    t3, p2, t2 = seq[k3], seq[k3 - 1], seq[k3 - 2]
    out: list[dict[str, Any]] = []
    if first_close_above(c, np.full(d - t3[0] + 1, p2[1]), t3[0], d):
        hgt = p2[1] - min(t2[1], t3[1])
        eq = max(EQ_ATR * atr, EQ_H * hgt)
        base = dict(trigger=p2[1], height=hgt, start=t2[0])
        pts = [(t2[0], t2[1], "L1"), (p2[0], p2[1], "P"), (t3[0], t3[1], "L2")]
        if d - t2[0] <= SPAN["w"]:
            if abs(t3[1] - t2[1]) <= eq:
                out.append(
                    dict(
                        family="w",
                        variant="W",
                        extreme=min(t2[1], t3[1]),
                        higher_low=t3[1],
                        points=pts,
                        **base,
                    )
                )
            elif t2[1] - SWEEP_W_H * hgt <= t3[1] < t2[1] - eq:
                out.append(
                    dict(
                        family="w",
                        variant="W, the 2nd low swept the 1st",
                        extreme=t3[1],
                        higher_low=t3[1],
                        points=pts,
                        **base,
                    )
                )
        if d - t2[0] <= SPAN["st"] and t3[1] > t2[1] + eq:
            out.append(
                dict(
                    family="st",
                    variant="sweep, higher low",
                    extreme=t2[1],
                    higher_low=t3[1],
                    points=[(t2[0], t2[1], "S"), (p2[0], p2[1], "P"), (t3[0], t3[1], "HL")],
                    **base,
                )
            )
    if k3 >= 4:
        t1, p1 = seq[k3 - 4], seq[k3 - 3]
        if d - t1[0] <= SPAN["ihs"] and p2[0] > p1[0]:
            slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
            line = p1[1] + slope * (np.arange(t3[0], d + 1) - p1[0])
            hgt = p1[1] + slope * (t2[0] - p1[0]) - t2[1]
            if (
                t2[1] < min(t1[1], t3[1]) - HEAD_ATR * atr
                and abs(t1[1] - t3[1]) <= SHOULDER_H * hgt
                and abs(p2[1] - p1[1]) <= NECK_H * hgt
                and first_close_above(c, line, t3[0], d)
            ):
                out.append(
                    dict(
                        family="ihs",
                        variant="inverse H&S",
                        extreme=t2[1],
                        higher_low=t3[1],
                        trigger=float(line[-1]),
                        height=hgt,
                        start=t1[0],
                        points=[
                            (t1[0], t1[1], "LS"),
                            (p1[0], p1[1], "N1"),
                            (t2[0], t2[1], "Head"),
                            (p2[0], p2[1], "N2"),
                            (t3[0], t3[1], "RS"),
                        ],
                    )
                )
    return out


def find_base(h: FloatArray, lo: FloatArray, c: FloatArray, atr: FloatArray, d: int) -> list[dict[str, Any]]:
    """patterns.find_base: the longest run of 8 .. 40 bars ending at d - 1 within 1.5 x ATR(d - 1), broken
    at d."""
    if d - BASE_MIN < 0 or not np.isfinite(atr[d - 1]):
        return []
    w = BASE_W * atr[d - 1]
    best = None
    hi, low = -np.inf, np.inf
    for n in range(1, min(BASE_MAX, d) + 1):
        hi, low = max(hi, h[d - n]), min(low, lo[d - n])
        if hi - low > w:
            break
        if n >= BASE_MIN:
            best = (n, hi, low)
    if best is None:
        return []
    n, hi, low = best
    side = 1 if c[d] > hi else -1 if c[d] < low else 0
    if not side:
        return []
    return [
        dict(
            family="base",
            variant="base",
            side=side,
            extreme=low if side > 0 else hi,
            trigger=hi if side > 0 else low,
            height=hi - low,
            start=d - n,
            box=(d - n, d - 1, low, hi),
            higher_low=np.nan,
            points=[(d - n, low if side > 0 else hi, "base")],
        )
    ]


def unmirror(p: dict[str, Any]) -> dict[str, Any]:
    q = dict(p)
    for key in ("extreme", "trigger", "higher_low"):
        q[key] = -p[key]
    q["points"] = [(b, -x, SELL_LABELS.get(lab, lab)) for b, x, lab in p["points"]]
    q["side"] = -1
    q["variant"] = SELL_NAMES[p["variant"]]
    return q


def patterns_at(b: Bars, atr: FloatArray, piv: Pivots, d: int) -> list[dict[str, Any]]:
    """patterns.patterns_at: every pattern breaking out at bar d, both sides, no taller than 4 x ATR(d)."""
    out = [dict(p, side=1) for p in find_buy(b.h, b.lo, b.c, atr[d], structure(piv, b.h, b.lo, d), d)]
    mh, ml, mc, mp = -b.lo, -b.h, -b.c, piv.mirror()
    out += [unmirror(p) for p in find_buy(mh, ml, mc, atr[d], structure(mp, mh, ml, d), d)]
    out += find_base(b.h, b.lo, b.c, atr, d)
    out = [p for p in out if p["height"] <= HEIGHT_ATR * atr[d]]
    for p in out:
        p["stop"] = p["extreme"] - p["side"] * STOP_ATR * atr[d]
        p["d"] = d
        p["atr"] = float(atr[d])
    return out


def at_level(
    p: dict[str, Any], close: float, levels: Sequence[tuple[float, str]], z: float, sweep: float
) -> dict[str, Any] | None:
    """patterns.at_level: 'at', 'swept' or 'base' against the levels; the nearest to the extreme wins."""
    s, ext = p["side"], p["extreme"]
    best: dict[str, Any] | None = None
    for lv, kind in levels:
        how: str | None
        if p["family"] == "base":
            lo_b, hi_b = p["box"][2], p["box"][3]
            how = "base" if (lo_b <= lv + z and hi_b >= lv - z) else None
        else:
            past = s * (lv - ext) - z
            if abs(ext - lv) <= z:
                how = "at"
            elif 0 < past <= sweep and s * (close - (lv - s * z)) > 0:
                how = "swept"
            else:
                how = None
            if p["family"] == "st" and (how != "swept" or s * (p["higher_low"] - (lv - s * z)) < 0):
                how = None
        if how is not None:
            dist = abs(ext - lv)
            if best is None or dist < best["dist"]:
                best = dict(level=lv, level_kind=kind, how=how, dist=dist)
    return best


def next_level(levels: FloatArray, entry: float, side: int, z: float, own: float) -> float:
    v = levels[(np.abs(levels - own) > z) & (side * (levels - entry) > z)]
    if not len(v):
        return math.nan
    return float(v.min() if side > 0 else v.max())


def confirm_b(
    h: FloatArray,
    lo: FloatArray,
    c: FloatArray,
    d: int,
    extreme: float,
    atr: float,
    side: int,
    max_wait: int = 30,
    pb_atr: float = 1.0,
) -> dict[str, float] | None:
    """p2_trades.confirm_b: the pullback of pb_atr x ATR from the post-breakout high, then the first close
    above the frozen high, within max_wait bars after d; None if a low reaches the extreme first."""
    if side < 0:
        x = confirm_b(-lo, -h, -c, d, -extreme, atr, 1, max_wait, pb_atr)
        return None if x is None else dict(k=x["k"], hi=-x["hi"], pull=-x["pull"])
    hi, pulled, pull = h[d], False, np.inf
    for k in range(d + 1, min(d + max_wait, len(c) - 1) + 1):
        if lo[k] <= extreme:
            return None
        if not pulled:
            if h[k] > hi:
                hi = h[k]
            elif hi - lo[k] >= pb_atr * atr:
                pulled, pull = True, lo[k]
            continue
        pull = min(pull, lo[k])
        if c[k] > hi:
            return dict(k=float(k), hi=float(hi), pull=float(pull))
    return None


# --- the owner's H1 levels (zones.levels_at) --------------------------------------------------------------


@dataclass(frozen=True)
class LevelInputs:
    avail: np.ndarray  # H1 bars complete by the evaluation, int64 ns
    h: FloatArray
    lo: FloatArray
    atr: FloatArray
    s_i: np.ndarray  # the fractal swings: bar, price, kind, known
    s_p: FloatArray
    s_k: np.ndarray
    s_known: np.ndarray
    d_avail: np.ndarray  # D1 (server day) bars complete by the evaluation
    d_high: FloatArray
    d_low: FloatArray


def fractals(h: FloatArray, lo: FloatArray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """foundation.fractals: the highest high / lowest low of the k bars on each side (equal ones each
    count)."""
    hw = pd.Series(h).rolling(2 * k + 1, center=True).max().to_numpy()
    lw = pd.Series(lo).rolling(2 * k + 1, center=True).min().to_numpy()
    return np.nonzero((h == hw) & np.isfinite(hw))[0], np.nonzero((lo == lw) & np.isfinite(lw))[0]


def _groups(
    opens: pd.DatetimeIndex, h: FloatArray, lo: FloatArray, c: FloatArray, key: pd.DatetimeIndex
) -> pd.DataFrame:
    df = pd.DataFrame({"h": h, "lo": lo, "c": c, "t": opens.as_unit("ns").to_numpy(dtype="datetime64[ns]")})
    g = df.groupby(pd.DatetimeIndex(key).as_unit("ns").to_numpy(dtype="datetime64[ns]"), sort=True)
    out = pd.DataFrame({"h": g.h.max(), "lo": g.lo.min(), "c": g.c.last(), "last": g.t.max()})
    out["avail"] = out["last"].to_numpy(dtype="datetime64[ns]").astype(np.int64) + NS_MIN
    return out


def level_inputs(
    opens: pd.DatetimeIndex, h: FloatArray, lo: FloatArray, c: FloatArray, t: pd.Timestamp
) -> LevelInputs:
    """patterns.level_inputs from the M1 bars closed by *t*: H1 bars on the UTC hour and D1 bars on the
    server day (avail = the last M1 bar's open + 1 minute, as indicators.bars), keeping only the ones whose
    hour / server day is over by *t* (the research's bars come from the full history: a running bar is not
    complete there)."""
    tn = pd.Timestamp(t).as_unit("ns").value
    hours = opens.floor("h")
    h1 = _groups(opens, h, lo, c, hours)
    end = (
        pd.DatetimeIndex(h1.index).as_unit("ns").to_numpy(dtype="datetime64[ns]").astype(np.int64)
        + 60 * NS_MIN
    )
    h1 = h1[end <= tn]
    hh, ll, cc = h1.h.to_numpy(float), h1.lo.to_numpy(float), h1.c.to_numpy(float)
    av = h1.avail.to_numpy(np.int64)
    hi_i, lo_i = fractals(hh, ll, H1_K)
    rows = sorted(
        [(int(i), float(hh[i]), 1) for i in hi_i] + [(int(i), float(ll[i]), -1) for i in lo_i],
        key=lambda r: (r[0], r[2]),  # zones.swings: sorted by bar, then kind
    )
    rows = [r for r in rows if r[0] + H1_K < len(hh)]
    s_i = np.array([r[0] for r in rows], int)
    local = opens.tz_convert(ATHENS).tz_localize(None).floor("1D")
    d1 = _groups(opens, h, lo, c, pd.DatetimeIndex(local))
    days = pd.DatetimeIndex(d1.index) + pd.Timedelta(days=1)
    day_end = (
        days.tz_localize(ATHENS)
        .tz_convert("UTC")
        .as_unit("ns")
        .to_numpy(dtype="datetime64[ns]")
        .astype(np.int64)
    )
    d1 = d1[day_end <= tn]
    return LevelInputs(
        av,
        hh,
        ll,
        mt5_atr(hh, ll, cc),
        s_i,
        np.array([r[1] for r in rows], float),
        np.array([r[2] for r in rows], int),
        av[s_i + H1_K] if len(s_i) else np.empty(0, np.int64),
        d1.avail.to_numpy(np.int64),
        d1.h.to_numpy(float),
        d1.lo.to_numpy(float),
    )


def merge(prices: FloatArray, kinds: np.ndarray, tol: float) -> list[tuple[float, int, int, int]]:
    """zones.merge: sorted; a price joins the zone while within tol of its first price -> (mean, touches,
    tops, lows)."""
    o = np.argsort(prices, kind="stable")
    v, kd = np.asarray(prices, float)[o], np.asarray(kinds)[o]
    rows, a = [], 0
    for j in range(1, len(v) + 1):
        if j == len(v) or v[j] - v[a] > tol:
            rows.append((float(v[a:j].mean()), j - a, int((kd[a:j] > 0).sum()), int((kd[a:j] < 0).sum())))
            a = j
    return rows


def levels_at(
    y: LevelInputs, t_ns: int, price: float, win: int = WIN
) -> tuple[list[tuple[float, str]], float]:
    """zones.levels_at: the owner's levels known at t_ns, strongest first, and that H1 ATR."""
    bi = int(np.searchsorted(y.avail, t_ns, side="right")) - 1
    if bi < 0 or not np.isfinite(y.atr[bi]):
        return [], math.nan
    a = float(y.atr[bi])
    sel = (y.s_known <= t_ns) & (y.s_i > bi - win)
    zones = merge(y.s_p[sel], y.s_k[sel], TOL_ATR * a) if sel.any() else []
    cand: list[tuple[float, str]] = []
    for zp, touches, tops, lows in zones:
        if touches >= 3 or (tops and lows):
            cand.append((zp, "x3+ / flip"))
        elif touches == 2:
            cand.append((zp, "x2"))
    a0 = max(bi - win + 1, 0)
    cand += [(float(y.h[a0 : bi + 1].max()), "5d high"), (float(y.lo[a0 : bi + 1].min()), "5d low")]
    kd = int(np.searchsorted(y.d_avail, t_ns, side="right")) - 1
    if kd >= 0:
        cand += [(float(y.d_high[kd]), "PDH"), (float(y.d_low[kd]), "PDL")]
    si, sp, sk = y.s_i[sel], y.s_p[sel], y.s_k[sel]
    tops = (sk == 1) & (sp > price)
    lows = (sk == -1) & (sp < price)
    if tops.any():
        cand.append((float(sp[tops][int(np.argmax(si[tops]))]), "last top"))
    if lows.any():
        cand.append((float(sp[lows][int(np.argmax(si[lows]))]), "last low"))
    cand.sort(key=lambda x: ORDER.index(x[1]))
    kept: list[tuple[float, str]] = []
    for cnd in cand:
        if all(abs(cnd[0] - k[0]) > TOL_ATR * a for k in kept):
            kept.append(cnd)
    return kept, a


# --- the strategy -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    side: int
    stop: float
    risk_dec: float
    pattern: dict[str, Any]
    level: dict[str, Any]
    z: float
    h1_atr_dec: float
    next_level: float
    t_dec: int
    conf: dict[str, float]
    close: float


@dataclass
class _Frame:
    """One evaluation's readings of the strategy's timeframe."""

    bars: Bars
    atr: FloatArray
    piv: Pivots
    extra: dict[str, Any] = field(default_factory=dict)


class Plan1B2Params(StrategyParams):
    window: str = "07:00-09:00"  # entry (confirmation) times, [start, end)
    window_zone: str = "Asia/Bangkok"
    max_wait_bars: int = Field(
        default=30, ge=1, le=240
    )  # the confirmation within this many bars after the pattern
    pullback_atr: float = Field(default=1.0, gt=0, le=10)
    hold_bars: int = Field(default=60, ge=1, le=1440)  # out after this many of the TF's bars
    # journal week 6: a second B2 of the morning only in the first one's direction (on in the frozen rules,
    # CHECKLIST 61-63; the journal deleted it in week 29: a switch)
    second_same_side: bool = True
    # no level beyond 1 R: the research has no target; the risk checks need one, so a far one (in R: a B2 stop
    # can be 90 USD wide)
    target_cap_r: float = Field(default=10.0, gt=1, le=50)
    atr_floor: float | None = Field(default=None, gt=0, le=1000)
    d1_atr20_min_usd: float | None = Field(
        default=60.0, gt=0, le=1000
    )  # the regime switch (row 62); None = off

    @field_validator("window")
    @classmethod
    def _check_window(cls, value: str) -> str:
        start, sep, end = value.partition("-")
        if not sep or hhmm(start) >= hhmm(end):
            raise ValueError(f"window: {value!r} is not 'HH:MM-HH:MM' with start < end")
        return value

    @field_validator("window_zone")
    @classmethod
    def _check_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown time zone {value!r}") from exc
        return value


def in_window(t: pd.Timestamp, window: str, zone: str) -> bool:
    """p4_trades.window_of: start included, end excluded, in *zone*."""
    local = t.tz_convert(zone)
    start, _, end = window.partition("-")
    s, e = hhmm(start), hhmm(end)
    m = local.hour * 60 + local.minute + local.second / 60
    return s.hour * 60 + s.minute <= m < e.hour * 60 + e.minute


class Plan1B2(BaseStrategy):
    """Asia B2 on M1 patterns (lane ``plan1``)."""

    name = "setup_plan1_b2"
    version = "1.0.0"
    description = (
        "Setup OWN PLAN-1, Asia B2 on M1: a chart pattern at the owner's H1 level, a pullback and a new "
        "close, 07:00-09:00 Thai; the structure exit; M1 gold. Lane only. Unproven."
    )
    Params = Plan1B2Params
    advised = False
    minutes: ClassVar[int] = 1
    entry_group: ClassVar[tuple[str, ...]] = ("setup_plan1_b2", "setup_plan1_b2m5")

    def __init__(self, params: StrategyParams | None = None) -> None:
        super().__init__(params)
        self._entries: dict[str, list[PastEntry]] = {}

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.M1,)

    def warmup_bars(self) -> int:
        return (
            10_000  # 125 complete H1 bars (the levels' 120) across a weekend; the ZigZag settles well within
        )

    def wants_bar(self, at: datetime) -> bool:
        p: Plan1B2Params = self.params
        t = pd.Timestamp(at)
        return in_window(t, p.window, p.window_zone) and not t.value % (self.minutes * NS_MIN)

    def attach_entries(self, symbol: str, entries: Sequence[PastEntry]) -> None:
        self._entries[symbol] = sorted(entries, key=lambda e: e.at)

    # readings ----------------------------------------------------------------------------------------------

    def _frame(self, m1: pd.DataFrame, at: pd.Timestamp) -> _Frame | None:
        opens = pd.DatetimeIndex(pd.to_datetime(m1["open_time"], utc=True))
        o, h, lo, c = (m1[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        b = tf_bars(opens, o, h, lo, c, self.minutes, at)
        if len(b.c) < 30 or b.avail[-1] != at.as_unit("ns").value:
            return None
        atr = mt5_atr(b.h, b.lo, b.c)
        return _Frame(b, atr, zigzag(b.h, b.lo, atr), {"opens": opens, "o": o, "h": h, "lo": lo, "c": c})

    def candidates(self, f: _Frame, y: LevelInputs | None = None) -> list[Candidate]:
        """The patterns of the last ``max_wait_bars`` bars confirmed by the last bar, located at a level,
        sorted by the risk at the confirming close (patterns.locate + p3_trades.candidates3)."""
        p: Plan1B2Params = self.params
        b, k = f.bars, len(f.bars.c) - 1
        x = f.extra
        out: list[Candidate] = []
        for d in range(max(k - p.max_wait_bars, 0), k):
            if not np.isfinite(f.atr[d]):
                continue
            for pat in patterns_at(b, f.atr, f.piv, d):
                conf = confirm_b(
                    b.h[: k + 1],
                    b.lo[: k + 1],
                    b.c[: k + 1],
                    d,
                    pat["extreme"],
                    pat["atr"],
                    pat["side"],
                    p.max_wait_bars,
                    p.pullback_atr,
                )
                if conf is None or int(conf["k"]) != k:
                    continue
                if d + 1 > k or b.t_open[d + 1] != b.avail[d]:
                    continue  # the research's entry needs the bar opening at the decision (patterns.locate)
                t_dec = int(b.avail[d])
                if y is None:  # read only when a pattern confirms (most bars have none)
                    y = level_inputs(
                        x["opens"], x["h"], x["lo"], x["c"], pd.Timestamp(int(b.avail[k]), tz="UTC")
                    )
                levels, a1 = levels_at(y, t_dec, float(b.c[d]))
                if not np.isfinite(a1) or not levels:
                    continue
                z = ZONE_H1 * a1
                hit = at_level(pat, float(b.c[d]), levels, z, SWEEP_H1 * a1)
                if hit is None:
                    continue
                prices = np.array([lv for lv, _ in levels], float)
                nl = next_level(prices, float(b.o[d + 1]), pat["side"], z, hit["level"])
                close = float(b.c[k])
                out.append(
                    Candidate(
                        pat["side"],
                        pat["stop"],
                        abs(close - pat["stop"]),
                        pat,
                        hit,
                        z,
                        a1,
                        nl,
                        t_dec,
                        conf,
                        close,
                    )
                )
        return sorted(out, key=lambda q: q.risk_dec)

    # the contract ------------------------------------------------------------------------------------------

    def evaluate(self, ctx: StrategyContext) -> Signal:
        p: Plan1B2Params = self.params
        market = ctx.market
        at = pd.Timestamp(market.decision_time_utc)
        if market.entry_timeframe is not Timeframe.M1:
            return self.hold(ctx, ReasonCode.DATA_QUALITY, explanation="B2 runs on an M1 lane")
        if not in_window(at, p.window, p.window_zone):
            return self.hold(ctx, ReasonCode.OUTSIDE_SESSION, explanation=f"{at:%a %H:%M} UTC")
        if at.value % (self.minutes * NS_MIN):
            return self.hold(ctx, ReasonCode.NO_SETUP, explanation=f"not an M{self.minutes} close")
        f = self._frame(ctx.frame(Timeframe.M1), at)
        if f is None:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, explanation="too few bars")
        cands = self.candidates(f)
        if not cands:
            return self.hold(ctx, ReasonCode.NO_SETUP, explanation="no confirmed pattern at a level")
        q = cands[0]
        buy = q.side > 0
        price = market.ask if buy else market.bid
        if price is None:
            return self.hold(ctx, ReasonCode.DATA_QUALITY, explanation="no quote")
        risk = q.side * (price - q.stop)
        if not risk > 0:
            return self.hold(ctx, ReasonCode.NO_SETUP, explanation=f"the price {price:.2f} is past the stop")
        target = (
            q.next_level if np.isfinite(q.next_level) and q.side * (q.next_level - price) > risk else math.nan
        )
        conds, ok = self.journal(ctx, f, q, at, price, risk, target)
        if not ok:
            return self.hold(ctx, ReasonCode.NO_SETUP, conditions=conds, explanation=explain(conds))
        tp = target if np.isfinite(target) else price + q.side * p.target_cap_r * risk
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=price,
            stop_loss=q.stop,
            take_profit=tp,
            conditions=conds,
            score=max(0.0, 100.0 - q.risk_dec),  # the smaller risk ranks first (the research's order)
            explanation=explain(conds),
        )

    def journal(
        self,
        ctx: StrategyContext,
        f: _Frame,
        q: Candidate,
        at: pd.Timestamp,
        price: float,
        risk: float,
        target: float,
    ) -> tuple[list[Condition], bool]:
        p: Plan1B2Params = self.params
        x, b = f.extra, f.bars
        pat = q.pattern
        tf = f"M{self.minutes}"
        h1 = h1_atr_at(x["opens"], x["h"], x["lo"], x["c"], at)
        floor_ok = p.atr_floor is None or (math.isfinite(h1) and h1 >= p.atr_floor)
        change = h4_change_at(ctx, at)
        side_ok, side_text = self.second_trade(ctx.symbol, at, q.side)
        pts = ", ".join(
            f"{lab} {px:.2f} @{pd.Timestamp(int(b.t_open[i]), tz='UTC'):%H:%M}"
            for i, px, lab in pat["points"]
        )
        other = "-"
        if self.minutes == 1:
            b5 = tf_bars(x["opens"], x["o"], x["h"], x["lo"], x["c"], 5, at)
            if len(b5.c) > 30:
                a5 = mt5_atr(b5.h, b5.lo, b5.c)
                other = f"M5 structure {m_structure(zigzag(b5.h, b5.lo, a5), len(b5.c) - 1)}"
        else:
            other = f"M1 structure {m_structure(*self._m1_piv(x, at))}"
        conds = [
            Condition(
                "rule",
                True,
                1.0,
                f"Asia B2 {tf}: {pat['variant']} ({NAMES[(pat['family'], q.side)]}) broke out at "
                f"{pd.Timestamp(q.t_dec, tz='UTC'):%H:%M} UTC; pullback to {q.conf['pull']:.2f}, close "
                f"{q.close:.2f} beyond {q.conf['hi']:.2f}",
            ),
            Condition("h1_atr", floor_ok, 1.0, atr_detail(h1, p.atr_floor)),
            regime(ctx, at, p.d1_atr20_min_usd),
            Condition(
                "level",
                True,
                1.0,
                f"{q.level['level']:.2f} {q.level['level_kind']} ({q.level['how']}), zone +-{q.z:.2f}; "
                "next level " + ("none" if not np.isfinite(q.next_level) else f"{q.next_level:.2f}"),
            ),
            Condition(
                "pattern", True, 1.0, f"{pts}; extreme {pat['extreme']:.2f}, height {pat['height']:.2f}"
            ),
            Condition("agreement", True, 1.0, other),
            Condition("pools", True, 1.0, pools_detail(pools(x["opens"], x["o"], x["h"], x["lo"], at))),
            Condition(
                "h4_atr_change",
                True,
                1.0,
                "H4 ATR(14) over 6 H4 bars "
                + ("unknown" if not math.isfinite(change) else f"{100 * change:+.1f} %"),
            ),
            Condition("second_trade", side_ok, 1.0, side_text),
            Condition(
                "stop_distance",
                True,
                1.0,
                f"{risk:.2f} to {q.stop:.2f} (0.2 ATR past the extreme); target "
                + (
                    f"{target:.2f} (the next level)"
                    if np.isfinite(target)
                    else f"none (no level beyond 1 R; a cap at {p.target_cap_r:g} R)"
                ),
            ),
            Condition("spread", True, 1.0, spread_detail(ctx.market.bid, ctx.market.ask, ctx)),
        ]
        return conds, floor_ok and side_ok and conds[2].passed

    def _m1_piv(self, x: dict[str, Any], at: pd.Timestamp) -> tuple[Pivots, int]:
        b1 = tf_bars(x["opens"], x["o"], x["h"], x["lo"], x["c"], 1, at)
        a1 = mt5_atr(b1.h, b1.lo, b1.c)
        return zigzag(b1.h, b1.lo, a1), len(b1.c) - 1

    def second_trade(self, symbol: str, at: pd.Timestamp, side: int) -> tuple[bool, str]:
        """Week 6: the morning's first B2 entry (the Thai day of *at*) sets the side of any later one."""
        p: Plan1B2Params = self.params
        day = at.tz_convert(p.window_zone).date()
        today = [
            e
            for e in self._entries.get(symbol, [])
            if pd.Timestamp(e.at).tz_convert(p.window_zone).date() == day and pd.Timestamp(e.at) < at
        ]
        if not today:
            return True, "the first B2 of the morning"
        first = today[0]
        same = (first.side is Side.BUY) == (side > 0)
        text = (
            f"B2 #{len(today) + 1} of the morning; the first: {first.side.value} at "
            f"{pd.Timestamp(first.at).tz_convert(p.window_zone):%H:%M} ({first.strategy})"
        )
        if not p.second_same_side:
            return True, text + "; rule off"
        return same, text + ("; same side" if same else "; a flip: skipped")

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        """The structure exit at the close of the TF bar beyond the last confirmed swing low (a buy) / high (a
        sell), and out after ``hold_bars`` TF bars (p2_trades.structure_exit_time, p3's time limit)."""
        p: Plan1B2Params = self.params
        at = pd.Timestamp(ctx.decision_time_utc)
        step = self.minutes * NS_MIN
        t_entry = (pd.Timestamp(pos.entry_time).value // step) * step
        if at.value >= t_entry + p.hold_bars * step:
            return PositionAdvice(close=ExitReason.TIME_STOP, note=f"{p.hold_bars} M{self.minutes} bars")
        if at.value % step:
            return None
        f = self._frame(ctx.frame(Timeframe.M1), at)
        if f is None:
            return None
        bk = len(f.bars.c) - 1
        if f.bars.t_open[bk] < t_entry:
            return None
        buy = pos.side is Side.BUY
        swing = last_swing(f.piv, bk, -1 if buy else 1)
        close = float(f.bars.c[bk])
        if np.isfinite(swing) and (close < swing if buy else close > swing):
            return PositionAdvice(
                close=ExitReason.SIGNAL, note=f"structure: close {close:.2f} beyond {swing:.2f}"
            )
        return None


class Plan1B2M5(Plan1B2):
    """Asia B2 on M5 patterns (bars built from M1 on the clock)."""

    name = "setup_plan1_b2m5"
    description = (
        "Setup OWN PLAN-1, Asia B2 on M5: a chart pattern at the owner's H1 level, a pullback and a new "
        "close, 07:00-09:00 Thai; the structure exit; gold. Lane only. Unproven."
    )
    minutes: ClassVar[int] = 5
