"""Agent "cross": AFTER the one test (a diagnosis, not a new rule). The London relation (equities' last 30 min ->
the pair's next 60 min) and the same-minute co-movement, by quarter from 2023-11 to 2026-10, plus the signal count.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/post_test.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from measure import PANEL, scaled_returns  # noqa: E402


def main() -> None:
    gold.below_normal_priority()
    p = pd.read_parquet(PANEL)
    t_ns = p.index.as_unit("ns").asi8
    eq = (scaled_returns(p, "US500", 30, -1, t_ns) + scaled_returns(p, "JP225", 30, -1, t_ns)) / 2
    eq1 = (np.log(p.US500).diff() + np.log(p.JP225).diff()).to_numpy()
    h = p.index.hour.to_numpy()
    ldn = (h >= 7) & (h < 12) & (p.index.minute.to_numpy() % 5 == 0)
    q = p.index.to_period("Q").astype(str).to_numpy()
    print("quarter | signals |eq30|>=2.5 (London) | corr x100 eq30 -> next 60 min: EURUSD GBPUSD USDCHF USDCAD USD"
          " | same-minute corr EURUSD vs equities (London)")
    tg = {k: scaled_returns(p, k, 60, +1, t_ns) for k in ("EURUSD", "GBPUSD", "USDCHF", "USDCAD", "USD")}
    for qq in sorted(set(q)):
        if qq < "2023Q4":
            continue
        m = ldn & (q == qq)
        nsig = int(((np.abs(eq) >= 2.5) & m).sum())
        cs = []
        for k, y in tg.items():
            ok = m & np.isfinite(eq) & np.isfinite(y)
            cs.append(100 * np.corrcoef(eq[ok], y[ok])[0, 1] if ok.sum() > 100 else np.nan)
        mm = (h >= 7) & (h < 12) & (q == qq)
        e1 = np.log(p.EURUSD).diff().to_numpy()
        ok = mm & np.isfinite(e1) & np.isfinite(eq1)
        same = 100 * np.corrcoef(e1[ok], eq1[ok])[0, 1] if ok.sum() > 100 else np.nan
        print(f"{qq} | {nsig:4} | " + " ".join(f"{c:+6.1f}" for c in cs) + f" | {same:+5.1f}")


if __name__ == "__main__":
    main()
