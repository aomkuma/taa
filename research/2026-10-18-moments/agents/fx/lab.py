"""Session events and context features for the majors (agent "fx").

An event = one day's decision at a local clock time (the close of the bar ending there), with the move of a prior
window, the window's range, and context known at the decision: H1 ATR(24), H1 EMA trend, the previous New York
day's high/low/close, the day's open (00:00 UTC). Everything from bars closed at or before the decision.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import fxlib as fx  # noqa: E402

_CTX: dict[str, pd.DataFrame] = {}


def context(P: fx.Pair) -> pd.DataFrame:
    """Per M1 bar d: context known at d's close (H1 values from H1 bars that closed at or before that time)."""
    if P.sym in _CTX:
        return _CTX[P.sym]
    b = P.h1()
    b = b[b.n >= 10]
    rng = (b.h - b.l)
    b["atr"] = rng.rolling(24, min_periods=12).mean()
    b["ema20"] = b.c.ewm(span=20, adjust=False).mean()
    b["ema50"] = b.c.ewm(span=50, adjust=False).mean()
    b["slope"] = b.ema20 - b.ema20.shift(3)
    # the hour bar [t, t+1h) is known once the M1 bar starting t+59 closes: map M1 index -> last closed H1 row
    close_i = b.ilast.to_numpy()  # M1 index of the hour's last bar; known from that bar's close on
    pos = np.searchsorted(close_i, np.arange(P.n), side="right") - 1  # last H1 row whose last bar <= d
    ok = pos >= 0
    out = pd.DataFrame(index=np.arange(P.n))
    for k in ("atr", "ema20", "ema50", "slope", "c"):
        v = np.full(P.n, np.nan)
        v[ok] = b[k].to_numpy()[pos[ok]]
        out["h1_" + k] = v
    # partial hours: bars that fall inside the hour whose last bar is later count only completed hours: fine,
    # because close_i of the current (forming) hour is > d.
    # the New York day (17:00 ET boundary): previous day's high / low / close
    ny = P.ot.tz_convert(fx.NYC)
    nyday = (ny + pd.Timedelta(hours=7)).normalize().tz_localize(None)  # 17:00 ET -> next day's 00:00
    dfd = pd.DataFrame({"h": P.h, "l": P.lo, "c": P.c, "day": nyday})
    g = dfd.groupby("day").agg(h=("h", "max"), l=("l", "min"), c=("c", "last"))
    prev = g.shift(1)
    out["pdh"] = prev.h.reindex(nyday).to_numpy()
    out["pdl"] = prev.l.reindex(nyday).to_numpy()
    out["pdc"] = prev.c.reindex(nyday).to_numpy()
    # today's running high/low so far (NY day), known at d's close
    out["dh"] = dfd.groupby("day").h.cummax().to_numpy()
    out["dl"] = dfd.groupby("day").l.cummin().to_numpy()
    out["dop"] = dfd.groupby("day").c.transform("first").to_numpy()  # ~ the first bar's close of the NY day
    _CTX[P.sym] = out
    return out


def local_index(P: fx.Pair, tz, hour: float) -> pd.Series:
    """Per local date: the M1 index of the bar that ends at local time *hour* (its close = the decision)."""
    loc = P.ot.tz_convert(tz)
    lm = loc.hour * 60 + loc.minute
    target = int(round(hour * 60)) - 1
    if target < 0:
        target += 1440
    m = lm == target
    day = loc.normalize().tz_localize(None)
    s = pd.Series(np.flatnonzero(m), index=day[m])
    return s[~s.index.duplicated()]


def local_start(P: fx.Pair, tz, hour: float) -> pd.Series:
    loc = P.ot.tz_convert(tz)
    lm = loc.hour * 60 + loc.minute
    m = lm == int(round(hour * 60))
    day = loc.normalize().tz_localize(None)
    s = pd.Series(np.flatnonzero(m), index=day[m])
    return s[~s.index.duplicated()]


def events(P: fx.Pair, tz, a0: float, a1: float, b1: float) -> pd.DataFrame:
    """Window a0..a1 (local hours) then a decision at a1, exit by b1 (local). Columns: d (decision bar), move (pips,
    close at a1 - open at a0), whi/wlo (window high/low), hz (minutes from the entry to b1), context."""
    ia = local_start(P, tz, a0)
    ib = local_index(P, tz, a1)
    ie = local_index(P, tz, b1)
    j = pd.concat({"a": ia, "d": ib, "x": ie}, axis=1, sort=True).dropna().astype(int)
    j = j[(j.d > j.a) & (j.x > j.d) & (j.d - j.a < 1440)]
    a, d, x = j.a.to_numpy(), j.d.to_numpy(), j.x.to_numpy()
    ev = pd.DataFrame({"a": a, "d": d, "x": x}, index=j.index)
    ev["t"] = P.ot[d]
    ev["move"] = P.c[d] - P.o[a]
    ev["whi"] = [P.h[p:q + 1].max() for p, q in zip(a, d)]
    ev["wlo"] = [P.lo[p:q + 1].min() for p, q in zip(a, d)]
    ev["hz"] = (P.tmin[x] - P.tmin[d]).astype(int)  # entry at d+1, last bar held x -> x - d minutes
    ev["half"] = fx.half_of(ev.t)
    ctx = context(P)
    for k in ctx.columns:
        ev[k] = ctx[k].to_numpy()[d]
    ev["px"] = P.c[d]
    return ev.reset_index(names="day")


def simulate(P: fx.Pair, ev: pd.DataFrame, side: np.ndarray, sl: np.ndarray, tp, be=None, trail=None) -> pd.DataFrame:
    """One trade per event (events are one per day per family, so they do not overlap within a family)."""
    rows = []
    tpa = np.broadcast_to(np.asarray(tp, dtype=float) if tp is not None else np.nan, len(ev))
    for k, r in enumerate(ev.itertuples()):
        if side[k] == 0 or not np.isfinite(sl[k]):
            continue
        t_ = None if not np.isfinite(tpa[k]) else float(tpa[k])
        z = P.trade(int(r.d), int(side[k]), t_, float(sl[k]), int(r.hz), be=be, trail=trail)
        if z is None:
            continue
        z |= {"t": r.t, "half": r.half, "side": int(side[k]), "sl": float(sl[k]), "ev": k}
        rows.append(z)
    return pd.DataFrame(rows)


def by_half(z: pd.DataFrame, halves=None) -> list[float]:
    halves = halves or [h for h, _, _ in fx.HALVES]
    return [z[z.half == h].R.mean() if len(z) and (z.half == h).any() else np.nan for h in halves]
