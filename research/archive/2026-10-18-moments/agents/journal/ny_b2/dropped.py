"""Observations raised in the journal and never measured (owner 2026-10-22: "is anything we thought of or saw still
left out?"), on every NY-B2 trade up to END, realistic variant unfiltered:

1. the H1 structure with / against the trade, and each part of the multi-TF score alone (D1, H4, H1, M15, fresh, mom)
2. M1 vs M5 entries; the Thai hour
3. the H4 ATR(14) change over 6 H4 bars at the entry (owner: "the big-TF ATR falling" = an unfavourable market)
4. the days since the last big day (a D1 range over 2 D1 ATR(20)): how long the market stays wild after a crash
5. the hold: 60 / 90 / 120 minutes, all and in calm hours (vol < 0.9) (week 18: base's 60-min exit won in a calm week)
6. trades entered before 10:00 New York: held through it vs closed at 10:00 (week 18's flush)
7. where in the zone: the distance to the nearest line as a share of the step

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/dropped.py 2026-03-07
"""

from __future__ import annotations

import json
import re
import sys

import numpy as np
import pandas as pd
import week as W


def main() -> None:
    end = pd.Timestamp(sys.argv[1], tz="UTC")
    X = W.load()
    X = X[X.t < end].sort_values("t").copy()
    X["r"] = W.realistic(X)
    X = X.join(W.pressure(X)).join(W.context(X))
    side = np.where(X.side == "BUY", 1, -1)
    X["h1_with"] = np.where(X.h1_structure == "?", "?", np.where(((X.h1_structure == "HH/HL") & (side > 0)) | ((X.h1_structure == "LH/LL") & (side < 0)), "with",
                            np.where(X.h1_structure == "mixed", "mixed", "against")))
    for tf in ("D1", "H4", "H1", "M15"):
        X[tf] = X.score_parts.str.extract(rf"\b{tf}([+\-0])")[0]
    X["tf"] = np.where(X.strategy.str.endswith("m5"), "M5", "M1")
    X["hour_th"] = X.t.dt.tz_convert("Asia/Bangkok").dt.hour
    J = {j["signal_id"]: j["conditions"].get("h4_atr_change", "") for j in map(json.loads, open(W.HERE / "journal.jsonl", encoding="utf-8"))}
    X["h4chg"] = [float(m.group(1)) if (m := re.search(r"([-+0-9.]+) %", J.get(s, ""))) else np.nan for s in X.signal_id]
    d1 = W.Z.bars("D1")
    g = W.Z.daily_grid(d1)
    big = d1.index[((d1.high - d1.low) > 2 * g.step.shift(1).reindex(d1.index)).values]
    X["days_since_big"] = [((t - big[big + pd.Timedelta(days=1) <= t][-1]).days if (big + pd.Timedelta(days=1) <= t).any() else 99) for t in X.t]
    ny = X.t.dt.tz_convert("America/New_York")
    X["m10"] = ny.dt.hour * 60 + ny.dt.minute - 600
    X["zone_share"] = X.zone_line_dist / (X.zone_line_dist / np.minimum(X.zone_pos, 1 - X.zone_pos))
    for h in (60, 90):
        X[f"r{h}"] = W.realistic(X, hold=h)
    pre = X.m10 <= 0
    X["r_close10"] = X.r
    X.loc[pre, "r_close10"] = W.realistic(X[pre], hold=(-X.m10[pre]).clip(lower=1, upper=120).astype(float))

    def by(col: str, edges: list[float] | None = None) -> None:
        key = pd.cut(X[col], [-np.inf, *edges, np.inf]) if edges else X[col]
        g = X.groupby(key, observed=True).agg(n=("r", "size"), base=("r_multiple", "sum"), real=("r", "sum"), win=("r", lambda s: (s > 0).mean() * 100))
        print(f"\n{col}\n{g.round(2).to_string()}")

    for c in ("h1_with", "D1", "H4", "H1", "M15", "tf", "hour_th"):
        by(c)
    by("h4chg", [-15.0, 0.0, 15.0])
    by("days_since_big", [2, 5, 10])
    by("zone_share", [0.1, 0.25, 0.4])
    calm = X.vol < 0.9
    print(f"\nhold 60 / 90 / 120 min: all {X.r60.sum():+.2f} / {X.r90.sum():+.2f} / {X.r.sum():+.2f} | calm (vol < 0.9, {calm.sum()}) "
          f"{X.r60[calm].sum():+.2f} / {X.r90[calm].sum():+.2f} / {X.r[calm].sum():+.2f} | other {X.r60[~calm].sum():+.2f} / {X.r90[~calm].sum():+.2f} / {X.r[~calm].sum():+.2f}")
    print(f"entered before 10:00 New York ({pre.sum()}): held {X.r[pre].sum():+.2f} | closed at 10:00 {X.r_close10[pre].sum():+.2f}")
    print(f"\nall: {len(X)} trades base {X.r_multiple.sum():+.2f} real unfiltered {X.r.sum():+.2f}")


if __name__ == "__main__":
    main()
