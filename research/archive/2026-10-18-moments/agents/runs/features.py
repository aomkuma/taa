"""Step 2 (notes.md): a feature for every M1 bar of gold (2023-10 .. 2026-10-16), each from bars closed at or
before that bar's close (no look-ahead). Saved as feats.parquet (float32), one row per M1 bar in the catalogue's
index (`i`).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/features.py
"""

from __future__ import annotations

import bisect
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(ROOT))
import gold  # noqa: E402
from catalogue import load  # noqa: E402

PAIRS = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "USDJPY": 1, "USDCHF": 1, "USDCAD": 1}
LDN, NY = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")
ONE = pd.Timedelta(minutes=1)


def roll_max(x: np.ndarray, w: int) -> np.ndarray:
    return pd.Series(x).rolling(w, min_periods=w).max().to_numpy()


def roll_min(x: np.ndarray, w: int) -> np.ndarray:
    return pd.Series(x).rolling(w, min_periods=w).min().to_numpy()


def roll_mean(x: np.ndarray, w: int) -> np.ndarray:
    return pd.Series(x).rolling(w, min_periods=w).mean().to_numpy()


def shift(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if k > 0:
        out[k:] = x[:-k]
    else:
        out[:] = x
    return out


def htf(m: pd.DataFrame, mins: int) -> pd.DataFrame:
    b = m.resample(f"{mins}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}).dropna()
    pc = b.close.shift(1)
    tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
    b["atr"] = tr.rolling(14).mean()
    b["end"] = b.index + pd.Timedelta(minutes=mins)
    return b


def at_close(values: pd.Series | np.ndarray, ends: pd.DatetimeIndex, ot: pd.DatetimeIndex) -> np.ndarray:
    """The value of the last higher-timeframe bar that ended at or before each M1 bar's close."""
    s = pd.Series(np.asarray(values, float), index=ends)
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(ot + ONE, method="ffill").to_numpy()


def tide(b: pd.DataFrame) -> np.ndarray:
    e20, e50 = b.close.ewm(span=20, adjust=False).mean(), b.close.ewm(span=50, adjust=False).mean()
    return np.where((e20 > e20.shift(3)) & (b.close > e50), 1, np.where((e20 < e20.shift(3)) & (b.close < e50), -1, 0))


def structure(b: pd.DataFrame) -> np.ndarray:
    """The bot's ChartReadFrame confirmed swing structure per bar: +1 UP, -1 DOWN, 2 CONTRACTING, 3 BROADENING,
    4 FLAT, 0 NONE (known at the bar's close: pivots confirmed by then)."""
    from app.indicators.chart_read import ChartReadFrame, Structure

    fr = ChartReadFrame("X", b[["open", "high", "low", "close"]], 0.01)
    code = {Structure.UP: 1, Structure.DOWN: -1, Structure.CONTRACTING: 2, Structure.BROADENING: 3,
            Structure.FLAT: 4, Structure.NONE: 0}
    out = np.zeros(len(b))
    for pos in range(len(b)):
        k = bisect.bisect_right(fr._confirm, pos)
        out[pos] = code[fr._trend[k - 1]] if k else 0
    return out


def frac_runs(x: np.ndarray, low: bool, half: int) -> tuple[np.ndarray, np.ndarray]:
    """Fractal lows (highs) of 2*half+1 bars, confirmed *half* bars later; for each bar, the length of the current
    run of higher lows (lower highs) among the confirmed fractals, and the last confirmed fractal's price."""
    n = len(x)
    y = x if low else -x
    ok = np.ones(n, bool)
    for k in range(1, half + 1):
        ok &= (y <= shift(y, k)) & (y < np.r_[y[k:], np.full(k, np.inf)])
    ok[:half] = False
    ok[n - half:] = False
    F = np.nonzero(ok)[0]
    run = np.zeros(len(F))
    for q in range(1, len(F)):
        run[q] = run[q - 1] + 1 if y[F[q]] > y[F[q - 1]] else 0
    out = np.full(n, np.nan)
    last = np.full(n, np.nan)
    out[F + half] = run
    last[F + half] = x[F]
    return pd.Series(out).ffill().to_numpy(), pd.Series(last).ffill().to_numpy()


def main() -> None:
    gold.below_normal_priority()
    m = load()
    m = m[m.index >= pd.Timestamp("2023-09-01", tz="UTC")]
    ot = m.index
    n = len(ot)
    o, h, lo, c, v = (m[k].to_numpy(float) for k in ("open", "high", "low", "close", "tick_volume"))
    sp = m.spread.to_numpy(float) * 0.01
    F: dict[str, np.ndarray] = {}
    u = c / 4100.0
    pc = shift(c, 1)
    tr = np.nanmax(np.c_[h - lo, np.abs(h - pc), np.abs(lo - pc)], axis=1)
    atr1 = roll_mean(tr, 14)
    m5, m15, h1 = htf(m, 5), htf(m, 15), htf(m, 60)
    a15 = at_close(m15.atr, m15.end, ot)
    F["atr15_u"] = a15 / u
    F["atr1_ratio"] = atr1 / roll_mean(tr, 1440)
    F["atr15_ratio"] = a15 / at_close(m15.atr.rolling(96 * 5).mean(), m15.end, ot)
    F["bbw1"] = 4 * pd.Series(c).rolling(20).std().to_numpy() / a15
    F["bbw5"] = 4 * at_close(m5.close.rolling(20).std(), m5.end, ot) / a15
    for w in (30, 60, 120):
        F[f"rng{w}"] = (roll_max(h, w) - roll_min(lo, w)) / a15
    # the 60-minute box
    hi60, lo60 = roll_max(h, 60), roll_min(lo, 60)
    hgt = hi60 - lo60
    F["pos60"] = (c - lo60) / np.where(hgt > 0, hgt, np.nan)
    kk = np.arange(60) - 29.5
    beta = np.convolve(c, kk[::-1] / (kk**2).sum(), mode="full")[:n]  # sum_k kk[k] * c[i-59+k]
    beta[:59] = np.nan
    F["slope60"] = beta * 60 / np.where(hgt > 0, hgt, np.nan)
    F["slope60_atr"] = beta * 60 / a15
    sh = np.zeros(n, bool)
    sl = np.zeros(n, bool)
    sh[2:-2] = (h[2:-2] >= np.maximum.reduce([h[:-4], h[1:-3], h[3:-1], h[4:]]))
    sl[2:-2] = (lo[2:-2] <= np.minimum.reduce([lo[:-4], lo[1:-3], lo[3:-1], lo[4:]]))
    top = np.zeros(n)
    bot = np.zeros(n)
    tol = 0.15 * hgt
    for k in range(2, 60):
        top += shift(sh.astype(float), k) * (shift(h, k) >= hi60 - tol)
        bot += shift(sl.astype(float), k) * (shift(lo, k) <= lo60 + tol)
    F["touch_top60"], F["touch_bot60"] = top, bot
    # equal highs / lows over 120 minutes (fractal swings within 0.1 M15 ATR of the extreme swing)
    fh = np.where(sh, h, -1e9)
    fl = np.where(sl, lo, 1e9)
    mxh = shift(roll_max(fh, 118), 2)
    mxh[mxh < -1e8] = np.nan
    mnl = shift(roll_min(fl, 118), 2)
    mnl[mnl > 1e8] = np.nan
    eqh = np.zeros(n)
    eql = np.zeros(n)
    for k in range(2, 120):
        eqh += shift(sh.astype(float), k) * (np.abs(shift(h, k) - mxh) <= 0.1 * a15)
        eql += shift(sl.astype(float), k) * (np.abs(shift(lo, k) - mnl) <= 0.1 * a15)
    F["eqh120"], F["eql120"] = eqh, eql
    F["dist_eqh"] = (mxh - c) / a15  # how far below the equal-high cluster's top
    F["dist_eql"] = (c - mnl) / a15
    # M1 / M5 swing structure: runs of higher lows / lower highs
    for half, name in ((1, "m1f3"), (2, "m1f5")):
        hl, last_l = frac_runs(lo, True, half)
        lh, last_h = frac_runs(h, False, half)
        F[f"{name}_hl"], F[f"{name}_lh"] = hl, lh
        F[f"{name}_net"] = hl - lh
    hl5, _ = frac_runs(m5.low.to_numpy(), True, 1)
    lh5, _ = frac_runs(m5.high.to_numpy(), False, 1)
    F["m5_hl"], F["m5_lh"] = at_close(hl5, m5.end, ot), at_close(lh5, m5.end, ot)
    F["m5_net"] = F["m5_hl"] - F["m5_lh"]
    # day / yesterday / Asian levels (UTC days)
    day = ot.normalize()
    dser = pd.Series(np.arange(n), index=ot)
    g = pd.Series(h).groupby(day.to_numpy())
    dhi = g.cummax().to_numpy()
    dlo = pd.Series(lo).groupby(day.to_numpy()).cummin().to_numpy()
    daily = pd.DataFrame({"h": h, "l": lo}, index=ot).groupby(day).agg({"h": "max", "l": "min"})
    yh = daily.h.shift(1).reindex(day).to_numpy()
    yl = daily.l.shift(1).reindex(day).to_numpy()
    asia = (ot.hour < 7)
    ah = pd.DataFrame({"h": np.where(asia, h, np.nan), "l": np.where(asia, lo, np.nan)}, index=ot).groupby(day).agg(
        {"h": "max", "l": "min"})
    a_h = np.where(ot.hour >= 7, ah.h.reindex(day).to_numpy(), np.nan)
    a_l = np.where(ot.hour >= 7, ah.l.reindex(day).to_numpy(), np.nan)
    for name, lv in (("dhi", dhi), ("dlo", dlo), ("yhi", yh), ("ylo", yl), ("ahi", a_h), ("alo", a_l)):
        F[f"d_{name}"] = (c - lv) / a15
    for step in (10.0, 50.0):
        F[f"round{int(step)}_pos"] = (c % step) / step  # 0 just above a round number, 1 just below the next
        F[f"round{int(step)}_dist"] = np.minimum(c % step, step - c % step) / a15
    # sweeps and reclaims within the last 15 minutes
    mn15, mx15 = roll_min(lo, 15), roll_max(h, 15)
    lvls_lo = {"p60": shift(roll_min(lo, 60), 15), "day": shift(dlo, 15), "yday": yl, "asia": shift(a_l, 15)}
    lvls_hi = {"p60": shift(roll_max(h, 60), 15), "day": shift(dhi, 15), "yday": yh, "asia": shift(a_h, 15)}
    same_day15 = shift(day.asi8.astype(float), 15) == day.asi8.astype(float)
    for name in lvls_lo:
        Ll, Lh = lvls_lo[name], lvls_hi[name]
        if name in ("day", "asia"):
            Ll = np.where(same_day15, Ll, np.nan)
            Lh = np.where(same_day15, Lh, np.nan)
        swl = (mn15 < Ll) & (c > Ll)
        swh = (mx15 > Lh) & (c < Lh)
        F[f"sweep_{name}"] = swl.astype(float) - swh.astype(float)
        F[f"brk_{name}"] = (c > Lh).astype(float) - (c < Ll).astype(float)  # beyond the level now
    # tides and the bot's swing structure
    F["h1_tide"] = at_close(tide(h1), h1.end, ot)
    F["m15_tide"] = at_close(tide(m15), m15.end, ot)
    F["m5_tide"] = at_close(tide(m5), m5.end, ot)
    F["h1_struct"] = at_close(structure(h1), h1.end, ot)
    F["m15_struct"] = at_close(structure(m15), m15.end, ot)
    e20h = h1.close.ewm(span=20, adjust=False).mean()
    F["h1_e20_dist"] = (c - at_close(e20h, h1.end, ot)) / at_close(h1.atr, h1.end, ot)
    e20q = m15.close.ewm(span=20, adjust=False).mean()
    F["m15_e20_dist"] = (c - at_close(e20q, m15.end, ot)) / a15
    # tick volume, spread
    F["tv5_60"] = roll_mean(v, 5) / roll_mean(v, 60)
    F["tv60_1440"] = roll_mean(v, 60) / roll_mean(v, 1440)
    F["tv15_slope"] = roll_mean(v, 15) / shift(roll_mean(v, 15), 15)
    F["sp_rel"] = sp / pd.Series(sp).rolling(1440).median().to_numpy()
    # wicks, consecutive closes, momentum
    lw = np.minimum(o, c) - lo
    uw = h - np.maximum(o, c)
    F["wick10"] = roll_mean(lw - uw, 10) / atr1
    F["wick3"] = roll_mean(lw - uw, 3) / atr1
    F["maxwick_lo10"] = roll_max(lw, 10) / atr1
    F["maxwick_hi10"] = roll_max(uw, 10) / atr1
    sgn = np.sign(c - o)
    cons = np.zeros(n)
    for i in range(1, n):
        cons[i] = (cons[i - 1] + sgn[i] if np.sign(cons[i - 1]) == sgn[i] else sgn[i]) if sgn[i] != 0 else 0
    F["consec"] = cons
    for k in (5, 15, 30, 60, 120):
        F[f"ret{k}"] = (c - shift(c, k)) / a15
    e20 = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
    F["ema20_dist"] = (c - e20) / atr1
    d = pd.Series(c).diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    F["rsi14"] = (100 - 100 / (1 + up / dn)).to_numpy()
    # time
    F["hour"] = ot.hour.to_numpy() + ot.minute.to_numpy() / 60
    F["dow"] = ot.dayofweek.to_numpy().astype(float)
    tl = ot.tz_convert(LDN)
    tn = ot.tz_convert(NY)
    F["min_ldn"] = ((tl.hour - 8) * 60 + tl.minute).to_numpy().astype(float)
    F["min_ny"] = ((tn.hour * 60 + tn.minute) - (9 * 60 + 30)).to_numpy().astype(float)
    F["min_ny0830"] = ((tn.hour * 60 + tn.minute) - (8 * 60 + 30)).to_numpy().astype(float)
    rel = pd.DatetimeIndex(gold.releases().t).sort_values().as_unit("ns")
    tc = (ot + ONE).as_unit("ns")
    p = rel.searchsorted(tc)
    nxt = np.where(p < len(rel), (rel[np.minimum(p, len(rel) - 1)].asi8 - tc.asi8) / 6e10, np.nan)
    prv = np.where(p > 0, (tc.asi8 - rel[np.maximum(p - 1, 0)].asi8) / 6e10, np.nan)
    F["min_to_rel"], F["min_since_rel"] = nxt, prv
    # the dollar and US500 (each per its own mean absolute 1-minute log move over the previous day)
    gl = np.log(c)
    gscale = shift(roll_mean(np.abs(np.diff(gl, prepend=np.nan)), 1440), 1)
    zs = {5: [], 30: []}
    for pair, sgnp in PAIRS.items():
        x = pd.read_parquet(ROOT / f"data/history/FBS-Demo/{pair}/M1.parquet", columns=["open_time", "close"])
        x.index = pd.DatetimeIndex(pd.to_datetime(x.open_time, utc=True))
        x = x[~x.index.duplicated(keep="last")].sort_index()
        lc = np.log(x.close.astype(float))
        sc = lc.diff().abs().rolling(1440).mean().shift(1)
        lc_a = lc.reindex(ot, method="ffill", limit=3).to_numpy()
        sc_a = sc.reindex(ot, method="ffill", limit=3).to_numpy()
        for k in zs:
            zs[k].append(sgnp * (lc_a - shift(lc_a, k)) / (sc_a * np.sqrt(k)))
    for k in zs:
        F[f"usd_z{k}"] = np.nanmean(np.vstack(zs[k]), axis=0)
        F[f"gold_z{k}"] = (gl - shift(gl, k)) / (gscale * np.sqrt(k))
        F[f"div_z{k}"] = F[f"gold_z{k}"] + F[f"usd_z{k}"]  # gold and the dollar the same way = a divergence
    x = pd.read_parquet(ROOT / "data/history/FBS-Demo/US500/M1.parquet", columns=["open_time", "close"])
    x.index = pd.DatetimeIndex(pd.to_datetime(x.open_time, utc=True))
    x = x[~x.index.duplicated(keep="last")].sort_index()
    lc = np.log(x.close.astype(float))
    sc = lc.diff().abs().rolling(1440).mean().shift(1)
    lc_a = lc.reindex(ot, method="ffill", limit=3).to_numpy()
    sc_a = sc.reindex(ot, method="ffill", limit=3).to_numpy()
    for k in (5, 30):
        F[f"spx_z{k}"] = (lc_a - shift(lc_a, k)) / (sc_a * np.sqrt(k))
    out = pd.DataFrame({k: np.asarray(val, float).astype(np.float32) for k, val in F.items()}, index=ot)
    out.index.name = "t"
    out.to_parquet(HERE / "feats.parquet")
    print(out.shape)
    print(out.describe().T[["mean", "50%", "min", "max"]].to_string())


if __name__ == "__main__":
    main()
