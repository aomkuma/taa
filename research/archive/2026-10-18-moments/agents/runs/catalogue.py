"""Step 1 (notes.md): the run catalogue - every real run on gold M1 (R = 10 U and 15 U within 30 minutes, no
pullback over 40 % of R, the start the extreme), 2023-11-01 .. 2026-10-16.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/catalogue.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import gold  # noqa: E402

REF, HZ, PB, END_HZ = 4100.0, 30, 0.40, 240
START = pd.Timestamp("2023-11-01", tz="UTC")
SPLIT = pd.Timestamp("2026-03-01", tz="UTC")
HALVES = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01",
                         "2026-10-17"], utc=True)
HLAB = ["H1 23-11", "H2 24-05", "H3 24-11", "H4 25-05", "H5 25-09", "W 26-03"]


def load() -> pd.DataFrame:
    m = gold.bars("M1")
    m = m[(m.index >= pd.Timestamp("2023-09-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-17", tz="UTC"))]
    m = m[~m.index.duplicated(keep="last")]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


def qualify(h: np.ndarray, lo: np.ndarray, c: np.ndarray, tmin: np.ndarray, R: np.ndarray, side: int):
    """For every bar i: does a run of *side* start at it (reach R within 30 minutes, the start never broken, no
    pullback > 40 % of R)? Returns (ok, the target bar)."""
    n = len(h)
    if side < 0:  # mirror: a down-run on prices is an up-run on the negated prices
        h, lo, c = -lo, -h, -c
    s = lo.copy()
    hmax = c.copy()
    alive = np.ones(n, bool)
    done = np.zeros(n, bool)
    tgt = np.full(n, -1)
    for k in range(1, HZ):
        idx = np.arange(n) + k
        valid = idx < n
        idx = np.minimum(idx, n - 1)
        inwin = valid & (tmin[idx] - tmin <= HZ - 1)
        lk, hk = lo[idx], h[idx]
        viol = (lk < s) | (hmax - lk > PB * R)
        alive &= ~(viol & ~done & inwin) | done
        alive &= inwin | done
        hmax = np.where(inwin, np.maximum(hmax, hk), hmax)
        new = alive & ~done & (hmax - s >= R)
        tgt[new] = idx[new]
        done |= new
    return done, tgt


def runs_of(ok: np.ndarray, tgt: np.ndarray, h: np.ndarray, lo: np.ndarray, tmin: np.ndarray, R: np.ndarray,
            side: int) -> list[tuple[int, int, float, int, int]]:
    """One run per leg: the first qualifying start (the lowest - nothing before its target goes below it), then
    every later same-side start up to the leg's end (a 40 % pullback) belongs to the same run."""
    out = []
    end = -1
    for i in np.nonzero(ok)[0]:
        if i <= end:
            continue
        size, xj, end = extend(i, h, lo, tmin, R[i], side)
        out.append((i, tgt[i], size, xj, end))
    return out


def extend(i: int, h: np.ndarray, lo: np.ndarray, tmin: np.ndarray, R: float, side: int) -> tuple[float, int, int]:
    """Follow the run from its start until a pullback of 40 % of the move (floor 40 % of R) or 240 minutes:
    (size, the extreme's bar, the bar that ended the leg)."""
    s = lo[i] if side > 0 else h[i]
    best, bj = 0.0, i
    j = i + 1
    n = len(h)
    while j < n and tmin[j] - tmin[i] <= END_HZ:
        adv = (s - lo[j]) if side > 0 else (h[j] - s)  # against: below the start
        back = best - ((lo[j] - s) if side > 0 else (s - h[j]))
        if adv > 0 or back > PB * max(best, R):
            break
        fav = (h[j] - s) if side > 0 else (s - lo[j])
        if fav > best:
            best, bj = fav, j
        j += 1
    return best, bj, j


def main() -> None:
    gold.below_normal_priority()
    m = load()
    ot = m.index
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    tmin = ((ot - ot[0]).total_seconds() // 60).to_numpy().astype(np.int64)
    rel = gold.releases()
    rel_t = pd.DatetimeIndex(rel.t).sort_values()
    # the M15 ATR(14) known at each M1 bar's open (the last M15 bar that ended at or before it)
    m15 = m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pc15 = m15.close.shift(1)
    tr15 = np.maximum(m15.high - m15.low, np.maximum((m15.high - pc15).abs(), (m15.low - pc15).abs()))
    a15 = tr15.rolling(14).mean()
    a15.index = a15.index + pd.Timedelta(minutes=15)
    atr15 = a15.reindex(ot, method="ffill").to_numpy()
    rows = []
    # R in U (x price / 4100) for 10 / 15; in M15 ATRs for 1.5 / 2.5 (the lead, 2026-10-18)
    for Ru in (10, 15, 1.5, 2.5):
        R = Ru * o / REF if Ru >= 10 else Ru * atr15
        R = np.where(np.isfinite(R), R, np.inf)
        for side in (1, -1):
            ok, tgt = qualify(h, lo, c, tmin, R, side)
            ok &= (ot >= START)
            for i, t, size, xj, endj in runs_of(ok, tgt, h, lo, tmin, R, side):
                endj = min(endj, len(ot) - 1)
                rows.append(dict(R=Ru, side=side, i=i, t=ot[i], tgt=t, t_tgt=ot[t], mins_to_R=int(tmin[t] - tmin[i] + 1),
                                 start_px=lo[i] if side > 0 else h[i], size=size, size_u=size / (o[i] / REF),
                                 dur=int(tmin[xj] - tmin[i] + 1), xj=xj, t_ext=ot[xj], endj=endj, t_end=ot[endj],
                                 u=o[i] / REF, atr15=atr15[i], size_atr=size / atr15[i]))
    C = pd.DataFrame(rows).sort_values(["R", "t"]).reset_index(drop=True)
    C["half"] = pd.cut(C.t, HALVES, labels=HLAB, right=False)
    C["part"] = np.where(C.t < SPLIT, "design", "window")
    # the nearest US release before / after the start
    pos = rel_t.searchsorted(C.t)
    nxt = np.array([(rel_t[p] - t).total_seconds() / 60 if p < len(rel_t) else np.nan for p, t in zip(pos, C.t)])
    prv = np.array([(t - rel_t[p - 1]).total_seconds() / 60 if p > 0 else np.nan for p, t in zip(pos, C.t)])
    C["min_to_rel"], C["min_since_rel"] = nxt, prv
    # a second leg: another run of the same R (either side) reached its extreme within 60 min before this start
    C["after_run"] = False
    for _Ru, g in C.groupby("R"):
        tt = np.sort(g.t_ext.to_numpy())
        st = g.t.to_numpy()
        p = np.searchsorted(tt, st, side="left") - 1
        ok = p >= 0
        gap = np.where(ok, st - tt[np.maximum(p, 0)], np.timedelta64(10**6, "m"))
        C.loc[g.index, "after_run"] = ok & (gap <= np.timedelta64(60, "m"))
    C.to_parquet(HERE / "catalogue.parquet")

    days = pd.Series(ot[ot >= START].normalize().unique())
    days = days[days.dt.dayofweek < 5]
    dh = pd.cut(days, HALVES, labels=HLAB, right=False).value_counts()
    dm = days.dt.strftime("%Y-%m").value_counts()
    a15m = pd.Series(atr15, index=ot)[(ot >= START) & (ot.hour < 21)]
    a15m = a15m.groupby(a15m.index.strftime("%Y-%m")).median()
    rngm = pd.Series(h - lo, index=ot)[(ot >= START)]
    for Ru, g in C.groupby("R"):
        unit = "U (x price/4100)" if Ru >= 10 else "x M15 ATR(14) at the start"
        print(f"\n=== R = {Ru} {unit} within 30 min, pullback <= 40 % of R ===")
        print(f"{'half':10} {'days':>5} {'runs':>5} {'/day':>5} {'up%':>5} {'med U':>6} {'med ATR':>7} {'med USD':>7}"
              f" {'min->R':>6} {'dur':>4} {'2nd leg%':>8} {'rel<=30m%':>9}")
        for hl, x in g.groupby("half", observed=True):
            nd = dh[hl]
            near_rel = ((x.min_since_rel <= 30) | (x.min_to_rel <= 5)).mean()
            print(f"{hl:10} {nd:5} {len(x):5} {len(x) / nd:5.2f} {100 * (x.side > 0).mean():5.1f} {x.size_u.median():6.1f}"
                  f" {x.size_atr.median():7.2f} {x['size'].median():7.1f} {x.mins_to_R.median():6.0f} {x.dur.median():4.0f}"
                  f" {100 * x.after_run.mean():8.1f} {100 * near_rel:9.1f}")
        for part, nd in (("design", dh[[x for x in HLAB if x != "W 26-03"]].sum()), ("window", dh["W 26-03"])):
            w = g[g.part == part]
            hrs = w.t.dt.hour.value_counts().sort_index()
            print(f"{part} runs per 100 days by UTC hour: " + " ".join(f"{hh:02d}:{100 * v / nd:.0f}" for hh, v in hrs.items()))
        w = g[g.part == "window"]
        print("window by weekday (runs per day): " + " ".join(
            f"{['Mon', 'Tue', 'Wed', 'Thu', 'Fri'][k]} {len(w[w.t.dt.dayofweek == k]) / max((days[days >= SPLIT].dt.dayofweek == k).sum(), 1):.1f}"
            for k in range(5)))
    print("\n=== runs per weekday, by month (all four definitions); M15 ATR(14) median in USD ===")
    piv = C.assign(mon=C.t.dt.strftime("%Y-%m")).groupby(["mon", "R"]).size().unstack("R")
    piv = piv.div(dm.reindex(piv.index), axis=0)
    piv["atr15_usd"] = a15m.reindex(piv.index)
    piv["days"] = dm.reindex(piv.index)
    print(piv.round(1).to_string())


if __name__ == "__main__":
    main()
