"""NS-3: the 08:30-NY straddle by release type (notes.md "NS-3", written before computing 2026-10-21 12:35 Thai).
PLAN-1's straddle rule (ns1_ticks.straddle, equal to dev1's runner) on every weekday 2021-09-01 .. 2026-10-16, ticks
from D:/taa-data/ticks (to 2025-09) and data/ticks (2025-10 on); typed by app/news/us_releases.csv (08:30 rows): NFP,
CPI, other release (PPI / PCE / GDP), none. The H1 ATR at 08:30 tags the VOL-16 band.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/ns3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import ns1_ticks as N

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # gold.py
ROOT = Path(__file__).resolve().parents[4]
OLD, NEW = Path("D:/taa-data/ticks/XAUUSD"), ROOT / "data/ticks/XAUUSD"
END = pd.Timestamp("2026-10-17", tz="UTC")


def ticks(day: pd.Timestamp):
    f = (OLD if day < pd.Timestamp("2025-10-01", tz="UTC") else NEW) / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f).sort_values("time_utc", kind="stable")
    return (pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), x.bid.to_numpy(float),
            x.ask.to_numpy(float))


def kind_of() -> dict[str, str]:
    cal = pd.read_csv(ROOT / "app/news/us_releases.csv")
    cal = cal[cal.time_et == "08:30"]
    out: dict[str, str] = {}
    for d, g in cal.groupby("date"):
        ev = set(g.event)
        out[d] = "NFP" if "NFP" in ev else "CPI" if "CPI" in ev else "other release"
    return out


def main() -> None:
    import gold  # noqa: PLC0415

    h = gold.bars("H1", before=END + pd.Timedelta(days=1))
    pc = h.close.shift(1)
    atr = pd.concat([h.high - h.low, (h.high - pc).abs(), (h.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    a_t, a_v = (h.index + pd.Timedelta(hours=1)).as_unit("ns").asi8, atr.to_numpy()
    kinds = kind_of()
    rows = []
    for day in pd.bdate_range("2021-09-01", "2026-10-16", tz="UTC"):
        tk = ticks(day)
        if tk is None:
            continue
        d = f"{day:%Y-%m-%d}"
        t0 = pd.Timestamp(f"{d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value
        s = N.straddle(*tk, t0)
        if s is None:
            continue
        i = int(np.searchsorted(a_t, t0, side="right")) - 1
        per = "exam (seen)" if d >= "2026-04-18" else f"{day.year if day.month >= 10 else day.year - 1}-" \
            f"{(day.year + 1 if day.month >= 10 else day.year) % 100:02d}"
        rows.append(dict(day=d, kind=kinds.get(d, "none"), period=per, atr=float(a_v[i]), R=s["R"]))
    T = pd.DataFrame(rows)
    T["band"] = (T.atr >= 12) & (T.atr < 16)
    tab = T.groupby(["kind", "period"]).R.agg(["size", "mean"]).round(3)
    print(tab.unstack("period").to_string())
    learn = T[T.period != "exam (seen)"]
    print("\npooled 2021-09 .. 2026-04-17 by type (trades, R, 95 % range) | in the VOL-16 band | outside")
    for k, g in learn.groupby("kind"):
        se = g.R.std() / np.sqrt(len(g))
        b, o = g[g.band], g[~g.band]
        ok = len(g) >= 40 and g.R.mean() >= 0.15 and g.R.mean() - 1.96 * se > 0
        print(f"  {k:14s} {len(g):4d} {g.R.mean():+.3f} ({g.R.mean() - 1.96 * se:+.3f}..{g.R.mean() + 1.96 * se:+.3f}) "
              f"{'PASS' if ok else 'fail'} | band {len(b):3d} {b.R.mean() if len(b) else float('nan'):+.3f} | "
              f"out {len(o):4d} {o.R.mean():+.3f}")
    T.to_parquet(Path(__file__).with_name("ns3.parquet"))


if __name__ == "__main__":
    main()
