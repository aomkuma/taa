"""The rule from the by-eye test, as the bot would trade it (owner, 2026-10-19: "backtest the method you proposed,
2025-06-01 .. 2025-12-01"): at every 5-minute moment of the present library - with the H1 trend (the 120 bars' way and
the swing structure agree, not flat), after M5 has pulled back against it (M5's last leg against the trend; for a buy
the close in the lower 60 % of M5's range, for a sell the upper 60 %), when M1 turns the trend's way (M1's last leg
with it) - enter the trend's side if no position is open; V2's trade (the labels: the stop one entry-TF ATR >= 5 USD,
the target 10 U, out after 12 entry-TF bars, the auditor's costs). Compared with the bot on the present library and a
coin's side at the same moments; week by week.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/rule_bt.py START END [h4]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))


def rule_side(P: pd.DataFrame, h4: bool = False) -> np.ndarray:
    """+1 buy / -1 sell / 0 no signal for every moment, from its readings; h4: the H4 120 bars' way must agree too."""
    trend = np.where((P.H1_net_way == P.H1_struct) & (P.H1_net_way != 0), P.H1_net_way, 0).astype(int)
    if h4:
        trend = np.where(P.H4_net_way.to_numpy() == trend, trend, 0)
    pulled = (P.M5_leg_way.to_numpy() == -trend) & np.where(trend > 0, P.M5_pos.to_numpy() <= 0.6, P.M5_pos.to_numpy() >= 0.4)
    turned = P.M1_leg_way.to_numpy() == trend
    return np.where(pulled & turned, trend, 0)


def main() -> None:
    import jlib  # noqa: PLC0415
    import wf  # noqa: PLC0415
    from present_wf import one_at_a_time  # noqa: PLC0415

    start, end = pd.Timestamp(sys.argv[1], tz="UTC"), pd.Timestamp(sys.argv[2], tz="UTC")
    P = pd.read_parquet(HERE / "present_3y.parquet")
    t = pd.DatetimeIndex(P.t_dec)
    rows = np.nonzero(np.asarray((t >= start) & (t < end)) & P.buy_R.notna().to_numpy())[0]
    h4 = sys.argv[3:] == ["h4"]
    side = rule_side(P, h4)[rows]
    xj = {1: P.buy_xj.to_numpy(), -1: P.sell_xj.to_numpy()}
    taken = one_at_a_time(rows, side, P.j0.to_numpy(), xj)
    idx = jlib.m1_frame("XAUUSD").index
    col = {1: "buy", -1: "sell"}
    T = pd.DataFrame([dict(row=r, side=s, t=idx[P.j0.iloc[r]], exit=P[f"{col[s]}_exit"].iloc[r], R=P[f"{col[s]}_R"].iloc[r],
                           pnl=P[f"{col[s]}_pnl"].iloc[r], coin=(P.buy_R.iloc[r] + P.sell_R.iloc[r]) / 2, cell="rule")
                      for r, s in taken])
    T.to_csv(HERE / f"rule_bt_{sys.argv[1]}{'_h4' if h4 else ''}.csv", index=False)
    pd.set_option("display.width", 200)
    days = np.busday_count(start.date(), end.date())
    eq = T.pnl.cumsum()
    print(f"signals: {int((side != 0).sum())} moments of {len(rows)}; the rule's trades {start.date()} .. {end.date()}: {len(T)} "
          f"({len(T) / days:.2f} a weekday), win {(T.pnl > 0).mean():.3f}, R {T.R.mean():+.3f}, USD {T.pnl.sum():+.1f}, max DD "
          f"{(eq.cummax().clip(lower=0) - eq).max():.1f}, worst {T.pnl.min():+.2f}, longest losing streak {wf.longest_run(T.pnl.to_numpy() < 0)}; "
          f"a coin's side at the same moments R {T.coin.mean():+.3f}; buys {int((T.side > 0).sum())} R {T.R[T.side > 0].mean():+.3f}, "
          f"sells {int((T.side < 0).sum())} R {T.R[T.side < 0].mean():+.3f}")
    W = pd.read_parquet(HERE / "present_wf_trades.parquet")
    W = W[(W.t >= start) & (W.t < end)]
    print(f"the bot on the present library, the same months: {len(W)} trades, win {(W.pnl > 0).mean():.3f}, R {W.R.mean():+.3f}, "
          f"USD {W.pnl.sum():+.1f}")
    print("\nweek by week (Thai weeks, Monday):")
    print(wf.weekly(T).drop(columns=["cell"]).to_string(index=False))


if __name__ == "__main__":
    main()
