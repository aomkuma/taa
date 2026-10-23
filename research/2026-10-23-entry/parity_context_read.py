"""Parity (SPEC.md 4.4) for app/strategy/context_read.py on real data:
- vol_ratio against week.py ``pressure`` (H1) on the 98 NY-B2 learning trades;
- day_so_far against week.py ``context`` day_run / day_rng on the same trades;
- last_day's strong days against retest_week.py's rule on every D1 bar 2021-10 .. 2026-10.

    .venv/Scripts/python research/2026-10-23-entry/parity_context_read.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/2026-10-18-moments/agents/journal/ny_b2"))
import week as W  # noqa: E402

from app.strategy import context_read as cr  # noqa: E402
from app.strategy.plan1_b2 import Bars  # noqa: E402


def to_bars(d: pd.DataFrame, hours: int) -> Bars:
    t = d.index.as_unit("ns").asi8
    return Bars(t, t + hours * 3600 * 10**9, d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float), d.close.to_numpy(float))


X = W.load().sort_values("t").reset_index(drop=True)
P, C = W.pressure(X), W.context(X)
h1, d1 = W.Z.bars("H1"), W.Z.bars("D1")
H1, D1 = to_bars(h1, 1), to_bars(d1, 24)
g = W.Z.daily_grid(d1)
vol_bad = day_bad = 0
for r, p, c in zip(X.itertuples(), P.itertuples(), C.itertuples(), strict=True):
    if not np.isclose(cr.vol_ratio(H1, r.t.value), p.vol, rtol=1e-9):
        vol_bad += 1
    k = g.index.searchsorted(r.t, side="right") - 1
    run, rng = cr.day_so_far(H1, r.t.value, r.entry_price, 1 if r.side == "BUY" else -1, g.step.values[k])
    if not (np.isclose(run, c.day_run) and np.isclose(rng, c.day_rng)):
        day_bad += 1
print(f"vol ratio equal on {len(X) - vol_bad} / {len(X)} trades; day so far equal on {len(X) - day_bad} / {len(X)}")

pc = d1.close.shift(1)
atr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)
ref, app = set(), set()
for i in range(21, len(d1)):
    b, a = d1.iloc[i], atr.iloc[i]
    if np.isfinite(a) and b.high != b.low and b.close != b.open:
        side = 1 if b.close > b.open else -1
        pos = (b.close - b.low) / (b.high - b.low) if side > 0 else (b.high - b.close) / (b.high - b.low)
        if (b.close - b.open) * side / a >= 1.0 and pos >= 0.7:
            ref.add(d1.index[i])
    if cr.last_day(D1, int(D1.avail[i])).strong:
        app.add(d1.index[i])
early = {t for t in ref ^ app if t < d1.index[40]}
print(f"strong days: research {len(ref)}, app {len(app)}, different {len(ref ^ app)} (in the first 40 bars, the ATR warm-up: {len(early)})")
print("PARITY", "OK" if vol_bad == 0 and day_bad == 0 and len(ref ^ app) == len(early) else "FAILED")
