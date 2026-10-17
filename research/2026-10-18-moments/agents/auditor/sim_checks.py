"""Auditor check 1a: the trade simulators on hand-made bars (ny_lab.M1.trade, exits.Path.run).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/sim_checks.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, ".")
from ny_lab import M1  # noqa: E402

SLIP = 0.07
FAILS: list[str] = []


def fake(bars: list[tuple[float, float, float, float]], sp: float = 0.30) -> M1:
    """A fake M1 with the given (open, high, low, close) bid bars, constant spread; padded with flat bars."""
    pad = [(bars[-1][3],) * 4] * 200
    a = np.array(bars + pad, dtype=float)
    P = M1.__new__(M1)
    P.ot = pd.date_range("2026-03-04 14:00", periods=len(a), freq="min", tz="UTC")
    P.o, P.h, P.lo, P.c = a[:, 0].copy(), a[:, 1].copy(), a[:, 2].copy(), a[:, 3].copy()
    P.sp = np.full(len(a), sp)
    return P


def check(name: str, got: dict, **want: object) -> None:
    bad = {k: (got[k], v) for k, v in want.items() if (abs(got[k] - v) > 1e-9 if isinstance(v, float) else got[k] != v)}
    print(f"  {'ok  ' if not bad else 'FAIL'} {name}: {got}" + (f"  expected {want}" if bad else ""))
    if bad:
        FAILS.append(name)


def m1_trade() -> None:
    print("ny_lab.M1.trade")
    # BUY fills at 100 + 0.30 + 0.07 = 100.37; target 5 -> bid high 105.37; stop 4 -> bid low 96.37
    P = fake([(100, 105.37, 99.0, 104)])
    check("buy target exactly on the bid high", P.trade(0, 1, 5, 4, None, 60), exit="win", usd=5.0, mins=1)
    P = fake([(100, 105.36, 99.0, 104)])
    check("buy target 1 point short -> not a win in bar 0", P.trade(0, 1, 5, 4, None, 3), exit="time")
    P = fake([(100, 106, 96.0, 100)])
    check("buy both in one bar = stop", P.trade(0, 1, 5, 4, None, 60), exit="stop", usd=-4.07)
    P = fake([(100, 101, 96.37, 100)])
    check("buy stop exactly touched", P.trade(0, 1, 5, 4, None, 60), exit="stop", usd=-4.07)
    # SELL fills at the bid 100 - 0.07 = 99.93; stop 4 -> ask high 103.93 = bid high 103.63; target -> ask low 94.93
    P = fake([(100, 103.64, 99, 100)])
    check("sell stop on the ask (bid high + spread)", P.trade(0, -1, 5, 4, None, 60), exit="stop", usd=-4.07)
    P = fake([(100, 103.63, 99, 100)])
    r = P.trade(0, -1, 5, 4, None, 60)
    print(f"  note exact touch: ask high 103.63 + 0.30 vs stop 99.93 + 4 -> {r['exit']} (float: {103.63 + 0.30!r} vs {99.93 + 4!r})")
    P = fake([(100, 101, 94.63, 95)])
    check("sell target on the ask low", P.trade(0, -1, 5, 4, None, 60), exit="win", usd=5.0)
    # time exit: hz 3 -> bars 0,1,2; exit at bar 2's close (buy: bid - slip)
    P = fake([(100, 101, 99, 100.5), (100.5, 101, 99, 100.2), (100.2, 101, 99, 101.0), (101, 110, 101, 109)])
    check("buy time exit at the hz-th bar's close", P.trade(0, 1, 5, 4, None, 3), exit="time", usd=101.0 - SLIP - 100.37, mins=3)
    check("sell time exit at ask + slip", P.trade(0, -1, 5, 4, None, 3), exit="time", usd=99.93 - (101.0 + 0.30 + SLIP), mins=3)
    # break-even: tp 8, be 0.6 -> arms at bid high >= 100.37 + 4.8 = 105.17; then back to entry
    P = fake([(100, 105.2, 99.5, 105), (105, 105.1, 100.3, 100.5)])
    check("break-even armed then hit -> -slip", P.trade(0, 1, 8, 6, 0.6, 60), exit="be", usd=-SLIP, mins=2)
    P = fake([(100, 105.2, 100.2, 105)])
    r = P.trade(0, 1, 8, 6, 0.6, 3)
    check("BE armed in bar 0 is not applied to bar 0's own low (order unknown)", r, exit="time")
    # loser kinds
    P = fake([(100, 101, 96, 97), (97, 106, 97, 105.5)])
    check("kind 3: stopped, then target from entry within 120 min", P.trade(0, 1, 5, 4, None, 60), exit="stop", kind="3")
    P = fake([(100, 103, 99.5, 102.5), (102.5, 102.6, 96, 96.5)])
    check("kind 2: half way (2.5) then stopped", P.trade(0, 1, 5, 4, None, 60), exit="stop", kind="2")
    # a stop bar that reached the target too: the kind ignores the stop bar's favourable side
    P = fake([(100, 106, 96, 100)])
    check("both-in-one-bar loser is kind 1 (target touched in the stop bar not counted)", P.trade(0, 1, 5, 4, None, 60), kind="1")
    # gap through the stop: the bar opens below the stop -> filled at the stop anyway (optimistic)
    P = fake([(100, 100.5, 99.5, 100), (95.0, 95.5, 94.0, 95)])
    r = P.trade(0, 1, 5, 4, None, 60)
    print(f"  note gap through the stop: bar 1 opens at 95.00 (< stop 96.37) -> usd {r['usd']:+.2f} (a real fill: {95.0 - SLIP - 100.37:+.2f})")


def path_run() -> None:
    from exits import Path

    print("exits.Path.run")

    def fp(bars: list[tuple[float, float, float, float]], sp: float = 0.30) -> Path:
        P = Path.__new__(Path)
        f = fake(bars, sp)
        P.ot, P.o, P.h, P.lo, P.c, P.sp = f.ot, f.o, f.h, f.lo, f.c, f.sp
        return P

    P = fp([(100, 105.37, 99.0, 104)])
    r, usd, mins = P.run(0, 1, 96.37, 5, False, 10)
    check("scalp target", dict(r=r, usd=usd, mins=mins), r=5 / 4, usd=5.0, mins=1)
    P = fp([(100, 106, 96.0, 100)])
    r, usd, mins = P.run(0, 1, 96.37, 5, False, 10)
    check("scalp both in one bar = stop", dict(r=r, usd=usd, mins=mins), usd=-4.07)
    # hold: the target arms a lock at half the target (102.87) and a trail 0.5 U (U=10 -> 5) behind the best
    P = fp([(100, 105.5, 99.5, 105), (105, 112, 104, 111), (111, 111.5, 106.0, 107)])
    r, usd, mins = P.run(0, 1, 96.37, 5, True, 10)
    check("hold: trail from best 112 - 5 = 107 hit in bar 2", dict(r=r, usd=usd, mins=mins), usd=107 - SLIP - 100.37, mins=3)


def main() -> None:
    m1_trade()
    path_run()
    print("\nFAILS:", FAILS or "none")


if __name__ == "__main__":
    main()
