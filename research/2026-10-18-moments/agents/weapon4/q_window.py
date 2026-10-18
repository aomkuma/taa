"""The one window run of W11 (round 50 at a fresh extreme, FROZEN in notes.md), with window_run.py's report.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/q_window.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402
import window_run as wr  # noqa: E402


def main():
    w.jlib.gold.below_normal_priority()
    P = wr.P
    a, b = w.WINDOW
    D = w.build(P, 1, a, b, [(0, 20)], "XAUUSD_M1_window")
    f1, s1, s2 = wr.others(D)
    R = w.add_anchors(w.build_round_multi(P, a, b, [(0, 20)], "XAUUSD_M1_window_rgrid", 50.0, [0.0])[0.0], P)
    S = w.signals(R, 3, 10, 8, 0.6, 60, c4=None)
    near = np.zeros(len(S), bool)
    for an in ("A72", "A24", "AW", "AS"):
        near |= (S[f"d_{an}"] < 4).to_numpy()
    S = S[near].reset_index(drop=True)
    z = wr.report("W11 round-50 at a fresh extreme (FROZEN)", S, f1, s1, s2)
    z.to_csv(Path(__file__).resolve().parent / "window_W11_trades.csv", index=False)
    zz = z.merge(S[["t", "side", "d_A72", "d_AS"]], on=["t", "side"], how="left")
    for lab, m in (("near the 72-h extreme (W7 part)", zz.d_A72 < 4), ("session / 24-h / week only", ~(zz.d_A72 < 4))):
        g = zz[m.to_numpy()]
        print(f"  {lab}: {len(g)} trades R {g.R.mean():+.3f} USD {g.usd.sum():+.1f}")


if __name__ == "__main__":
    main()
