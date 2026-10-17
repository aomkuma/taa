"""What makes a TS trade go the wrong way, read from gold's own behaviour rather than from textbook context (owner,
2026-10-17: "find what really makes it go wrong; too much theory, not enough of the symbol's habits").

For every structure-break trigger of the given outcomes file(s) (ts_study.py output): the day-trade plan's result
(stop 0.25 ATR beyond the pullback extreme, 2 R, at most 12 h) and its class (target / time exit / stopped and then
"too early / noise", "half right" or "wrong direction", ts_losers.path), plus behaviour at the entry:

- ``ny_hour``: the New York hour (US data at 08:30 / 10:00 NY); ``dow``: the weekday;
- ``bar_atr``: the trigger bar's range in ATR; ``close_loc``: where it closed in its range, the trade's way (1 = at
  the extreme the trade wants);
- ``run4`` / ``run16``: the move into the entry over the last 4 / 16 M15 bars in ATR, the trade's way;
- ``day_pos``: the entry within the broker day's range so far, the trade's way (1 = at the day's extreme the
  trade wants, i.e. a buy at the day's high);
- ``pdx_room``: the room to the previous day's high (a buy) / low (a sell) in ATR (negative: already beyond it);
- ``r50_room``: the room to the next 50.00 round number ahead in ATR;
- ``atr_ratio``: the entry ATR against its median of the last 20 days (volatility regime).

Writes <first file's folder>/behaviour.csv and prints, per feature bin: n, R/trade, the wrong-way share and R per
half-year. usage: python ts_behaviour.py <outcomes.csv> [<outcomes.csv> ...]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
files = sys.argv[1:]
sys.argv = ["x", files[0].replace("outcomes.csv", "triggers.csv")]
__file__ = str(ROOT / "research/2026-10-17-ts/ts_study.py")
exec(compile(open(__file__, encoding="utf-8").read().split("def hour_bucket")[0], "study", "exec"))  # outcome()
src = open(ROOT / "research/2026-10-17-ts/ts_losers.py", encoding="utf-8").read()
exec(compile(src.split("def from_study")[0], "losers", "exec"))  # path(), M1 arrays

d = pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in files], ignore_index=True).sort_values("time")
d = d.reset_index(drop=True)
m15 = pd.read_parquet(ROOT / "data/history/FBS-Demo/XAUUSD/M15.parquet").sort_values("close_time").reset_index(drop=True)
d1 = pd.read_parquet(ROOT / "data/history/FBS-Demo/XAUUSD/D1.parquet").sort_values("open_time").reset_index(drop=True)
ct = m15.close_time.to_numpy(dtype="datetime64[ns]")
H, L, C = (m15[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
d1_open = d1.open_time.to_numpy(dtype="datetime64[ns]")
tr = np.maximum(H[1:] - L[1:], np.maximum(np.abs(H[1:] - C[:-1]), np.abs(L[1:] - C[:-1])))
atr_s = pd.Series(np.r_[np.nan, tr]).ewm(alpha=1 / 14, adjust=False).mean()
atr_med = atr_s.rolling(20 * 92, min_periods=200).median().to_numpy()  # ~20 trading days of M15 bars

rows = []
for r in d.itertuples():
    t = np.datetime64(r.time.tz_convert(None))
    i = int(np.searchsorted(ct, t, side="right")) - 1  # the trigger bar (closes at the decision time)
    if i < 20 or ct[i] != t:
        rows.append({})
        continue
    buy = r.side == "BUY"
    sg = 1 if buy else -1
    atr = r.atr
    k = int(np.searchsorted(d1_open, t, side="right")) - 1  # the broker day of the entry
    day_open = d1_open[k]
    j0 = min(int(np.searchsorted(ct, day_open, side="right")), i)  # a bar closing at the day open: itself
    dh, dl = H[j0 : i + 1].max(), L[j0 : i + 1].min()
    pd_hi, pd_lo = float(d1.high.iloc[k - 1]), float(d1.low.iloc[k - 1])
    rng = H[i] - L[i]
    nxt50 = (np.floor(r.close / 50) + 1) * 50 if buy else np.ceil(r.close / 50) * 50 - 50
    rows.append({
        "ny_hour": r.time.tz_convert("America/New_York").hour,
        "dow": r.time.tz_convert("America/New_York").dayofweek,
        "bar_atr": rng / atr,
        "close_loc": ((C[i] - L[i]) / rng if buy else (H[i] - C[i]) / rng) if rng > 0 else np.nan,
        "run4": (C[i] - C[i - 4]) * sg / atr,
        "run16": (C[i] - C[i - 16]) * sg / atr,
        "day_pos": ((C[i] - dl) / (dh - dl) if buy else (dh - C[i]) / (dh - dl)) if dh > dl else np.nan,
        "pdx_room": ((pd_hi - r.close) if buy else (r.close - pd_lo)) / atr,
        "r50_room": abs(nxt50 - r.close) / atr,
        "atr_ratio": atr / atr_med[i] if np.isfinite(atr_med[i]) and atr_med[i] > 0 else np.nan,
    })
b = pd.DataFrame(rows, index=d.index)
d = d.join(b)
spread = d.spread_points.fillna(25.0) * POINT
isbuy = d.side == "BUY"
entry = np.where(isbuy, d.close + spread, d.close)
stop = np.where(isbuy, d["pivot"] - 0.25 * d.atr - spread, d["pivot"] + 0.25 * d.atr + spread)
tp = np.where(isbuy, entry + 2 * np.abs(entry - stop), entry - 2 * np.abs(entry - stop))
d["R"] = [outcome(row, 0.25, 2.0, 0.5) for row in d.itertuples()]
paths = [path(t, s == "BUY", e, st, p) for t, s, e, st, p in zip(d.time, d.side, entry, stop, tp)]
d["cls"] = [p.get("after", p["exit"]) for p in paths]
d["wrong"] = d.cls == "wrong direction"
edges = [pd.Timestamp(x, tz="UTC") for x in ("2023-10-01", "2024-04-01", "2024-10-01", "2025-04-01", "2025-10-01",
                                             "2026-04-01", "2026-10-01")]
d["half"] = pd.cut(d.time, edges, labels=["23H2", "24H1", "24H2", "25H1", "25H2", "26H1"], right=False)
out = Path(files[0]).with_name("behaviour.csv")
d.to_csv(out, index=False)
halves = [h for h in ["23H2", "24H1", "24H2", "25H1", "25H2", "26H1"] if (d.half == h).any()]
print(f"{len(d)} triggers ({', '.join(halves)}): R/trade {d.R.mean():+.3f}, wrong-way {d.wrong.mean():.0%}, "
      f"target {(d.cls == 'TP').mean():.0%}  -> {out}")
BINS = {
    "ny_hour": [-1, 2, 5, 7, 9, 11, 14, 17, 20, 23],
    "dow": [-1, 0, 1, 2, 3, 4],
    "bar_atr": [0, 0.75, 1.25, 2, 3, 99],
    "close_loc": [-0.01, 0.5, 0.75, 0.9, 1.01],
    "run4": [-99, 0, 1, 2, 3, 99],
    "run16": [-99, 0, 2, 4, 6, 99],
    "day_pos": [-0.01, 0.5, 0.8, 0.95, 1.01],
    "pdx_room": [-99, 0, 1, 3, 6, 99],
    "r50_room": [0, 0.5, 1, 2, 99],
    "atr_ratio": [0, 0.8, 1.0, 1.25, 1.6, 99],
}
for col, edges_ in BINS.items():
    print(f"\n{col}: bin n | R/trade | wrong % | R per half " + " ".join(halves))
    for v, g in d.groupby(pd.cut(d[col], edges_), observed=True):
        if len(g) < 40:
            continue
        hs = [g.loc[g.half == h, "R"].mean() for h in halves]
        tag = "  all > 0" if all(x > 0 for x in hs) else ("  all < 0" if all(x < 0 for x in hs) else "")
        print(f"  {str(v):14} {len(g):5d} | {g.R.mean():+.3f} | {g.wrong.mean():4.0%} | "
              + " ".join(f"{x:+.2f}" for x in hs) + tag)
