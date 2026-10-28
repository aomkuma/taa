"""Second-level features from gold's ticks (data/ticks/XAUUSD, download_ticks.py) at each candidate minute of
ml_dataset.py (the decision at the minute's start, ticks strictly before it): tick intensity, the up/down tick
imbalance, micro returns, spread widening, the last tick's age.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/tick_features.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SRC = "data/research/own_ml.parquet"
OUT = "data/research/own_ml_ticks.parquet"
TICKS = Path("data/ticks/XAUUSD")
NS = 1_000_000_000


def day_ticks(day: pd.Timestamp) -> pd.DataFrame | None:
    parts = []
    for d in (day - pd.Timedelta(days=1), day):  # the previous day too, for the hour before 00:00 UTC
        p = TICKS / f"{d:%Y-%m-%d}.parquet"
        if p.exists():
            parts.append(pd.read_parquet(p))
    if not parts:
        return None
    x = pd.concat(parts, ignore_index=True)
    return x if len(x) else None


def main() -> None:
    d = pd.read_parquet(SRC, columns=["t"])
    t_all = pd.to_datetime(d.t.drop_duplicates(), utc=True).sort_values()
    rows = []
    for day, ts in t_all.groupby(t_all.dt.normalize()):
        x = day_ticks(day)
        if x is None:
            continue
        tt = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
        order = np.argsort(tt, kind="stable")
        tt = tt[order]
        bid, ask = x.bid.to_numpy(float)[order], x.ask.to_numpy(float)[order]
        mid, spr = (bid + ask) / 2, ask - bid
        dm = np.r_[0.0, np.diff(mid)]
        up_c, dn_c = np.cumsum(dm > 0), np.cumsum(dm < 0)
        for t in ts:
            t0 = t.as_unit("ns").value
            i = int(np.searchsorted(tt, t0, side="left"))  # ticks before t: [0, i)
            if i < 50:
                continue

            def at(sec: float) -> int:
                return int(np.searchsorted(tt, t0 - int(sec * NS), side="left"))

            j10, j60, j3600 = at(10), at(60), at(3600)
            n60 = i - j60
            rate_h = (i - j3600) / 60.0
            rec = {
                "t": t,
                "tk_n10": i - j10,
                "tk_n60": n60,
                "tk_rate_rel": n60 / max(rate_h, 1.0),
                "tk_age": (t0 - tt[i - 1]) / NS,
                "tk_imb60": ((up_c[i - 1] - up_c[max(j60 - 1, 0)]) - (dn_c[i - 1] - dn_c[max(j60 - 1, 0)])) / max(n60, 1),
                "tk_spr60": float(spr[j60:i].mean()) if n60 else np.nan,
                "tk_spr_rel": float(spr[j60:i].mean() / spr[j3600:i].mean()) if n60 and i > j3600 else np.nan,
                "tk_spr_max60": float(spr[j60:i].max()) if n60 else np.nan,
            }
            for sec in (5, 15, 30, 60):
                j = at(sec)
                rec[f"tk_ret{sec}"] = mid[i - 1] - (mid[j - 1] if j > 0 else mid[0])
            rec["tk_vol60"] = float(np.abs(dm[j60:i]).sum()) if n60 else 0.0
            rec["tk_pos60"] = (
                (mid[i - 1] - mid[j60:i].min()) / max(mid[j60:i].max() - mid[j60:i].min(), 1e-9) if n60 else 0.5
            )
            rows.append(rec)
        print(f"{day:%Y-%m-%d}: {len(ts)} minutes", flush=True) if day.day == 1 else None
    f = pd.DataFrame(rows)
    f.to_parquet(OUT)
    print(f.shape)
    print(f.describe().T[["mean", "50%", "max"]].round(3).to_string())


if __name__ == "__main__":
    main()
