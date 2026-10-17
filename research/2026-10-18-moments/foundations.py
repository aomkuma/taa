"""Where does gold's own price carry direction at all? (Setup OWN, round 10 diagnostics, docs/OWN_SETUP.md)

1. Drift by hour: the mean M1 log return per Thai hour, per half-year (bp per hour, t-statistic).
2. Continuation or reversal: the variance ratio VR(k) = Var(k-minute returns) / (k x Var(1-minute returns)) per
   session; VR > 1 = moves continue (momentum), < 1 = they reverse; and the correlation between the last k minutes'
   return and the next k minutes' return.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/foundations.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

WINDOWS = [
    ("2023-11..2024-04", "2023-11-01", "2024-05-01"),
    ("2024-05..2024-10", "2024-05-01", "2024-11-01"),
    ("2024-11..2025-04", "2024-11-01", "2025-05-01"),
    ("2025-05..2025-10", "2025-05-01", "2025-11-01"),
    ("2025-11..2026-02", "2025-11-01", "2026-03-01"),
    ("TEST 2026-03..10", "2026-03-01", "2026-10-15"),
]
SESS = {"Asia 07-14 Thai": (0, 7), "London 14-19 Thai": (7, 12), "NY 19-23 Thai": (12, 16), "late 23-04 Thai": (16, 21)}


def main() -> None:
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= pd.Timestamp("2023-10-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    lr = np.log(m1.close).diff()
    gap = m1.index.to_series().diff() != pd.Timedelta(minutes=1)
    lr[gap.to_numpy()] = np.nan  # no returns across gaps (weekends, the daily break)
    th = m1.index.tz_convert("Asia/Bangkok").hour
    print("1. Mean return per Thai hour, bp per hour (t-stat); every half-year")
    rows = {}
    for name, a, b in WINDOWS:
        msk = (m1.index >= pd.Timestamp(a, tz="UTC")) & (m1.index < pd.Timestamp(b, tz="UTC"))
        x = lr[msk]
        hourly = x.groupby([x.index.normalize(), th[msk]]).sum()  # each day's return in that hour
        g = hourly.groupby(level=1)
        rows[name] = (g.mean() * 1e4).round(1).astype(str) + " (" + (g.mean() / g.std() * np.sqrt(g.size())).round(1).astype(str) + ")"
    print(pd.DataFrame(rows).to_string())

    print("\n2. Variance ratio VR(k) per session (> 1 continuation, < 1 reversal) and corr(last k, next k)")
    for sname, (h0, h1) in SESS.items():
        print(f" {sname}")
        for name, a, b in WINDOWS:
            msk = (m1.index >= pd.Timestamp(a, tz="UTC")) & (m1.index < pd.Timestamp(b, tz="UTC"))
            utc_h = m1.index.hour
            s = msk & (utc_h >= h0) & (utc_h < h1)
            x = lr.where(s)
            v1 = np.nanvar(x)
            cells = []
            for k in (5, 15, 60):
                rk = x.rolling(k, min_periods=k).sum()
                block = rk.iloc[k - 1 :: k]  # non-overlapping k-minute returns
                vr = np.nanvar(block) / (k * v1)
                nxt = block.shift(-1)
                ok = block.notna() & nxt.notna()
                cr = np.corrcoef(block[ok], nxt[ok])[0, 1] if ok.sum() > 30 else np.nan
                cells.append(f"VR{k} {vr:.2f} corr {cr:+.3f} (n {int(ok.sum())})")
            print(f"   {name:18} " + " | ".join(cells))


if __name__ == "__main__":
    main()
