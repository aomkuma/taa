"""Agent "cross", step 2: the shape of the lead (design data only). Buckets of a market's (or a composite's)
vol-scaled last-L-minute move; gold's next H minutes in USD (close t -> close t+H, before costs) and in gold-sd units,
by half-year and session. A side = the sign of the signal; "hit" = gold moved that way.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/buckets.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from measure import HALVES, PANEL, scaled_returns  # noqa: E402

SESS = {"asia 00-07": (0, 7), "london 07-12": (7, 12), "ny 12-17": (12, 17), "late 17-21": (17, 21)}


def features(p: pd.DataFrame) -> pd.DataFrame:
    t_ns = p.index.as_unit("ns").asi8
    f = pd.DataFrame(index=p.index)
    for L in (30, 60):
        for k in ("US500", "US100", "US30", "JP225", "AUDJPY", "USD", "USDJPY", "gc"):
            f[f"{k}_{L}"] = scaled_returns(p, k, L, -1, t_ns)
        f[f"risk_{L}"] = f[[f"US500_{L}", "JP225_{L}".replace("{L}", str(L)), f"AUDJPY_{L}"]].mean(axis=1, skipna=False)
        f[f"gap_{L}"] = f[f"risk_{L}"] - f[f"gc_{L}"]
    for H in (30, 60, 120):
        n = H
        c = p.gc.to_numpy()
        fwd = np.full(len(c), np.nan)
        ok = (t_ns[n:] - t_ns[:-n]) == np.int64(n * 60_000_000_000)
        fwd[:-n] = np.where(ok, c[n:] - c[:-n], np.nan)
        f[f"y{H}"] = fwd
    return f


def main() -> None:
    gold.below_normal_priority()
    p = pd.read_parquet(PANEL)
    f = features(p)
    f.to_parquet("research/2026-10-18-moments/agents/cross/feats.parquet")
    f = f[(f.index >= pd.Timestamp("2023-11-01", tz="UTC")) & (f.index < pd.Timestamp("2026-03-01", tz="UTC"))]
    f = f[f.index.minute % 5 == 0]
    hour = f.index.hour
    half = pd.Series("", index=f.index)
    for n, a, b in HALVES:
        half[(f.index >= pd.Timestamp(a, tz="UTC")) & (f.index < pd.Timestamp(b, tz="UTC"))] = n
    for sig in ("risk_60", "risk_30", "gap_60", "AUDJPY_60", "US500_60", "JP225_60", "USD_60"):
        for sname, (h0, h1) in SESS.items():
            m = (hour >= h0) & (hour < h1)
            x = f[m]
            print(f"\n{sig} | {sname}: |z| >= thr -> side = sign; gold's next H (USD, side-signed; hit %) per half")
            for thr in (1.0, 1.5, 2.0):
                for H in (30, 60, 120):
                    s = np.sign(x[sig])
                    sel = (x[sig].abs() >= thr) & x[f"y{H}"].notna()
                    v = (s * x[f"y{H}"])[sel]
                    parts = []
                    for n, _a, _b in HALVES:
                        vv = v[half[m][sel] == n]
                        parts.append(f"{vv.mean():+5.2f}/{100 * (vv > 0).mean():3.0f}%/{len(vv):4}")
                    print(f"  thr {thr} H{H:<4} all {v.mean():+5.2f} hit {100 * (v > 0).mean():3.0f}% n {len(v):5} | " + "  ".join(parts))


if __name__ == "__main__":
    main()
