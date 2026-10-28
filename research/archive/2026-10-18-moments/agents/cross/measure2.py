"""Agent "cross", step 1b (owner, 2026-10-17: trade gold and the seven majors; indices/crosses as inputs only).
Lead-lag to every traded market, design data only (2023-11 .. 2026-02, five halves).

Targets: gold (gc) and EURUSD GBPUSD USDJPY AUDUSD USDCHF USDCAD NZDUSD. Inputs (vol-scaled last L minutes):
eq = mean z of US500 and JP225 (equities); US100; USDx = the dollar composite without the target pair (signed, up
= stronger dollar); the target's own move. Target: its vol-scaled next H minutes. Corr x100 per half and the partial
beta after the target's own L. Every 5th minute.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/measure2.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from measure import HALVES, PANEL, scaled_returns  # noqa: E402

TARGETS = ["gc", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
MAJ_SIGN = {"EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1, "NZDUSD": -1, "USDJPY": 1, "USDCHF": 1, "USDCAD": 1}
SESS = {"all": (0, 24), "asia 00-07": (0, 7), "london 07-12": (7, 12), "ny 12-17": (12, 17), "late 17-21": (17, 21)}


def dollar_ex(p: pd.DataFrame, target: str) -> pd.Series:
    ks = [k for k in MAJ_SIGN if k != target]
    return sum(MAJ_SIGN[k] * np.log(p[k]) for k in ks) / len(ks)


def main() -> None:
    gold.below_normal_priority()
    p = pd.read_parquet(PANEL)
    t_ns = p.index.as_unit("ns").asi8
    hour = p.index.hour.to_numpy()
    keep = (p.index.minute.to_numpy() % 5) == 0
    halves = [(n, (p.index >= pd.Timestamp(a, tz="UTC")) & (p.index < pd.Timestamp(b, tz="UTC"))) for n, a, b in HALVES]
    base = {(k, L): scaled_returns(p, k, L, -1, t_ns) for k in ("US500", "JP225", "US100") for L in (30, 60)}

    def corr(x, y, m):
        ok = m & np.isfinite(x) & np.isfinite(y)
        return 100 * np.corrcoef(x[ok], y[ok])[0, 1] if ok.sum() > 200 else np.nan

    def partial(x, g, y, m):
        ok = m & np.isfinite(x) & np.isfinite(y) & np.isfinite(g)
        if ok.sum() < 200:
            return np.nan
        A = np.column_stack([x[ok], g[ok], np.ones(ok.sum())])
        return 100 * np.linalg.lstsq(A, y[ok], rcond=None)[0][0]

    for tgt in TARGETS:
        q = p.copy()
        q["USDx"] = dollar_ex(p, tgt)
        feats = {}
        for L in (30, 60):
            feats[("eq", L)] = (base[("US500", L)] + base[("JP225", L)]) / 2
            feats[("US100", L)] = base[("US100", L)]
            feats[("USDx", L)] = scaled_returns(q, "USDx", L, -1, t_ns)
            feats[("own", L)] = scaled_returns(q, tgt, L, -1, t_ns)
        targ = {H: scaled_returns(q, tgt, H, +1, t_ns) for H in (30, 60, 120)}
        print(f"\n##### target {tgt}")
        for sname, (h0, h1) in SESS.items():
            sm = keep & (hour >= h0) & (hour < h1)
            for (k, L), x in feats.items():
                for H, y in targ.items():
                    cs = [corr(x, y, sm & hm) for _n, hm in halves]
                    ps = [partial(x, feats[("own", L)], y, sm & hm) for _n, hm in halves] if k != "own" else cs
                    same = max(sum(c > 0 for c in cs), sum(c < 0 for c in cs))
                    samep = max(sum(c > 0 for c in ps), sum(c < 0 for c in ps))
                    flag = " <<" if same == 5 and samep >= 4 and abs(np.mean(cs)) >= 2 else ""
                    if flag:
                        print(f"  {sname:12} {k:5} L{L:<3} H{H:<4} corr " + " ".join(f"{c:+5.1f}" for c in cs)
                              + f" | mean {np.mean(cs):+5.1f} | partial " + " ".join(f"{c:+5.1f}" for c in ps) + flag)


if __name__ == "__main__":
    main()
