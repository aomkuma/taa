"""The second leg (exploration on design data; the window printed only as a description, no rule chosen on it):
after a run's first 40 % pullback (its leg-end bar, known at that bar's close), (a) the next run's side against the
run's; (b) a trade in the run's way at the next open, stop beyond the run's start (0.3 U), target the run's extreme
(retest) or +5 / +8 U, 120 min, real costs; against the mirror (same minute, same stop distance and target).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/second_leg.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import gold  # noqa: E402
from catalogue import load  # noqa: E402
from frame_b import trade_label  # noqa: E402


def main() -> None:
    gold.below_normal_priority()
    m = load()
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01
    n = len(o)
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[(C.t.dt.dayofweek < 5)]
    for R, g in C.groupby("R"):
        g = g.sort_values("t").reset_index(drop=True)
        st, sd = g.t.to_numpy(), g.side.to_numpy()
        print(f"\n=== R = {R} U: after the leg's first 40 % pullback ===")
        print(f"{'half':10} {'n':>5} {'next same':>9} | trade: stop at the start, target (win %, R, mirror R)")
        for hl, x in g.groupby("half", observed=True):
            x = x[(x.endj + 130 < n) & (x.t_end.dt.hour <= 20)]
            s = x.side.to_numpy()
            te = x.t_end.to_numpy()
            p = np.searchsorted(st, te, side="left")
            ok = (p < len(st))
            p = np.minimum(p, len(st) - 1)
            within = ok & (st[p] - te <= np.timedelta64(60, "m"))
            same = (sd[p] == s)[within].mean()
            e = x.endj.to_numpy() + 1
            u = o[e] / 4100
            stop = x.start_px.to_numpy() - s * 0.3 * u
            ext = x.start_px.to_numpy() + s * x["size"].to_numpy()
            out = []
            for name, tp in (("retest", None), ("+5", 5.0), ("+8", 8.0)):
                entry = o[e] + np.where(s > 0, sp[e] + 0.15, -0.07)
                tpx = (ext - entry) * s if tp is None else tp * u
                sl = (entry - stop) * s
                ok2 = (sl >= 3 * u) & (sl <= 10 * u) & (tpx > 1 * u)
                res, pnl, _ = trade_label(o, h, lo, c, sp, e[ok2], s[ok2], stop[ok2], tpx[ok2])
                Rr = pnl / (sl[ok2] + 0.15)
                m_entry = o[e[ok2]] + np.where(-s[ok2] > 0, sp[e[ok2]] + 0.15, -0.07)
                mres, mpnl, _ = trade_label(o, h, lo, c, sp, e[ok2], -s[ok2], m_entry + s[ok2] * sl[ok2], tpx[ok2])
                mR = mpnl / (sl[ok2] + 0.15)
                out.append(f"{name} n {ok2.sum()} {100 * (res > 0).mean():3.0f}% {Rr.mean():+.3f} m {mR.mean():+.3f}")
            print(f"{hl:10} {len(x):5} {100 * same:8.1f}% | " + " | ".join(out))


if __name__ == "__main__":
    main()
