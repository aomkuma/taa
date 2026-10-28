"""Auditor: per-minute summary of every tick file (data/ticks/XAUUSD) -> auditor/tick_minutes.parquet.

Per UTC minute: ticks, bid open/high/low/close, ask high/low, spread first/min/mean/max/last, the largest tick-to-
tick bid jump, and data issues (non-positive spread, out-of-order or duplicate ticks).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/tick_minutes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

TICKS = Path("data/ticks/XAUUSD")
OUT = Path(__file__).with_name("tick_minutes.parquet")


def main() -> None:
    gold.below_normal_priority()
    parts, issues = [], []
    for f in sorted(TICKS.glob("*.parquet")):
        x = pd.read_parquet(f)
        if not len(x):
            issues.append((f.stem, "empty", 0))
            continue
        t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
        unordered = int((np.diff(t) < 0).sum())
        dup = int(x.duplicated().sum())
        order = np.argsort(t, kind="stable")
        t, bid, ask = t[order], x.bid.to_numpy(float)[order], x.ask.to_numpy(float)[order]
        spr = np.round(ask - bid, 2)
        jump = np.r_[0.0, np.abs(np.diff(bid))]
        m = t // 60_000_000_000
        df = pd.DataFrame({"m": m, "bid": bid, "ask": ask, "spr": spr, "jump": jump, "neg": (spr <= 0).astype(int)})
        g = df.groupby("m", sort=True)
        s = pd.DataFrame(
            {
                "n": g.size(),
                "b_o": g.bid.first(), "b_h": g.bid.max(), "b_l": g.bid.min(), "b_c": g.bid.last(),
                "a_o": g.ask.first(), "a_h": g.ask.max(), "a_l": g.ask.min(), "a_c": g.ask.last(),
                "s_first": g.spr.first(), "s_min": g.spr.min(), "s_mean": g.spr.mean(), "s_max": g.spr.max(),
                "s_last": g.spr.last(), "jump_max": g.jump.max(),
                "neg_spr": g.neg.sum(),
            }
        )
        s.index = pd.to_datetime(s.index * 60, unit="s", utc=True)
        parts.append(s)
        issues.append((f.stem, f"ticks {len(x)} unordered {unordered} duplicate rows {dup}", int(len(x))))
        if f.stem.endswith("-01"):
            print(f.stem, flush=True)
    out = pd.concat(parts).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    out.to_parquet(OUT)
    iss = pd.DataFrame(issues, columns=["day", "info", "n"])
    iss.to_csv(OUT.with_name("tick_files.csv"), index=False)
    print(out.shape)


if __name__ == "__main__":
    main()
