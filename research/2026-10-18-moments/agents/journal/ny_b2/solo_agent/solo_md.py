"""The week's markdown for DECISIONS.md, from the ledger and weeks.csv only (week N and earlier):

    solo_md.py 1
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import solo_lib as S
import solo_week as SW


def f(v: float) -> str:
    return "-" if not np.isfinite(v) else f"{v:+.2f}"


def main(n: int) -> None:
    s, e = S.bounds(n)
    L = S.ledger()
    Wk = L[L.week == n]
    w = pd.read_csv(S.SOLO / "weeks.csv").set_index("week").loc[n]
    print(f"## Exam week {n} - {s + pd.Timedelta(days=2):%Y-%m-%d} .. {e - pd.Timedelta(days=1):%m-%d}\n")
    d = SW.d1_week(n)
    print("D1: " + "; ".join(f"{r.day} {r.open:.0f}->{r.close:.0f} (hi {r.high:.0f} lo {r.low:.0f}, body {r.body_atr:+.2f} ATR)" for r in d.itertuples()) + "\n")
    if len(Wk):
        print("| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by | shadow hits |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in Wk.itertuples():
            print(f"| {r.thai} | {r.piece} | {r.side} | {r.tf if isinstance(r.tf, str) else ''} | {r.entry_price:.2f} | {r.risk:.1f} | {f(r.r_base)} | "
                  f"{f(r.r_cur)} | {f(r.r_realized)} | {f(r.r_nolearn)} | {r.skipped_by if isinstance(r.skipped_by, str) else ''} | "
                  f"{r.shadow_hits if isinstance(r.shadow_hits, str) else ''} |")
    else:
        print("No trades or signals.")
    print(f"\nRealized: {w.trades} trades ({w.wins} won / {w.losses} lost) {w.r_realized:+.2f} R -> 100 USD account **{w.acct100:.2f}**, "
          f"300 USD account **{w.acct300:.2f}**. No-learning: {w.nl_trades} trades ({w.nl_wins}/{w.nl_losses}) {w.r_nolearn:+.2f} R -> "
          f"{w.nl_acct100:.2f} / {w.nl_acct300:.2f}. Base (the bot as is, B2 only): {w.b2_signals} trades {w.r_base:+.2f} R -> "
          f"{w.base_acct100:.2f} / {w.base_acct300:.2f}.\n")


if __name__ == "__main__":
    main(int(sys.argv[1]))
