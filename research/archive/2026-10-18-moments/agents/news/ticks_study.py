"""News agent, step 1: the first seconds after a US release in gold's ticks (design window only: 2025-10-01 ..
2026-02-28). Per release: the spread second by second, when the first impulse peaks, how far it pulls back, and
where the spike's opposite extreme sits.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/ticks_study.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

TICKS = Path("data/ticks/XAUUSD")
END = pd.Timestamp("2026-03-01", tz="UTC")


def load(day: str) -> pd.DataFrame | None:
    f = TICKS / f"{day}.parquet"
    if not f.exists():
        return None
    t = pd.read_parquet(f)
    t["ns"] = pd.to_datetime(t.time_utc, utc=True).dt.as_unit("ns").astype("int64")
    return t


def main() -> None:
    gold.below_normal_priority()
    cal = gold.releases()
    cal = cal[(cal.t >= pd.Timestamp("2025-10-01", tz="UTC")) & (cal.t < END)]
    ev = cal.groupby("t").event.apply(lambda x: "+".join(sorted(set(x)))).reset_index()
    rows, spread_rows = [], []
    for t, name in zip(ev.t, ev.event, strict=True):
        tk = load(t.strftime("%Y-%m-%d"))
        if tk is None:
            continue
        t0 = t.value
        w = tk[(tk.ns >= t0 - 600e9) & (tk.ns < t0 + 3 * 3600e9)]
        sec = (w.ns.to_numpy() - t0) / 1e9
        mid = ((w.bid + w.ask) / 2).to_numpy()
        spr = (w.ask - w.bid).to_numpy()
        pre = mid[sec < 0]
        if len(pre) < 10:
            continue
        p0 = pre[-1]
        # the pre-release hour's typical 1-minute range from ticks (10 minutes here)
        pre_rng = pd.Series(mid[sec < 0], index=pd.to_datetime(w.ns[sec < 0])).resample("1min").agg(
            lambda x: x.max() - x.min() if len(x) else np.nan).mean()
        for b0, b1 in ((-60, -5), (-5, 0), (0, 2), (2, 5), (5, 10), (10, 20), (20, 30), (30, 60), (60, 120),
                       (120, 300), (300, 600)):
            m = (sec >= b0) & (sec < b1)
            if m.any():
                spread_rows.append(dict(t=t, event=name, bucket=f"{b0}..{b1}s", spread=np.median(spr[m]),
                                        spread_max=spr[m].max(), ticks_per_s=m.sum() / (b1 - b0)))
        # first impulse: the sign of the move at +60 s; its extreme within the first 5 minutes and when
        m60 = mid[(sec >= 0) & (sec <= 60)]
        if not len(m60):
            continue
        s = np.sign(m60[-1] - p0) or 1.0
        rec = dict(t=t, event=name, pre_rng=pre_rng, side=s)
        for k in (5, 10, 30, 60, 120, 300):
            x = mid[(sec <= k) & (sec >= 0)]
            rec[f"mv{k}"] = (x[-1] - p0) * s if len(x) else np.nan
        first5 = (sec >= 0) & (sec <= 300)
        fm = (mid[first5] - p0) * s
        j = int(np.argmax(fm))
        rec["peak"] = fm[j]
        rec["peak_s"] = sec[first5][j]
        rec["adverse_before_peak"] = -fm[: j + 1].min()
        # the pullback from the peak inside the next 10 minutes and the move at +30/+60/+120 min
        after = (sec > sec[first5][j]) & (sec <= sec[first5][j] + 600)
        rec["pullback10m"] = fm[j] - ((mid[after] - p0) * s).min() if after.any() else np.nan
        for k in (15, 30, 60, 120):
            x = mid[sec <= k * 60]
            rec[f"m{k}min"] = (x[-1] - p0) * s
        rows.append(rec)
    d = pd.DataFrame(rows)
    sp = pd.DataFrame(spread_rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print("== spread (USD) and tick rate around the release, median over releases 2025-10 .. 2026-02")
    order = sp.bucket.unique()
    print(sp.groupby("bucket").agg(spread=("spread", "median"), spread_max=("spread_max", "median"),
                                   spread_max_p90=("spread_max", lambda v: v.quantile(0.9)),
                                   tps=("ticks_per_s", "median")).reindex(order).round(2).to_string())
    print("\n== per release: first impulse (USD, signed by the +60 s move)")
    d["ev"] = d.event.str.split("+").str[0]
    print(d.drop(columns=["side"]).round(2).to_string())
    print("\n== medians by event")
    print(d.groupby("ev").median(numeric_only=True).round(2).to_string())
    d.to_parquet("research/2026-10-18-moments/agents/news/ticks_first.parquet")


if __name__ == "__main__":
    main()
