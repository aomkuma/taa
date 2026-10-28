"""Auditor check 2/3: the M1 bars against the ticks, the real spread by hour and around releases, the daily break.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/tick_vs_m1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

HERE = Path(__file__).parent
pd.set_option("display.width", 220)


def q(s: pd.Series) -> str:
    return " ".join(f"p{k}={np.nanpercentile(s, k):.2f}" for k in (5, 25, 50, 75, 95, 99)) + f" mean={s.mean():.3f}"


def main() -> None:
    tm = pd.read_parquet(HERE / "tick_minutes.parquet")
    m1 = gold.bars("M1")
    m1 = m1[m1.index >= pd.Timestamp("2025-10-01", tz="UTC")]
    m1 = m1.drop(columns=["open_time"])
    lo_, hi_ = tm.index.min(), m1.index.max()
    tm = tm[tm.index <= hi_]
    print(f"overlap {lo_} .. {hi_}: tick minutes {len(tm)}, M1 bars {len(m1)}")
    j = m1.join(tm, how="outer")
    j.index = pd.DatetimeIndex(j.index)
    only_m1 = j.n.isna() & j.open.notna()
    only_tk = j.open.isna() & j.n.notna()
    print(f"M1 bars without ticks: {int(only_m1.sum())}; tick minutes without an M1 bar: {int(only_tk.sum())}")
    if only_m1.any():
        print("   M1-only by day (top):", j[only_m1].index.normalize().value_counts().head(8).to_dict())
    if only_tk.any():
        print("   tick-only by day (top):", j[only_tk].index.normalize().value_counts().head(8).to_dict())
    b = j[j.open.notna() & j.n.notna()].copy()
    for a, t in (("open", "b_o"), ("high", "b_h"), ("low", "b_l"), ("close", "b_c")):
        dlt = (b[a] - b[t]).round(2)
        print(f"M1 {a:5} - tick bid {t}: exact {100 * (dlt == 0).mean():5.1f}%  |diff|>0.05 {100 * (dlt.abs() > 0.05).mean():4.1f}%  {q(dlt)}")
    sp = b.spread * 0.01
    for col in ("s_first", "s_min", "s_mean", "s_max", "s_last"):
        dlt = (sp - b[col]).round(3)
        print(f"M1 spread - tick {col:7}: exact {100 * (dlt.abs() < 0.0051).mean():5.1f}%  {q(dlt)}")
    # what the simulator assumes vs the real ask
    print("Simulated ask prices (bid + M1 spread) vs the real ask:")
    print("  entry BUY  real ask open - (open + spread):", q((b.a_o - (b.open + sp)).round(2)))
    print("  SELL stop  real ask high - (high + spread):", q((b.a_h - (b.high + sp)).round(2)))
    print("  SELL tgt   real ask low  - (low + spread) :", q((b.a_l - (b.low + sp)).round(2)))
    print("  time exit  real ask close- (close+spread) :", q((b.a_c - (b.close + sp)).round(2)))

    # spread by UTC hour, tick-minute mean (the cost an entry at a random moment of the minute pays)
    t = tm.copy()
    t["hour"] = t.index.hour
    t["half"] = np.where(t.index < pd.Timestamp("2026-04-01", tz="UTC"), "2025-10..26-03", "2026-04..10")
    print("\nReal spread (USD) by UTC hour: median of per-minute mean / p90 / the first tick of the minute (median) / M1 column median")
    m1h = m1.spread.groupby(m1.index.hour).median() * 0.01
    tab = t.groupby("hour").agg(med=("s_mean", "median"), p90=("s_mean", lambda v: v.quantile(0.9)), first=("s_first", "median"),
                                ticks=("n", "median"), minutes=("n", "size"))
    tab["m1_col"] = m1h
    tab.to_csv(HERE / "spread_by_hour.csv")
    print(tab.round(3).to_string())
    print("\nby half-year, sessions (per-minute mean spread: median / p90):")
    t["ny"] = t.index.tz_convert("America/New_York")
    t["ldn"] = t.index.tz_convert("Europe/London")
    mins_ny = t.ny.dt.hour * 60 + t.ny.dt.minute
    mins_ld = t.ldn.dt.hour * 60 + t.ldn.dt.minute
    sess = np.select(
        [t.index.hour < 2, (mins_ld >= 480) & (mins_ld < 570), (mins_ny >= 495) & (mins_ny < 675)],
        ["Asia 00-02 UTC", "London 08:00-09:30", "NY 08:15-11:15"], "other")
    t["sess"] = sess
    print(t.groupby(["sess", "half"]).s_mean.agg(["median", lambda v: v.quantile(0.9), "size"]).round(3).to_string())

    # around releases: minute offset -5 .. +15 from the release, versus the same clock minute on other days
    rel = gold.releases()
    rel = rel[(rel.t >= lo_) & (rel.t <= hi_)]
    rows = []
    for r in rel.itertuples():
        for k in range(-5, 16):
            tt = r.t + pd.Timedelta(minutes=k)
            if tt in tm.index:
                rows.append((r.event, k, tm.at[tt, "s_mean"], tm.at[tt, "s_max"], tm.at[tt, "jump_max"]))
    R = pd.DataFrame(rows, columns=["event", "k", "s_mean", "s_max", "jump"])
    print(f"\nAround {len(rel)} releases in the tick window: per-minute mean spread / max spread / largest tick jump (medians)")
    print(R.groupby("k")[["s_mean", "s_max", "jump"]].median().round(2).T.to_string())
    print("  by event at minute 0 and +1 (median mean spread):", R[R.k.isin([0, 1])].groupby("event").s_mean.median().round(2).to_dict())
    base = t[(t.ny.dt.hour * 60 + t.ny.dt.minute).between(500, 520)].s_mean.median()
    print(f"  baseline: 08:20-08:40 ET all days median mean spread {base:.3f}")

    # the daily break and missing minutes (weekdays, per UTC minute of day)
    t["mod"] = t.index.hour * 60 + t.index.minute
    t["dst"] = t.index.tz_convert("Europe/Athens").map(lambda x: x.utcoffset().total_seconds() / 3600)
    days = t.index.normalize().nunique()
    cov = t.groupby(["dst", "mod"]).size().unstack(0).fillna(0)
    for off in cov.columns:
        nd = t[t.dst == off].index.normalize().nunique()
        low = cov.index[cov[off] < 0.5 * nd]
        print(f"server UTC+{off:.0f} ({nd} days): UTC minutes of day with ticks on < half the days: "
              f"{[f'{m // 60:02d}:{m % 60:02d}' for m in low[:3]]} .. {[f'{m // 60:02d}:{m % 60:02d}' for m in low[-3:]]} ({len(low)} min)")
    # spikes: a single tick-to-tick bid jump of >= 2 USD that reverts within the minute (bad ticks?)
    big = tm[tm.jump_max >= 2.0]
    print(f"\nminutes with a single tick jump >= 2 USD: {len(big)} of {len(tm)}; >= 5 USD: {int((tm.jump_max >= 5).sum())}")
    print(big.sort_values("jump_max", ascending=False).head(10)[["n", "b_o", "b_h", "b_l", "b_c", "s_max", "jump_max"]].to_string())
    print("non-positive spreads (ticks):", int(tm.neg_spr.sum()))
    print("tick-file stats:", pd.read_csv(HERE / "tick_files.csv")["info"].str.contains("unordered 0 duplicate rows 0").value_counts().to_dict(),
          "(files with no out-of-order / duplicate ticks)")
    print(f"total days {days}")


if __name__ == "__main__":
    main()
