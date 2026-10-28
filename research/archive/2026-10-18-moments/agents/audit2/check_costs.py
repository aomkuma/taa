"""Audit 6: the M1 cost formula against the raw ticks of the learning parts (2025-10-18 .. 2026-04-17).

The M1-only formula: the spread an entry pays = the M1 spread column x 0.01 + 0.08. Here, per minute, from the raw tick
files (not the earlier audit's tick_minutes.parquet): the first tick's spread (what an entry at the minute's open pays)
and the minute's mean spread, against the formula; overall and in the owner's windows (Asia 07-09 Thai, London 13-14
Thai, the NY open 09:30 NY + 2 h). The slippage numbers are the earlier audit's (auditor/notes.md, tick_sim.log).

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_costs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
TICKS = ROOT / "data" / "ticks" / "XAUUSD"
STORE = ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
LO, HI = pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-04-18", tz="UTC")


def minutes_from_ticks() -> pd.DataFrame:
    parts = []
    for d in pd.date_range(LO, HI - pd.Timedelta(days=1), freq="D"):
        f = TICKS / f"{d:%Y-%m-%d}.parquet"
        if not f.exists():
            continue
        x = pd.read_parquet(f)
        if not len(x):
            continue
        t = pd.to_datetime(x["time_utc"], utc=True).dt.as_unit("ns")
        o = np.argsort(t.to_numpy(), kind="stable")
        spr = (x["ask"].to_numpy(float) - x["bid"].to_numpy(float))[o]
        m = t.iloc[o].dt.floor("min").to_numpy()
        g = pd.DataFrame({"m": m, "s": spr}).groupby("m", sort=True)["s"]
        parts.append(pd.DataFrame({"first": g.first(), "mean": g.mean(), "min": g.min()}))
    out = pd.concat(parts)
    out.index = pd.DatetimeIndex(out.index).tz_localize("UTC") if out.index.tz is None else out.index
    return out


def windows(idx: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    th = idx.tz_convert("Asia/Bangkok")
    ny = idx.tz_convert("America/New_York")
    th_min = th.hour * 60 + th.minute
    ny_min = ny.hour * 60 + ny.minute
    return {
        "all": np.ones(len(idx), bool),
        "Asia 07-09 Thai": np.asarray((th_min >= 7 * 60) & (th_min < 9 * 60)),
        "London 13-14 Thai": np.asarray((th_min >= 13 * 60) & (th_min < 14 * 60)),
        "NY open 09:30-11:30 NY": np.asarray((ny_min >= 9 * 60 + 30) & (ny_min < 11 * 60 + 30)),
    }


def main() -> int:
    tk = minutes_from_ticks()
    m = pd.read_parquet(STORE, columns=["open_time", "spread"], filters=[("open_time", ">=", LO), ("open_time", "<", HI)])
    m = m.set_index(pd.DatetimeIndex(m["open_time"]).as_unit("ns"))
    j = tk.join(m["spread"], how="inner")
    formula = j["spread"] * 0.01 + 0.08
    print(f"learning parts {LO.date()} .. {HI.date()}: {len(j)} minutes with ticks and an M1 bar")
    print("window | minutes | first-tick spread median / mean | formula median / mean | formula - first: median / "
          "mean / p10 / p90 | formula >= first | M1 column = min spread")
    for name, w in windows(j.index).items():
        x = j[w]
        f, d = formula[w], (formula[w] - x["first"])
        print(
            f"{name:24} | {len(x):6} | {x['first'].median():.3f} / {x['first'].mean():.3f} | {f.median():.3f} / "
            f"{f.mean():.3f} | {d.median():+.3f} / {d.mean():+.3f} / {d.quantile(0.1):+.3f} / {d.quantile(0.9):+.3f} | "
            f"{100 * (d >= -1e-9).mean():.1f} % | {100 * ((x['spread'] * 0.01).round(2) == x['min'].round(2)).mean():.1f} %"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
