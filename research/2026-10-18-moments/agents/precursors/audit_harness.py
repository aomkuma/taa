"""Does the trade simulator itself make everything lose? (owner, 2026-10-18: "every setup loses whichever way it
trades - could it be the code?") Five checks on the shared harness (jlib.Instr.trade, used by the research agents) and
on LV's manage():

1. random entries, no costs -> about 0 R; 2. random entries with costs -> about minus the costs, no more;
3. each trade and its mirror (same minute, other side), no costs -> their sum about 0;
4. an oracle that knows the next 30 minutes -> clearly positive (else the simulator is broken);
5. how often a bar holds both the stop and the target (counted as the stop: a conservative bias) and what it costs.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/audit_harness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import jlib  # noqa: E402
import lvl  # noqa: E402
import plib  # noqa: E402

N, TP, SL, HZ = 6000, 6.0, 6.0, 120


def run_jlib(P: jlib.Instr, es: np.ndarray, sides: np.ndarray) -> pd.DataFrame:
    rows = []
    for e, s in zip(es, sides):
        r = P.trade(int(e), int(s), TP, SL, None, HZ)
        rows.append(dict(e=e, side=s, R=r["pnl"] / (SL + P.stop_slip), exit=r["exit"], pnl=r["pnl"]))
    return pd.DataFrame(rows)


def run_lvl(P: jlib.Instr, es: np.ndarray, sides: np.ndarray, gross: bool) -> pd.DataFrame:
    sp = np.zeros_like(P.sp) if gross else P.sp
    slip, ss = (0.0, 0.0) if gross else (P.slip, P.stop_slip)
    rows = []
    for e, s in zip(es, sides):
        e = int(e)
        entry = P.o[e] + (sp[e] + slip if s > 0 else -slip)
        r = lvl.manage(P.o, P.h, P.lo, P.c, sp, P.ot, e, int(s), entry, SL, TP, 2.0, P.ot[e] + pd.Timedelta(minutes=HZ),
                       slip, ss, True)
        rows.append(dict(e=e, side=s, R=r["pnl"] / (SL + ss), exit=r["exit"], pnl=r["pnl"]))
    return pd.DataFrame(rows)


def line(name: str, t: pd.DataFrame) -> str:
    se = t.R.std() / np.sqrt(len(t))
    return (f"{name:48s} n {len(t):5d}  R {t.R.mean():+.4f} (se {se:.4f})  win {(t.pnl > 0).mean():.3f}  "
            f"stop {(t.exit == 'stop').mean():.3f}  time {(t.exit == 'time').mean():.3f}")


def main() -> None:
    rng = np.random.default_rng(42)
    P = jlib.Instr("XAUUSD")
    W = plib.window_mask(P.ot)
    ok = W.any(axis=1).to_numpy() & (P.ot >= pd.Timestamp("2023-11-01", tz="UTC")) & (P.ot < pd.Timestamp("2026-10-01", tz="UTC"))
    es = np.sort(rng.choice(np.nonzero(ok)[0], N, replace=False))
    sides = rng.choice([-1, 1], N)
    cost_rt = np.mean(P.sp[es]) + 2 * P.slip  # entry spread + entry / exit slippage (a stop pays 0.15 instead)
    print(f"gold, {N} random minutes in the focus windows 2023-11 .. 2026-09; target = stop = {TP} USD, {HZ} min")
    print(f"average real spread {np.mean(P.sp[es]):.3f} USD; a round trip costs about {cost_rt + P.stop_slip - P.slip:.2f} "
          f"USD = {(cost_rt) / (SL + P.stop_slip):.3f} .. {(cost_rt + P.stop_slip) / (SL + P.stop_slip):.3f} R\n")
    with_costs = run_jlib(P, es, sides)
    mirror_c = run_jlib(P, es, -sides)
    # the oracle: the side of the close 30 minutes later
    fut = np.array([P.c[min(e + 30, len(P.c) - 1)] - P.o[e] for e in es])
    oracle = run_jlib(P, es, np.where(fut >= 0, 1, -1))
    P.gross()
    gross = run_jlib(P, es, sides)
    mirror = run_jlib(P, es, -sides)
    print("== jlib.Instr.trade (the shared research harness)")
    print(line("1. random side, no costs (expect ~0)", gross))
    print(line("   the mirror of the same trades, no costs", mirror))
    print(f"3. trade + mirror, no costs: mean R sum {(gross.R + mirror.R).mean():+.4f} (expect ~0; < 0 = a bias)")
    print(line("2. random side, real costs (expect ~ -costs)", with_costs))
    print(line("   its mirror, real costs", mirror_c))
    print(line("4. oracle side (knows the next 30 min)", oracle))
    both = (gross.exit == "stop") & (mirror.exit == "stop")
    print(f"5. both the trade and its mirror stopped (a bar or path holding both levels): {both.mean():.4f} of trades; "
          f"cost to the mean R about {2 * both.mean():.4f} per pair\n")
    P2 = jlib.Instr("XAUUSD")
    g2 = run_lvl(P2, es, sides, True)
    m2 = run_lvl(P2, es, -sides, True)
    c2 = run_lvl(P2, es, sides, False)
    o2 = run_lvl(P2, es, np.where(fut >= 0, 1, -1), False)
    print("== lvl.manage (LV's exits)")
    print(line("1. random side, no costs", g2))
    print(f"3. trade + mirror, no costs: mean R sum {(g2.R + m2.R).mean():+.4f}")
    print(line("2. random side, real costs", c2))
    print(line("4. oracle side", o2))


if __name__ == "__main__":
    main()
