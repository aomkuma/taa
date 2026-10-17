"""Agent "cross": fxlab.Inst.trade against ny_lab.M1.trade on 400 random gold trades with ny_lab's costs
(extra 0, stop slip 0.07). Note ny_lab enters at index e; fxlab decides at d = e - 1.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/check_sim.py
"""

from __future__ import annotations

import sys

import numpy as np

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
from fxlab import Inst  # noqa: E402
from ny_lab import M1  # noqa: E402


def main() -> None:
    g = Inst("XAUUSD")
    g.extra, g.ask_add, g.sslip = 0.0, g.sp.copy(), np.full(len(g.o), 0.07)
    P = M1()
    assert len(P.o) == len(g.o) and (P.ot == g.ot).all()
    rng = np.random.default_rng(1)
    bad = 0
    for _ in range(400):
        e = int(rng.integers(1000, len(g.o) - 500))
        if g.tmin[e] - g.tmin[e - 1] != 1 or g.tmin[e + 200] - g.tmin[e] != 200:
            continue
        side = int(rng.choice([-1, 1]))
        be = [None, 0.6][int(rng.integers(0, 2))]
        a = P.trade(e, side, 6.0, 5.0, be, 120)
        b = g.trade(e - 1, side, 6.0, 5.0, be, 120)
        if abs(a["usd"] - b["pnl"]) > 1e-9 or a["exit"] != b["exit"] or a["kind"] != b["kind"] or a["mins"] != b["mins"]:
            bad += 1
            if bad < 6:
                print("mismatch", e, side, be, a, b)
    print("mismatches:", bad)


if __name__ == "__main__":
    main()
