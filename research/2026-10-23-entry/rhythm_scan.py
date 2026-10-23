"""Every timeframe at this moment - does it have a rhythm? (owner 2026-10-23: "be adaptive and look at every TF - at
this moment, which TF has a rhythm and which does not"). A live read, not a backtest: the bot's code only, bars closed
by AS_OF.

Per frame (M1, M5, M15, H1, H4, D1):
- the trend of the last 500 bars (big_trend: swings of 3 x ATR, the running leg counted);
- the rhythm swings (a ZigZag of 2 x ATR on the last 300 bars): the last swings, each leg in ATR and in bars;
- the rhythm: the last two rhythm highs AND lows lower (down) or higher (up), with the big trend the same way;
- now: the running leg - with the rhythm (a push, late to join) or against it (a pullback: how much of the last push
  it has taken back, the price where the rhythm would resume).

    .venv/Scripts/python research/2026-10-23-entry/rhythm_scan.py [AS_OF_UTC]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import zone_wait as ZW  # noqa: E402

from app.strategy.plan1_b2 import Bars  # noqa: E402
from app.strategy.rhythm import rhythm  # noqa: E402  (TAA-1802: the app's copy is the only one)
from app.strategy.strong_levels import closed  # noqa: E402

TFS = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}
TH = "Asia/Bangkok"


def load(tf: str, as_of: pd.Timestamp) -> Bars:
    """The frame's last 1,300 bars closed by ``as_of``; M5 is built from M1 (the stored M5 starts 2025-10)."""
    if tf == "M5":
        m1 = ZW.load("M1")
        m1 = m1[(m1.index >= as_of - pd.Timedelta(minutes=5 * 1400)) & (m1.index < as_of)]
        d = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    else:
        d = ZW.load(tf)
        d = d[(d.index >= as_of - pd.Timedelta(minutes=TFS[tf] * 2600)) & (d.index < as_of)]
    t = d.index.as_unit("ns").asi8
    return Bars(t, t + TFS[tf] * 60 * 10**9, d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float),
                d.close.to_numpy(float))


def main() -> None:
    as_of = pd.Timestamp(sys.argv[1], tz="UTC") if len(sys.argv) > 1 else pd.Timestamp(ZW.load("M1").index[-1], tz="UTC")
    bars = {tf: load(tf, as_of) for tf in TFS}
    t = as_of.value
    print(f"# Every timeframe at {as_of.tz_convert(TH):%a %d %b %H:%M} Thai\n")
    for tf, b in bars.items():
        x = closed(b, t)
        r = rhythm(x, t)
        sign, atr, pts, big = r.sign, r.atr, r.swings, r.big
        highs = [p for _, k, p in pts if k == 1][-3:]
        lows = [p for _, k, p in pts if k == -1][-3:]
        down = len(highs) >= 2 and len(lows) >= 2 and highs[-1] < highs[-2] and lows[-1] < lows[-2]
        up = len(highs) >= 2 and len(lows) >= 2 and highs[-1] > highs[-2] and lows[-1] > lows[-2]
        name = "DOWN" if sign < 0 else "UP" if sign > 0 else "down (big trend not)" if down else \
            "up (big trend not)" if up else "none"
        price = float(x.c[-1])
        last = pts[-1] if pts else None
        line = f"{tf:3s} ATR {atr:6.2f} | big trend {'DOWN' if big.sign < 0 else 'UP' if big.sign > 0 else 'none'} " \
               f"(LH {big.lower_highs}, LL {big.lower_lows}, HH {big.higher_highs}, HL {big.higher_lows}) | rhythm {name}"
        print(line)
        if pts:
            legs = [(pts[k][2], pts[k + 1][2], pts[k + 1][0] - pts[k][0]) for k in range(max(0, len(pts) - 4), len(pts) - 1)]
            seq = ", ".join(f"{'H' if kk == 1 else 'L'} {p:.1f}" for _, kk, p in pts[-5:])
            print(f"    swings: {seq}; legs {', '.join(f'{abs(b2 - a2) / atr:.1f} ATR / {n} bars' for a2, b2, n in legs)}")
        if last is not None and len(pts) >= 2:
            _, k, p = last
            prev = pts[-2][2]
            push = abs(p - prev)
            now = (price - p) * (-k)  # how far the running leg has come from the last swing, toward the opposite side
            back = now / push if push else np.nan
            heading = "down" if k == 1 else "up"
            with_rhythm = (sign < 0 and k == 1) or (sign > 0 and k == -1)
            print(f"    now {price:.2f}: running {heading} from {p:.1f} for {now:.1f} ({now / atr:.1f} ATR, {back * 100:.0f} % of the last "
                  f"leg) - {'WITH the rhythm (a push)' if with_rhythm else 'AGAINST the rhythm (a pullback)' if sign else 'no rhythm'}")


if __name__ == "__main__":
    main()
