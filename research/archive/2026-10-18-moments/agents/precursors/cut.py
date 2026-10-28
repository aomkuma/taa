"""Steps 2-4 of the owner's cut (2026-10-19: "keep two or three trades a day on average - take out the ones that lose a
lot, the wrong-way ones, and run again"; notes.md "The owner's cut"). On the floor-5 trades (stop and target max(one
ATR, 5 USD), the costs), the buckets losing more than 0.10 R a trade in both learning parts (losers.py) are taken out -
by the context only, never by the side (a side rule would be a bet on the learning half's rising gold):
- the trade against the H1 swing structure (H1_struct == -1: a buy while H1 makes lower highs / lows, a sell the mirror);
- the late session (17-24 UTC = 00-07 Thai);
- the first touches of an H1 / H4 level.
Step 2: what is left, one position at a time (at one moment the larger timeframe first). Step 3: at most one trade a
session (Asia 00-07, London 07-12, New York 12-17 UTC; the first that qualifies, the position free). Step 4 ('exam'):
the exam once, week by week.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/cut.py [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from base_after_costs import HELD_BACK  # noqa: E402
from losers import session  # noqa: E402
from model_trades import take  # noqa: E402

TF_RANK = {"M5": 1, "M15": 2, "M30": 3, "H1": 4}
# step 3 again (notes.md, written before it was computed): the smallest event timeframe kept, one trade a session or not
VARIANTS = {"A": ("M15", False), "B": ("M30", False), "C": ("H1", False), "D": ("M15", True)}
EXAM_VARIANT = "B"  # chosen on the learning parts by the written rule (notes.md); its minimum R is below 0: exam not read


def keep(D: pd.DataFrame) -> pd.Series:
    """The candidates left after the cut."""
    return (D.H1_struct != -1) & (D.hour_utc < 17) & ~D.kind.str.startswith("touch")


def take_sessions(S: pd.DataFrame) -> pd.DataFrame:
    """One position and one trade a session: walk the candidates in time order; a candidate is taken when the position
    is free and its session has no trade yet."""
    P = S.sort_values(["t", "p"], ascending=[True, False], kind="mergesort").reset_index(drop=True)
    day = pd.DatetimeIndex(P.t).tz_convert("UTC").normalize()
    ses = session(P.hour_utc).astype(str).to_numpy()
    out, busy, used = [], -1, set()
    for r in range(len(P)):
        key = (day[r], ses[r])
        if P.j0.iloc[r] <= busy or key in used:
            continue
        out.append(r)
        used.add(key)
        busy = int(P.xj.iloc[r])
    return P.iloc[out].reset_index(drop=True)


def report(T: pd.DataFrame, a: str, b: str) -> str:
    import wf  # noqa: PLC0415

    eq = T.pnl.cumsum()
    return (f"{len(T)} trades ({len(T) / np.busday_count(a, b):.2f} a weekday), win {(T.pnl > 0).mean():.3f}, R {T.R.mean():+.3f}, "
            f"USD {T.pnl.sum():+.1f}, lowest running total {eq.min():+.1f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, "
            f"worst {T.pnl.min():+.2f}, longest losing streak {wf.longest_run(T.pnl.to_numpy() < 0)}, buys {int((T.side > 0).sum())} / sells {int((T.side < 0).sum())}")


def main() -> None:
    import wf  # noqa: PLC0415

    A = pd.read_parquet(HERE / "combined_trades_floor5.parquet")
    A["p"] = A.tf.map(TF_RANK)  # at one moment the larger timeframe first (smaller costs)
    parts = (("part 1 (2023-11 .. 2025-10-15)", (A.half == "learn") & (A.t < HELD_BACK), "2023-11-01", "2025-10-16"),
             ("part 2 (2025-10-16 .. 2026-04-17)", (A.half == "learn") & (A.t >= HELD_BACK), "2025-10-16", "2026-04-18"))
    if sys.argv[1:] == ["exam"]:
        parts = (("THE EXAM (2026-04-18 .. 10-16)", A.half == "exam", "2026-04-20", "2026-10-17"),)
    for name, k, a, b in parts:
        D = A[k]
        print(f"\n{name}")
        print("  step 0, every candidate one at a time:     ", report(take(D, 0), a, b))
        C = D[keep(D)]
        print(f"  step 2, the cut ({len(C)} of {len(D)} candidates):", report(take(C, 0), a, b))
        T = take_sessions(C)
        print("  step 3, + one trade a session:            ", report(T, a, b))
        print("    by pattern:", T.groupby("pattern").agg(n=("R", "size"), R=("R", "mean")).round(3).to_dict("index"))
        print("    by session:", T.groupby(session(T.hour_utc), observed=True).agg(n=("R", "size"), R=("R", "mean")).round(3).to_dict("index"))
        for v, (lo, per_session) in VARIANTS.items():
            Cv = C[C.tf.map(TF_RANK) >= TF_RANK[lo]]
            Tv = take_sessions(Cv) if per_session else take(Cv, 0)
            print(f"  step 3{v}, {lo} and up{', one a session' if per_session else ''}: ", report(Tv, a, b))
            if v == EXAM_VARIANT:
                T = Tv
        if "EXAM" in name:
            print(f"\nthe exam: variant {EXAM_VARIANT} - ", report(T, a, b))
            print("    by pattern:", T.groupby("pattern").agg(n=("R", "size"), R=("R", "mean")).round(3).to_dict("index"))
            print("    by timeframe:", T.groupby("tf").agg(n=("R", "size"), R=("R", "mean"), usd=("pnl", "sum")).round(3).to_dict("index"))
            T["cell"] = f"cut_{EXAM_VARIANT}"
            pd.set_option("display.width", 220)
            print("\nthe exam week by week (Thai weeks, Monday):")
            print(wf.weekly(T).to_string(index=False))
            T.to_parquet(HERE / "cut_exam_trades.parquet")


if __name__ == "__main__":
    main()
