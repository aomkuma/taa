"""Agent "cross", step 1: lead-lag from other markets to gold, design data only (2023-11 .. 2026-02).

At every 5th minute t (decision at the close of bar t): each market's vol-scaled log return over the last L minutes
(closes t-L .. t) against gold's vol-scaled return over the next H minutes (close t .. close t+H). Correlation x100
by half-year, all hours and by session; also the partial effect after gold's own last L minutes (OLS on both).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/measure.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

PANEL = "research/2026-10-18-moments/agents/cross/panel.parquet"
HALVES = [("23-11", "2023-11-01", "2024-05-01"), ("24-05", "2024-05-01", "2024-11-01"),
          ("24-11", "2024-11-01", "2025-05-01"), ("25-05", "2025-05-01", "2025-11-01"),
          ("25-11", "2025-11-01", "2026-03-01")]
MARKETS = ["US500", "US100", "US30", "JP225", "USD", "AUDJPY", "USDJPY", "EURUSD", "AUDUSD", "gc"]
LS, HS = (5, 15, 30, 60), (15, 30, 60, 120)
SESS = {"asia 00-07": (0, 7), "london 07-12": (7, 12), "ny 12-17": (12, 17), "late 17-24": (17, 24)}


def logp(p: pd.DataFrame, k: str) -> np.ndarray:
    return p[k].to_numpy(float) if k == "USD" else np.log(p[k].to_numpy(float))


def scaled_returns(p: pd.DataFrame, k: str, n: int, sign: int, t_ns: np.ndarray) -> np.ndarray:
    """Return over n rows (backward for sign -1 i.e. x[t]-x[t-n]; forward for +1 x[t+n]-x[t]), NaN where the
    rows do not span exactly n minutes; divided by the 1-minute std of the previous 1440 rows x sqrt(n)."""
    x = logp(p, k)
    r1 = pd.Series(np.diff(x, prepend=np.nan))
    sd = r1.rolling(1440, min_periods=600).std().shift(1).to_numpy()
    out = np.full(len(x), np.nan)
    span = np.int64(n * 60_000_000_000)
    if sign < 0:
        ok = np.zeros(len(x), bool)
        ok[n:] = (t_ns[n:] - t_ns[:-n]) == span
        out[n:] = x[n:] - x[:-n]
    else:
        ok = np.zeros(len(x), bool)
        ok[:-n] = (t_ns[n:] - t_ns[:-n]) == span
        out[:-n] = x[n:] - x[:-n]
    out[~ok] = np.nan
    return np.clip(out / (sd * np.sqrt(n)), -6, 6)


def main() -> None:
    gold.below_normal_priority()
    p = pd.read_parquet(PANEL)
    t_ns = p.index.asi8.astype(np.int64)
    if p.index.dtype.unit != "ns":
        t_ns = p.index.as_unit("ns").asi8
    feats = {(k, L): scaled_returns(p, k, L, -1, t_ns) for k in MARKETS for L in LS}
    targ = {H: scaled_returns(p, "gc", H, +1, t_ns) for H in HS}
    hour = p.index.hour.to_numpy()
    keep = (p.index.minute.to_numpy() % 5) == 0
    halves = [(n, (p.index >= pd.Timestamp(a, tz="UTC")) & (p.index < pd.Timestamp(b, tz="UTC"))) for n, a, b in HALVES]

    def corr(x: np.ndarray, y: np.ndarray, m: np.ndarray) -> float:
        ok = m & np.isfinite(x) & np.isfinite(y)
        return 100 * np.corrcoef(x[ok], y[ok])[0, 1] if ok.sum() > 200 else np.nan

    def partial(x: np.ndarray, g: np.ndarray, y: np.ndarray, m: np.ndarray) -> float:
        ok = m & np.isfinite(x) & np.isfinite(y) & np.isfinite(g)
        if ok.sum() < 200:
            return np.nan
        A = np.column_stack([x[ok], g[ok], np.ones(ok.sum())])
        b = np.linalg.lstsq(A, y[ok], rcond=None)[0]
        return 100 * b[0]

    print("corr x100 (market's last L min -> gold's next H min), five design halves | partial beta x100 after gold's own L")
    for sname, (h0, h1) in [("ALL HOURS", (0, 24)), *SESS.items()]:
        sm = keep & (hour >= h0) & (hour < h1)
        print(f"\n=== {sname}")
        for k in MARKETS:
            for L in LS:
                for H in HS:
                    cs = [corr(feats[(k, L)], targ[H], sm & hm) for _n, hm in halves]
                    ps = [partial(feats[(k, L)], feats[("gc", L)], targ[H], sm & hm) for _n, hm in halves] if k != "gc" else cs
                    same = max(sum(c > 0 for c in cs), sum(c < 0 for c in cs))
                    flag = " <<" if same == 5 and abs(np.mean(cs)) >= 2 else ""
                    print(f"  {k:6} L{L:<3} H{H:<4} corr " + " ".join(f"{c:+5.1f}" for c in cs)
                          + f" | mean {np.mean(cs):+5.1f} same {same}/5 | partial " + " ".join(f"{c:+5.1f}" for c in ps) + flag)
    # contemporaneous check (sanity): gold vs dollar / indices in the same 15 minutes
    print("\nsanity, same-minute co-movement (corr x100 of 15-min returns, all hours):")
    g15 = feats[("gc", 15)]
    for k in MARKETS[:-1]:
        print(f"  {k:6} " + " ".join(f"{corr(feats[(k, 15)], g15, keep & hm):+5.1f}" for _n, hm in halves))


if __name__ == "__main__":
    main()
