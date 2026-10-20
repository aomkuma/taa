"""Part (a) (notes.md "The picks as trades"; owner, 2026-10-19: "one part at a time"): every candidate of
combined_events.parquet as the trade model_trades.py takes (stop and target one ATR of the event's timeframe, out
after 240 minutes, the auditor's costs) - no model, no picking - and its result after the costs by pattern (M, W, the
hunts, the breaks, the touches) and timeframe, in the two learning parts (to 2025-10-15, and the held-back part to
2026-04-17). The exam's rows are labelled too (combined_trades.parquet) but not printed: no rule is chosen yet.
Part (b1): with FLOOR (USD) the stop and the target are max(one ATR, FLOOR) - the owner's 5-USD floor; nothing else
changes (combined_trades_floorN.parquet).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/base_after_costs.py [FLOOR]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from model_trades import trade_1atr  # noqa: E402

PATTERNS = ["W (buy)", "M (sell)", "hunt below a low -> buy back", "hunt above a high -> sell back", "high broken -> buy on",
            "low broken -> sell on", "first touch of an H1/H4 level"]
HELD_BACK = pd.Timestamp("2025-10-16", tz="UTC")  # model.py's held-back part starts at its first row on this day


def pattern(kind: pd.Series, side: pd.Series) -> np.ndarray:
    """The owner's names for combine.py's kinds: a double is a W (a buy) or an M (a sell); a pierce read as a reversal is
    a hunt (a low pierced -> buy back), read as a continuation a break (a high broken -> buy on)."""
    dbl, rev, cont = kind.str.startswith("double"), kind == "pierce_reversal", kind == "pierce_continuation"
    return np.select([dbl & (side > 0), dbl & (side < 0), rev & (side > 0), rev & (side < 0), cont & (side > 0), cont & (side < 0)],
                     PATTERNS[:6], PATTERNS[6])


def table(D: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = D.groupby(by, sort=False)
    return pd.DataFrame({"n": g.size(), "win": g.pnl.agg(lambda x: (x > 0).mean()), "R": g.R.mean(), "usd": g.pnl.mean(),
                         "stop_usd": g.dist.median()})


def main() -> None:
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    mm = plib.load()
    mk = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), lo=mm.low.to_numpy(float), c=mm.close.to_numpy(float),
              sp=mm.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=mm.index.as_unit("ns").asi8, ny=plib.ny_mask(mm.index))
    floor = float(sys.argv[1]) if sys.argv[1:] else 0.0
    tag = f"_floor{floor:g}" if floor else ""
    A = pd.read_parquet(HERE / "combined_events.parquet")
    A["pattern"] = pattern(A.kind, A.side)
    A["dist"] = np.maximum(A.atr_ev, floor)  # the stop and the target in USD
    X = pd.DataFrame([trade_1atr(mk, int(j), int(s), float(a)) for j, s, a in zip(A.j0, A.side, A.dist)], index=A.index)
    A = pd.concat([A, X], axis=1)
    A.to_parquet(HERE / f"combined_trades{tag}.parquet")
    print(f"the stop and the target max(one ATR, {floor:g} USD); exits {A.exit.value_counts(normalize=True).round(3).to_dict()}")
    # the same trade as model_trades.py's for every exam trade it took (the same rows, the same result)
    T = pd.read_parquet(HERE / "model_trades_noside.parquet")
    chk = T.merge(A, on=["t", "kind", "tf", "side", "j0"], suffixes=("", "_a"))
    same = (chk.dist == chk.atr_ev).to_numpy()  # with a floor: only the trades whose ATR is above it stay the same
    assert len(chk) == len(T) and np.allclose(chk.pnl[same], chk.pnl_a[same]) and (chk.exit[same] == chk.exit_a[same]).all(), "trades differ"
    print(f"{len(A)} candidates as trades; model_trades.py's {len(T)} exam trades equal where the stop is unchanged ({int(same.sum())})", flush=True)
    L = A[A.half == "learn"].copy()
    L["part"] = np.where(L.t < HELD_BACK, "1: 2023-11 .. 2025-10-15", "2: 2025-10-16 .. 2026-04-17")
    pd.set_option("display.width", 250)
    for by in (["pattern"], ["pattern", "tf"]):
        W = table(L, [*by, "part"]).unstack("part")
        W.columns = [f"{a}{b[0]}" for a, b in W.columns]
        W = W.reindex(pd.MultiIndex.from_product([PATTERNS, ["M5", "M15", "M30", "H1"]]) if len(by) == 2 else PATTERNS).dropna(how="all")
        W["both_plus"] = (W.R1 > 0) & (W.R2 > 0)
        print("\nafter the costs, every candidate (n, win, R a trade, USD a trade at 0.01 lot, the stop in USD) - part 1 | part 2:")
        print(W[["n1", "win1", "R1", "usd1", "n2", "win2", "R2", "usd2", "stop_usd2", "both_plus"]].round(3).to_string())


if __name__ == "__main__":
    main()
