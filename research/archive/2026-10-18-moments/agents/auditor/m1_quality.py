"""Auditor check 3: the M1 history's quality (gold.bars("M1")): duplicates, OHLC sanity, gaps inside trading hours,
the old/new store overlap, spikes, the spread column over time, the daily break by DST regime.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/m1_quality.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

pd.set_option("display.width", 220)


def main() -> None:
    gold.below_normal_priority()
    m = gold.bars("M1")
    print(f"bars {len(m)}  {m.index.min()} .. {m.index.max()}")
    print("duplicate open times:", int(m.index.duplicated().sum()))
    bad = (m.high < m[["open", "close"]].max(1)) | (m.low > m[["open", "close"]].min(1)) | (m.high < m.low)
    print("OHLC inconsistent bars:", int(bad.sum()), "; zero-range bars:", int((m.high == m.low).sum()),
          f"({100 * (m.high == m.low).mean():.2f}%)", "; spread <= 0:", int((m.spread <= 0).sum()))
    ct = pd.to_datetime(m.close_time, utc=True)
    print("close_time - open_time != 60 s:", int(((ct - m.index).dt.total_seconds() != 60).sum()))
    # old vs new store in the overlap
    old = pd.read_parquet(gold.OLD / "M1.parquet")
    new = pd.read_parquet(gold.NEW / "M1.parquet")
    old.index = pd.DatetimeIndex(pd.to_datetime(old.open_time, utc=True))
    new.index = pd.DatetimeIndex(pd.to_datetime(new.open_time, utc=True))
    ov = old.join(new, how="inner", lsuffix="_o", rsuffix="_n")
    print(f"old store {old.index.min()} .. {old.index.max()}, new {new.index.min()} .. {new.index.max()}; overlap bars {len(ov)}")
    if len(ov):
        for k in ("open", "high", "low", "close", "spread"):
            dd = (ov[f"{k}_o"] - ov[f"{k}_n"]).abs()
            print(f"   overlap {k}: equal {100 * (dd < 1e-9).mean():.1f}%  max |diff| {dd.max():.2f}")
        # best shift (hours) between the stores, by close correlation of returns
        for h in (-3, -2, -1, 0, 1, 2, 3):
            a = old.close.diff()
            b = new.close.diff().shift(freq=pd.Timedelta(hours=h))
            jj = pd.concat([a, b], axis=1, join="inner").dropna()
            print(f"   shift new by {h:+d} h: return correlation {jj.corr().iloc[0, 1]:.3f} ({len(jj)})")
    # gaps inside trading hours: consecutive bars more than 1 minute apart, not at the daily break or the weekend
    dt = pd.Series(m.index[1:] - m.index[:-1], index=m.index[1:])
    gap = dt[dt > pd.Timedelta(minutes=1)]
    ny = gap.index.tz_convert("America/New_York")
    prev_ny = (gap.index - gap.values).tz_convert("America/New_York")
    brk = (prev_ny.hour.isin([16, 17])) | (ny.hour.isin([17, 18]) & (gap.values <= pd.Timedelta(hours=2)))
    wkend = gap.values >= pd.Timedelta(hours=40)
    other = gap[~brk & ~wkend]
    print(f"\ngaps > 1 min: {len(gap)}; at the daily break (~17:00-18:00 ET) {int(brk.sum())}; weekends/holidays {int(wkend.sum())}; other {len(other)}")
    print("   other gaps by length:", pd.cut(other.dt.total_seconds() / 60, [1, 2, 5, 15, 60, 600, 1e9]).value_counts().sort_index().to_dict())
    o2 = other[other > pd.Timedelta(minutes=5)]
    print("   other gaps > 5 min, by year:", o2.groupby(o2.index.year).size().to_dict())
    print("   the 10 longest other gaps:")
    for t, g in other.sort_values(ascending=False).head(10).items():
        print(f"      {t - g} -> {t} ({g})")
    # are the session windows ever inside a gap? count missing minutes in the three active windows (2023-11 ..)
    # spikes: a bar whose high or low lies > 8 x the rolling median range away from both neighbours' closes
    rng = (m.high - m.low)
    med = rng.rolling(240, min_periods=60).median()
    c = m.close
    up = (m.high - np.maximum(c.shift(1), c.shift(-1))) > 8 * med
    dn = (np.minimum(c.shift(1), c.shift(-1)) - m.low) > 8 * med
    sp = m[(up | dn) & (med > 0)]
    print(f"\nspike bars (wick > 8x the 4-hour median range beyond both neighbours' closes): {len(sp)}; by year {sp.groupby(sp.index.year).size().to_dict()}")
    print(sp.assign(med=med[sp.index]).sort_values("high").tail(0).to_string())
    for t, r in sp.head(12).iterrows():
        print(f"      {t} o {r.open} h {r.high} l {r.low} c {r.close} sp {r.spread} med range {med[t]:.2f}")
    # spread column by year-month (median, points) and the share of 'minimum spread' bars
    s = m.spread.groupby(m.index.strftime("%Y")).describe()[["mean", "25%", "50%", "75%", "max"]]
    print("\nM1 spread column (points; the minute's MINIMUM spread) by year:\n", s.round(1).to_string())
    # daily break by DST regime (US and EU)
    mod = m.index.hour * 60 + m.index.minute
    for yr in (2021, 2023, 2025, 2026):
        for mo in (1, 3, 7, 11):
            x = m[(m.index.year == yr) & (m.index.month == mo) & (m.index.weekday < 4)]
            if not len(x):
                continue
            mm = pd.Series(x.index.hour * 60 + x.index.minute).value_counts()
            nd = x.index.normalize().nunique()
            low = sorted(set(range(1440)) - set(mm[mm >= 0.5 * nd].index))
            if low:
                print(f"   {yr}-{mo:02d}: UTC minutes mostly empty (Mon-Thu): {low[0] // 60:02d}:{low[0] % 60:02d} .. {low[-1] // 60:02d}:{low[-1] % 60:02d} ({len(low)} min)")
    _ = mod


if __name__ == "__main__":
    main()
