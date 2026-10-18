"""The combined model's picks as trades (notes.md "Every layer together - the first probability model", written before
the run): every candidate whose predicted chance is at least the threshold the held-back learning part chose is a trade
at the next M1 open (the ask for a buy) its way, the stop and the target one ATR of the event's timeframe, out after
240 minutes at the last close, the auditor's costs (spread col x 0.01 + 0.08, slippage 0.07, stop slippage 0.15 /
0.20 in the New York windows); one position at a time in time order (at one moment the highest chance first, so one
market moment on several timeframes is one trade). The held-back part and the exam, the exam week by week.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/model_trades.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from present_wf import one_at_a_time  # noqa: E402

HOLD_MIN = 240
# (the model's tag, the held-back choice of threshold; notes.md): the side-blind model is the one written down first
RUNS = (("_noside", 0.52), ("", 0.54))


def trade_1atr(mk: dict, j0: int, side: int, atr: float, hold_min: int = HOLD_MIN) -> dict:
    """From the M1 open of j0 the given way: stop and target one ATR from the filled entry, out after hold_min minutes."""
    from lvl2 import NS_MIN, manage  # noqa: PLC0415

    o, h, lo, c, sp, ot_ns, ny = (mk[k] for k in ("o", "h", "lo", "c", "sp", "ot_ns", "ny"))
    ss = 0.20 if ny[j0] else 0.15
    entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
    t_end = int(ot_ns[j0] + hold_min * NS_MIN)
    empty = (np.array([], np.int64), np.array([], float))
    x = manage(o, h, lo, c, sp, ot_ns, j0, side, entry, atr, atr, 0.0, *empty, 99.0, t_end, 0.07, ss)
    return dict(exit=x["exit"], pnl=x["pnl"], R=x["pnl"] / (atr + ss), xj=x["xj"], ss=ss)


def take(S: pd.DataFrame, p_min: float) -> pd.DataFrame:
    """The picks (p >= p_min) one position at a time; S needs t, p, side, j0, xj (each row's own exit bar)."""
    P = S[S.p >= p_min].sort_values(["t", "p"], ascending=[True, False], kind="mergesort").reset_index(drop=True)
    xj = P.xj.to_numpy()
    taken = one_at_a_time(np.arange(len(P)), P.side.to_numpy(), P.j0.to_numpy(), {1: xj, -1: xj})
    return P.iloc[[r for r, _ in taken]].reset_index(drop=True)


def main() -> None:
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415

    plib.gold.below_normal_priority()
    mm = plib.load()  # the M1 bars combine.py's j0 index
    mk = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), lo=mm.low.to_numpy(float), c=mm.close.to_numpy(float),
              sp=mm.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=mm.index.as_unit("ns").asi8, ny=plib.ny_mask(mm.index))
    pd.set_option("display.width", 220)
    for tag, th in RUNS:
        name = "side-blind" if tag else "with the side"
        for part, fn, a, b in (("held-back learning", "heldback", "2025-10-16", "2026-04-18"),
                               ("the exam", "exam", "2026-04-18", "2026-10-17")):
            S = pd.read_parquet(HERE / f"model_{fn}_scored{tag}.parquet")
            S = S[S.p >= th].copy()
            t_ns = pd.DatetimeIndex(S.t).as_unit("ns").asi8
            j0 = S.j0.to_numpy()
            # the entry bar is the first M1 bar opening at or after the decision
            assert (mk["ot_ns"][j0] >= t_ns).all() and (mk["ot_ns"][j0 - 1] < t_ns).all(), "entry bars"
            X = pd.DataFrame([trade_1atr(mk, int(j), int(s), float(x)) for j, s, x in zip(j0, S.side, S.atr_ev)], index=S.index)
            S = pd.concat([S, X], axis=1)
            T = take(S, th)
            T["cell"] = f"{tag or '_side'}_p{th}"
            agree = ((T.exit == "win") == (T.fp1 == "win")).mean()
            eq = T.pnl.cumsum()
            print(f"\n{name}, p >= {th}, {part}: {len(S)} picks -> {len(T)} trades one at a time "
                  f"({len(T) / np.busday_count(a, b):.2f} a weekday); win {(T.exit == 'win').mean():.3f} (the 1-ATR passage "
                  f"won {(T.fp1 == 'win').mean():.3f}; the same result {agree:.3f}); R {T.R.mean():+.3f}, USD {T.pnl.sum():+.1f} "
                  f"(0.01 lot = 1 USD a 1-USD move), max DD {(eq.cummax() - eq).max():.1f}, worst {T.pnl.min():+.2f}, "
                  f"longest losing streak {wf.longest_run(T.pnl.to_numpy() < 0)}")
            print("  exits:", T.exit.value_counts().to_dict(), "| buys", int((T.side > 0).sum()), "sells", int((T.side < 0).sum()))
            # by timeframe: the stop in USD (one ATR), and the spread + slippage paid in and out against it
            T["cost_R"] = (mk["sp"][T.j0.to_numpy()] + 2 * 0.07) / T.atr_ev
            G = T.groupby("tf").agg(n=("R", "size"), win=("exit", lambda x: (x == "win").mean()), R=("R", "mean"),
                                    stop_usd=("atr_ev", "median"), cost_R=("cost_R", "median"))
            print(G.round(3).to_string())
            if fn == "exam":
                print("  the exam week by week (Thai weeks, Monday):")
                print(wf.weekly(T).to_string(index=False))
                T.to_parquet(HERE / f"model_trades{tag}.parquet")


if __name__ == "__main__":
    main()
