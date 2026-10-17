"""Auditor check 3b: the majors' M1 data quality and their spread column (the minute's MINIMUM spread, as measured
for gold against its ticks) by UTC hour, by session and around US releases. No FX ticks exist.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/fx_quality.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
HERE = Path(__file__).parent
pd.set_option("display.width", 240)


def main() -> None:
    gold.below_normal_priority()
    rel = gold.releases()
    hours = {}
    summ = []
    for pair in PAIRS:
        base = Path("data/history/FBS-Demo") / pair
        spec = json.load(open(base / "spec.json"))["spec"]
        point = spec["point"]
        pip = 0.01 if "JPY" in pair else 0.0001
        m = pd.read_parquet(base / "M1.parquet")
        m.index = pd.DatetimeIndex(pd.to_datetime(m.open_time, utc=True))
        m = m.sort_index()
        dup = int(m.index.duplicated().sum())
        m = m[~m.index.duplicated()]
        bad = int(((m.high < np.maximum(m.open, m.close)) | (m.low > np.minimum(m.open, m.close))).sum())
        zero = float((m.high == m.low).mean())
        sp = m.spread * point / pip  # pips
        dt = pd.Series(m.index[1:] - m.index[:-1], index=m.index[1:])
        gap = dt[dt > pd.Timedelta(minutes=1)]
        prev_ny = (gap.index - gap.values).tz_convert("America/New_York")
        brk = prev_ny.hour.isin([16, 17]) & (gap.values <= pd.Timedelta(hours=2))
        wk = gap.values >= pd.Timedelta(hours=40)
        other = gap[~brk & ~wk]
        rng = m.high - m.low
        med = rng.rolling(240, min_periods=60).median()
        c = m.close
        spike = ((m.high - np.maximum(c.shift(1), c.shift(-1))) > 10 * med) | ((np.minimum(c.shift(1), c.shift(-1)) - m.low) > 10 * med)
        recent = m.index >= pd.Timestamp("2025-10-01", tz="UTC")
        ny = m.index.tz_convert("America/New_York")
        ld = m.index.tz_convert("Europe/London")
        mny, mld = ny.hour * 60 + ny.minute, ld.hour * 60 + ld.minute
        s_asia = sp[(m.index.hour < 2) & recent]
        s_ldn = sp[(mld >= 480) & (mld < 570) & recent]
        s_ny = sp[(mny >= 495) & (mny < 675) & recent]
        s_roll = sp[((m.index.hour >= 20) & (m.index.hour < 24)) & recent]
        # around releases (minute 0 and +1 vs the same clock other days)
        rt = pd.DatetimeIndex(rel.t)
        at = sp.reindex(rt).dropna()
        summ.append(dict(pair=pair, first=m.index.min().date(), last=m.index.max().date(), bars=len(m), dup=dup, bad_ohlc=bad,
                         zero_rng=f"{100 * zero:.1f}%", gaps_other=len(other), gaps_other_gt5=int((other > pd.Timedelta(minutes=5)).sum()),
                         spikes=int(spike.sum()), sp_le0=int((m.spread <= 0).sum()),
                         asia=s_asia.median(), london=s_ldn.median(), ny=s_ny.median(), rollover=s_roll.median(),
                         all_mean=sp[recent].mean(), at_release=at.median(), ny_p90=s_ny.quantile(0.9)))
        hours[pair] = sp[recent].groupby(m.index[recent].hour).median()
        if len(other):
            print(pair, "longest other gaps:", [(str(t - g), str(g)) for t, g in other.sort_values(ascending=False).head(3).items()])
    S = pd.DataFrame(summ)
    print("\nMajors' M1 (FBS-Demo): quality, and the spread column in pips (the minute's MINIMUM spread), 2025-10 .. :")
    print(S.round(2).to_string(index=False))
    H = pd.DataFrame(hours).round(2)
    print("\nspread column median by UTC hour (pips), 2025-10 ..:")
    print(H.T.to_string())
    S.to_csv(HERE / "fx_quality.csv", index=False)
    H.to_csv(HERE / "fx_spread_by_hour.csv")


if __name__ == "__main__":
    main()
