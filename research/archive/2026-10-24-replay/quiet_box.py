"""Trade the quiet, wait for the break (owner 2026-10-26: "don't rush to place limit or stop orders; place them
when price forms a clear pattern; trade when it is quiet, waiting for the break").

The rule measured, inside the owner's windows (Asia 07:00-09:00, London 13:00-15:00, New York 08:00-11:30 NY):
- a BOX: the last N (6-24) complete M5 bars span at most WIDTH x the M5 ATR(14) of the bars before them - the
  longest such N at each M5 close; nothing is placed before a box exists;
- the order: a stop order beyond the box edge, on the D1 regime's side (or both sides when D1 has none / with
  --both); it fills at the first M5 close through the edge (the same rule as the bot's stop orders);
- the stop: beyond the opposite box edge by 0.2 M5 ATR; the take-profit: max(5 USD, TP_R x the risk);
- one trade per window; results to the window's end + 2 hours (then closed at the bar's close), bid bars, the
  spread not counted; each trade in R.

Measured on the design months before the exam (2026-03-02 .. 2026-04-17) week by week, and on the journal days
06-08 Jul as a cross-check only.

    .venv/Scripts/python research/2026-10-24-replay/quiet_box.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy import knowledge as kn  # noqa: E402

TH = "Asia/Bangkok"
NY = "America/New_York"


def windows(day: pd.Timestamp) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """The owner's windows of the Thai day ``day`` (a date) in UTC."""
    th = pd.Timestamp(day.date(), tz=TH)
    ny = pd.Timestamp(day.date(), tz=NY)
    return [
        ("asia", (th + pd.Timedelta(hours=7)).tz_convert("UTC"), (th + pd.Timedelta(hours=9)).tz_convert("UTC")),
        ("london", (th + pd.Timedelta(hours=13)).tz_convert("UTC"), (th + pd.Timedelta(hours=15)).tz_convert("UTC")),
        ("ny", (ny + pd.Timedelta(hours=8)).tz_convert("UTC"), (ny + pd.Timedelta(hours=11, minutes=30)).tz_convert("UTC")),
    ]


def atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> float:
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(abs(h - prev), abs(lo - prev)))
    return float(tr[-14:].mean())


def box_at(m5: pd.DataFrame, i: int, width: float) -> tuple[float, float, int, float] | None:
    """(top, bottom, bars, ATR) of the longest box ending at bar ``i`` (6-24 bars), or None."""
    best = None
    for n in range(6, 25):
        s = i - n + 1
        if s < 15:
            break
        x = m5.iloc[s : i + 1]
        b = m5.iloc[s - 15 : s]
        a = atr(b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float))
        top, bot = float(x.high.max()), float(x.low.min())
        if a > 0 and top - bot <= width * a:
            best = (top, bot, n, a)
    return best


def trade(m1: pd.DataFrame, t: pd.Timestamp, entry: float, stop: float, tp: float, sell: bool, until: pd.Timestamp) -> float:
    x = m1[(m1.index >= t) & (m1.index < until)]
    risk = abs(stop - entry)
    for _, b in x.iterrows():
        if (b.high >= stop) if sell else (b.low <= stop):
            return -1.0
        if (b.low <= tp) if sell else (b.high >= tp):
            return abs(tp - entry) / risk
    last = float(x.close.iloc[-1]) if len(x) else entry
    return ((entry - last) if sell else (last - entry)) / risk


def run(f: dict, days: pd.DatetimeIndex, width: float, tp_r: float, both: bool) -> pd.DataFrame:
    m1 = f[Timeframe.M1]
    out = []
    for day in days:
        for name, w0, w1 in windows(day):
            seg = m1[(m1.index >= w0 - pd.Timedelta(hours=3)) & (m1.index < w1 + pd.Timedelta(hours=2))]
            if len(seg) < 200:
                continue
            m5 = seg.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            fr = kn.Frames(m1[m1.index < w0], f[Timeframe.M15], f[Timeframe.H1], f[Timeframe.H4], f[Timeframe.D1], ())
            d1 = kn.features(fr, w0)["d1_regime"]
            sides = ["SELL", "BUY"] if (both or d1 == "none") else (["SELL"] if d1 == "down" else ["BUY"])
            idx = list(m5.index)
            done = False
            box = None
            for i, t in enumerate(idx):
                close_t = t + pd.Timedelta(minutes=5)
                if close_t <= w0 or done:
                    continue
                if close_t > w1:
                    break
                bar = m5.iloc[i]
                if box is not None:  # a box from the bars before: does this bar close through an edge?
                    top, bot, n, a = box
                    for side in sides:
                        sell = side == "SELL"
                        if (bar.close < bot) if sell else (bar.close > top):
                            entry = float(bar.close)
                            stop = top + 0.2 * a if sell else bot - 0.2 * a
                            risk = abs(stop - entry)
                            tp = entry - max(5.0, tp_r * risk) if sell else entry + max(5.0, tp_r * risk)
                            r = trade(m1, close_t, entry, stop, tp, sell, w1 + pd.Timedelta(hours=2))
                            out.append({"day": day, "window": name, "side": side, "d1": d1, "at": close_t,
                                        "box": n, "height": top - bot, "risk": risk, "r": r})
                            done = True
                            break
                if not done:
                    box = box_at(m5, i, width)
    return pd.DataFrame(out)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(ROOT / "data/history")
    tfs = (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1)
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in tfs}
    design = pd.bdate_range("2026-03-02", "2026-04-17")
    print("== design months 2026-03-02 .. 04-17: variants (box width x M5 ATR, TP in R, sides) ==")
    print("| width | TP | sides | trades | win % | R / trade | total R | weeks + / - |")
    print("|---|---|---|---|---|---|---|---|")
    results = {}
    for width in (1.5, 2.0, 2.5):
        for tp_r in (1.0, 1.5):
            for both in (False, True):
                df = run(f, design, width, tp_r, both)
                results[(width, tp_r, both)] = df
                if not len(df):
                    continue
                wk = df.groupby(pd.to_datetime(df.day).dt.isocalendar().week).r.sum()
                print(f"| {width} | {tp_r} R | {'both' if both else 'D1'} | {len(df)} | {(df.r > 0).mean():.0%} | "
                      f"{df.r.mean():+.3f} | {df.r.sum():+.1f} | {(wk > 0).sum()} / {(wk <= 0).sum()} |")
    print("\n== the journal days 06-08 Jul (cross-check), width 2.0, TP 1.5 R, D1 side ==")
    df = run(f, pd.bdate_range("2026-07-06", "2026-07-08"), 2.0, 1.5, False)
    for _, r in df.iterrows():
        print(f"- {pd.Timestamp(r['at']).tz_convert(TH):%m-%d %H:%M} {r['window']} {r['side']} (D1 {r['d1']}): box "
              f"{r['box']} bars, {r['height']:.1f} USD, risk {r['risk']:.1f} -> {r['r']:+.2f} R")


if __name__ == "__main__":
    main()
