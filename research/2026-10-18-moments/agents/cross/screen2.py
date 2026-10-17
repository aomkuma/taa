"""Agent "cross", step 3b: episodes for gold and the seven majors (design data only, 2023-11 .. 2026-02).

A signal fires when |z| of an input's last L minutes reaches thr (first minute, then silent 60 minutes) inside a
session; side = sign(z) x the direction measured in step 1b (corr sign: +1 = the target moves with the input).
Target move close t -> close t+H in pips (gold: USD), signed by side, minus the drift of that session-half;
cost = the median spread of that session-half in pips + 0.4 pip (gold: + 0.14 USD). Per half: excess pips.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/screen2.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from measure import HALVES, PANEL, scaled_returns  # noqa: E402
from measure2 import dollar_ex  # noqa: E402
from screen import episodes  # noqa: E402

PIP = {"gc": 1.0, "EURUSD": 1e-4, "GBPUSD": 1e-4, "AUDUSD": 1e-4, "NZDUSD": 1e-4, "USDCHF": 1e-4, "USDCAD": 1e-4, "USDJPY": 1e-2}
POINT = {"gc": 0.01, "USDJPY": 0.001}
SESS = {"asia": (0, 7), "london": (7, 12), "ny": (12, 17), "late": (17, 21)}
LO, HI = pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")


def spread_pips(tgt: str, idx: pd.DatetimeIndex) -> np.ndarray:
    if tgt == "gc":
        g = gold.bars("M1")
        s = g["spread"].astype(float) * 0.01
    else:
        d = pd.read_parquet(f"data/history/FBS-Demo/{tgt}/M1.parquet", columns=["open_time", "spread"])
        d.index = pd.DatetimeIndex(pd.to_datetime(d.open_time, utc=True))
        s = d["spread"].astype(float) * POINT.get(tgt, 1e-5) / PIP[tgt]
    s = s[~s.index.duplicated()]
    return s.reindex(idx).to_numpy()


def main() -> None:
    gold.below_normal_priority()
    p = pd.read_parquet(PANEL)
    t_ns = p.index.as_unit("ns").asi8
    eq = {L: (scaled_returns(p, "US500", L, -1, t_ns) + scaled_returns(p, "JP225", L, -1, t_ns)) / 2 for L in (30, 60)}
    us100 = {L: scaled_returns(p, "US100", L, -1, t_ns) for L in (30, 60)}
    win = (p.index >= LO) & (p.index < HI)
    hour = p.index.hour.to_numpy()
    half = np.full(len(p), "", dtype=object)
    for n, a, b in HALVES:
        half[(p.index >= pd.Timestamp(a, tz="UTC")) & (p.index < pd.Timestamp(b, tz="UTC"))] = n
    rows = []
    for tgt in PIP:
        q = p.copy()
        q["USDx"] = dollar_ex(p, tgt)
        sp = spread_pips(tgt, p.index)
        c = q[tgt].to_numpy(float)
        inputs = {**{f"eq{L}": eq[L] for L in (30, 60)}, **{f"US100_{L}": us100[L] for L in (30, 60)},
                  **{f"USDx{L}": scaled_returns(q, "USDx", L, -1, t_ns) for L in (30, 60)},
                  **{f"own{L}": scaled_returns(q, tgt, L, -1, t_ns) for L in (30, 60)}}
        for H in (30, 60, 120):
            y = np.full(len(c), np.nan)
            ok = (t_ns[H:] - t_ns[:-H]) == np.int64(H * 60_000_000_000)
            y[:-H] = np.where(ok, (c[H:] - c[:-H]) / PIP[tgt], np.nan)
            for sname, (h0, h1) in SESS.items():
                sm = win & (hour >= h0) & (hour < h1)
                drift = {n: np.nanmean(y[sm & (half == n)]) for n, _a, _b in HALVES}
                cost = {n: np.nanmedian(sp[sm & (half == n)]) + (0.14 if tgt == "gc" else 0.4) for n, _a, _b in HALVES}
                sd = np.nanstd(y[sm])
                for name, z in inputs.items():
                    zz = pd.Series(np.where(sm, z, np.nan), index=p.index)
                    for thr in (1.5, 2.0, 2.5):
                        ix = episodes(zz, thr)
                        ix = ix[np.isfinite(y[ix])]
                        if len(ix) < 60:
                            continue
                        s = np.sign(z[ix])
                        raw = s * y[ix] - s * np.array([drift[h] for h in half[ix]])
                        direction = 1 if raw.mean() > 0 else -1
                        ex = direction * raw
                        net = ex - np.array([cost[h] for h in half[ix]])
                        row = dict(tgt=tgt, sess=sname, sig=name, thr=thr, H=H, dir=direction, n=len(ix), ex=ex.mean(),
                                   net=net.mean(), ex_sd=ex.mean() / sd, sd=sd, cost=np.mean(list(cost.values())),
                                   hit=100 * np.mean(direction * s * y[ix] > 0))
                        pos = 0
                        for n, _a, _b in HALVES:
                            m = half[ix] == n
                            row[n] = ex[m].mean() if m.sum() else np.nan
                            pos += row[n] > 0
                        row["pos"] = pos
                        rows.append(row)
        print(tgt, "done", flush=True)
    r = pd.DataFrame(rows)
    r.to_csv("research/2026-10-18-moments/agents/cross/screen2.csv", index=False)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_rows", 300)
    best = r[(r.pos == 5) & (r.n >= 80)].sort_values("ex_sd", ascending=False)
    print(best.head(80).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
