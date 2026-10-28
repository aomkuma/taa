"""Why the cut's trades lose and what would have paid (owner, 2026-10-19: "for the losing ones, analyse how to make them
profitable - hold the goal, be flexible in the method"). Variant B of cut.py (the cut, events from M30 up, one position)
in the two learning parts; every stopped trade sorted into the owner's three kinds (v2_loser_kinds.kind_of, with the
look-after window the trade's own 240 minutes):
1 wrong way - less than half the way to the target before the stop, no run to the target afterwards;
2 right way, fell short - at least half the way, then back to the stop;
3 right way, entered too early - stopped, then the target reached from the original entry within 240 minutes;
against the opposite side (the opposite trade at the same moment, the same stop and target). The winners: how deep they
went against first (the stop a tighter one would have cost) and how far all trades got (the share of the target).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/losers_b.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import v2_loser_kinds  # noqa: E402
from base_after_costs import HELD_BACK  # noqa: E402
from cut import TF_RANK, keep  # noqa: E402
from model_trades import HOLD_MIN, take, trade_1atr  # noqa: E402

v2_loser_kinds.AFTER = HOLD_MIN  # the look-after window: the trade's own hold


def b_trades(A: pd.DataFrame) -> pd.DataFrame:
    """cut.py's variant B in the two learning parts."""
    A = A.assign(p=A.tf.map(TF_RANK))
    out = []
    for part, k in (("1", (A.half == "learn") & (A.t < HELD_BACK)), ("2", (A.half == "learn") & (A.t >= HELD_BACK))):
        D = A[k]
        T = take(D[keep(D) & (D.tf.map(TF_RANK) >= TF_RANK["M30"])], 0)
        out.append(T.assign(part=part))
    return pd.concat(out, ignore_index=True)


def anatomy(mk: dict, j0: int, side: int, dist: float, x: dict) -> dict:
    """The kind of a trade (x: trade_1atr's result) and its path: how far it got its way (mfe) and against it (mae)
    before its exit, in shares of the distance."""
    o, h, lo, sp = mk["o"], mk["h"], mk["lo"], mk["sp"]
    entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
    xj = int(x["xj"])
    seg = slice(j0, xj + 1)
    fav = (h[seg] - entry).max() if side > 0 else (entry - (lo[seg] + sp[seg])).max()
    adv = (entry - lo[seg]).max() if side > 0 else ((h[seg] + sp[seg]) - entry).max()
    rec = dict(mfe=fav / dist, mae=adv / dist)
    if x["exit"] == "stop":
        k = v2_loser_kinds.kind_of(h, lo, sp, j0, xj, side, entry, dist)
        rec["kind"], rec["survive"] = k["kind"], k["survive"] / dist
    else:
        rec["kind"] = "won" if x["exit"] == "win" else ("time exit, profit" if x["pnl"] >= 0 else "time exit, loss")
    return rec


def main() -> None:
    import plib  # noqa: PLC0415

    mm = plib.load()
    mk = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), lo=mm.low.to_numpy(float), c=mm.close.to_numpy(float),
              sp=mm.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=mm.index.as_unit("ns").asi8, ny=plib.ny_mask(mm.index))
    T = b_trades(pd.read_parquet(HERE / "combined_trades_floor5.parquet"))
    rows = []
    for r in T.itertuples():
        for who, side in (("B", int(r.side)), ("the opposite side", -int(r.side))):
            x = {k: getattr(r, k) for k in ("exit", "pnl", "xj", "R")} if who == "B" else trade_1atr(mk, int(r.j0), side, float(r.dist))
            rows.append(dict(who=who, part=r.part, R=x["R"], pnl=x["pnl"]) | anatomy(mk, int(r.j0), side, float(r.dist), x))
    K = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    for part in ("1", "2"):
        for who in ("B", "the opposite side"):
            P = K[(K.part == part) & (K.who == who)]
            g = P.groupby("kind").agg(trades=("R", "size"), R_sum=("R", "sum"), mfe=("mfe", "median"), mae=("mae", "median"),
                                      survive=("survive", "median"))
            g["share"] = g.trades / len(P)
            print(f"\npart {part} - {who}: {len(P)} trades, R {P.R.mean():+.3f}")
            print(g.round(3).to_string())
    B = K[K.who == "B"]
    print("\nhow far every B trade got its way before its exit (share of the target), parts 1 / 2:")
    for q in (0.25, 0.5, 0.75, 1.0):
        print(f"  reached {q:.2f}: " + " / ".join(f"{(B[B.part == p].mfe >= q).mean():.3f}" for p in ("1", "2")))
    W = B[B.kind == "won"]
    print("the winners' depth against them first (share of the stop), parts 1 / 2: median "
          + " / ".join(f"{W[W.part == p].mae.median():.2f}" for p in ("1", "2"))
          + "; went past 0.5: " + " / ".join(f"{(W[W.part == p].mae >= 0.5).mean():.3f}" for p in ("1", "2")))
    K.to_parquet(HERE / "losers_b.parquet")


if __name__ == "__main__":
    main()
