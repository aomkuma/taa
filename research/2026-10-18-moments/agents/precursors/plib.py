"""Precursors (notes.md): the run catalogue (X U within 15 minutes), the focus windows, the six-timeframe chart
state at every decision minute, and the labels. Closed bars only; everything as written in notes.md."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import gold  # noqa: E402

REF = 4100.0
HZ = 15  # a run reaches X within 15 minutes
PB, END_HZ = 0.40, 120  # the leg ends at a 40 % pullback or after 120 minutes
LOOKAHEAD = 15  # a run "comes" when it starts within the next 15 minutes
FIRST_HZ = 60
START = pd.Timestamp("2023-08-01", tz="UTC")
END = pd.Timestamp("2026-10-17", tz="UTC")
SPLIT = pd.Timestamp("2026-03-01", tz="UTC")
HALVES = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01",
                         "2026-10-17"], utc=True)
HLAB = ["H1", "H2", "H3", "H4", "H5", "W"]
TH = "Asia/Bangkok"
# focus windows: (name, zone, start minute of the local day, end minute) - [start, end)
WINDOWS = [
    ("A07", TH, 7 * 60 - 5, 7 * 60 + 30),
    ("A08", TH, 8 * 60 - 5, 8 * 60 + 30),
    ("A09", TH, 9 * 60, 12 * 60),
    ("FR13", "Europe/Berlin", 8 * 60 - 5, 8 * 60 + 30),
    ("LO14", "Europe/London", 8 * 60, 12 * 60),
    ("NY19", "America/New_York", 8 * 60 - 5, 8 * 60 + 30),
    ("NY1930", "America/New_York", 8 * 60 + 25, 9 * 60),
    ("NY2030", "America/New_York", 9 * 60 + 25, 10 * 60),
    ("NY21", "America/New_York", 9 * 60 + 55, 10 * 60 + 30),
    ("NY22", "America/New_York", 11 * 60, 14 * 60),
]
TFS = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}


def load() -> pd.DataFrame:
    m = gold.bars("M1")
    m = m[(m.index >= START) & (m.index < END)]
    m = m[~m.index.duplicated(keep="last")]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


def minutes(idx: pd.DatetimeIndex) -> np.ndarray:
    return ((idx - idx[0]).total_seconds() // 60).to_numpy().astype(np.int64)


# ---------------------------------------------------------------- the run catalogue
def qualify(h, lo, c, tmin, X, side):
    """Every bar i: does a `side` run start at it (X within 15 minutes, the start never broken first)?"""
    n = len(h)
    if side < 0:
        h, lo, c = -lo, -h, -c
    s = lo.copy()
    hmax = c.copy()
    alive = np.ones(n, bool)
    done = np.zeros(n, bool)
    tgt = np.full(n, -1)
    for k in range(1, HZ):
        idx = np.minimum(np.arange(n) + k, n - 1)
        inwin = (np.arange(n) + k < n) & (tmin[idx] - tmin <= HZ - 1)
        alive &= done | (inwin & ~(lo[idx] < s))
        hmax = np.where(inwin & alive, np.maximum(hmax, h[idx]), hmax)
        new = alive & ~done & (hmax - s >= X)
        tgt[new] = idx[new]
        done |= new
    return done, tgt


def extend(i, h, lo, tmin, X, side):
    s = lo[i] if side > 0 else h[i]
    best, bj, j, n = 0.0, i, i + 1, len(h)
    while j < n and tmin[j] - tmin[i] <= END_HZ:
        adv = (s - lo[j]) if side > 0 else (h[j] - s)
        back = best - ((lo[j] - s) if side > 0 else (s - h[j]))
        if adv > 0 or back > PB * max(best, X):
            break
        fav = (h[j] - s) if side > 0 else (s - lo[j])
        if fav > best:
            best, bj = fav, j
        j += 1
    return best, bj, j


def catalogue(m: pd.DataFrame, xu: float) -> pd.DataFrame:
    ot = m.index
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    tmin = minutes(ot)
    X = xu * o / REF
    rows = []
    for side in (1, -1):
        ok, tgt = qualify(h, lo, c, tmin, X, side)
        end = -1
        for i in np.nonzero(ok)[0]:
            if i <= end:
                continue
            size, xj, end = extend(i, h, lo, tmin, X[i], side)
            rows.append((side, i, tgt[i], int(tmin[tgt[i]] - tmin[i] + 1), lo[i] if side > 0 else h[i], size / (o[i] / REF),
                         int(tmin[xj] - tmin[i] + 1)))
    C = pd.DataFrame(rows, columns=["side", "i", "tgt", "mins_to_x", "start_px", "size_u", "dur"]).sort_values("i")
    C["t"] = ot[C.i.to_numpy()]
    return C.reset_index(drop=True)


# ---------------------------------------------------------------- focus windows
def window_mask(idx: pd.DatetimeIndex) -> pd.DataFrame:
    out = {}
    for name, zone, a, b in WINDOWS:
        loc = idx.tz_convert(zone)
        mod = loc.hour * 60 + loc.minute
        out[name] = np.asarray((mod >= a) & (mod < b))
    w = pd.DataFrame(out, index=idx)
    wd = idx.tz_convert("America/New_York").dayofweek
    th = idx.tz_convert(TH).dayofweek
    week = (np.asarray(wd) < 5) | (np.asarray(th) < 5)
    w = w & week[:, None]
    return w


# ---------------------------------------------------------------- timeframe bars and their state
def tf_bars(m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Bars of a timeframe from M1; H4 on the broker's server day (Europe/Athens). `avail` = the time the bar is
    complete in the data (its last M1 bar's open + 1 minute) - usable at a decision at or after it."""
    if rule == "4h":
        loc = m.index.tz_convert("Europe/Athens").tz_localize(None)
        key = loc.floor("4h")
    else:
        key = m.index.floor(rule)
    g = m.assign(_k=key, _t=m.index).groupby("_k", sort=True)
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "tv": g.tick_volume.sum(), "last": g._t.max(), "n": g.open.size()})
    b["avail"] = b["last"] + pd.Timedelta(minutes=1)
    return b.reset_index(drop=True)


def pivots(h: np.ndarray, lo: np.ndarray, k: int = 3):
    """Fractal swings (k bars each side) as (bar, value) known k bars later."""
    n = len(h)
    hw = pd.Series(h).rolling(2 * k + 1, center=True).max().to_numpy()
    lw = pd.Series(lo).rolling(2 * k + 1, center=True).min().to_numpy()
    ph = np.nonzero((h == hw) & np.isfinite(hw))[0]
    pl = np.nonzero((lo == lw) & np.isfinite(lw))[0]
    return ph, pl


def last_two(piv: np.ndarray, vals: np.ndarray, n: int, k: int):
    """For each bar: the last and the previous confirmed swing value and the last swing's bar."""
    last = np.full(n, np.nan)
    prev = np.full(n, np.nan)
    lbar = np.full(n, -1)
    known = piv + k
    ok = known < n
    piv, known = piv[ok], known[ok]
    v = vals[piv]
    s_last = pd.Series(np.nan, index=range(n))
    s_prev = pd.Series(np.nan, index=range(n))
    s_bar = pd.Series(np.nan, index=range(n))
    s_last.iloc[known] = v
    s_prev.iloc[known] = np.r_[np.nan, v[:-1]]
    s_bar.iloc[known] = piv
    last = s_last.ffill().to_numpy()
    prev = s_prev.ffill().to_numpy()
    lbar = s_bar.ffill().fillna(-1).to_numpy()
    return last, prev, lbar


def tf_state(b: pd.DataFrame, pfx: str) -> pd.DataFrame:
    o, h, lo, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(c)
    cs = pd.Series(c)
    pc = cs.shift(1).to_numpy()
    tr = np.nanmax(np.vstack([h - lo, np.abs(h - pc), np.abs(lo - pc)]), axis=0)
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    e20 = cs.ewm(span=20, adjust=False).mean().to_numpy()
    e50 = cs.ewm(span=50, adjust=False).mean().to_numpy()
    e20_3 = np.r_[np.full(3, np.nan), e20[:-3]]
    tide = np.where((e20 > e20_3) & (c > e50), 1, np.where((e20 < e20_3) & (c < e50), -1, 0))
    k = 3
    ph, pl = pivots(h, lo, k)
    hl_, hp_, hb = last_two(ph, h, n, k)
    ll_, lp_, lb = last_two(pl, lo, n, k)
    hh, hlw = hl_ > hp_, ll_ > lp_
    struct = np.where(hh & hlw, 1, np.where(~hh & ~hlw, -1, np.where(~hh & hlw, 2, 3)))
    struct = np.where(np.isfinite(hp_) & np.isfinite(lp_), struct, 0)
    leg = np.where(lb > hb, 1, np.where(hb > lb, -1, 0))  # the latest swing a low -> an up leg
    phase = np.where(np.isin(struct, (1, -1)), np.where(leg == struct, 1, -1), 0)  # 1 impulse, -1 correction
    leg_from = np.where(leg > 0, ll_, hl_)
    leg_atr = (c - leg_from) / atr
    hi20 = pd.Series(h).rolling(20).max().to_numpy()
    lo20 = pd.Series(lo).rolling(20).min().to_numpy()
    pos20 = (c - lo20) / np.where(hi20 > lo20, hi20 - lo20, np.nan)
    phi = np.r_[np.nan, hi20[:-1]]
    plo = np.r_[np.nan, lo20[:-1]]
    brk_now = np.where(c > phi, 1, np.where(c < plo, -1, 0))
    up3 = pd.Series(brk_now == 1).rolling(3).max().to_numpy()
    dn3 = pd.Series(brk_now == -1).rolling(3).max().to_numpy()
    brk3 = np.where((up3 > 0) & ~(dn3 > 0), 1, np.where((dn3 > 0) & ~(up3 > 0), -1, 0))
    sd = cs.rolling(20).std().to_numpy()
    atr_pct = pd.Series(atr).rolling(120, min_periods=60).rank(pct=True).to_numpy()
    bbw_pct = pd.Series(sd).rolling(120, min_periods=60).rank(pct=True).to_numpy()
    c3 = np.r_[np.full(3, np.nan), c[:-3]]
    out = pd.DataFrame({
        "avail": b["avail"].to_numpy(), "tide": tide, "struct": struct, "leg": leg, "phase": phase,
        "leg_atr": leg_atr, "pos20": pos20, "brk3": brk3, "atr": atr, "atr_pct": atr_pct, "bbw_pct": bbw_pct,
        "ema_d": (c - e20) / atr, "mom3": (c - c3) / atr,
        "bar_dir": np.sign(c - o), "body_atr": (c - o) / atr,
    })
    out.columns = ["avail"] + [f"{pfx}_{x}" for x in out.columns[1:]]
    return out


# ---------------------------------------------------------------- M1 local forms and levels
def m1_forms(m: pd.DataFrame, atr15: np.ndarray) -> pd.DataFrame:
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    tv = m.tick_volume.to_numpy(float)
    idx = m.index
    H, L, C = pd.Series(h), pd.Series(lo), pd.Series(c)
    pc = C.shift(1).to_numpy()
    tr = np.nanmax(np.vstack([h - lo, np.abs(h - pc), np.abs(lo - pc)]), axis=0)
    atr1 = pd.Series(tr).rolling(14).mean().to_numpy()
    # the 30-minute box before this bar, and this bar's close against it
    bh = H.shift(1).rolling(30).max().to_numpy()
    bl = L.shift(1).rolling(30).min().to_numpy()
    boxed = (bh - bl) <= atr15
    box_brk = np.where(boxed & (c > bh), 1, np.where(boxed & (c < bl), -1, 0))
    box_now = ((H.rolling(30).max() - L.rolling(30).min()).to_numpy() <= atr15).astype(int)
    # a sweep of the last 60 minutes' low / high within the last 15 bars, reclaimed by this close
    l60 = L.shift(1).rolling(60).min().to_numpy()
    h60 = H.shift(1).rolling(60).max().to_numpy()
    lv_dn = pd.Series(np.where(lo < l60, l60, np.nan)).ffill(limit=14).to_numpy()
    lv_up = pd.Series(np.where(h > h60, h60, np.nan)).ffill(limit=14).to_numpy()
    bull = np.isfinite(lv_dn) & (c > lv_dn)
    bear = np.isfinite(lv_up) & (c < lv_up)
    sweep = np.where(bull & ~bear, 1, np.where(bear & ~bull, -1, 0))
    # staircase: three rising M1 swing lows (2 bars each side), or three falling highs
    k = 2
    ph, pl = pivots(h, lo, k)
    n = len(c)

    def three(piv, vals, rising):
        known = piv + k
        ok = known < n
        piv, known = piv[ok], known[ok]
        v = vals[piv]
        s = np.r_[np.nan, np.nan, v[:-2]]
        p = np.r_[np.nan, v[:-1]]
        cond = (p > s) & (v > p) if rising else (p < s) & (v < p)
        x = pd.Series(np.nan, index=range(n))
        x.iloc[known] = cond.astype(float)
        return x.ffill().fillna(0).to_numpy() > 0

    stair = np.where(three(pl, lo, True), 1, 0) - np.where(three(ph, h, False), 1, 0)
    spike = np.where(tr >= 2.5 * atr1, np.sign(c - o), 0)
    tvr = pd.Series(tv).rolling(5).mean().to_numpy() / pd.Series(tv).rolling(60).mean().to_numpy()
    mom15 = (c - C.shift(15).to_numpy()) / atr15
    mom60 = (c - C.shift(60).to_numpy()) / atr15
    rng30 = (H.rolling(30).max() - L.rolling(30).min()).to_numpy() / atr15
    # levels: today's server day so far, the Asian session (00-07 UTC), yesterday, 72 hours
    sday = idx.tz_convert("Europe/Athens").tz_localize(None).normalize()
    g = pd.Series(h).groupby(sday.values)
    dhi = g.cummax().groupby(sday.values).shift(1).to_numpy()
    dlo = pd.Series(lo).groupby(sday.values).cummin().groupby(sday.values).shift(1).to_numpy()
    dd = pd.DataFrame({"h": h, "l": lo, "d": sday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
    yh = pd.Series(dd.h.shift(1).reindex(sday).to_numpy())
    yl = pd.Series(dd.l.shift(1).reindex(sday).to_numpy())
    uday = idx.normalize()
    asia = (idx.hour < 7)
    ah = pd.Series(np.where(asia, h, np.nan)).groupby(uday.values).cummax().groupby(uday.values).ffill().to_numpy()
    al = pd.Series(np.where(asia, lo, np.nan)).groupby(uday.values).cummin().groupby(uday.values).ffill().to_numpy()
    after_asia = ~asia
    h72 = H.shift(15).rolling(4305, min_periods=3000).max().to_numpy()
    l72 = L.shift(15).rolling(4305, min_periods=3000).min().to_numpy()

    def side_of(up, dn):
        return np.where(up, 1, np.where(dn, -1, 0))

    day_brk = side_of(c > dhi, c < dlo)
    yday_brk = side_of(c > yh.to_numpy(), c < yl.to_numpy())
    asia_brk = np.where(after_asia, side_of(c > ah, c < al), 0)
    x72 = side_of(c >= h72, c <= l72)
    pos72 = (c - l72) / np.where(h72 > l72, h72 - l72, np.nan)
    r50 = np.abs(c - np.round(c / 50) * 50) / atr15
    return pd.DataFrame({
        "m1_atr": atr1, "box_brk": box_brk, "box_now": box_now, "sweep": sweep, "stair": stair, "spike": spike,
        "tvr": tvr, "mom15": mom15, "mom60": mom60, "rng30": rng30, "day_brk": day_brk, "yday_brk": yday_brk,
        "asia_brk": asia_brk, "x72": x72, "pos72": pos72, "r50": r50,
    }, index=idx)


def m15_atr(m: pd.DataFrame) -> np.ndarray:
    b = tf_bars(m, "15min")
    s = tf_state(b, "x")
    a = pd.Series(s["x_atr"].to_numpy(), index=pd.DatetimeIndex(b["avail"]))
    a = a[~a.index.duplicated(keep="last")]
    # known at a decision = at the M1 bar's close (its open + 1 minute)
    return a.reindex(m.index + pd.Timedelta(minutes=1), method="ffill").to_numpy()
