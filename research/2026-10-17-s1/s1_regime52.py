"""S1 by gold's 52-week position at the entry (the TS session's suggestion, 2026-10-17: gold made new highs through
2024-26 and not in 2021-23). ``pos52`` = the last closed D1 close within the previous 252 D1 bars' low..high
(1 = at the 52-week high), as of the entry. The threshold is chosen on A and B (2024-10 .. 2026-09) only; C, D and
E judge it. S1 with the spread floor (15 spreads, time stop 240, cooldown 60), the harness of s1_funnel.py.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/s1_regime52.py
"""

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
sys.path.insert(0, ".")
import s1_funnel as f  # noqa: E402

YEARS = {
    "E": ("2021-10-01", "2022-10-01", "data/history_old/FBS-Demo/XAUUSD"),
    "D": ("2022-10-01", "2023-10-01", "data/history_old/FBS-Demo/XAUUSD"),
    "C": ("2023-10-01", "2024-10-01", "data/history/FBS-Demo/XAUUSD"),
    "A": ("2024-10-01", "2025-10-01", "data/history/FBS-Demo/XAUUSD"),
    "B": ("2025-10-01", "2026-10-01", "data/history/FBS-Demo/XAUUSD"),
}


def d1_pos52() -> pd.Series:
    d = pd.concat([pd.read_parquet(f"{h}/D1.parquet") for h in sorted({v[2] for v in YEARS.values()})])
    d = d.drop_duplicates("open_time").sort_values("open_time")
    close_t = pd.to_datetime(d["close_time"], utc=True)
    hi = d["high"].rolling(252, min_periods=200).max().shift(1)
    lo = d["low"].rolling(252, min_periods=200).min().shift(1)
    pos = ((d["close"] - lo) / (hi - lo)).to_numpy()
    return pd.Series(pos, index=close_t.to_numpy())


def trades(h: str) -> pd.DataFrame:
    f.H = h
    point = json.load(open(f"{h}/spec.json"))["spec"]["point"]
    m1 = f.load("M1")
    d = f.outcomes(m1, f.events(m1, 20), point, k=15, spreads_only=True, time_stop=240)
    ny = d["t"].dt.tz_convert(f.NY)
    nym = ny.dt.hour * 60 + ny.dt.minute
    utc = d["t"].dt.hour + d["t"].dt.minute / 60
    wd = d["t"].dt.weekday
    keep = (wd < 5) & ~((wd == 4) & (utc >= 16)) & (utc >= 7) & (utc < 20) & ~((nym >= 480) & (nym < 720))
    return f.one_at_a_time(d[keep], 60)


def main() -> None:
    f.below_normal_priority()
    pos = d1_pos52()
    out = []
    for h in sorted({v[2] for v in YEARS.values()}):
        t = trades(h)
        for y, (a, b, hh) in YEARS.items():
            if hh != h:
                continue
            x = t[(t.t >= pd.Timestamp(a, tz="UTC")) & (t.t < pd.Timestamp(b, tz="UTC"))].copy()
            j = pos.index.searchsorted(x.t.to_numpy(), side="right") - 1
            x["pos52"] = np.where(j >= 0, pos.to_numpy()[np.clip(j, 0, None)], np.nan)
            x["year"] = y
            out.append(x)
    d = pd.concat(out)
    d["side_name"] = np.where(d.side > 0, "BUY", "SELL")
    d["band"] = pd.cut(d.pos52, [-0.01, 0.5, 0.75, 0.9, 1.01], labels=["<0.5", "0.5-0.75", "0.75-0.9", ">=0.9"])
    print("R per trade (trades) by 52-week position and side, per year")
    g = d.groupby(["side_name", "band", "year"], observed=True).r.agg(["count", "mean"]).round(3)
    print(g.unstack("year").to_string())
    d.to_parquet("data/research/s1_regime52.parquet")


if __name__ == "__main__":
    main()
