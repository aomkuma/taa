"""Candidate table for the journal agent: every minute of the three active windows (as own_ml_long: Asia 00:00-02:00
UTC, London 08:00-09:30 London, New York 08:15-11:15 ET) x both sides, with the confluence rule's parts (round 9,
research/2026-10-18-moments/confluence.py, re-implemented from M1 so it runs before 2025-12 and on FX pairs) and the
context a trader reads on the chart (the approach into the level, compression, H1/M15 structure, news, room ahead).
Everything at the decision bar's close (the minute before the entry bar).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/journal/build.py SYM design|test

design = candidates 2023-11-01 .. 2026-02-28; test = 2026-03-01 .. 2026-10-13. Needs app (ChartReadFrame): .venv.
"""

from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))
import jlib  # noqa: E402

from app.indicators.chart_read import ChartReadFrame  # noqa: E402

WINDOWS = [(0, "UTC", "00:00", "02:00"), (1, "Europe/London", "08:00", "09:30"), (2, "America/New_York", "08:15", "11:15")]
STRUCT = {"UP": 1, "DOWN": -1}


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False).mean()


def tf_features(m1: pd.DataFrame, minutes: int, t: pd.DatetimeIndex) -> pd.DataFrame:
    b = m1.resample(f"{minutes}min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    c = b["close"]
    atr = (b["high"] - b["low"]).rolling(14).mean()
    e20, e50 = ema(c, 20), ema(c, 50)
    f = pd.DataFrame({"c_e20": (c - e20) / atr, "c_e50": (c - e50) / atr, "e20_slope": (e20 - e20.shift(3)) / atr, "atr": atr})
    k = (b.index + pd.Timedelta(minutes=minutes)).searchsorted(t, side="right") - 1
    out = f.iloc[np.clip(k, 0, None)].reset_index(drop=True)
    out[k < 0] = np.nan
    return out


def m5_signals(m1: pd.DataFrame) -> pd.DataFrame:
    """confluence.m5_signals (close-time index)."""
    b = m1.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    c = b.close
    d = c.diff()
    rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14).mean())
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    k = (100 * (c - b.low.rolling(14).min()) / (b.high.rolling(14).max() - b.low.rolling(14).min())).rolling(3).mean()
    dd = k.rolling(3).mean()
    out = pd.DataFrame({"rsi": rsi, "rsi_d": rsi.diff(), "hist_d": hist.diff(),
                        "k_cross_up": (k > dd) & (k.shift(1) <= dd.shift(1)), "k_cross_dn": (k < dd) & (k.shift(1) >= dd.shift(1)),
                        "o": b.open, "h": b.high, "l": b.low, "c": c})
    out.index = out.index + pd.Timedelta(minutes=5)
    return out


def hammer(o, h, lo, c, side):
    rng = np.maximum(h - lo, 1e-12)
    lower = (np.minimum(o, c) - lo) / rng
    upper = (h - np.maximum(o, c)) / rng
    pos = (c - lo) / rng
    return np.where(side > 0, (lower >= 0.5) & (pos >= 2 / 3), (upper >= 0.5) & (pos <= 1 / 3))


def chart_reads(m1: pd.DataFrame, minutes: int, name: str, times: pd.DatetimeIndex, point: float):
    """Per candidate time: nearest chart-read level above/below the decision close, the structure (no-repaint and
    'now'), the last pivot high/low; plus a table of each read bar's level prices (for the charts)."""
    b = m1.resample(f"{minutes}min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b.index = b.index + pd.Timedelta(minutes=minutes)
    fr = ChartReadFrame(name, b, point)
    pos = b.index.searchsorted(times, side="right") - 1
    close = m1.close.reindex(times - pd.Timedelta(minutes=1)).to_numpy()
    cache: dict[int, tuple] = {}
    cols = {k: [] for k in ("res", "sup", "struct", "now", "phi", "plo", "leg_dir", "leg_atr")}
    for p, x in zip(pos, close, strict=True):
        if p not in cache:
            r = fr.at(int(p)) if p >= 0 else None
            if r is None:
                cache[p] = ([], 0, 0, np.nan, np.nan, 0, np.nan)
            else:
                his = [pv.price for pv in r.pivots if pv.kind.value == "HIGH"]
                los = [pv.price for pv in r.pivots if pv.kind.value == "LOW"]
                cache[p] = ([lv.price for lv in r.levels], STRUCT.get(r.structure.value, 0),
                            STRUCT.get(r.structure_now.value, 0) if r.structure_now is not None else 0,
                            his[-1] if his else np.nan, los[-1] if los else np.nan,
                            r.leg.direction if r.leg else 0, r.leg.leg_atr if r.leg else np.nan)
        lv, st, now, phi, plo, ld, la = cache[p]
        lv = np.array(lv)
        a, bl = lv[lv > x], lv[lv < x]
        cols["res"].append(a.min() - x if len(a) else np.nan)
        cols["sup"].append(x - bl.max() if len(bl) else np.nan)
        cols["struct"].append(st)
        cols["now"].append(now)
        cols["phi"].append(phi)
        cols["plo"].append(plo)
        cols["leg_dir"].append(ld)
        cols["leg_atr"].append(la)
    lv_table = pd.DataFrame({"tf": name, "close_t": [b.index[p] for p in cache if p >= 0],
                             "levels": [list(map(float, cache[p][0])) for p in cache if p >= 0]})
    return pd.DataFrame({f"{name}_{k}": v for k, v in cols.items()}), lv_table


def main() -> None:
    sym, part = sys.argv[1], sys.argv[2]
    jlib.gold.below_normal_priority()
    lo_t, hi_t = (("2023-11-01", "2026-03-01") if part == "design" else ("2026-03-01", "2026-10-14"))
    P = jlib.Instr(sym)
    m1 = P.m
    ot, o, h, lo, c, sp, v = P.ot, P.o, P.h, P.lo, P.c, P.sp, P.v
    n = len(c)
    # candidate entry bars
    days = [d for d in pd.date_range(lo_t, pd.Timestamp(hi_t) - pd.Timedelta(days=1), freq="D") if d.weekday() < 5]
    cand = []
    for d in days:
        for sess, zone, a, b in WINDOWS:
            z = ZoneInfo(zone)
            t0 = pd.Timestamp(f"{d.date()} {a}").tz_localize(z).tz_convert("UTC")
            t1 = pd.Timestamp(f"{d.date()} {b}").tz_localize(z).tz_convert("UTC")
            for t in pd.date_range(t0, t1 - pd.Timedelta(minutes=1), freq="min"):
                cand.append((t, sess, t0))
    cd = pd.DataFrame(cand, columns=["t", "session", "t0"])
    posi = pd.Series(np.arange(n), index=ot)
    cd["e"] = posi.reindex(cd.t).to_numpy()
    cd = cd.dropna(subset=["e"])
    cd["e"] = cd.e.astype(int)
    cd = cd[(cd.e > 3000) & (cd.e + 130 < n)]
    cd = cd[(ot[cd.e - 1] == cd.t - pd.Timedelta(minutes=1))].reset_index(drop=True)
    e = cd.e.to_numpy()
    p = e - 1
    T = pd.DatetimeIndex(cd.t)
    print(sym, part, "candidate minutes", len(cd), flush=True)

    F = pd.DataFrame({"t": cd.t, "e": e, "session": cd.session})
    F["min_in"] = ((cd.t - cd.t0).dt.total_seconds() / 60).to_numpy()
    atr14 = pd.Series(np.maximum(h - lo, np.abs(np.r_[np.nan, c[:-1]] - h))).rolling(14).mean().to_numpy()
    F["atr1"] = atr14[p]
    F["close"] = c[p]
    F["spread"] = sp[e]
    for k in (5, 15, 30, 60):
        F[f"ret{k}"] = (c[p] - c[p - k]) / F.atr1
    for k in (5, 15, 60, 240):
        hh = np.array([h[i - k + 1 : i + 1].max() for i in p])
        ll = np.array([lo[i - k + 1 : i + 1].min() for i in p])
        F[f"rng{k}"] = (hh - ll) / F.atr1
        F[f"pos{k}"] = (c[p] - ll) / np.maximum(hh - ll, 1e-12)
    F["atr_ratio"] = F.atr1 / pd.Series(atr14).rolling(1440, min_periods=200).median().to_numpy()[p]
    vmean = pd.Series(v).rolling(60).mean().to_numpy()
    F["vol5"] = np.array([v[i - 4 : i + 1].sum() for i in p]) / np.maximum(5 * vmean[p], 1)
    # broker-day and Asian levels (confluence.py)
    bday = pd.Series(ot.tz_convert("Europe/Athens").date)
    day_hi = pd.Series(h).groupby(bday).cummax().to_numpy()
    day_lo = pd.Series(lo).groupby(bday).cummin().to_numpy()
    dly = pd.DataFrame({"h": h, "l": lo, "d": bday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
    prev = dly.shift(1)
    adr = (dly.h - dly.l).shift(1).rolling(20).mean()
    uday = pd.Series(ot.normalize())
    asia = pd.Series(ot.hour < 7)
    asia_hi = pd.Series(np.where(asia, h, np.nan)).groupby(uday).cummax().groupby(uday).ffill().to_numpy()
    asia_lo = pd.Series(np.where(asia, lo, np.nan)).groupby(uday).cummin().groupby(uday).ffill().to_numpy()
    q = np.clip(p - 15, 0, n - 1)
    bd = bday.to_numpy()
    same_bday = bd[q] == bd[p]
    same_uday = uday.to_numpy()[q] == uday.to_numpy()[p]
    F["day_rng_adr"] = (day_hi[p] - day_lo[p]) / adr.reindex(bd[p]).to_numpy()
    F["day_pos"] = (c[p] - day_lo[p]) / np.maximum(day_hi[p] - day_lo[p], 1e-12)
    # higher timeframes
    for mins, name in ((60, "h1"), (15, "m15")):
        tf = tf_features(m1, mins, T)
        for col in tf.columns:
            F[f"{name}_{col}"] = tf[col].to_numpy()
    lvt = []
    for mins, name in ((15, "M15"), (60, "H1")):
        cr, table = chart_reads(m1, mins, name, T, P.point)
        for col in cr.columns:
            F[f"cr_{col}"] = cr[col].to_numpy()
        lvt.append(table)
        print(name, "reads done", flush=True)
    pd.concat(lvt).to_parquet(HERE / f"levels_{sym}_{part}.parquet")
    # news (US releases)
    rel = jlib.gold.releases()
    rt = np.sort(rel.t.to_numpy())
    tv = cd.t.to_numpy()
    k = np.searchsorted(rt, tv, side="right") - 1
    since = (tv - rt[np.clip(k, 0, None)]) / np.timedelta64(1, "m")
    F["since_rel"] = np.where(k >= 0, since, 1e4)
    k2 = np.searchsorted(rt, tv, side="left")
    F["until_rel"] = np.where(k2 < len(rt), (rt[np.clip(k2, 0, len(rt) - 1)] - tv) / np.timedelta64(1, "m"), 1e4)
    m5 = m5_signals(m1)
    k5 = m5.index.searchsorted(T, side="right") - 1
    r5 = m5.iloc[k5]
    ext = {kk: (np.array([lo[i - kk + 1 : i + 1].min() for i in p]), np.array([h[i - kk + 1 : i + 1].max() for i in p])) for kk in (3, 5)}

    rows = []
    for side in (1, -1):
        G = F.copy()
        G["side"] = side
        x = c[p]
        sd = np.full(len(G), side)
        cands_ = {
            "today": np.where(same_bday, day_lo[q] if side > 0 else day_hi[q], np.nan),
            "yesterday": (prev.l if side > 0 else prev.h).reindex(bd[p]).to_numpy(),
            "asia": np.where(same_uday, asia_lo[q] if side > 0 else asia_hi[q], np.nan),
            "round": (np.floor(x / P.round_step) * P.round_step) if side > 0 else (np.ceil(x / P.round_step) * P.round_step),
            "M15": x - side * (G.cr_M15_sup if side > 0 else G.cr_M15_res).to_numpy(float),
            "H1": x - side * (G.cr_H1_sup if side > 0 else G.cr_H1_res).to_numpy(float),
        }
        names = np.array(list(cands_))
        L = np.vstack(list(cands_.values())).T
        gap = (x[:, None] - L) * side
        gap[~np.isfinite(gap) | (gap <= 0)] = np.inf
        j = gap.argmin(1)
        dist = gap[np.arange(len(j)), j]
        level = x - side * dist
        G["level"], G["level_kind"], G["dist_atr"] = level, names[j], dist / G.atr1
        # how many level kinds lie within 1 ATR of the chosen one (a cluster)
        G["cluster"] = (np.abs(L - level[:, None]) <= G.atr1.to_numpy()[:, None]).sum(1)
        # the room ahead: nearest opposite level (in front of the trade), same six kinds mirrored
        ahead = {
            "today": np.where(same_bday, day_hi[q] if side > 0 else day_lo[q], np.nan),
            "yesterday": (prev.h if side > 0 else prev.l).reindex(bd[p]).to_numpy(),
            "asia": np.where(same_uday, asia_hi[q] if side > 0 else asia_lo[q], np.nan),
            "round": (np.ceil(x / P.round_step) * P.round_step) if side > 0 else (np.floor(x / P.round_step) * P.round_step),
            "M15": x + side * (G.cr_M15_res if side > 0 else G.cr_M15_sup).to_numpy(float),
            "H1": x + side * (G.cr_H1_res if side > 0 else G.cr_H1_sup).to_numpy(float),
        }
        A = np.vstack(list(ahead.values())).T
        ga = (A - x[:, None]) * side
        ga[~np.isfinite(ga) | (ga <= 0)] = np.inf
        G["room"] = ga.min(1)  # price units
        tide = (G.h1_e20_slope * side > 0) & (G.h1_c_e50 * side > 0)
        e5 = ext[5][0] if side > 0 else ext[5][1]
        at_level = np.isfinite(dist) & (dist <= 3 * G.atr1) & ((e5 - level) * side <= G.atr1)
        pa_m1 = hammer(o[p], h[p], lo[p], c[p], sd)
        pa_m5 = hammer(r5.o.to_numpy(), r5.h.to_numpy(), r5.l.to_numpy(), r5.c.to_numpy(), sd)
        prev_bear = (c[p - 1] - o[p - 1]) * side < 0
        engulf = prev_bear & ((c[p] - o[p - 1]) * side > 0) & ((c[p] - o[p]) * side > 0)
        e3 = ext[3][0] if side > 0 else ext[3][1]
        reclaim = ((level - e3) * side >= 0.1 * G.atr1) & ((c[p] - level) * side > 0)
        rsi_ok = ((r5.rsi_d > 0) & (r5.rsi < 50)).to_numpy() if side > 0 else ((r5.rsi_d < 0) & (r5.rsi > 50)).to_numpy()
        macd_ok = (r5.hist_d * side > 0).to_numpy()
        stoch_ok = (r5.k_cross_up if side > 0 else r5.k_cross_dn).to_numpy()
        G["tide"], G["at_level"] = tide.to_numpy(), at_level.to_numpy()
        G["pa_m1"], G["pa_m5"], G["engulf"], G["reclaim"] = pa_m1, pa_m5, engulf, reclaim.to_numpy()
        G["rsi_ok"], G["macd_ok"], G["stoch_ok"] = rsi_ok, macd_ok, stoch_ok
        G["m5_rsi"] = r5.rsi.to_numpy() if side > 0 else 100 - r5.rsi.to_numpy()
        G["fill"] = o[e] + (sp[e] + P.slip if side > 0 else -P.slip)
        G["risk"] = (G.fill - (level - side * G.atr1)) * side
        # signed context
        for col in ("ret5", "ret15", "ret30", "ret60", "h1_c_e20", "h1_c_e50", "h1_e20_slope", "m15_c_e20", "m15_c_e50", "m15_e20_slope"):
            G[col] = G[col] * side
        for col in ("pos5", "pos15", "pos60", "pos240", "day_pos"):
            G[col] = G[col] if side > 0 else 1 - G[col]
        for tfn in ("M15", "H1"):
            G[f"cr_{tfn}_struct"] = G[f"cr_{tfn}_struct"] * side
            G[f"cr_{tfn}_now"] = G[f"cr_{tfn}_now"] * side
            G[f"cr_{tfn}_leg_dir"] = G[f"cr_{tfn}_leg_dir"] * side
        rows.append(G)
    D = pd.concat(rows, ignore_index=True)
    D.to_parquet(HERE / f"cand_{sym}_{part}.parquet")
    print(D.shape, "saved", flush=True)


if __name__ == "__main__":
    main()
