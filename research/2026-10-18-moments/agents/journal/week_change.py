"""Apply the journal's running changes to a week of PLAN-1 trades and compare each trade with the base (the journal's
"one change a week", applied forward only). Change 1 (from week 2, decided on week 1): the stop leaves the sweep zone -
if a pool (yesterday's high / low, the Asia high / low, today's open, the last M15 swing, a 10-USD round number) lies
between the entry and the stop within 0.25 H1 ATR of the stop, the stop moves to 0.5 H1 ATR beyond that pool (repeated
while another pool falls in the new zone, at most 3 times). The target price stays; R is counted on the new risk.
London ORB (target 2 R of the base risk, out 60 min after the fill) and NY straddle (out 08:30 + 30 min) are re-simulated
on the ticks with check_plan1.manage; Asia B2 is left as it is (its stop is at the pattern's far side, its exits are its
own).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/week_change.py 2025-10-27 2025-11-01
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liq_journal as L  # noqa: E402

C, gold = L.C, L.gold
MIN = L.MIN


def moved_stop(entry: float, stop: float, side: int, P: dict[str, float], H: float) -> tuple[float, list[str]]:
    """Change 1: push the stop out of every pool's sweep zone (pools and 10-USD round numbers between entry and stop)."""
    why = []
    for _ in range(3):
        rn = {f"round {x:.0f}": x for x in np.arange(np.floor(min(entry, stop) / 10) * 10, max(entry, stop) + 10, 10)}
        cands = {**P, **rn}
        zone = {k: v for k, v in cands.items() if (entry - v) * side > 0 and 0 <= (v - stop) * side <= 0.25 * H}
        if not zone:
            break
        k, v = max(zone.items(), key=lambda kv: (kv[1] - stop) * side)  # the pool nearest the stop
        stop = v - side * 0.5 * H
        why.append(k)
    return stop, why


def main(start: str, end: str) -> None:
    A = pd.read_parquet(L.AG / "dev" / "plan1_trades_learn_s0_x0.parquet")
    for c in ("t_in", "t_out", "t_dec"):
        if not np.issubdtype(A[c].dtype, np.integer):
            A[c] = pd.to_datetime(A[c], utc=True).astype("int64")
    W = A[(A.t_in >= pd.Timestamp(start, tz="UTC").value) & (A.t_in < pd.Timestamp(end, tz="UTC").value)].sort_values("t_in")
    m1 = gold.bars("M1", before=pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=2))
    m1 = m1[m1.index >= pd.Timestamp(start, tz="UTC") - pd.Timedelta(days=5)]
    h = gold.bars("H1", before=pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=2))
    pc = h.close.shift(1)
    atr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    base_sum = new_sum = 0.0
    for r in W.itertuples():
        t_dec = pd.Timestamp(int(r.t_dec), tz="UTC")
        H = float(atr[atr.index + pd.Timedelta(hours=1) <= t_dec].iloc[-1])
        P = L.pools(m1, H, t_dec)
        newR, note = r.R, "unchanged (B2)"
        if r.piece in ("London ORB", "NY straddle"):
            stop2, why = moved_stop(r.entry, r.stop, r.side, P, H)
            if why:
                t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
                f = int(np.searchsorted(t, int(r.t_in)))
                if r.piece == "London ORB":
                    tgt, t_end = r.entry + r.side * 2 * r.risk, int(t[f]) + 60 * MIN
                else:
                    tgt, t_end = None, int(r.t_dec) + 30 * MIN
                px, tx, kind = C.manage(t, bid, ask, f, r.entry, r.side, stop2, tgt, t_end)
                risk2 = (r.entry - stop2) * r.side
                newR = (px - r.entry) * r.side / risk2
                note = f"stop {r.stop:.2f} -> {stop2:.2f} (out of {', '.join(why)}), risk {r.risk:.1f} -> {risk2:.1f}, {kind}"
            else:
                note = "stop not in a sweep zone: unchanged"
        base_sum += r.R
        new_sum += newR
        print(f"{L.th(r.t_in)} {r.piece:11s} {'BUY ' if r.side > 0 else 'SELL'} @{r.entry:.2f} H1ATR {H:.1f} | base {r.exit:9s} R {r.R:+.2f}"
              f" | change 1: R {newR:+.2f} | {note}")
    print(f"week: base {len(W)} trades {base_sum:+.2f} R | with change 1 {new_sum:+.2f} R")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
