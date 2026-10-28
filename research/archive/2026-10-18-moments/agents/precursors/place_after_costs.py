"""Part (b2) (owner, 2026-10-19: "the weight is where it happens - we trade at the edge of the timeframe larger than the
entry's, never the middle"): the after-cost trades of part (b1) (combined_trades_floor5.parquet: stop and target
max(one ATR, 5 USD)) by the place on H1 and H4 from the trade's side (combine.side_place: 0 = at the trade's own edge of
the 120-bar range, a buy at the low; 1 = at the far edge) and by the distance to the level the trade leans on (a buy:
the nearest swing bottom below; in that timeframe's ATRs). Pattern groups: the doubles (W + M), the hunts bought / sold
back, the breaks followed. The two learning parts only; the exam stays unread.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/place_after_costs.py [FLOOR]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from base_after_costs import HELD_BACK  # noqa: E402

PLACE = ([-np.inf, 0.1, 0.3, 0.7, 0.9, np.inf], ["at / beyond its own edge", "near its own edge", "middle", "near the far edge",
                                                  "at / beyond the far edge"])
LEAN = ([-np.inf, 0.5, 1.0, 2.0, np.inf], ["< 0.5 ATR from its level", "0.5-1", "1-2", "> 2"])


def group(kind: pd.Series) -> np.ndarray:
    return np.select([kind.str.startswith("double"), kind == "pierce_reversal", kind == "pierce_continuation"],
                     ["doubles (W + M)", "hunts, back", "breaks, on"], "touches")


def bins(x: pd.Series, spec: tuple) -> pd.Series:
    """The bin label; a missing distance (no level inside the window) counts as the farthest bin."""
    edges, labels = spec
    return pd.cut(x.fillna(np.inf), edges, labels=labels, right=False)


def table(D: pd.DataFrame, col: str) -> pd.DataFrame:
    g = D.groupby([col, "part"], observed=True)
    T = pd.DataFrame({"n": g.size(), "win": g.R.agg(lambda x: (x > 0).mean()), "R": g.R.mean(),
                      "se": g.R.std() / np.sqrt(g.size())}).unstack("part")
    T.columns = [f"{a}{b[0]}" for a, b in T.columns]
    T["both_plus"] = (T.R1 > 0) & (T.R2 > 0)
    return T[["n1", "win1", "R1", "se1", "n2", "win2", "R2", "se2", "both_plus"]]


def main() -> None:
    floor = sys.argv[1] if sys.argv[1:] else "5"
    A = pd.read_parquet(HERE / f"combined_trades_floor{floor}.parquet")
    L = A[A.half == "learn"].copy()
    L["part"] = np.where(L.t < HELD_BACK, "1", "2")
    L["group"] = group(L.kind)
    for tf in ("H1", "H4"):
        L[f"{tf}_place"] = bins(L[f"{tf}_pos_side"], PLACE)
        L[f"{tf}_near"] = bins(L[f"{tf}_lean"], LEAN)
    pd.set_option("display.width", 250)
    print(f"stop and target max(one ATR, {floor} USD), after the costs; part 1 = 2023-11 .. 2025-10-15, part 2 = 2025-10-16 .. "
          f"2026-04-17; R a trade and its standard error")
    for grp in ("doubles (W + M)", "hunts, back", "breaks, on"):
        D = L[L.group == grp]
        print(f"\n=== {grp}: {len(D)} trades, R part 1 {D[D.part == '1'].R.mean():+.3f}, part 2 {D[D.part == '2'].R.mean():+.3f}")
        for col in ("H1_place", "H4_place", "H1_near", "H4_near"):
            print(f"\n{grp} by {col}:")
            print(table(D, col).round(3).to_string())


if __name__ == "__main__":
    main()
