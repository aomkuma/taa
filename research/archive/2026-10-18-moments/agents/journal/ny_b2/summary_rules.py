"""The NY-B2 journal's end (weeks 2-26): each realistic-variant rule judged only on the weeks after it took effect
(the weeks it was found on are not evidence), counting a trade under every rule that would skip it; plus the
weekly totals of base, realistic and the re-test piece.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/summary_rules.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import retest_week as RT
import week as W

END = pd.Timestamp("2026-04-18", tz="UTC")


def main() -> None:
    X = W.build(END)
    X["r_all"] = W.realistic(X)  # the variant with only the exit (band target from week 8), no skip rule
    sc = W.context(X).score
    ny = X.t.dt.tz_convert("America/New_York")
    m10 = ny.dt.hour * 60 + ny.dt.minute - 600
    rules = (("zone-grid trend (wk 11-12)", W.TREND_FROM, W.TREND_UNTIL, ~X.with_trend if "with_trend" in X else None),
             ("near a zone line < 10 USD (wk 14-)", W.NEAR_FROM, END, X.zone_line_dist < W.NEAR_USD),
             ("H1 vol > 1.1x (wk 16-)", W.VOL_FROM, END, X.vol > W.VOL_MAX),
             ("10:00-10:30 New York (wk 20-)", W.NEWS_FROM, END, (m10 > 0) & (m10 <= 30)),
             ("multi-TF score (wk 21-25)", W.SCORE_FROM, W.SCORE_UNTIL, sc > W.SCORE_MAX))
    print("rule: the skipped trades' realistic R after the rule took effect (negative = it saved), and before (where found)")
    for name, t0, t1, m in rules:
        if m is None:
            continue
        aft = X[m & (X.t >= t0) & (X.t < t1)].r_all
        bef = X[m & (X.t < t0)].r_all
        print(f"  {name:36s} after {aft.sum():+6.2f} on {len(aft):2d} | before {bef.sum():+6.2f} on {len(bef):2d}")
    R = RT.trades(RT.RETEST_FROM, END)
    wk = X.t.dt.tz_convert("Asia/Bangkok").dt.to_period("W-SUN")
    T = pd.DataFrame({"base": X.r_multiple.groupby(wk).sum(), "real": X.r_real.groupby(wk).sum(min_count=0).fillna(0),
                      "real_no_skip": X.r_all.groupby(wk).sum()})
    print(f"\nweeks 2-26: base {T.base.sum():+.2f} R on {len(X)}, realistic with its rules {np.nansum(X.r_real):+.2f} on {X.r_real.notna().sum()}, "
          f"realistic exit only {X.r_all.sum():+.2f}; re-test (wk 23-26) {R.r_real.sum():+.2f} on {len(R)}")
    print(f"weeks won: base {(T.base > 0).sum()}/{len(T)}, realistic {(T.real > 0).sum()}/{len(T)}, exit only {(T.real_no_skip > 0).sum()}/{len(T)}")


if __name__ == "__main__":
    main()
