"""The frozen exam of the NY-B2 journal's result (owner 2026-10-22: "ก" = run it): 2026-04-18 .. the data end, once.
Frozen as decided at the journal's end (week 26), nothing tuned on the exam:

- base: the bot's B2 in the NY window as it is (the structure exit) - what DEMO runs
- exit: the realistic exit (half at +1 R, the rest at break-even to 0.1 step before the next zone line, 120 min)
- exit + vol: the exit and standing aside when H1 ATR(14) > 1.1x its 20-day median (the one skip rule that held forward)
- as it stood: exit + vol + near a zone line < 10 USD + 10:00-10:30 New York (the rules in force at week 26)
- re-test: the re-test after a strong D1 bar (retest_week.py), both sides
Accounts: 100 USD at 7.5 % and 300 USD at 3 %, equity sizing, at least 0.01 lot; "exit + vol" and the re-test in one
account (the proposal), base alone. Ticks, spread only.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/exam.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import retest_week as RT
import week as W

START, END = pd.Timestamp("2026-04-18", tz="UTC"), pd.Timestamp("2026-10-22", tz="UTC")
W.C.EXAM = pd.Timestamp("2026-10-23", tz="UTC")  # the owner's go-ahead to read the exam (2026-10-22)


def main() -> None:
    W.HERE = W.HERE / "exam"
    X = W.load()
    X = X[(X.t >= START) & (X.t < END)].sort_values("t").copy()
    X["exit"] = W.realistic(X, band=0.1)
    X = X.join(W.pressure(X))
    ny = X.t.dt.tz_convert("America/New_York")
    m10 = ny.dt.hour * 60 + ny.dt.minute - 600
    hv = X.vol > W.VOL_MAX
    X["exit_vol"] = X.exit.where(~hv)
    X["as_stood"] = X.exit.where(~hv & ~(X.zone_line_dist < W.NEAR_USD) & ~((m10 > 0) & (m10 <= 30)))
    R = RT.trades(START, END)
    R["piece"] = "re-test"
    X["piece"] = "B2"
    wk = lambda t: t.dt.tz_convert("Asia/Bangkok").dt.to_period("W-SUN").dt.start_time.dt.date  # noqa: E731
    T = pd.DataFrame({"n": X.groupby(wk(X.t)).size(), "base": X.r_multiple.groupby(wk(X.t)).sum(), "exit": X.exit.groupby(wk(X.t)).sum(),
                      "exit_vol": X.exit_vol.groupby(wk(X.t)).sum(), "as_stood": X.as_stood.groupby(wk(X.t)).sum()})
    T["retest"] = R.r_real.groupby(wk(R.t)).sum() if len(R) else 0.0
    T = T.fillna(0.0)
    A = pd.concat([X[["t", "side", "entry_price", "sl_initial"]].assign(r=X.exit_vol, piece="B2"),
                   R[["t", "side", "entry_price", "sl_initial"]].assign(r=R.r_real, piece="re-test")]).sort_values("t").reset_index(drop=True)
    A = W.accounts(A, "r", "p")
    Bse = W.accounts(X.assign(r=X.r_multiple).reset_index(drop=True), "r", "b")
    T["prop_100"] = A.groupby(wk(A.t)).balp_100.last()
    T["prop_300"] = A.groupby(wk(A.t)).balp_300.last()
    T["base_100"] = Bse.groupby(wk(Bse.t)).balb_100.last()
    T["base_300"] = Bse.groupby(wk(Bse.t)).balb_300.last()
    T[["prop_100", "prop_300", "base_100", "base_300"]] = T[["prop_100", "prop_300", "base_100", "base_300"]].ffill()
    pd.set_option("display.width", 200)
    print(T.round(2).to_string())
    n = len(X)
    print(f"\nB2 {n} trades | base {X.r_multiple.sum():+.2f} ({X.r_multiple.mean():+.3f}/trade) | exit {X.exit.sum():+.2f} ({X.exit.mean():+.3f}) | "
          f"exit+vol {X.exit_vol.sum():+.2f} on {X.exit_vol.notna().sum()} ({X.exit_vol.mean():+.3f}) | as it stood {X.as_stood.sum():+.2f} on {X.as_stood.notna().sum()} ({X.as_stood.mean():+.3f})")
    if len(R):
        print(f"re-test {len(R)} trades {R.r_real.sum():+.2f} ({R.r_real.mean():+.3f}/trade), won {(R.r_real > 0).mean() * 100:.0f} %, "
              f"sells {R[R.side == 'SELL'].r_real.sum():+.2f} on {(R.side == 'SELL').sum()}, buys {R[R.side == 'BUY'].r_real.sum():+.2f} on {(R.side == 'BUY').sum()}")
    print(f"proposal (B2 exit+vol + re-test): 100 -> {A.balp_100.iloc[-1]:.2f}, 300 -> {A.balp_300.iloc[-1]:.2f} | base: 100 -> {Bse.balb_100.iloc[-1]:.2f}, 300 -> {Bse.balb_300.iloc[-1]:.2f}")
    print(f"min balance: proposal 100 {A.balp_100.min():.2f}, 300 {A.balp_300.min():.2f} | base 100 {Bse.balb_100.min():.2f}, 300 {Bse.balb_300.min():.2f}")
    print(f"weeks won: base {(T.base > 0).sum()}/{len(T)}, exit+vol {(T.exit_vol > 0).sum()}/{len(T)}, exit+vol+re-test {((T.exit_vol + T.retest) > 0).sum()}/{len(T)}")
    if len(R):
        print("\nre-test trades:")
        print(R.assign(th=R.t.dt.tz_convert("Asia/Bangkok").dt.strftime("%m-%d %a %H:%M"), stop=(R.entry_price - R.sl_initial).abs())[["th", "side", "stop", "r_real", "exit1"]].round(2).to_string())


if __name__ == "__main__":
    main()
