"""Every number relative to the market's own state (owner 2026-10-27: "the problem is the code, measuring
things as fixed numbers ... the market is flexible with its conditions, so fixed numbers make it hard to place
the entry, the exit and the stop").

What was absolute in `bots.py`, and what it becomes here:

| was | why it breaks | now |
|---|---|---|
| take-profit at least 5.00 USD | gold went 2,170 -> 4,383 and its H1 ATR 5.3 -> 21.6, so the same 5 USD is 0.95 ATR in 2023 and 0.23 ATR in 2026 | at least ``min_tp_atr`` x the H1 ATR |
| ZigZag deviation 0.05 USD | a fixed price step on a price that doubled | ``zz_dev_atr`` x the frame's ATR |
| spread 0.30 USD a trade | a cost in price units, not in what the market pays | ``spread_atr`` x the H1 ATR |

Everything else was already a ratio (the box against the leg, the stop against the box, the run against the
stop) and is unchanged.

**And no variant is chosen here.** Each setting is run on all three periods at once and all three are printed,
because picking the best of a grid on one year is what produced +0.331 R that became -0.035 R
(PREDICTION.md). A mechanism that is real should hold in every period without being tuned.

    .venv/Scripts/python research/2026-10-26-three-bots/relative.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
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

TH = "Asia/Bangkok"
PERIODS = {
    "2023-09 .. 2024-09": ("2023-09-05", "2024-09-30"),
    "2024-10 .. 2025-10": ("2024-10-01", "2025-10-19"),
    "2025-10 .. 2026-10": ("2025-10-20", "2026-10-23"),
}


@dataclass
class R:
    """The three bots with every threshold expressed against the market's own state."""

    retrace: tuple[float, float] = (0.382, 0.786)
    box: float = 0.25
    buffer: float = 0.2
    min_r: float = 1.0
    tp_range: float = 0.5
    run: float = 1.2
    min_tp_atr: float = 0.25  # the take-profit at least this many H1 ATRs (was 5.00 USD)
    zz_dev_atr: float = 0.01  # the ZigZag's deviation (was 0.05 USD)
    spread_atr: float = 0.015  # the cost a trade (was 0.30 USD)
    bots: tuple[str, ...] = ("DOWN", "UP", "RANGE")
    range_mode: str = "break"
    range_tf: str = "H4"
    range_flat: bool = True
    exit_mode: str = "tp"
    be_at: float = 0.5


def h1_atr(h1: pd.DataFrame, at: pd.Timestamp, n: int = 14) -> float:
    x = h1[h1.index + pd.Timedelta(hours=1) <= at].iloc[-n:]
    if len(x) < 2:
        return 0.0
    h, lo, c = (x[k].to_numpy(float) for k in ("high", "low", "close"))
    prev = np.concatenate([[c[0]], c[:-1]])
    return float(np.maximum(h - lo, np.maximum(abs(h - prev), abs(lo - prev))).mean())


def run(f: dict, p: R, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """bots.run with the absolute thresholds replaced by multiples of the H1 ATR at the decision."""
    m1, h1 = f[Timeframe.M1], f[Timeframe.H1]
    h4 = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    m1 = m1[(m1.index >= start - pd.Timedelta(days=3)) & (m1.index < end + pd.Timedelta(days=2))]
    m5 = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    busy = dict.fromkeys(p.bots, start)
    out = []
    for day in pd.date_range(start, end, freq="D"):
        if day.weekday() >= 5:
            continue
        day_end = (pd.Timestamp(day.date(), tz=TH) + pd.Timedelta(days=1, hours=7)).tz_convert("UTC")
        for w0, w1 in bots.windows(day):
            bars = m5[(m5.index >= w0 - pd.Timedelta(hours=2)) & (m5.index < w1)]
            seen, sw, sw4, atr = None, [], [], 0.0
            for i in range(len(bars)):
                t = bars.index[i] + pd.Timedelta(minutes=5)
                if t <= w0 or t > w1:
                    continue
                hx = h1[h1.index + pd.Timedelta(hours=1) <= t].iloc[-400:]
                if seen != len(hx):
                    seen = len(hx)
                    atr = h1_atr(h1, t)
                    dev = max(p.zz_dev_atr * atr, 1e-6)
                    sw, _ = zigzag(hx.high.to_numpy(float), hx.low.to_numpy(float), deviation=dev)
                    h4x = h4[h4.index + pd.Timedelta(hours=4) <= t].iloc[-300:]
                    sw4, _ = zigzag(h4x.high.to_numpy(float), h4x.low.to_numpy(float), deviation=dev)
                if len(sw) < 3 or atr <= 0:
                    continue
                past = bars.iloc[: i + 1]
                step = replace(bots.P(), retrace=p.retrace, box=p.box, buffer=p.buffer, min_r=p.min_r,
                               tp_range=p.tp_range, min_tp=p.min_tp_atr * atr, range_mode=p.range_mode,
                               range_tf=p.range_tf, range_flat=p.range_flat, spread=p.spread_atr * atr,
                               exit_mode=p.exit_mode, be_at=p.be_at)  # fmt: skip
                for bot in p.bots:
                    if t < busy[bot]:
                        continue
                    tr = bots.signal(bot, sw, sw4, past, step, t)
                    if tr is None:
                        continue
                    before = m1[(m1.index >= t - pd.Timedelta(minutes=60)) & (m1.index < t)]
                    up = (tr.entry - before.low.min()) if tr.side == "SELL" else (before.high.max() - tr.entry)
                    if p.run and up > p.run * abs(tr.stop - tr.entry):
                        continue
                    own = replace(step, exit_mode="tp" if bot == "DOWN" else "be", be_at=p.be_at)
                    tr = bots.settle(m1, tr, day_end, own)
                    out.append({"bot": bot, "at": tr.at, "r": tr.r, "atr": atr})
                    busy[bot] = tr.extra["closed"]
    return pd.DataFrame(out)


def show(label: str, per: dict[str, pd.DataFrame]) -> None:
    cells = []
    for name in PERIODS:
        d = per[name]
        cells.append(f"{d.r.mean():+.3f} ({len(d)})" if len(d) else "- (0)")
    allt = pd.concat(per.values())
    worst = min((d.r.mean() if len(d) else 0.0) for d in per.values())
    print(f"| {label} | {' | '.join(cells)} | {allt.r.mean():+.3f} ({len(allt)}) | {worst:+.3f} |")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in (Timeframe.M1, Timeframe.H1)}
    print("R a trade in each period - no variant is chosen; the last column is the worst period, which is")
    print("what a system has to survive.\n")
    print(f"| setting | {' | '.join(PERIODS)} | all | worst period |")
    print("|---|---|---|---|---|---|")
    base = R()
    for label, over in [
        ("the measured settings, now relative", {}),
        ("take-profit 0.4 ATR", {"min_tp_atr": 0.4}),
        ("take-profit 0.6 ATR", {"min_tp_atr": 0.6}),
        ("min R 1.2", {"min_r": 1.2}),
        ("box 0.2 of the leg", {"box": 0.2}),
        ("retrace 0.5-0.886", {"retrace": (0.5, 0.886)}),
        ("DOWN only", {"bots": ("DOWN",)}),
        ("RANGE only", {"bots": ("RANGE",)}),
        ("UP only", {"bots": ("UP",)}),
    ]:
        p = replace(base, **over)
        per = {n: run(f, p, pd.Timestamp(s, tz="UTC"), pd.Timestamp(e, tz="UTC")) for n, (s, e) in PERIODS.items()}
        show(label, per)


if __name__ == "__main__":
    main()
