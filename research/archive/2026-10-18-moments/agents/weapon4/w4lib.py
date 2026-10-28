"""weapon4 library: the F1 confluence frame (journal/build.py + rules.py B0 + C4 + C5 + the M15-ATR floor),
re-implemented from M1 for any decision timeframe (M1 / M5 / M15), any hours and any market with M1 history.

Everything at the decision bar's close (the entry is the next M1 bar's open); the chart reads (``ChartReadFrame``) are
cached per market and timeframe in ``cache/``. Run with .venv (needs ``app``) and PYTHONPATH = the repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "journal"))
sys.path.insert(0, str(HERE.parent / "portfolio"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import jlib  # noqa: E402
import plib  # noqa: E402

CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)
GOLD_ATR_U = 1.63
HALVES = jlib.HALVES
DESIGN = ("2023-11-01", "2026-03-01")
WINDOW = ("2026-03-01", "2026-10-14")
ROUND = {"XAUUSD": 50.0, "XAUAUD": 50.0, "US100": 500.0, "US30": 500.0, "US500": 100.0, "JP225": 500.0,
         "EURUSD": 0.005, "GBPUSD": 0.005, "USDJPY": 0.5, "AUDUSD": 0.005, "USDCAD": 0.005, "USDCHF": 0.005,
         "NZDUSD": 0.005}
# USD per 1.00 of price at 0.01 lot (approximate for the non-USD quotes)
USD_PER_PX = {"XAUUSD": 1.0, "XAUAUD": 0.66, "US100": 0.10, "US30": 0.10, "US500": 0.10, "JP225": 0.1 / 150,
              "EURUSD": 1000.0, "GBPUSD": 1000.0, "AUDUSD": 1000.0, "NZDUSD": 1000.0, "USDJPY": 1000.0 / 150,
              "USDCAD": 1000.0 / 1.37, "USDCHF": 1000.0 / 0.85}
HTF = {1: 5, 5: 15, 15: 60}


def instr(sym: str) -> jlib.Instr:
    """jlib.Instr with real costs; markets outside jlib.SPEC get gold's cost ratios to the design median spread."""
    if sym not in jlib.SPEC:
        spec = json.load(open(ROOT / f"data/history/FBS-Demo/{sym}/spec.json"))["spec"]
        point = float(spec["point"])
        m = pd.read_parquet(ROOT / f"data/history/FBS-Demo/{sym}/M1.parquet", columns=["open_time", "spread"])
        t = pd.to_datetime(m.open_time, utc=True)
        x = m.spread[(t >= "2025-09-01") & (t < "2026-03-01")] * point
        med = float(x.median())
        jlib.SPEC[sym] = dict(pip=point * 10, point=point, slip=0.30 * med, extra=0.35 * med, stop_slip=0.65 * med,
                              stop_slip_ny=0.65 * med, round_step=ROUND.get(sym, 0.0))
    return jlib.Instr(sym)


def resample(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    return m1.resample(f"{minutes}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def atr_b(h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> np.ndarray:
    """build.py's ATR: mean of max(high - low, |previous close - high|) over 14 bars."""
    return pd.Series(np.maximum(h - lo, np.abs(np.r_[np.nan, c[:-1]] - h))).rolling(14).mean().to_numpy()


def true_atr(b: pd.DataFrame) -> pd.Series:
    pc = b.close.shift()
    tr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(14).mean()


def osc(b: pd.DataFrame) -> pd.DataFrame:
    """journal/build.m5_signals on frame b (index = open time); returned with the close-time index."""
    c = b.close
    d = c.diff()
    rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14).mean())
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    k = (100 * (c - b.low.rolling(14).min()) / (b.high.rolling(14).max() - b.low.rolling(14).min())).rolling(3).mean()
    dd = k.rolling(3).mean()
    out = pd.DataFrame({"rsi": rsi, "rsi_d": rsi.diff(), "hist_d": hist.diff(),
                        "k_up": (k > dd) & (k.shift(1) <= dd.shift(1)), "k_dn": (k < dd) & (k.shift(1) >= dd.shift(1)),
                        "o": b.open, "h": b.high, "l": b.low, "c": c})
    return out


def hammer(o, h, lo, c, side):
    rng = np.maximum(h - lo, 1e-12)
    lower = (np.minimum(o, c) - lo) / rng
    upper = (h - np.maximum(o, c)) / rng
    pos = (c - lo) / rng
    return np.where(side > 0, (lower >= 0.5) & (pos >= 2 / 3), (upper >= 0.5) & (pos <= 1 / 3))


def chart_cache(P: jlib.Instr, minutes: int, name: str) -> pd.DataFrame:
    """Per bar of the frame (close time): the chart-read levels, structure and leg (ChartReadFrame, no repaint)."""
    f = CACHE / f"cr_{P.sym}_{name}.parquet"
    if f.exists():
        d = pd.read_parquet(f)
        d["close_t"] = pd.to_datetime(d.close_t, utc=True)
        return d
    from app.indicators.chart_read import ChartReadFrame

    b = resample(P.m, minutes)
    b.index = b.index + pd.Timedelta(minutes=minutes)
    fr = ChartReadFrame(name, b, P.point)
    lv, st, ld = [], [], []
    smap = {"UP": 1, "DOWN": -1}
    for p in range(len(b)):
        r = fr.at(p)
        if r is None:
            lv.append([])
            st.append(0)
            ld.append(0)
            continue
        lv.append(sorted(float(x.price) for x in r.levels))
        st.append(smap.get(r.structure.value, 0))
        ld.append(r.leg.direction if r.leg else 0)
    d = pd.DataFrame({"close_t": b.index, "levels": lv, "struct": st, "leg_dir": ld})
    d.to_parquet(f)
    return d


def nearest(cache: pd.DataFrame, T: pd.DatetimeIndex, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Distance from x to the nearest chart level above (res) and below (sup) in the read at time T."""
    pos = pd.DatetimeIndex(cache.close_t).searchsorted(T, side="right") - 1
    res, sup = np.full(len(T), np.nan), np.full(len(T), np.nan)
    levels = cache.levels.to_numpy()
    order = np.argsort(pos, kind="stable")
    ps = pos[order]
    for g in np.split(order, np.flatnonzero(np.diff(ps)) + 1):
        if not len(g):
            continue
        p = pos[g[0]]
        if p < 0:
            continue
        lv = np.asarray(levels[p], float)
        if not len(lv):
            continue
        xi = x[g]
        i = np.searchsorted(lv, xi, side="right")
        ok = i < len(lv)
        res[g[ok]] = lv[i[ok]] - xi[ok]
        j = np.searchsorted(lv, xi, side="left") - 1
        ok = j >= 0
        sup[g[ok]] = xi[ok] - lv[j[ok]]
    return res, sup


def at_time(index_close: pd.DatetimeIndex, values: np.ndarray, T: pd.DatetimeIndex) -> np.ndarray:
    """The value of the last frame bar whose close time is <= T."""
    k = index_close.searchsorted(T, side="right") - 1
    out = values[np.clip(k, 0, None)].astype(float)
    out[k < 0] = np.nan
    return out


def unit_of(P: jlib.Instr) -> np.ndarray:
    """Per M1 bar: gold price / 4100; others the trailing 28-day median M1 ATR / 1.63."""
    if P.sym == "XAUUSD":
        return P.c / jlib.REF
    a = pd.Series(atr_b(P.h, P.lo, P.c), index=P.ot)
    return (a.rolling("28D", min_periods=2000).median() / GOLD_ATR_U).to_numpy()


def build(P: jlib.Instr, tf: int, start: str, end: str, hours: list[tuple[float, float]], name: str,
          windows72: dict[str, int] | None = None, kinds: list[str] | None = None, round_offset: float = 0.0,
          round_step: float | None = None) -> pd.DataFrame:
    """Candidate rows (both sides) on decision timeframe *tf* minutes whose entry time falls in *hours* (UTC, [a, b)
    in hours, weekdays) between start and end; rows kept when the H1 tide is with the side and price is at a level.
    Cached as cache/cand_<name>.parquet."""
    f = CACHE / f"cand_{name}.parquet"
    if f.exists():
        d = pd.read_parquet(f)
        d["t"] = pd.to_datetime(d.t, utc=True)
        return d
    windows72 = windows72 or {"front72": 4305, "front24": 1425, "front120": 7185}
    m1, ot, n = P.m, P.ot, len(P.ot)
    B = m1[["open", "high", "low", "close"]] if tf == 1 else resample(m1, tf)
    Tc = B.index + pd.Timedelta(minutes=tf)
    bo, bh, bl, bc = (B[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    batr = atr_b(bh, bl, bc)
    bmed = pd.Series(batr).rolling(1440 // tf, min_periods=max(40, 200 // tf)).median().to_numpy()
    lo3 = pd.Series(bl).rolling(3).min().to_numpy()
    hi3 = pd.Series(bh).rolling(3).max().to_numpy()
    lo5 = pd.Series(bl).rolling(5).min().to_numpy()
    hi5 = pd.Series(bh).rolling(5).max().to_numpy()
    # decision rows
    hrs = Tc.hour + Tc.minute / 60
    keep = (Tc >= pd.Timestamp(start, tz="UTC")) & (Tc < pd.Timestamp(end, tz="UTC")) & (Tc.weekday < 5)
    hk = np.zeros(len(Tc), bool)
    for a, b in hours:
        hk |= (hrs >= a) & (hrs < b)
    keep &= hk
    posi = pd.Series(np.arange(n), index=ot)
    e = posi.reindex(Tc).to_numpy()
    keep &= np.isfinite(e)
    pB = np.flatnonzero(keep)
    e = e[pB].astype(int)
    ok = (e > 7300) & (e + 200 < n) & (ot[e - 1] == Tc[pB] - pd.Timedelta(minutes=1)) & (pB > 5)
    pB, e = pB[ok], e[ok]
    T = Tc[pB]
    p1 = e - 1
    print(name, "decision bars", len(pB), flush=True)
    F = pd.DataFrame({"t": T, "e": e})
    F["atr"] = batr[pB]
    F["atr_ratio"] = batr[pB] / bmed[pB]
    x = bc[pB]
    F["c_dec"] = x
    F["spread"] = P.sp[e]
    u = unit_of(P)
    F["unit"] = u[p1]
    # the 72-h (and other) extremes of M1 bars i-W-15 .. i-16
    for col, w in windows72.items():
        F[f"{col}_hi"] = pd.Series(P.h).rolling(w).max().to_numpy()[p1 - 16]
        F[f"{col}_lo"] = pd.Series(P.lo).rolling(w).min().to_numpy()[p1 - 16]
    # M15 ATR (floor) and its 288-bar median (RM3 regime)
    m15 = resample(m1, 15)
    a15 = true_atr(m15)
    c15 = m15.index + pd.Timedelta(minutes=15)
    F["a15"] = at_time(c15, a15.to_numpy(), T)
    F["a15_3d"] = at_time(c15, a15.rolling(288, min_periods=100).median().to_numpy(), T)
    # H1 tide
    h1 = resample(m1, 60)
    hc = h1.close
    hatr = (h1.high - h1.low).rolling(14).mean()
    e20, e50 = hc.ewm(span=20, adjust=False).mean(), hc.ewm(span=50, adjust=False).mean()
    c60 = h1.index + pd.Timedelta(minutes=60)
    h1_slope = at_time(c60, ((e20 - e20.shift(3)) / hatr).to_numpy(), T)
    h1_ce50 = at_time(c60, ((hc - e50) / hatr).to_numpy(), T)
    # higher timeframe: price action bar + indicators
    htf = HTF[tf]
    Hb = resample(m1, htf)
    O = osc(Hb)
    ch = Hb.index + pd.Timedelta(minutes=htf)
    k = ch.searchsorted(T, side="right") - 1
    k = np.clip(k, 0, None)
    Ov = {c: O[c].to_numpy()[k] for c in O.columns}
    # day / yesterday / asia levels as of 15 minutes before (M1 bar p1 - 15)
    bday = pd.Series(ot.tz_convert("Europe/Athens").date)
    day_hi = pd.Series(P.h).groupby(bday).cummax().to_numpy()
    day_lo = pd.Series(P.lo).groupby(bday).cummin().to_numpy()
    dly = pd.DataFrame({"h": P.h, "l": P.lo, "d": bday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
    prev = dly.shift(1)
    uday = pd.Series(ot.normalize())
    asia = pd.Series(ot.hour < 7)
    asia_hi = pd.Series(np.where(asia, P.h, np.nan)).groupby(uday).cummax().groupby(uday).ffill().to_numpy()
    asia_lo = pd.Series(np.where(asia, P.lo, np.nan)).groupby(uday).cummin().groupby(uday).ffill().to_numpy()
    q = p1 - 15
    bd = bday.to_numpy()
    same_b = bd[q] == bd[p1]
    same_u = uday.to_numpy()[q] == uday.to_numpy()[p1]
    kinds = kinds or ["today", "yesterday", "asia", "round", "M15", "H1"]
    if "M15" in kinds or "H1" in kinds:
        m15r, h1r = chart_cache(P, 15, "M15"), chart_cache(P, 60, "H1")
        r15, s15 = nearest(m15r, T, x)
        r60, s60 = nearest(h1r, T, x)
        F["h1_struct"] = at_time(pd.DatetimeIndex(h1r.close_t), h1r.struct.to_numpy(), T)
        F["h1_leg"] = at_time(pd.DatetimeIndex(h1r.close_t), h1r.leg_dir.to_numpy(), T)
    else:
        r15 = s15 = r60 = s60 = np.full(len(T), np.nan)
        F["h1_struct"] = F["h1_leg"] = 0.0
    rs = round_step or P.round_step
    ro = round_offset
    KN = ["today", "yesterday", "asia", "round", "M15", "H1"]
    off = np.array([k not in kinds for k in KN])
    rows = []
    atr = F.atr.to_numpy()
    for side in (1, -1):
        G = F.copy()
        G["side"] = side
        tide = (h1_slope * side > 0) & (h1_ce50 * side > 0)
        L = np.vstack([
            np.where(same_b, day_lo[q] if side > 0 else day_hi[q], np.nan),
            (prev.l if side > 0 else prev.h).reindex(bd[p1]).to_numpy(),
            np.where(same_u, asia_lo[q] if side > 0 else asia_hi[q], np.nan),
            (np.floor((x - ro) / rs) * rs + ro) if side > 0 else (np.ceil((x - ro) / rs) * rs + ro),
            x - side * (s15 if side > 0 else r15),
            x - side * (s60 if side > 0 else r60),
        ]).T
        gap = (x[:, None] - L) * side
        gap[~np.isfinite(gap) | (gap <= 0)] = np.inf
        gap[:, off] = np.inf
        j = gap.argmin(1)
        dist = gap[np.arange(len(j)), j]
        level = x - side * dist
        A = np.vstack([
            np.where(same_b, day_hi[q] if side > 0 else day_lo[q], np.nan),
            (prev.h if side > 0 else prev.l).reindex(bd[p1]).to_numpy(),
            np.where(same_u, asia_hi[q] if side > 0 else asia_lo[q], np.nan),
            (np.ceil((x - ro) / rs) * rs + ro) if side > 0 else (np.floor((x - ro) / rs) * rs + ro),
            x + side * (r15 if side > 0 else s15),
            x + side * (r60 if side > 0 else s60),
        ]).T
        ga = (A - x[:, None]) * side
        ga[~np.isfinite(ga) | (ga <= 0)] = np.inf
        ga[:, off] = np.inf
        e5 = lo5[pB] if side > 0 else hi5[pB]
        e3 = lo3[pB] if side > 0 else hi3[pB]
        at_level = np.isfinite(dist) & (dist <= 3 * atr) & ((e5 - level) * side <= atr)
        m = tide & at_level
        sd = np.full(len(G), side)
        pa_b = hammer(bo[pB], bh[pB], bl[pB], bc[pB], sd)
        pa_h = hammer(Ov["o"], Ov["h"], Ov["l"], Ov["c"], sd)
        engulf = ((bc[pB - 1] - bo[pB - 1]) * side < 0) & ((bc[pB] - bo[pB - 1]) * side > 0) & ((bc[pB] - bo[pB]) * side > 0)
        reclaim = ((level - e3) * side >= 0.1 * atr) & ((x - level) * side > 0)
        if side > 0:
            rsi_ok = (Ov["rsi_d"] > 0) & (Ov["rsi"] < 50)
            st_ok = Ov["k_up"].astype(bool)
        else:
            rsi_ok = (Ov["rsi_d"] < 0) & (Ov["rsi"] > 50)
            st_ok = Ov["k_dn"].astype(bool)
        macd_ok = Ov["hist_d"] * side > 0
        G["level"], G["level_kind"], G["dist_atr"] = level, j, dist / atr
        G["room"] = ga.min(1)
        for k in range(ga.shape[1]):  # every kind's distance in front (shadow/tp70.py; inf: none)
            G[f"fr{k}"] = ga[:, k]
        G["pa"] = pa_b | pa_h | engulf | reclaim
        G["n_ind"] = rsi_ok.astype(int) + macd_ok.astype(int) + st_ok.astype(int)
        fill = P.o[e] + (P.sp[e] + P.slip if side > 0 else -P.slip)
        G["sl0"] = (fill - (level - side * atr)) * side
        for col in windows72:
            G[col] = G[f"{col}_hi"] if side > 0 else G[f"{col}_lo"]
        G["h1_slope"], G["h1_ce50"] = h1_slope * side, h1_ce50 * side
        G["h1_struct"], G["h1_leg"] = G.h1_struct * side, G.h1_leg * side
        rows.append(G[m])
    D = pd.concat(rows, ignore_index=True).drop(columns=[f"{c}_{s}" for c in windows72 for s in ("hi", "lo")])
    D.to_parquet(f)
    print(name, "rows (tide + at a level)", len(D), flush=True)
    return D


def session_of(t: pd.Series) -> np.ndarray:
    h = pd.DatetimeIndex(t).hour
    return np.where(h < 7, 0, np.where(h < 12, 1, 2))


def signals(D: pd.DataFrame, rmin: float, rmax: float, tp_u: float, be: float, hz: int, c4: float | None = 4.0,
            c4_col: str = "front72", c5: bool = True, floor: float = 0.5) -> pd.DataFrame:
    """F1's selection on candidate rows: PA + 2 of 3, stop within [rmin, rmax] U (before the floor), C4, C5."""
    m = D.pa.to_numpy() & (D.n_ind.to_numpy() >= 2)
    m &= (D.sl0 >= rmin * D.unit).to_numpy() & (D.sl0 <= rmax * D.unit).to_numpy()
    if c4 is not None:
        m &= ((D[c4_col] - D.c_dec) * D.side < c4 * D.unit).to_numpy()
    if c5:
        m &= (D.atr_ratio < 2).to_numpy()
    S = D[m].copy()
    S["sl"] = np.maximum(S.sl0, floor * S.a15) if floor else S.sl0
    S["session"] = session_of(S.t)
    S["tp"], S["be"], S["hz"], S["trail"] = tp_u * S.unit, be, hz, False
    return S.sort_values("t").reset_index(drop=True)


def run(S: pd.DataFrame, P: jlib.Instr, **kw) -> pd.DataFrame:
    z = plib.run(S, P, **kw)
    if len(z):
        z["t"] = pd.to_datetime(z.t, utc=True)
        z["usd"] = z.pnl * USD_PER_PX.get(P.sym, 1.0)
    z.attrs = {}
    return z


def days_in(a: str, b: str) -> int:
    return pd.bdate_range(a, b, inclusive="left").size


def by_half(z: pd.DataFrame) -> tuple[str, int, int]:
    h = plib.half_of(z.t)
    g = z.R.groupby(h).mean().reindex([x[0] for x in HALVES])
    nn = z.R.groupby(h).size().reindex([x[0] for x in HALVES]).fillna(0).astype(int)
    txt = " ".join(f"{v:+.2f}({k})" for v, k in zip(g.to_numpy(), nn.to_numpy()))
    return txt, int((g > 0).sum()), int(g.notna().sum())


def by_month(z: pd.DataFrame) -> tuple[str, int, int]:
    g = z.groupby(z.t.dt.strftime("%Y-%m"))
    s = g.usd.sum()
    return " ".join(f"{k[5:]} {len(v)} {v.R.mean():+.2f}R {v.usd.sum():+.1f}" for k, v in g), int((s > 0).sum()), len(s)


def account(z: pd.DataFrame) -> str:
    usd = z.usd.to_numpy()
    eq = np.r_[0, np.cumsum(usd)]
    dd = float((np.maximum.accumulate(eq) - eq).max())
    st = mx = 0
    for v in usd:
        st = st + 1 if v < 0 else 0
        mx = max(mx, st)
    stops = usd[(z.exit == "stop").to_numpy()]
    avg = float(-stops.mean()) if len(stops) else 0.0
    return (f"worst {usd.min():.2f} USD, streak {mx}, max DD {dd:.1f} USD, avg stop loss {avg:.2f} -> 6 in a row "
            f"{6 * avg:.1f} ({'fits' if 6 * avg < 50 else 'NOT'} 50 / {'fits' if 6 * avg < 100 else 'NOT'} 100)")


def summary(z: pd.DataFrame, days: int, label: str, design: bool = True) -> str:
    if not len(z):
        return f"  {label:28}    0 trades"
    per, pos, tot = by_half(z) if design else by_month(z)
    return (f"  {label:28} {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}%"
            f" R {z.R.mean():+.3f} USD {z.usd.sum():+7.1f} | {'halves' if design else 'months'}+ {pos}/{tot}: {per}")


def coin_line(S: pd.DataFrame, P: jlib.Instr, z: pd.DataFrame, seeds: int = 10, **kw) -> str:
    c = plib.coin(S, P, seeds=seeds, **kw)
    w = (z.exit == "win").mean()
    return (f"    coin R {c['R']:+.3f} (win {100 * c['win']:.0f}%) vs ours {z.R.mean():+.3f} (win {100 * w:.0f}%, edge"
            f" {100 * (w - c['win']):+.1f} pts); kinds ours {plib.kinds(z)} / coin {c['kinds']}; longs {100 * (z.side > 0).mean():.0f}%")


# ---------------------------------------------------------------------------------------------- F1 v2 exits

def runner(P: jlib.Instr, e, s, sl, room, atr1, a15v, be_at, hz, ss):
    """shadow/level_runner.runner with the instrument as a parameter."""
    entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
    stop, armed, broke, best = entry - s * sl, False, False, -np.inf
    lvl = entry + s * room if np.isfinite(room) else np.nan
    end = min(e + hz, len(P.o) - 1)
    for j in range(e, end):
        adv = P.lo[j] if s > 0 else P.h[j] + P.sp[j]
        if (adv - stop) * s <= 0:
            return (stop - s * ss - entry) * s, j - e + 1, "stop" if not (armed or broke) else "trail"
        fav = (P.h[j] - entry) if s > 0 else (entry - P.lo[j] - P.sp[j])
        if not armed and fav >= be_at:
            armed, stop = True, entry if (entry - stop) * s > 0 else stop
        cl = P.c[j] if s > 0 else P.c[j] + P.sp[j]
        if np.isfinite(lvl) and not broke and (cl - lvl) * s > 0:
            broke = True
            ns = lvl - s * 0.5 * atr1
            if (ns - stop) * s > 0:
                stop = ns
        if broke:
            best = max(best, (cl - entry) * s)
            ns = entry + s * (best - a15v)
            if (ns - stop) * s > 0:
                stop = ns
    x = end - 1
    px = P.c[x] - (P.slip if s > 0 else -(P.sp[x] + P.slip))
    return (px - entry) * s, end - e, "time"


def scratch(P: jlib.Instr, e, s, tp, sl, ss, after, need):
    """shadow/f1_improve.scratch (BE 0.6, 60 min, out at bar e+after-1's close when the best < need and the close
    is against the entry); *need* in price units. Returns pnl, mins, exit, mfe."""
    entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
    stop, armed, mfe = entry - s * sl, False, 0.0
    end = min(e + 60, len(P.o) - 1)
    for j in range(e, end):
        adv = P.lo[j] if s > 0 else P.h[j] + P.sp[j]
        fav = P.h[j] if s > 0 else P.lo[j] + P.sp[j]
        if (adv - stop) * s <= 0:
            return (stop - s * ss - entry) * s, j - e + 1, "be" if armed else "stop", mfe
        if (fav - entry) * s >= tp:
            return tp, j - e + 1, "win", mfe
        mfe = max(mfe, (fav - entry) * s)
        if not armed and mfe >= 0.6 * tp:
            armed, stop = True, entry
        if j == e + after - 1 and mfe < need:
            px = P.c[j] - (P.slip if s > 0 else -(P.sp[j] + P.slip))
            if (px - entry) * s < 0:
                return (px - entry) * s, j - e + 1, "scratch", mfe
    x = end - 1
    px = P.c[x] - (P.slip if s > 0 else -(P.sp[x] + P.slip))
    return (px - entry) * s, end - e, "time", mfe


def run_v2(S: pd.DataFrame, P: jlib.Instr, per_sess: int = 2, coin: np.random.Generator | None = None) -> pd.DataFrame:
    """F1 v2's exits (RM3 regime runner, else 8 U + BE 0.6 + 60 min + the 10-bar scratch), one position at a time,
    at most *per_sess* a session-day. S needs t, e, side, session, sl, tp, unit, room, c_dec, atr, a15, a15_3d."""
    rows, free, cnt = [], pd.Timestamp(0, tz="UTC"), {}
    x = S.sort_values("t").drop_duplicates("t")
    for r in x.itertuples():
        key = (r.t.normalize(), r.session)
        if r.t < free or cnt.get(key, 0) >= per_sess:
            continue
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        e = int(r.e)
        s = int(r.side) if coin is None else int(coin.choice([-1, 1]))
        strong = np.isfinite(r.a15_3d) and r.a15 >= 1.3 * r.a15_3d
        if strong:
            fill = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
            room_f = (r.room - (fill - r.c_dec) * s) if s == int(r.side) else np.nan
            pnl, mins, ex = runner(P, e, s, r.sl, room_f, r.atr, r.a15, 0.6 * r.tp, 180, ss)
            mfe = np.nan
        else:
            pnl, mins, ex, mfe = scratch(P, e, s, r.tp, r.sl, ss, 10, 2.0 * r.unit)
        kind = ""
        if ex == "stop":
            later = range(e + int(mins), min(e + 120, len(P.o)))
            entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
            hit = any(((P.h[k] if s > 0 else P.lo[k] + P.sp[k]) - entry) * s >= r.tp for k in later)
            kind = "3" if hit else ("2" if np.isfinite(mfe) and mfe >= 0.5 * r.tp else "1")
        rows.append(dict(t=r.t, side=s, session=int(r.session), e=e, pnl=pnl, mins=mins, exit=ex, kind=kind,
                         R=pnl / (r.sl + ss), sl=r.sl, tp=r.tp, unit=r.unit, strong=strong))
        free = r.t + pd.Timedelta(minutes=int(mins))
        cnt[key] = cnt.get(key, 0) + 1
    z = pd.DataFrame(rows)
    if len(z):
        z["usd"] = z.pnl * USD_PER_PX.get(P.sym, 1.0)
        z["pnl_u"] = z.pnl / z.unit
    return z


# ---------------------------------------------------------------------------------------------- round frames, many grids

def build_round_multi(P: jlib.Instr, start: str, end: str, hours: list[tuple[float, float]], name: str,
                      step: float, offsets: list[float]) -> dict[float, pd.DataFrame]:
    """The M1 frame with the round grid (step, + offset) as the only level, for several offsets at once (the base
    features computed once). Same definitions as build(..., kinds=["round"]); cached per offset."""
    out, todo = {}, []
    for o in offsets:
        f = CACHE / f"cand_{name}_o{o:g}.parquet"
        if f.exists():
            d = pd.read_parquet(f)
            d["t"] = pd.to_datetime(d.t, utc=True)
            out[o] = d
        else:
            todo.append(o)
    if not todo:
        return out
    tf = 1
    m1, ot, n = P.m, P.ot, len(P.ot)
    bo, bh, bl, bc = P.o, P.h, P.lo, P.c
    Tc = ot + pd.Timedelta(minutes=1)
    batr = atr_b(bh, bl, bc)
    bmed = pd.Series(batr).rolling(1440, min_periods=200).median().to_numpy()
    lo3, hi3 = pd.Series(bl).rolling(3).min().to_numpy(), pd.Series(bh).rolling(3).max().to_numpy()
    lo5, hi5 = pd.Series(bl).rolling(5).min().to_numpy(), pd.Series(bh).rolling(5).max().to_numpy()
    hrs = Tc.hour + Tc.minute / 60
    keep = (Tc >= pd.Timestamp(start, tz="UTC")) & (Tc < pd.Timestamp(end, tz="UTC")) & (Tc.weekday < 5)
    hk = np.zeros(n, bool)
    for a, b in hours:
        hk |= (hrs >= a) & (hrs < b)
    keep &= hk
    pB = np.flatnonzero(keep)
    pB = pB[(pB > 7300) & (pB + 201 < n)]
    pB = pB[ot[pB + 1] == Tc[pB]]
    e = pB + 1
    T = Tc[pB]
    p1 = pB
    F = pd.DataFrame({"t": T, "e": e})
    atr = batr[pB]
    F["atr"], F["atr_ratio"] = atr, batr[pB] / bmed[pB]
    x = bc[pB]
    F["c_dec"], F["spread"] = x, P.sp[e]
    F["unit"] = unit_of(P)[p1]
    hi72 = pd.Series(P.h).rolling(4305).max().to_numpy()[p1 - 16]
    lo72 = pd.Series(P.lo).rolling(4305).min().to_numpy()[p1 - 16]
    m15 = resample(m1, 15)
    a15 = true_atr(m15)
    c15 = m15.index + pd.Timedelta(minutes=15)
    F["a15"] = at_time(c15, a15.to_numpy(), T)
    F["a15_3d"] = at_time(c15, a15.rolling(288, min_periods=100).median().to_numpy(), T)
    h1 = resample(m1, 60)
    hc = h1.close
    hatr = (h1.high - h1.low).rolling(14).mean()
    e20, e50 = hc.ewm(span=20, adjust=False).mean(), hc.ewm(span=50, adjust=False).mean()
    c60 = h1.index + pd.Timedelta(minutes=60)
    h1_slope = at_time(c60, ((e20 - e20.shift(3)) / hatr).to_numpy(), T)
    h1_ce50 = at_time(c60, ((hc - e50) / hatr).to_numpy(), T)
    Hb = resample(m1, 5)
    O = osc(Hb)
    ch = Hb.index + pd.Timedelta(minutes=5)
    k = np.clip(ch.searchsorted(T, side="right") - 1, 0, None)
    Ov = {c: O[c].to_numpy()[k] for c in O.columns}
    F["h1_struct"] = F["h1_leg"] = 0.0
    print(name, "decision bars", len(pB), flush=True)
    for o in todo:
        rows = []
        for side in (1, -1):
            G = F.copy()
            G["side"] = side
            tide = (h1_slope * side > 0) & (h1_ce50 * side > 0)
            level = (np.floor((x - o) / step) * step + o) if side > 0 else (np.ceil((x - o) / step) * step + o)
            dist = (x - level) * side
            nxt = level + side * step
            e5 = lo5[pB] if side > 0 else hi5[pB]
            e3 = lo3[pB] if side > 0 else hi3[pB]
            at_level = (dist > 0) & (dist <= 3 * atr) & ((e5 - level) * side <= atr)
            m = tide & at_level
            sd = np.full(len(G), side)
            pa_b = hammer(bo[pB], bh[pB], bl[pB], bc[pB], sd)
            pa_h = hammer(Ov["o"], Ov["h"], Ov["l"], Ov["c"], sd)
            engulf = ((bc[pB - 1] - bo[pB - 1]) * side < 0) & ((bc[pB] - bo[pB - 1]) * side > 0) & ((bc[pB] - bo[pB]) * side > 0)
            reclaim = ((level - e3) * side >= 0.1 * atr) & ((x - level) * side > 0)
            if side > 0:
                rsi_ok, st_ok = (Ov["rsi_d"] > 0) & (Ov["rsi"] < 50), Ov["k_up"].astype(bool)
            else:
                rsi_ok, st_ok = (Ov["rsi_d"] < 0) & (Ov["rsi"] > 50), Ov["k_dn"].astype(bool)
            macd_ok = Ov["hist_d"] * side > 0
            G["level"], G["level_kind"], G["dist_atr"] = level, 3, dist / atr
            G["room"] = (nxt - x) * side
            G["pa"] = pa_b | pa_h | engulf | reclaim
            G["n_ind"] = rsi_ok.astype(int) + macd_ok.astype(int) + st_ok.astype(int)
            fill = P.o[e] + (P.sp[e] + P.slip if side > 0 else -P.slip)
            G["sl0"] = (fill - (level - side * atr)) * side
            G["front72"] = hi72 if side > 0 else lo72
            G["h1_slope"], G["h1_ce50"] = h1_slope * side, h1_ce50 * side
            rows.append(G[m])
        d = pd.concat(rows, ignore_index=True)
        d.to_parquet(CACHE / f"cand_{name}_o{o:g}.parquet")
        out[o] = d
    return out


# ---------------------------------------------------------------------------------------------- anchors (Q1)

_ANCH: dict = {}


def anchor_arrays(P: jlib.Instr) -> dict:
    """Per M1 bar q (the bar the anchor is read at = decision bar - 16): highs / lows of the anchors."""
    if P.sym in _ANCH:
        return _ANCH[P.sym]
    h, lo, ot = pd.Series(P.h), pd.Series(P.lo), P.ot
    A = {"A72": (h.rolling(4305).max().to_numpy(), lo.rolling(4305).min().to_numpy()),
         "A24": (h.rolling(1425).max().to_numpy(), lo.rolling(1425).min().to_numpy()),
         "AW": (h.rolling(7185).max().to_numpy(), lo.rolling(7185).min().to_numpy())}
    hr = ot.hour
    sess = np.where(hr < 7, 0, np.where(hr < 12, 1, np.where(hr < 20, 2, 3)))
    key = pd.Series(ot.normalize().asi8 * 4 + sess)
    A["AS"] = (h.groupby(key).cummax().to_numpy(), lo.groupby(key).cummin().to_numpy())
    A["_skey"] = key.to_numpy()
    bday = pd.Series(ot.tz_convert("Europe/Athens").date)
    dly = pd.DataFrame({"h": P.h, "l": P.lo, "d": bday}).groupby("d").agg(h=("h", "max"), l=("l", "min")).shift(1)
    A["AY"] = (dly.h.reindex(bday).to_numpy(), dly.l.reindex(bday).to_numpy())
    _ANCH[P.sym] = A
    return A


def add_anchors(D: pd.DataFrame, P: jlib.Instr) -> pd.DataFrame:
    """Signed distance (U) from the decision close to each anchor in the trade's way (< 0 = already behind)."""
    A = anchor_arrays(P)
    p = D.e.to_numpy() - 1
    q = p - 16
    s = D.side.to_numpy()
    x = D.c_dec.to_numpy()
    u = D.unit.to_numpy()
    D = D.copy()
    for k in ("A72", "A24", "AW", "AY"):
        hi, lo_ = A[k]
        idx = p if k == "AY" else q
        D[f"d_{k}"] = (np.where(s > 0, hi[idx], lo_[idx]) - x) * s / u
    hi, lo_ = A["AS"]
    same = A["_skey"][q] == A["_skey"][p]
    started = A["_skey"][np.maximum(q - 14, 0)] == A["_skey"][p]  # >= 30 minutes into the session
    D["d_AS"] = np.where(same & started, (np.where(s > 0, hi[q], lo_[q]) - x) * s / u, np.nan)
    return D
