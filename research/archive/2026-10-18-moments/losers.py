"""Learn from the losers (owner, 2026-10-17): round 1's moment entries (q70 stop, the exits of exits.py), what the
losers share at the entry against the winners, in the first three months and the last three side by side.

At the entry only (no look-ahead): minutes after the moment, the chase (how far price already moved the trade's
way from the moment's open, in U), contraction, flow, session.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/losers.py
"""

from __future__ import annotations

import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from moments import END, FIT_END, OUT, START  # noqa: E402
from select_fit import group  # noqa: E402

TH = ZoneInfo("Asia/Bangkok")


def table(t: pd.DataFrame, col: str) -> str:
    g = t.groupby([col, "half"], observed=True).agg(
        n=("r_S70", "size"), win=("win", "mean"), r=("r_S70", "mean"), stop_min=("loss_min", "median")
    )
    g = g.unstack("half")
    lines = [f"\n{col}:  n / win% / R per trade / losers' minutes to the stop  (first 3 months | last 3 months)"]
    for idx, row in g.iterrows():
        cells = []
        for half in ("first", "last"):
            if (("n", half) in row.index) and pd.notna(row[("n", half)]):
                cells.append(
                    f"{int(row[('n', half)]):4} {100 * row[('win', half)]:3.0f}% {row[('r', half)]:+.3f}"
                    f" {row[('stop_min', half)]:4.0f}m"
                )
            else:
                cells.append(" " * 22)
        lines.append(f"  {str(idx):22} " + " | ".join(cells))
    return "\n".join(lines)


def main() -> None:
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= START - pd.Timedelta(days=2)) & (m1.index < END + pd.Timedelta(days=2))]
    o = m1["open"].to_numpy(float)
    ot = m1.index
    t = pd.read_parquet(f"{OUT}_exits.parquet")
    f = pd.read_parquet(f"{OUT}_features.parquet")
    t = t[(t.kind == "moment") & t.r_S70.notna() & (t.t < END)].merge(
        f[["rid", "bb_pct", "atr_pct", "pre_range_u", "h1_now", "m15_now"]], on="rid"
    )
    t["half"] = np.where(t.t < FIT_END, "first", "last")
    t["win"] = (t.r_S70 > 0).astype(float)
    t["loss_min"] = t.min_S70.where(t.r_S70 < -0.5)
    t["delay"] = (t.te - t.t).dt.total_seconds() / 60
    e, s0 = ot.searchsorted(t.te), ot.searchsorted(t.t)
    t["chase_u"] = (o[e] - o[s0]) * t.side.to_numpy() / t.u.to_numpy()
    t["session"] = t.tags.map(group)
    t["thai"] = t.t.dt.tz_convert(TH).dt.strftime("%H:%M")
    t["delay_bin"] = pd.cut(t.delay, [-1, 2, 9, 19, 60], labels=["0-2 min", "3-9 min", "10-19 min", "20+ min"])
    t["chase_bin"] = pd.cut(
        t.chase_u, [-9, -0.3, -0.1, 0.1, 0.3, 9], labels=["against >0.3U", "against 0.1-0.3U", "flat", "with 0.1-0.3U", "with >0.3U"]
    )
    t["bb_bin"] = pd.cut(t.bb_pct, [-1, 20, 50, 80, 101], labels=["squeeze <=20", "20-50", "50-80", ">80"])
    t["atr_bin"] = pd.cut(t.atr_pct, [-1, 20, 50, 80, 101], labels=["<=20", "20-50", "50-80", ">80"])
    t["pre_bin"] = pd.cut(t.pre_range_u, [-1, 0.8, 1.2, 1.8, 99], labels=["<0.8U", "0.8-1.2U", "1.2-1.8U", ">1.8U"])
    t["flow_rel"] = np.sign(t.with_flow).map({1: "with the flow", -1: "against", 0: "no flow"})
    t["clear_rel"] = np.where(t.clear == t.side, "clear, our way", np.where(t.clear == -t.side, "clear, against", "not clear"))
    t["pb_session"] = t.pb + " " + t.session

    los = t[t.r_S70 < -0.5]
    print(f"Moment entries {len(t)}, losers (R < -0.5) {len(los)} ({100 * len(los) / len(t):.0f}%), minutes to the stop:"
          f" median {los.min_S70.median():.0f}, q25 {los.min_S70.quantile(0.25):.0f}, q75 {los.min_S70.quantile(0.75):.0f}")
    fast = (los.min_S70 <= 5).mean()
    print(f"Losers stopped within 5 minutes of the entry: {100 * fast:.0f}%")
    for col in ("pb_session", "thai", "delay_bin", "chase_bin", "bb_bin", "atr_bin", "pre_bin", "flow_rel", "clear_rel"):
        print(table(t, col))
    t.to_parquet(f"{OUT}_losers.parquet")


if __name__ == "__main__":
    main()
