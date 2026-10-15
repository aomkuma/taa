"""Why the box breakout loses (owner, 2026-10-15: "find out why others make it pay, find our good setup").

For every trade of the bot's rule (``box_harness.py``: the bot's detector, the bot's limits, all hours except
the rollover), the path after entry and the features traders use to sort breakouts:

- path: the best (MFE) and worst (MAE) excursion in R within the 48 bars, and whether +1 R came before -1 R
  (an exit problem: it went our way, then came back) or the stop came first (an entry problem: a false break);
- features at the break bar: tick volume against the last 20 bars, the break bar's body as a share of its range
  and how far it closed beyond the edge (in box heights), the box height against the run (a flag's depth),
  the box height against a long ATR (a real squeeze), the hour.

Exploratory: each feature is split in halves at its median and shown for both halves of the year; a feature is
worth a walk-forward test only when it sorts winners from losers in both halves.

    .venv/Scripts/python research/2026-10-15-day-trade/box_why.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-15-day-trade")
import box_harness as bh  # noqa: E402

WINDOW = bh.WINDOWS["00-20:30 (+Asia)"]


def paths(m: bh.Market, evs: list[tuple[int, int, float, float]]) -> pd.DataFrame:
    raw = pd.read_parquet(f"{bh.H}/M5.parquet").sort_values("close_time").reset_index(drop=True)
    vol = raw["tick_volume"].to_numpy(dtype=float)
    o = raw["open"].to_numpy(dtype=float)
    long_atr = pd.Series(m.atr["wilder"]).rolling(288).mean().to_numpy()  # a day of M5 bars
    trades = bh.simulate(m, evs, WINDOW, False)
    when = {ts for ts, *_ in trades}
    rows = []
    for t, s, other, edge in evs:
        ts = m.times[t]
        if ts not in when:
            continue
        r_final = next(r for tts, _, r, _ in trades if tts == ts)
        entry = m.c[t] + s * m.cost[t]
        stop = other - s * m.cost[t]
        risk = (entry - stop) * s
        end = min(t + bh.TIME_STOP, len(m.c) - 1)
        mfe = mae = 0.0
        first = "none"
        for k in range(t + 1, end + 1):
            up = ((m.h[k] if s > 0 else m.lo[k]) - entry) * s / risk
            dn = ((m.lo[k] if s > 0 else m.h[k]) - entry) * s / risk
            mfe, mae = max(mfe, up), min(mae, dn)
            if first == "none" and dn <= -1:
                first = "stop"
            elif first == "none" and up >= 1:
                first = "+1R"
            if first != "none" and dn <= -1:
                break
        height = abs(edge - other)
        run_start = t - 1
        rows.append(
            {
                "at": ts,
                "r": r_final,
                "mfe": mfe,
                "mae": mae,
                "first": first,
                "vol_x": vol[t] / max(1.0, vol[t - 20 : t].mean()),
                "body": abs(m.c[t] - o[t]) / max(1e-9, m.h[t] - m.lo[t]),
                "beyond_h": (m.c[t] - edge) * s / max(1e-9, height),
                "box_long_atr": height / long_atr[t] if np.isfinite(long_atr[t]) else np.nan,
                "hour": ts.hour,
                "box_atr": height / m.atr["wilder"][t],
                "run_start": run_start,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    m = bh.Market()
    x = paths(m, bh.events(m, "wilder", "latest"))
    mid = m.times[len(m.times) // 2]
    x["half"] = np.where(x["at"] < mid, "1st", "2nd")
    print(f"{len(x)} trades, mean {x.r.mean():+.3f} R")
    print("\nWhat happened first after entry:")
    print(
        x.groupby("first")
        .agg(n=("r", "size"), mean_r=("r", "mean"), mfe=("mfe", "mean"), mae=("mae", "mean"))
        .round(2)
        .to_string()
    )
    print("\nLosers (R < 0): how far they went our way first (MFE in R):")
    print(x.loc[x.r < 0, "mfe"].describe(percentiles=[0.25, 0.5, 0.75]).round(2).to_string())
    print("\nFeatures at the break: mean R below / above the median, per half of the year")
    for f in ("vol_x", "body", "beyond_h", "box_long_atr", "box_atr"):
        med = x[f].median()
        g = (
            x.assign(side=np.where(x[f] <= med, "low", "high"))
            .groupby(["side", "half"])
            .r.agg(["count", "mean"])
            .round(2)
        )
        print(f"\n{f} (median {med:.2f})")
        print(g.unstack("half").to_string())
