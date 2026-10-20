"""Row 45 - the readings known before an entry (the pre-registration at the top of PROPOSALS.md). Pure functions on
arrays (tested by hand in test_readings.py) and `compute(E, ...)`, which reads them for every event.

Availability: a D1 / H4 bar of MT5's own history is available at the NEXT bar's open time (never earlier; the last bar
at open + 1 day / + 4 h). Nothing at or after the
exam start (2026-04-18) is loaded. An H1 bar counts from the end of its hour.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import slib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import foundation as F  # noqa: E402
import indicators  # noqa: E402

HIST = slib.ROOT / "data/history/FBS-Demo/XAUUSD"
NS_H = 3600 * 10**9
NS_MIN = 60 * 10**9


# ---------------------------------------------------------------- pure functions (hand-tested)
def pct_rank_recent(rng: np.ndarray, j: int, recent: int = 5, hist: int = 60) -> float:
    """The mean of rng[j-recent+1 .. j] as the share of rng[j-hist+1 .. j] that is <= it; NaN without the history."""
    if j < hist - 1:
        return np.nan
    v = rng[j - recent + 1:j + 1].mean()
    return float(np.mean(rng[j - hist + 1:j + 1] <= v))


def season(rng: np.ndarray, j: int, n: int = 20, base: int = 120) -> float:
    """ADR(n) / the median range of the last `base` bars (both ending at bar j)."""
    if j < base - 1:
        return np.nan
    return float(rng[j - n + 1:j + 1].mean() / np.median(rng[j - base + 1:j + 1]))


def efficiency(c: np.ndarray, j: int, n: int) -> float:
    """abs(c[j] - c[j-n]) / sum of abs(c[k] - c[k-1]) for k = j-n+1 .. j."""
    if j < n:
        return np.nan
    path = np.abs(np.diff(c[j - n:j + 1])).sum()
    return float(abs(c[j] - c[j - n]) / path) if path > 0 else 0.0


def fail_share(t_break: np.ndarray, t_settle: np.ndarray, failed: np.ndarray, t_from: int, t: int,
               min_n: int = 10) -> float:
    """The failed share of the breaks that happened at / after t_from and were settled at / before t."""
    m = (t_break >= t_from) & (t_settle <= t)
    if m.sum() < min_n:
        return np.nan
    return float(failed[m].mean())


def since_big(avail: np.ndarray, big: np.ndarray, j: int, t: int, cap: float = 999.0) -> float:
    """Hours from the availability of the last big bar among bars 0 .. j to t (cap when none)."""
    k = np.nonzero(big[:j + 1])[0]
    if not len(k):
        return cap
    return min(cap, (t - avail[k[-1]]) / NS_H)


def big_bars(h: np.ndarray, lo: np.ndarray, atr: np.ndarray, mult: float = 2.5) -> np.ndarray:
    """A bar whose range >= mult x the ATR of the bar before it."""
    prev = np.r_[np.nan, atr[:-1]]
    with np.errstate(invalid="ignore"):
        return (h - lo) >= mult * prev


def own_trailing(t_exit: np.ndarray, R: np.ndarray, t: int, n: int = 20, min_n: int = 10) -> float:
    """The mean R of the last n trades (by exit time) that exited at / before t."""
    m = (t_exit <= t) & np.isfinite(R) & (t_exit > 0)
    if m.sum() < min_n:
        return np.nan
    o = np.argsort(t_exit[m], kind="stable")
    return float(R[m][o][-n:].mean())


# ---------------------------------------------------------------- loaders
def load_mt5(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(HIST / f"{tf}.parquet", filters=[("open_time", "<", slib.EXAM_START)])
    d = d.sort_values("open_time").drop_duplicates("open_time", keep="last").reset_index(drop=True)
    t = pd.DatetimeIndex(pd.to_datetime(d.open_time, utc=True)).as_unit("ns").asi8
    step = (24 if tf == "D1" else 4) * NS_H
    d["t_open"] = t
    d["avail"] = np.r_[t[1:], t[-1] + step]
    return d


# ---------------------------------------------------------------- per event
def compute(E: pd.DataFrame, m: pd.DataFrame, B: pd.DataFrame) -> pd.DataFrame:
    """The readings for every event row (t_in ns, H, stream). m = M1 bars (UTC index) before the exam."""
    D1, H4 = load_mt5("D1"), load_mt5("H4")
    d_rng = (D1.high - D1.low).to_numpy(float)
    d_c = D1.close.to_numpy(float)
    d_adx = F.adx(D1.high.to_numpy(float), D1.low.to_numpy(float), d_c, 14)[2]
    h4_c = H4.close.to_numpy(float)
    h4_adx = F.adx(H4.high.to_numpy(float), H4.low.to_numpy(float), h4_c, 14)[2]
    h1 = indicators.bars(m, "1h")
    # an H1 bar counts from the end of its hour (a forming bar never counts, even when the data end inside it)
    h1_av = (pd.DatetimeIndex(h1["last"]).floor("1h") + pd.Timedelta(hours=1)).as_unit("ns").asi8
    h1_atr = F.atr(h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float), 14)
    big = big_bars(h1.high.to_numpy(float), h1.low.to_numpy(float), h1_atr)
    ti = m.index.asi8
    mh, ml = m.high.to_numpy(float), m.low.to_numpy(float)
    msp = m.spread.to_numpy(float) * 0.01 + 0.08
    sday = m.index.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
    sday_ns = sday.as_unit("ns").asi8
    bt, bs, bf = (B[k].to_numpy() for k in ("t_break", "t_settle", "failed"))
    bf = bf.astype(float)

    def m1_range(a: int, b: int) -> float:
        i, k = np.searchsorted(ti, a), np.searchsorted(ti, b)
        return float(mh[i:k].max() - ml[i:k].min()) if k - i >= 60 else np.nan

    out = []
    for r in E.itertuples():
        t = int(r.t_in)
        jd = int(np.searchsorted(D1.avail.to_numpy(), t, side="right") - 1)
        j4 = int(np.searchsorted(H4.avail.to_numpy(), t, side="right") - 1)
        j1 = int(indicators.at(h1_av, np.array([t]))[0])
        x = dict(
            rng60=pct_rank_recent(d_rng, jd),
            season=season(d_rng, jd),
            eff_d1=efficiency(d_c, jd, 20),
            adx_d1=float(d_adx[jd]) if jd >= 28 else np.nan,
            eff_h4=efficiency(h4_c, j4, 30),
            adx_h4=float(h4_adx[j4]) if j4 >= 28 else np.nan,
            fail20=fail_share(bt, bs, bf, int(D1.t_open.iloc[max(jd - 19, 0)]), t),
        )
        # the 6 h before the entry against the same clock window on the previous 10 weekdays
        now = m1_range(t - 6 * NS_H, t)
        prev, back = [], 1
        while len(prev) < 10 and back < 20:
            tb = pd.Timestamp(t - back * 24 * NS_H, tz="UTC")
            back += 1
            if tb.weekday() >= 5:
                continue
            v = m1_range(tb.value - 6 * NS_H, tb.value)
            if np.isfinite(v):
                prev.append(v)
        x["sess10"] = now / np.mean(prev) if len(prev) >= 5 and np.isfinite(now) else np.nan
        i = int(np.searchsorted(ti, t))
        x["spr_atr"] = float(np.median(msp[max(i - 60, 0):i]) / r.H) if i >= 60 else np.nan
        x["since_big"] = since_big(h1_av, big, j1, t) if j1 >= 15 else np.nan
        # the server day so far
        k0 = int(np.searchsorted(sday_ns, sday_ns[i - 1]))  # the first M1 of the current server day
        same_day = i > 0 and sday_ns[i - 1] == sday_ns[min(i, len(ti) - 1)]
        adr20 = d_rng[jd - 19:jd + 1].mean() if jd >= 19 else np.nan
        x["used"] = float((mh[k0:i].max() - ml[k0:i].min()) / adr20) if same_day and i > k0 else 0.0
        out.append(x)
    R = pd.DataFrame(out, index=E.index)
    # own20: per stream, from the stream's own earlier exits
    R["own20"] = np.nan
    for st, g in E.groupby("stream"):
        te, rr = g.t_exit.to_numpy(np.int64), g.R.to_numpy(float)
        R.loc[g.index, "own20"] = [own_trailing(te, rr, int(t)) for t in g.t_in]
    return R
