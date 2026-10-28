"""Task P3, item 3: the paths of B2's trades from the fill, over each trade's own window (60 entry-TF bars), on the
ticks - the most against (MAE) and the most our way (MFE), in R and USD, and the minute of each - for the leads (the
H&S family; M5 entries) against the rest, per part. Descriptive: the rule written from it goes into DEV_LOG.md before
it is run.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p3_paths.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p2_trades as P2  # noqa: E402

NS_MIN = 60 * 10**9


def path_stats(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, entry_t: int, entry: float, side: int, risk: float,
               t_limit: int) -> dict:
    """From the tick after the fill (entry_t) to the first tick at / after t_limit (or the last tick), read on the side
    the trade closes on (a buy the bid, a sell the ask): MFE / MAE in USD and R (>= 0) and their minutes from the fill
    (the first tick that reached each; 0 / NaN minute when never our way / against)."""
    f = int(np.searchsorted(t, entry_t, side="left"))
    e = min(int(np.searchsorted(t, t_limit, side="left")), len(t) - 1)
    fav = side * ((bid if side > 0 else ask)[f + 1:e + 1] - entry)
    tt = t[f + 1:e + 1]
    if not len(fav):
        return dict(mfe=0.0, mae=0.0, mfe_r=0.0, mae_r=0.0, mfe_min=np.nan, mae_min=np.nan)
    i, j = int(np.argmax(fav)), int(np.argmin(fav))
    mfe, mae = max(float(fav[i]), 0.0), max(-float(fav[j]), 0.0)
    return dict(mfe=mfe, mae=mae, mfe_r=mfe / risk, mae_r=mae / risk,
                mfe_min=(tt[i] - entry_t) / NS_MIN if mfe > 0 else np.nan,
                mae_min=(tt[j] - entry_t) / NS_MIN if mae > 0 else np.nan)


def describe(G: pd.DataFrame) -> dict:
    return dict(n=len(G), R=G.R.mean(), mfe_r=G.mfe_r.median(), mae_r=G.mae_r.median(), mfe_min=G.mfe_min.median(),
                mae_min=G.mae_min.median(), mfe_1r=(G.mfe_r >= 1).mean(), mfe_2r=(G.mfe_r >= 2).mean(),
                mae_1r=(G.mae_r >= 1).mean(), mfe_first=(G.mfe_min < G.mae_min.fillna(np.inf)).mean(),
                risk=G.risk.median(), height=G.height.median())


def main() -> None:
    A = pd.read_parquet(HERE / "p2_trades.parquet")
    B = A[(A.variant == "B2") & (A.news_cost == 0.0)].reset_index(drop=True)
    ticks = P2.Ticks()
    rows = []
    for r in B.itertuples(index=False):
        t, bid, ask = ticks.span(r.entry_t)
        rows.append(path_stats(t, bid, ask, r.entry_t, r.entry, r.side, r.risk, r.t_limit))
    B = pd.concat([B, pd.DataFrame(rows)], axis=1)
    B["hs"] = np.where(B.family == "ihs", "H&S", "rest")
    B.to_parquet(HERE / "p3_paths.parquet")
    pd.set_option("display.width", 220)
    for by in ("hs", "tf", "family"):
        out = []
        for (p, g), G in B.groupby(["part", by]):
            out.append(dict(part=p, group=g, **describe(G)))
        print(f"\n== by {by} (medians; shares of trades)")
        print(pd.DataFrame(out).round(2).to_string(index=False))
    print("\n== the MFE by the minutes of the window (median MFE in R reached by minute m, of trades still in their window)")
    for (p, g), G in B.groupby(["part", "tf"]):
        print(f"  {p} {g}: median MFE minute {G.mfe_min.median():.1f}, the MFE's minute as a share of the window "
              f"{(G.mfe_min / ((G.t_limit - G.entry_t) / NS_MIN)).median():.2f}")


if __name__ == "__main__":
    main()
