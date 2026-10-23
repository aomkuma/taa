"""Parity (SPEC.md 4.4): app/strategy/zone_break.py against research/2026-10-23-entry/zone_wait.py's B events on all
M15 bars 2023-08-15 .. 2026-10-16: the same arrivals, entry bars, sides and stops.

    .venv/Scripts/python research/2026-10-23-entry/parity_zone_break.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from app.strategy import zone_break as zb  # noqa: E402

src = (HERE / "zone_wait.py").read_text(encoding="utf-8")
src = src.replace(
    'rows.append(dict(t=m.index[i], kind=f"B consolidate, then {way}", r=r))',
    'rows.append(dict(t=m.index[i], kind=f"B consolidate, then {way}", r=r, entry_t=m.index[q], side=side, stop=stop))',
)
src = src.replace("    R = pd.DataFrame(rows).dropna()", "    return pd.DataFrame(rows), m, anchor, step")
ns = {"__file__": str(HERE / "zone_wait.py"), "__name__": "zw"}
exec(compile(src, "zone_wait", "exec"), ns)  # noqa: S102 - the research module itself, run with its returns exposed
R, m, anchor, step = ns["main"]()
ref = R[R.kind.str.startswith("B")][["t", "entry_t", "side", "stop"]].reset_index(drop=True)
h, lo, c = m.high.to_numpy(float), m.low.to_numpy(float), m.close.to_numpy(float)
last_i = len(c) - 2 * zb.WAIT - 32  # the research loop's last arrival bar
ev = [e for e in zb.zone_breaks(h, lo, c, anchor, step) if e.arrival < last_i]
app = pd.DataFrame({"t": [m.index[e.arrival] for e in ev], "entry_t": [m.index[e.entry_bar] for e in ev],
                    "side": [float(e.side) for e in ev], "stop": [e.stop for e in ev]})
key = ["t", "entry_t", "side"]
both = ref.merge(app, on=key, how="outer", suffixes=("_ref", "_app"), indicator=True)
only_ref, only_app = int((both._merge == "left_only").sum()), int((both._merge == "right_only").sum())
matched = both[both._merge == "both"]
stop_diff = float(np.max(np.abs(matched.stop_ref - matched.stop_app))) if len(matched) else 0.0
print(f"research B events {len(ref)}, app events {len(app)}, matched {len(matched)}, only research {only_ref}, only app {only_app}, "
      f"stop max diff {stop_diff:.2e}")
print("PARITY", "OK" if only_ref == 0 and only_app == 0 and stop_diff < 1e-9 else "FAILED")
