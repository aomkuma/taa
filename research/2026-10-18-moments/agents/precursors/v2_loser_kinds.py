"""Why V2s's losers lost - the owner's three kinds (docs/OWN_SETUP.md, loser_kinds.py's definitions) for every
walk-forward trade stopped before its target, against a coin's side (the opposite trade from the same snap, the
same stop and target):
1 wrong way - less than half the way to the target before the stop, no run to the target afterwards;
2 right way, fell short - at least half the way, then back to the stop, no run afterwards;
3 right way, entered too early - stopped, then the target reached from the original entry within 120 minutes of
  the entry (and how wide a stop would have survived: the adverse extreme before the target).
Losers by the time exit are counted apart.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/v2_loser_kinds.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

AFTER, HALF = 120, 0.5


def kind_of(h, lo, sp, e: int, hit: int, side: int, entry: float, tp_dist: float) -> dict:
    """A trade entered at bar e and stopped at bar hit: its kind, the share of the target reached before the stop,
    and for kind 3 the adverse extreme before the target (the stop that would have survived)."""
    fav = (h[e:hit] - entry) if side > 0 else (entry - (lo[e:hit] + sp[e:hit]))
    mfe = float(fav.max()) if hit > e else 0.0
    tp = entry + side * tp_dist
    end = min(e + AFTER, len(h))
    for j in range(hit + 1, end):
        if ((h[j] if side > 0 else lo[j] + sp[j]) - tp) * side >= 0:
            seg = slice(e, j + 1)
            worst = (entry - lo[seg].min()) if side > 0 else ((h[seg] + sp[seg]).max() - entry)
            return dict(kind="3 entered too early", mfe=mfe / tp_dist, survive=float(worst))
    return dict(kind="2 fell short" if mfe >= HALF * tp_dist else "1 wrong way", mfe=mfe / tp_dist, survive=np.nan)


def main() -> None:
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415

    W = pd.read_parquet(HERE / "v2s_wf_trades.parquet")
    L = pd.read_parquet(HERE / "snap_trade_labels.parquet").set_index("row")
    m = jlib.m1_frame("XAUUSD")
    o, h, lo, sp = m.open.to_numpy(float), m.high.to_numpy(float), m.low.to_numpy(float), m.spread.to_numpy(float) * 0.01 + 0.08
    rows = []
    for r in W.itertuples():
        for who, side in (("V2s", r.side), ("a coin's side", -r.side)):
            nm = "buy" if side > 0 else "sell"
            lab = L.loc[r.row]
            ex, xj, pnl = lab[f"{nm}_exit"], int(lab[f"{nm}_xj"]), float(lab[f"{nm}_pnl"])
            entry = o[r.j0] + sp[r.j0] + 0.07 if side > 0 else o[r.j0] - 0.07
            rec = dict(who=who, half="exam" if r.t >= plib.EXAM_START else "learning", exit=ex, pnl=pnl)
            if ex == "stop":
                rec |= kind_of(h, lo, sp, int(r.j0), xj, side, entry, float(lab[f"{nm}_tp"]))
            elif pnl < 0:
                rec["kind"] = "time exit at a loss"
            else:
                rec["kind"] = "won / time exit in profit"
            rows.append(rec)
    K = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    for half in ("learning", "exam"):
        print(f"\n=== {half}: V2s's walk-forward trades and a coin's side at the same snaps ===")
        for who in ("V2s", "a coin's side"):
            P = K[(K.half == half) & (K.who == who)]
            g = P.groupby("kind").agg(trades=("pnl", "size"), usd=("pnl", "sum"), mfe=("mfe", "median"), survive=("survive", "median"))
            g["share"] = g.trades / len(P)
            print(f"-- {who}: {len(P)} trades, USD {P.pnl.sum():+.1f}")
            print(g.round(3).to_string())


if __name__ == "__main__":
    main()
