"""The owner's M15 rhythm (2026-10-23): "it depends on the timeframe you look at - on M15, sell with the rhythm and you
profit; take the profit and leave; when the market grows unsure, wait. It cannot lose with every move."

Rules fixed before the run (the bot's code only):
- the big picture: H1 AND H4 trend (app/strategy/big_trend.py) both down -> sells only; both up -> buys only;
  otherwise wait;
- the rhythm on M15: a ZigZag sized 1.5 x the M15 ATR(14); when a pullback high is confirmed (price fell the size
  from it) -> sell at that bar's close (mirror for buys);
- the stop 0.1 M15 ATR above the pullback high; the target the last M15 swing low before it (take it and leave);
  out after 16 M15 bars; the stop first when a bar holds both; 0.35 USD spread;
- one trade at a time.
Every signal of the period is listed.

    .venv/Scripts/python research/2026-10-23-entry/rhythm_sell.py 2026-10-19 2026-10-24
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from candidates import FRAMES, frame, window  # noqa: E402

from app.strategy import big_trend as bt  # noqa: E402
from app.strategy.plan1_b2 import mt5_atr  # noqa: E402

SIZE, PAD, HOLD, SPREAD = 1.5, 0.1, 16, 0.35
TH = "Asia/Bangkok"


def main() -> None:
    a, b = pd.Timestamp(sys.argv[1], tz="UTC"), pd.Timestamp(sys.argv[2], tz="UTC")
    data = {tf: frame(tf) for tf in FRAMES}
    m, M = data["M15"]
    atr = mt5_atr(M.h, M.lo, M.c, 14)
    i0, i1 = int(np.searchsorted(M.t_open, a.value)), int(np.searchsorted(M.t_open, b.value))
    rows, busy_until = [], -1
    for i in range(i0, min(i1, len(M.c) - 1)):
        t = int(M.avail[i])
        w = slice(max(0, i - 200), i + 1)
        size = SIZE * float(atr[i])
        pts, leg, _ = bt.zigzag(M.h[w], M.lo[w], size)
        if not pts or pts[-1][0] + w.start != _last_confirm(M, w, pts, size, i):
            continue
        k, piv_price = pts[-1][1], pts[-1][2]
        side = -1 if k == 1 else 1  # a confirmed high -> sell; a confirmed low -> buy
        h1 = bt.big_trend(window(data["H1"][1], t, 600), t).sign
        h4 = bt.big_trend(window(data["H4"][1], t, 600), t).sign
        if i <= busy_until:
            continue
        if not (h1 == side and h4 == side):
            rows.append(dict(t=t, side=side, taken=False, why=f"wait: H1 {h1:+d} / H4 {h4:+d}"))
            continue
        prev = [p for _, kk, p in pts[:-1] if kk == -k]
        if not prev:
            continue
        entry = float(M.c[i]) - side * SPREAD / 2
        stop = piv_price + PAD * float(atr[i]) if side < 0 else piv_price - PAD * float(atr[i])
        target = prev[-1]
        risk = abs(entry - stop)
        if (target - entry) * side <= 0 or risk <= 0:
            rows.append(dict(t=t, side=side, taken=False, why="no room to the last swing"))
            continue
        out, how = None, "time"
        for j in range(i + 1, min(i + 1 + HOLD, len(M.c))):
            if (M.h[j] >= stop) if side < 0 else (M.lo[j] <= stop):
                out, how = stop, "stop"
                break
            if (M.lo[j] <= target) if side < 0 else (M.h[j] >= target):
                out, how = target, "target"
                break
        if out is None:
            j = min(i + HOLD, len(M.c) - 1)
            out = float(M.c[j])
        busy_until = j
        r = (out - entry) * side / risk - SPREAD / 2 / risk
        rows.append(dict(t=t, side=side, taken=True, entry=entry, stop=stop, target=target, out=out, how=how, r=r,
                         usd=(out - entry) * side - SPREAD / 2, why=f"H1 {h1:+d} / H4 {h4:+d}"))
    R = pd.DataFrame(rows)
    for r in R.itertuples():
        th = pd.Timestamp(r.t, tz="UTC").tz_convert(TH)
        if r.taken:
            print(f"{th:%a %d %H:%M} {'SELL' if r.side < 0 else 'BUY '} {r.entry:.2f} stop {r.stop:.2f} target {r.target:.2f} -> "
                  f"{r.how} {r.out:.2f}: {r.r:+.2f} R ({r.usd:+.2f} USD a 1-oz unit)  [{r.why}]")
        else:
            print(f"{th:%a %d %H:%M} {'sell' if r.side < 0 else 'buy '} signal - {r.why}")
    T = R[R.taken]
    if len(T):
        print(f"\ntaken {len(T)}: {T.r.sum():+.2f} R, {T.r.mean():+.3f} a trade, won {(T.r > 0).mean() * 100:.0f} %; waited {(~R.taken).sum()}")


def _last_confirm(M, w, pts, size, i):
    """The bar index (in M) where the last pivot was confirmed: the first bar after it moving ``size`` away."""
    j0, k, p = pts[-1]
    j0 += w.start
    for j in range(j0 + 1, i + 1):
        if (p - M.lo[j] >= size) if k == 1 else (M.h[j] - p >= size):
            return j0 if j == i else -1
    return -1


if __name__ == "__main__":
    main()
