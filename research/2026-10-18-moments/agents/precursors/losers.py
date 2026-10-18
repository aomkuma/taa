"""Step 1 of the owner's cut (2026-10-19: "keep two or three trades a day on average - take out the ones that lose a lot,
the many wrong-way ones, and run again"): where the floor-5 trades (combined_trades_floor5.parquet) lose, by the
direction against the larger timeframes (H1 / H4 way and swing structure with the trade +1, against -1, flat 0), the
pattern, the timeframe, the session and the owner's windows - R a trade and the share of full stops, in the two
learning parts. The exam stays unread.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/losers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from base_after_costs import HELD_BACK  # noqa: E402


def session(hour_utc: pd.Series) -> pd.Series:
    """Asia 00-07 UTC (07-14 Thai), London 07-12, New York 12-17, late 17-24."""
    return pd.cut(hour_utc, [0, 7, 12, 17, 24], labels=["Asia", "London", "New York", "late"], right=False)


def table(D: pd.DataFrame, col: str) -> pd.DataFrame:
    g = D.groupby([col, "part"], observed=True)
    T = pd.DataFrame({"n": g.size(), "R": g.R.mean(), "stopped": g.exit.agg(lambda x: (x == "stop").mean())}).unstack("part")
    T.columns = [f"{a}{b}" for a, b in T.columns]
    T["both_below_-0.10"] = (T.R1 < -0.10) & (T.R2 < -0.10)
    return T[["n1", "R1", "stopped1", "n2", "R2", "stopped2", "both_below_-0.10"]]


def main() -> None:
    A = pd.read_parquet(HERE / "combined_trades_floor5.parquet")
    L = A[A.half == "learn"].copy()
    L["part"] = np.where(L.t < HELD_BACK, "1", "2")
    L["session"] = session(L.hour_utc)
    L["dir"] = np.where(L.side > 0, "buy", "sell")
    L["H1+H4 way"] = L.H1_way.astype(int).astype(str) + " / " + L.H4_way.astype(int).astype(str)
    L["H1+H4 structure"] = L.H1_struct.astype(int).astype(str) + " / " + L.H4_struct.astype(int).astype(str)
    pd.set_option("display.width", 220)
    print("floor-5 trades, learning; part 1 = 2023-11 .. 2025-10-15, part 2 = 2025-10-16 .. 2026-04-17; way / structure "
          "+1 with the trade, -1 against, 0 flat")
    for col in ("dir", "H1_way", "H4_way", "H1+H4 way", "H1_struct", "H4_struct", "H1+H4 structure", "pattern", "tf", "session", "inwin"):
        print(f"\nby {col}:")
        print(table(L, col).round(3).to_string())


if __name__ == "__main__":
    main()
