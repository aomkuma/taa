"""Parity (SPEC.md 4.4): the bot's zone grid (app/strategy/zone_grid.py) against the research original
(research/2026-10-22-zones/zone_grid_v1.py ``daily_grid``) on every stored XAUUSD D1 bar. The two ATRs differ only in
the first bar's true range (MT5: none), so rows from bar 20 must agree exactly; the anchors from the first impulse on.

    .venv/Scripts/python research/2026-10-23-entry/parity_zone_grid.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "2026-10-22-zones"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import zone_grid_v1 as R  # noqa: E402

from app.strategy import zone_grid as zg  # noqa: E402

d = R.bars("D1")
g = R.daily_grid(d)
t = d.index.as_unit("ns").asi8
a = zg.grid_rows(t, d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float), d.close.to_numpy(float))
known_ok = bool((a.known == g.index.as_unit("ns").asi8).all())
s = slice(20, None)
step_diff = float(np.nanmax(np.abs(a.step[s] - g.step.to_numpy()[s])))
shift_ok = bool((a.shift[s] == np.where(g["shift"].to_numpy()[s] == "down", -1, np.where(g["shift"].to_numpy()[s] == "up", 1, 0))).all())
an, gn = a.anchor[s], g.anchor.to_numpy()[s]
both = np.isfinite(an) & np.isfinite(gn)
anchor_diff = float(np.max(np.abs(an[both] - gn[both]))) if both.any() else 0.0
nan_ok = bool((np.isfinite(an) == np.isfinite(gn)).all())
print(f"D1 bars {len(d)} ({d.index[0].date()} .. {d.index[-1].date()}); shifts {int((a.shift != 0).sum())}")
print(f"known times equal: {known_ok} | step max diff from bar 20: {step_diff:.2e} | shifts equal: {shift_ok} | "
      f"anchor max diff: {anchor_diff:.2e}, NaN pattern equal: {nan_ok}")
print("PARITY", "OK" if known_ok and step_diff < 1e-9 and shift_ok and anchor_diff < 1e-9 and nan_ok else "FAILED")
