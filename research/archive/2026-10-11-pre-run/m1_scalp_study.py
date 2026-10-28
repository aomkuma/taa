"""M1 scalping: how price behaves after an M1 break, inside an H1 + M15 trend (owner, 2026-10-14: "scalping
needs M1"; theory a third, measured behaviour the rest).

Definitions (fixed before the run):

- **trend**: the H1 and the M15 market-map states (``state_frame``, default parameters) agree, UP or DOWN, at the
  last bar closed before the event;
- **events**: the first M1 close beyond the previous 20 M1 bars' high/low, weekdays 07:00-20:00 UTC:
  ``counter`` = a break against the trend (the setup trades it *with* the trend, i.e. fades the break),
  ``with`` = a break in the trend's direction (traded with it, i.e. follows the break);
- **scale**: ATR over 60 M1 bars (one hour) at the event, ``A``; the entry is the break bar's close plus the spread
  for a BUY;
- **outcomes** on the following M1 bars (a bar touching both levels counts the stop): for each stop ``S`` and target
  ``T`` (in A) and a time stop (30 / 60 min, closed at the bar's close), the result in R net of the spread at the
  entry; plus the best excursion with the trade (MFE) and against it (MAE) within 5 / 15 / 30 / 60 minutes;
- **spread**: the bar's spread, at least the owner's account spread (gold 30, currencies 10 points);
- **halves**: before / from 2026-04-09; the stop/target/time stop is **chosen on the first half and judged on
  the second** (walk-forward); reported per symbol and per New York time bucket.

    .venv/Scripts/python research/2026-10-11-pre-run/m1_scalp_study.py [XAUUSD USDJPY]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.indicators.market_map import MapParams, state_frame

HIST = Path("data/history/FBS-Demo")
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")
# the owner's account (2026-10-14): spreads about 30 points on gold, 10 on currencies; never cheaper
SPREAD_FLOOR = {"XAUUSD": 30.0}
SPREAD_FLOOR_DEFAULT = 10.0
NY = ZoneInfo("America/New_York")
STOPS = (1.0, 1.5, 2.0, 3.0)
TARGETS = (0.5, 1.0, 1.5, 2.0, 3.0)
TIME_STOPS = (30, 60)
HORIZONS = (5, 15, 30, 60)


def load(symbol: str, tf: str) -> pd.DataFrame:
    d = pd.read_parquet(HIST / symbol / f"{tf}.parquet").sort_values("close_time")
    d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    return d


def ny_bucket(t: pd.Timestamp) -> str:
    m = t.tz_convert(NY).hour * 60 + t.tz_convert(NY).minute
    if 2 * 60 <= m < 8 * 60:
        return "london"
    if 8 * 60 <= m < 9 * 60 + 30:
        return "pre_ny"
    if 9 * 60 + 30 <= m < 12 * 60:
        return "ny_open"
    if 12 * 60 <= m < 17 * 60:
        return "ny_late"
    return "other"


def resolve(hi: np.ndarray, lo: np.ndarray, cl: np.ndarray, sign: int, entry: float, stop: float, tp: float) -> float:
    risk = abs(entry - stop)
    for h, low in zip(hi, lo, strict=True):
        if ((low if sign > 0 else h) - stop) * sign <= 0:
            return -1.0
        if ((h if sign > 0 else low) - tp) * sign >= 0:
            return (tp - entry) * sign / risk
    return (cl[-1] - entry) * sign / risk if len(cl) else 0.0


def study(symbol: str) -> pd.DataFrame:
    point = json.loads((HIST / symbol / "spec.json").read_text(encoding="utf-8"))["spec"]["point"]
    m1 = load(symbol, "M1")
    states = {tf: state_frame(load(symbol, tf), MapParams())["state"] for tf in ("H1", "M15")}
    pc = m1["close"].shift(1)
    tr = pd.concat([m1["high"] - m1["low"], (m1["high"] - pc).abs(), (m1["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(60).mean().to_numpy()
    hh = m1["high"].rolling(20).max().shift(1)
    ll = m1["low"].rolling(20).min().shift(1)
    c = m1["close"]
    up = ((c > hh) & (c.shift(1) <= hh.shift(1))).to_numpy()
    dn = ((c < ll) & (c.shift(1) >= ll.shift(1))).to_numpy()
    t = m1.index
    hi, lo, cl = (m1[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    floor = SPREAD_FLOOR.get(symbol, SPREAD_FLOOR_DEFAULT)
    sp = np.maximum(m1["spread"].to_numpy(dtype=float), floor) * point
    rows = []
    for i in np.flatnonzero(up | dn):
        at = t[i]
        if at.weekday() >= 5 or not 7 <= at.hour < 20 or not np.isfinite(atr[i]) or i + 61 >= len(t):
            continue
        st = []
        for tf in ("H1", "M15"):
            s = states[tf]
            j = s.index.searchsorted(at, side="right") - 1
            st.append(s.iloc[j] if j >= 0 else "UNKNOWN")
        if st[0] != st[1] or st[0] not in ("UP", "DOWN"):
            continue
        trend = 1 if st[0] == "UP" else -1
        brk = 1 if up[i] else -1
        kind = "counter" if brk != trend else "with"
        sign = trend  # always traded with the trend: a counter break is faded, a with break is followed
        a = atr[i]
        entry = cl[i] + (sp[i] if sign > 0 else 0.0)
        row = {"symbol": symbol, "at": at, "kind": kind, "bucket": ny_bucket(at), "A": a, "spread_A": sp[i] / a}
        for h in HORIZONS:
            seg_hi, seg_lo = hi[i + 1 : i + 1 + h], lo[i + 1 : i + 1 + h]
            fav = (seg_hi.max() - entry) if sign > 0 else (entry - seg_lo.min())
            adv = (entry - seg_lo.min()) if sign > 0 else (seg_hi.max() - entry)
            row[f"mfe{h}"] = fav / a
            row[f"mae{h}"] = adv / a
        for ts in TIME_STOPS:
            seg = slice(i + 1, i + 1 + ts)
            for s_ in STOPS:
                for t_ in TARGETS:
                    stop = entry - sign * s_ * a
                    tp = entry + sign * t_ * a
                    row[f"r_{s_}_{t_}_{ts}"] = resolve(hi[seg], lo[seg], cl[seg], sign, entry, stop, tp)
        rows.append(row)
    return pd.DataFrame(rows)


def main(symbols: list[str]) -> None:
    t = pd.concat([study(s) for s in symbols], ignore_index=True)
    t["half"] = np.where(t["at"] < SPLIT, "1st", "2nd")
    print(f"=== M1 breaks inside an H1+M15 trend, weekdays 07-20 UTC: {len(t)} events ===")
    print(t.groupby(["symbol", "kind"]).size().unstack().to_string())
    print("\nexcursions in ATR(60 M1) after the event, traded with the trend (median MFE / MAE):")
    for (sym, kind), g in t.groupby(["symbol", "kind"]):
        print(f"  {sym} {kind:7} " + "  ".join(f"{h}m {g[f'mfe{h}'].median():.2f}/{g[f'mae{h}'].median():.2f}" for h in HORIZONS))
    cols = [c for c in t.columns if c.startswith("r_")]
    for (sym, kind), g in t.groupby(["symbol", "kind"]):
        res = []
        for c in cols:
            h1, h2 = g.loc[g.half == "1st", c].mean(), g.loc[g.half == "2nd", c].mean()
            res.append((c, g[c].mean(), h1, h2, len(g)))
        chosen = max(res, key=lambda x: x[2])
        _, cs, ct, cts = chosen[0].split("_")
        print(
            f"\n{sym} {kind}: WALK-FORWARD, chosen on the 1st half: stop {cs} A, target {ct} A, time stop {cts} m:"
            f"  1st {chosen[2]:+.3f} -> 2nd (unseen) {chosen[3]:+.3f}  (n={chosen[4]})"
        )
        print("  by NY time, 2nd half: " + "  ".join(
            f"{b} {x.loc[x.half == '2nd', chosen[0]].mean():+.2f} (n={int((x.half == '2nd').sum())})"
            for b, x in g.groupby("bucket")))
        res.sort(key=lambda x: -x[1])
        print(f"\n{sym} {kind}: best stop/target/time-stop (R per trade net of the spread; both halves)")
        for c, m, h1, h2, n in res[:8]:
            _, s_, t_, ts = c.split("_")
            print(f"  stop {s_} A, target {t_} A, time stop {ts} m:  {m:+.3f}  halves {h1:+.3f} / {h2:+.3f}  n={n}")
        best = res[0][0]
        print("  by NY time (best combination): " + "  ".join(f"{b} {x[best].mean():+.2f} (n={len(x)})" for b, x in g.groupby("bucket")))


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "USDJPY"])
