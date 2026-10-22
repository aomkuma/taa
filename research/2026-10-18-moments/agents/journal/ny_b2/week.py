"""The weekly journal of Asia B2 moved to the NY window (20:30-23:00 Thai): the bot's trades (trades.csv) with their
decision records (journal.jsonl), plus where each entry sat in the owner's zone grid v1 (research/2026-10-22-zones).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/week.py 2025-10-20 2025-10-25
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "2026-10-22-zones"))
import zone_grid_v1 as Z  # noqa: E402


def load() -> pd.DataFrame:
    T = pd.read_csv(HERE / "trades.csv")
    J = pd.DataFrame([json.loads(x) for x in open(HERE / "journal.jsonl", encoding="utf-8")])
    J = pd.concat([J.drop(columns=["conditions"]), pd.json_normalize(J.conditions)], axis=1)
    X = T.merge(J[["signal_id", "level", "pattern", "rule", "agreement", "h1_atr", "stop_distance"]], on="signal_id", how="left")
    X["t"] = pd.to_datetime(X.entry_time, utc=True)
    g = Z.daily_grid(Z.bars("D1"))
    k = g.index.searchsorted(X.t, side="right") - 1
    anc, stp = g.anchor.values[k], g.step.values[k]
    pos = (X.entry_price - anc) / stp
    X["zone_pos"] = pos - np.floor(pos)  # 0 = on a grid line, 0.5 = mid-zone
    X["zone_line_dist"] = np.minimum(X.zone_pos, 1 - X.zone_pos) * stp  # USD to the nearest grid line
    return X


if __name__ == "__main__":
    X = load()
    W = X[(X.t >= pd.Timestamp(sys.argv[1], tz="UTC")) & (X.t < pd.Timestamp(sys.argv[2], tz="UTC"))]
    for r in W.itertuples():
        tf = "M5" if r.strategy.endswith("m5") else "M1"
        how = re.sub(r",.*", "", str(r.level))
        pat = re.sub(r" \(.*", "", str(r.rule).split(": ", 1)[-1])
        risk = abs(r.entry_price - r.sl_initial)
        print(f"{r.t.tz_convert('Asia/Bangkok'):%a %d %H:%M} {tf} {r.side:4s} R {r.r_multiple:+.2f} {r.exit_reason:6s} "
              f"best {r.mfe / risk:+.2f}R worst {-r.mae / risk:+.2f}R | {pat} | level {how} | {r.agreement} | stop {str(r.stop_distance).split(' to')[0]} "
              f"| grid line {r.zone_line_dist:.1f} USD away")
    print(f"week: {len(W)} trades {W.r_multiple.sum():+.2f} R")
