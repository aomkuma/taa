"""Round 4: the old release ticks (data/ticks_old/XAUUSD, written by precursors/fetch_release_ticks.py) - their UTC time.

Every file is a day of 2021-09 .. 2025-10 (before the learning parts; no exam day). Two checks of the server-time
conversion:
1. against the M1 store (gold.bars, OLD / NEW merge): the ticks' bid re-aggregated per UTC minute (open = first bid,
   high / low, close = last bid) against the stored M1 bar of that minute - equal when the times agree; a shift of an
   hour (a wrong DST rule) would leave the minutes unequal;
2. against the clock of the news (an outside source): on the 08:30-NY release days, where the largest one-minute bid
   range of the 08:20 .. 09:05 NY window sits, in minutes from 08:30 NY.
Also: the file's span (first / last tick against 08:20 / 09:05 NY) and the file name = the New York date.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_ticks_old.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = ROOT / "data" / "ticks_old" / "XAUUSD"
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
sys.path.insert(0, str(ROOT / "research" / "2026-10-18-moments"))


def main() -> None:
    import gold  # noqa: PLC0415

    files = sorted(OLD.glob("*.parquet"))
    days = [f.stem for f in files]
    assert all(pd.Timestamp(d, tz="UTC") < EXAM for d in days)
    m = gold.bars("M1", before=pd.Timestamp(days[-1], tz="UTC") + pd.Timedelta(days=2))
    m = m.loc[m.index >= pd.Timestamp(days[0], tz="UTC") - pd.Timedelta(days=1)]
    m = m[~m.index.duplicated(keep="last")]
    cal = pd.read_csv(ROOT / "app/news/us_releases.csv")
    rel = set(cal[cal.time_et == "08:30"].date)
    eq_min = tot_min = 0
    eq_shift = {-60: 0, 60: 0}
    span_bad, name_bad, peak = [], [], []
    per_day_bad = []
    for f, d in zip(files, days, strict=True):
        x = pd.read_parquet(f)
        t = pd.DatetimeIndex(pd.to_datetime(x.time_utc, utc=True))
        o = np.argsort(t.asi8, kind="stable")
        t, bid = t[o], x.bid.to_numpy(float)[o]
        a = pd.Timestamp(f"{d} 08:20").tz_localize("America/New_York").tz_convert("UTC")
        z = a + pd.Timedelta(minutes=45)
        if t[0] < a or t[-1] >= z or (t[0] - a) > pd.Timedelta(minutes=2) or (z - t[-1]) > pd.Timedelta(minutes=2):
            span_bad.append((d, str(t[0]), str(t[-1])))
        if t.tz_convert("America/New_York")[0].strftime("%Y-%m-%d") != d:
            name_bad.append(d)
        g = pd.Series(bid, index=t).groupby(t.floor("min"))
        agg = pd.DataFrame({"open": g.first(), "high": g.max(), "low": g.min(), "close": g.last()})
        agg = agg.iloc[1:-1]  # the first / last minute of the window are cut by the window itself

        def equal(shift: int) -> np.ndarray:
            idx = agg.index + pd.Timedelta(minutes=shift)
            ok = idx.isin(m.index)
            mm = m.reindex(idx)
            same = ok & np.isclose(mm.open.to_numpy(), agg.open.to_numpy()) & np.isclose(mm.high.to_numpy(), agg.high.to_numpy()) \
                & np.isclose(mm.low.to_numpy(), agg.low.to_numpy()) & np.isclose(mm.close.to_numpy(), agg.close.to_numpy())
            return same

        s0 = equal(0)
        eq_min += int(s0.sum())
        tot_min += len(agg)
        for sh in eq_shift:
            eq_shift[sh] += int(equal(sh).sum())
        if s0.mean() < 0.95:
            per_day_bad.append((d, round(float(s0.mean()), 3)))
        if d in rel:
            rng = (agg.high - agg.low)
            k = (rng.idxmax() - (a + pd.Timedelta(minutes=10))) / pd.Timedelta(minutes=1)
            peak.append(int(k))
    pk = pd.Series(peak).value_counts().sort_index()
    print(f"files {len(files)} ({days[0]} .. {days[-1]}); file name = the NY date of its first tick: {len(files) - len(name_bad)} "
          f"of {len(files)}; span 08:20 .. 09:05 NY (within 2 min): {len(files) - len(span_bad)} of {len(files)}")
    for b in span_bad[:5]:
        print(f"   span: {b}")
    print(f"1. tick minutes (bid OHLC) = the M1 store: {eq_min} of {tot_min} ({eq_min / tot_min:.4f}); with the ticks "
          f"shifted -60 min {eq_shift[-60]}, +60 min {eq_shift[60]}; days under 95 % equal: {per_day_bad[:10]}")
    print(f"2. release days {len(peak)}: the largest one-minute range at (minutes from 08:30 NY): "
          f"{pk.to_dict()}; at 0: {int((pd.Series(peak) == 0).sum())}")


if __name__ == "__main__":
    main()
