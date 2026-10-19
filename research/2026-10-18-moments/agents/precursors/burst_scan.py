"""The moments gold runs far in a few minutes (owner, 2026-10-19: "from the pictures I sent - moments like this happen
many times a day, it runs far in a few minutes; we have to find that moment"). On M1: a burst starts at the open of
bar i when within the next N minutes price goes X USD one way while going less than Q against first (a clean run).
Consecutive starts of the same way are one burst (its first minute). Per day and hour, and what was there just before
each: the last 30 minutes' range in M15 ATRs (a squeeze), the last 5 minutes' volume against the same minutes, the place
in the M30 range, the D1 way. Description only - the trades are judged later on moments taken by the clock.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/burst_scan.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

N_MIN, X_USD, Q_USD = 5, 10.0, 3.0


def bursts(o: np.ndarray, h: np.ndarray, lo: np.ndarray, n: int = N_MIN, x: float = X_USD, q: float = Q_USD) -> pd.DataFrame:
    """Every bar i whose open is followed, within bars i .. i+n-1, by x its way before q against (both judged on the
    running extremes bar by bar: the bar reaching x must come before any bar reaching q against; a bar reaching both:
    not clean). Returns the first bar of each run of consecutive same-way starts."""
    m = len(o)
    side = np.zeros(m, int)
    for way in (1, -1):
        hit = np.full(m, n)
        bad = np.full(m, n)
        for k in range(n):
            idx = np.minimum(np.arange(m) + k, m - 1)
            ok = np.arange(m) + k < m
            fav = (h[idx] - o) if way > 0 else (o - lo[idx])
            adv = (o - lo[idx]) if way > 0 else (h[idx] - o)
            hit = np.where((hit == n) & ok & (fav >= x), k, hit)
            bad = np.where((bad == n) & ok & (adv >= q), k, bad)
        clean = (hit < n) & (hit < bad)
        side = np.where(clean & (side == 0), way, side)
    start = (side != 0) & ~((np.r_[0, side[:-1]] == side) & (side != 0))
    i = np.nonzero(start)[0]
    return pd.DataFrame({"i": i, "side": side[i]})


def main() -> None:
    import foundation as F  # noqa: PLC0415
    import plib  # noqa: PLC0415

    from indicators import at, bars  # noqa: PLC0415

    m = plib.load()
    o, h, lo, c, v = (m[k].to_numpy(float) for k in ("open", "high", "low", "close", "tick_volume"))
    B = bursts(o, h, lo)
    t = m.index[B.i.to_numpy()]
    B["t"] = t
    B["part"] = np.where(t >= pd.Timestamp("2026-04-18", tz="UTC"), "exam", np.where(t >= pd.Timestamp("2025-10-18", tz="UTC"), "latest learning", "older"))
    th = t.tz_convert("Asia/Bangkok")
    B["hour_th"] = th.hour
    days = {p: np.busday_count(a, b) for p, (a, b) in {"older": ("2023-08-01", "2025-10-18"), "latest learning": ("2025-10-18", "2026-04-18"),
                                                        "exam": ("2026-04-18", "2026-10-17")}.items()}
    print(f"bursts: {X_USD:g} USD within {N_MIN} minutes, less than {Q_USD:g} against first")
    for p, d in days.items():
        b = B[B.part == p]
        print(f"  {p}: {len(b)} ({len(b) / d:.1f} a weekday), up {int((b.side > 0).sum())} / down {int((b.side < 0).sum())}")
    L = B[B.part == "latest learning"]
    print("\nthe latest learning months, by the Thai hour (bursts a weekday):")
    print((L.groupby("hour_th").size() / days["latest learning"]).round(2).to_string())
    # what was there just before each burst (closed bars only), against the same readings at every M1 bar of those months
    t_ns = m.index.as_unit("ns").asi8
    m15 = bars(m, "15min")
    a15 = F.atr(m15.high.to_numpy(), m15.low.to_numpy(), m15.close.to_numpy(), 14)
    b15 = at(pd.DatetimeIndex(m15["avail"]).as_unit("ns").asi8, t_ns)
    rng30 = (pd.Series(h).rolling(30).max() - pd.Series(lo).rolling(30).min()).shift(1).to_numpy() / np.where(b15 >= 0, a15[np.maximum(b15, 0)], np.nan)
    v5 = pd.Series(v).rolling(5).sum().shift(1)
    key = m.index.hour * 60 + m.index.minute
    med = v5.groupby(key).transform(lambda s: s.shift(1).rolling(20, min_periods=10).median())
    vol_rel = (v5 / med).to_numpy()
    R = pd.DataFrame({"squeeze30": rng30, "vol5": vol_rel})
    lm = (m.index >= pd.Timestamp("2025-10-18", tz="UTC")) & (m.index < pd.Timestamp("2026-04-18", tz="UTC"))
    pre = R.iloc[L.i.to_numpy()]
    allm = R[lm]
    print("\njust before the bursts vs every minute (latest learning months), median [quartiles]:")
    for col in R.columns:
        q1 = pre[col].quantile([0.25, 0.5, 0.75]).round(2).tolist()
        q2 = allm[col].quantile([0.25, 0.5, 0.75]).round(2).tolist()
        print(f"  {col:10s} bursts {q1}   every minute {q2}")
    B.to_parquet(HERE / "bursts.parquet")


if __name__ == "__main__":
    main()
