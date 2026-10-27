"""How deep a pullback goes, by the momentum of the leg before it (owner 2026-10-27: "it depends on the
direction you measure and the momentum in the big picture - weak momentum, it pulls back deep and bounces
high; a clear trend with momentum, and it is neither deep nor high").

Every ZigZag leg A -> B on H1 (MetaTrader 5's 12/5/3) over the 12 months to 2026-10-23, with three readings of
the leg's momentum taken at B, from closed bars only:

- **straightness**: |B - A| divided by the sum of the bar-to-bar closes along the leg - 1.0 is a straight run,
  low is a grind;
- **speed**: |B - A| in ATR(14) at B, divided by the bars the leg took;
- **H4 agrees**: the H4 ZigZag steps the same way as this leg.

Then the counter swing B -> C as a share of the leg, split by each reading. If the owner is right, the strong
buckets pull back less.

    .venv/Scripts/python research/2026-10-26-three-bots/momentum_depth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bots  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.zigzag import zigzag  # noqa: E402

START, END = pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-10-24", tz="UTC")


def atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, i: int, n: int = 14) -> float:
    s = max(0, i - n + 1)
    prev = np.concatenate([[c[s]], c[s:i]])
    tr = np.maximum(h[s : i + 1] - lo[s : i + 1], np.maximum(abs(h[s : i + 1] - prev), abs(lo[s : i + 1] - prev)))
    return float(tr.mean()) if len(tr) else 0.0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    h1 = to_frame(hs.load("FBS-Demo", "XAUUSD", Timeframe.H1, None, None))
    h1 = h1[(h1.index >= START - pd.Timedelta(days=90)) & (h1.index < END)]
    h4 = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    hh, ll, cc = (h1[k].to_numpy(float) for k in ("high", "low", "close"))
    sw, _ = zigzag(hh, ll)
    sw4, _ = zigzag(h4.high.to_numpy(float), h4.low.to_numpy(float))
    # the H4 direction at each H1 bar time: the last confirmed H4 pair before it
    h4_dir = []
    for s in sw4:
        h4_dir.append((h4.index[s.bar], s))
    rows = []
    for j in range(1, len(sw) - 1):
        a, b, c = sw[j - 1], sw[j], sw[j + 1]
        leg = abs(b.price - a.price)
        if leg <= 0 or b.bar <= a.bar:
            continue
        path = float(np.abs(np.diff(cc[a.bar : b.bar + 1])).sum())
        straight = leg / path if path > 0 else 0.0
        at = atr(hh, ll, cc, b.bar)
        speed = (leg / at / (b.bar - a.bar)) if at > 0 and b.bar > a.bar else 0.0
        t = h1.index[b.bar]
        past4 = [s for ts, s in h4_dir if ts + pd.Timedelta(hours=4) <= t]
        agree = False
        if len(past4) >= 4:
            h4h = [s.price for s in past4 if s.kind == 1][-2:]
            h4l = [s.price for s in past4 if s.kind == -1][-2:]
            if len(h4h) == 2 and len(h4l) == 2:
                down4 = h4h[1] < h4h[0] and h4l[1] < h4l[0]
                up4 = h4h[1] > h4h[0] and h4l[1] > h4l[0]
                agree = (down4 if b.kind == -1 else up4)
        if t < START:
            continue
        rows.append({"depth": abs(c.price - b.price) / leg * 100, "straight": straight,
                     "speed": speed, "agree": agree, "leg": leg})  # fmt: skip
    d = pd.DataFrame(rows)
    print(f"== {len(d)} H1 legs, {START.date()} .. {END.date()}; median leg {d.leg.median():.1f} USD ==")
    for name in ("straight", "speed"):
        q = d[name].quantile([1 / 3, 2 / 3]).tolist()
        d[name + "_b"] = pd.cut(d[name], [-1, q[0], q[1], 1e9], labels=["weak", "middle", "strong"])
        print(f"\n| leg {name} | legs | median pullback % | under 50 % | over 78.6 % | over 100 % |")
        print("|---|---|---|---|---|---|")
        for lab in ("weak", "middle", "strong"):
            g = d[d[name + "_b"] == lab]
            if not len(g):
                continue
            print(f"| {lab} | {len(g)} | {g.depth.median():.0f} | {(g.depth < 50).mean():.0%} | "
                  f"{(g.depth > 78.6).mean():.0%} | {(g.depth > 100).mean():.0%} |")
    print("\n| H4 steps the leg's way | legs | median pullback % | under 50 % | over 78.6 % | over 100 % |")
    print("|---|---|---|---|---|---|")
    for lab, g in d.groupby("agree"):
        print(f"| {'yes' if lab else 'no'} | {len(g)} | {g.depth.median():.0f} | {(g.depth < 50).mean():.0%} | "
              f"{(g.depth > 78.6).mean():.0%} | {(g.depth > 100).mean():.0%} |")


if __name__ == "__main__":
    main()
