"""Sit at a moment and wait, one step at a time, until the picture is worth trading.

A moment - a real day's window, or one of the retired sampled moments - is **where I sit down**. From
there the chart advances a few bars at a time and I look again, seeing only what had printed by then -
never a bar from the future. The waiting is part of the record: how long I sat before a setup appeared, or
that none did.

What is drawn is the owner's setup (METHOD 2e, owner, 2026-10-28): the trend on **H1** gives the side with
the edge; the entry is read on **M15 and M5**; peaks are counted on MT5's **ZigZag**, and divergence is
read between price and **MACD** and **RSI** - all three at MT5's own default settings. Two images per
look: ``_a`` is H1 above M15 with its MACD and RSI, ``_b`` is M5 with its MACD and RSI.

    python eye/walk.py "2026-04-03 07:00" 12   # a real day, advanced 12 M5 bars
    python eye/walk.py <moment id> <step>      # a retired sampled moment, advanced <step> M5 bars

Nothing on a chart uses a bar that had not closed by ``now``: every frame is cut to its closed bars first,
and the indicators and the ZigZag are computed on that cut. MT5 draws its last ZigZag point while it can
still move; that leg is drawn dashed for the same reason.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from app.indicators.chart_read import zigzag_pivots  # noqa: E402
from app.indicators.common import ema_values  # noqa: E402
from app.indicators.momentum import rsi  # noqa: E402
from app.indicators.price_action import SwingKind  # noqa: E402

TH = "Asia/Bangkok"
DATA = ROOT / "data/history/FBS-Demo/XAUUSD"
POINT = float(json.loads((DATA / "spec.json").read_text(encoding="utf-8"))["spec"]["point"])

# MT5's own defaults (the owner, 2026-10-28: "use MT5's values as they are").
ZIGZAG = {"depth": 12, "deviation": 5, "backstep": 3}
MACD = (12, 26, 9)
RSI = 14

# How much of each frame is on the screen. H1 about three weeks, so the left of the chart holds the levels;
# M15 about three days; M5 about 33 hours, the width of the owner's own screen.
SHOWN = {"H1": 500, "M15": 288, "M5": 400}
STEP = {"H1": pd.Timedelta(hours=1), "M15": pd.Timedelta(minutes=15), "M5": pd.Timedelta(minutes=5)}
# Bars before the left edge used only to warm the indicators up: the EMA here is seeded with a mean where
# MT5 seeds with a price, and the difference has decayed to nothing long before 1500 bars.
WARMUP = 1500


def frame(tf: str) -> pd.DataFrame:
    df = pd.read_parquet(DATA / f"{tf}.parquet")
    col = next(c for c in df.columns if "time" in c.lower())
    df[col] = pd.to_datetime(df[col], utc=True)
    return df.set_index(col).sort_index()


def moment(mid: str) -> pd.Timestamp:
    """A sampled moment by id, or a Thai wall-clock time written out - the owner, 2026-10-28: run real
    days, one at a time, instead of sampled moments, so nothing is selected and every wait is walked."""
    if "-" in mid:  # "2026-04-01 07:00" Thai
        return pd.Timestamp(mid, tz=TH).tz_convert("UTC")
    for r in csv.DictReader((HERE / "moments.csv").open(encoding="utf-8")):
        if r["id"] == mid:
            return pd.Timestamp(r["cutoff_utc"])
    raise SystemExit(f"no moment {mid}")


def macd_mt5(close: pd.Series) -> pd.DataFrame:
    """MACD as MT5 draws it: the main line EMA12 - EMA26 as the histogram, and the signal line a **simple**
    9-bar average of it. ``app.indicators.trend.macd`` uses an EMA signal and plots main - signal, which is
    not the picture the owner reads."""
    fast, slow, signal = MACD
    values = close.to_numpy(dtype=np.float64)
    main = ema_values(values, fast) - ema_values(values, slow)
    sig = pd.Series(main, index=close.index).rolling(signal, min_periods=signal).mean()
    return pd.DataFrame({"main": main, "signal": sig.to_numpy()}, index=close.index)


def candles(ax: plt.Axes, bars: pd.DataFrame, width: float = 0.34, lw: float = 1.0) -> None:
    for i, (_, b) in enumerate(bars.iterrows()):
        up = b.close >= b.open
        colour = "#10795f" if up else "#a83242"
        ax.plot([i, i], [b.low, b.high], color=colour, linewidth=lw, zorder=2)
        lo, hi = (b.open, b.close) if up else (b.close, b.open)
        ax.add_patch(
            plt.Rectangle(
                (i - width, lo), width * 2, max(hi - lo, 0.01), facecolor=colour, edgecolor=colour, zorder=3
            )
        )
    tidy(ax, bars)


def tidy(ax: plt.Axes, bars: pd.DataFrame) -> None:
    loc = bars.index.tz_convert(TH)
    ticks = list(range(0, len(bars), max(1, len(bars) // 20)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{loc[i]:%d/%m %H:%M}" for i in ticks], rotation=45, ha="right", fontsize=8)
    ax.grid(True, alpha=0.18, linewidth=0.6)
    ax.set_xlim(-1, len(bars))
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def zigzag(ax: plt.Axes, calc: pd.DataFrame, offset: int) -> None:
    """MT5's ZigZag on the closed bars: fixed pivots joined in solid blue, each labelled with its price, and
    the last leg - the point MT5 still moves as new bars print - dashed."""
    pivots = zigzag_pivots(
        calc.high.to_numpy(dtype=np.float64), calc.low.to_numpy(dtype=np.float64), POINT, **ZIGZAG
    )
    if not pivots:
        return
    xs = [p.pivot_pos - offset for p in pivots]
    ys = [p.price for p in pivots]
    ax.plot(xs, ys, color="#1f5fbf", linewidth=1.3, zorder=4)
    for p, x in zip(pivots, xs, strict=True):
        if x < 0:
            continue
        above = p.kind is SwingKind.HIGH
        ax.annotate(
            f"{p.price:.2f}",
            (x, p.price),
            xytext=(0, 7 if above else -12),
            textcoords="offset points",
            ha="center",
            fontsize=7,
            color="#1f5fbf",
        )
    last = pivots[-1]
    after = calc.iloc[last.pivot_pos + 1 :]
    if after.empty:
        return
    if last.kind is SwingKind.LOW:
        at = int(np.argmax(after.high.to_numpy())) + last.pivot_pos + 1
        price = float(calc.high.iloc[at])
    else:
        at = int(np.argmin(after.low.to_numpy())) + last.pivot_pos + 1
        price = float(calc.low.iloc[at])
    ax.plot([last.pivot_pos - offset, at - offset], [last.price, price], "--", color="#1f5fbf", linewidth=1.0)


def panel(axes: list[plt.Axes], tf: str, now: pd.Timestamp, title: str, oscillators: bool) -> pd.DataFrame:
    """One timeframe: price with the ZigZag, and under it MACD and RSI when asked."""
    closed = frame(tf)
    closed = closed[closed.index + STEP[tf] <= now]
    calc = closed.iloc[-(SHOWN[tf] + WARMUP) :]
    shown = calc.iloc[-SHOWN[tf] :]
    offset = len(calc) - len(shown)

    ax = axes[0]
    candles(ax, shown, width=0.3, lw=0.7)
    zigzag(ax, calc, offset)
    lo, hi = float(shown.low.min()), float(shown.high.max())
    pad = (hi - lo) * 0.04
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_title(title, fontsize=11)

    if oscillators:
        m = macd_mt5(calc.close).iloc[-SHOWN[tf] :]
        x = np.arange(len(m))
        ax_m, ax_r = axes[1], axes[2]
        ax_m.bar(x, m.main, width=0.8, color="#9a9a9a")
        ax_m.plot(x, m.signal, ":", color="#c0392b", linewidth=1.2)
        ax_m.axhline(0, color="#555555", linewidth=0.6)
        ax_m.set_ylabel(f"MACD {MACD[0]},{MACD[1]},{MACD[2]}", fontsize=8)
        tidy(ax_m, shown)
        r = rsi(calc.close, RSI).iloc[-SHOWN[tf] :]
        ax_r.plot(x, r.to_numpy(), color="#6c3483", linewidth=1.0)
        for level in (30, 70):
            ax_r.axhline(level, color="#888888", linewidth=0.6, linestyle="--")
        ax_r.set_ylim(0, 100)
        ax_r.set_ylabel(f"RSI {RSI}", fontsize=8)
        tidy(ax_r, shown)
        for a in (ax, ax_m):
            a.tick_params(labelbottom=False)
    return shown


def draw(mid: str, step: int) -> None:
    start = moment(mid)
    now = start + pd.Timedelta(minutes=5 * step)
    stem = mid.replace(" ", "_").replace(":", "") if "-" in mid else f"{int(mid):03d}"
    out_dir = HERE / "walk"
    out_dir.mkdir(exist_ok=True)

    fig_a, axes_a = plt.subplots(4, 1, figsize=(21, 17), dpi=100, height_ratios=[3, 3, 1, 1], sharex=False)
    h1 = panel([axes_a[0]], "H1", now, "", oscillators=False)
    axes_a[0].set_title(
        f"H1 - three weeks, the trend and the levels   (to {h1.index[-1].tz_convert(TH):%d/%m %H:%M} Thai)",
        fontsize=11,
    )
    m15 = panel(list(axes_a[1:]), "M15", now, "", oscillators=True)
    axes_a[1].set_title(
        f"M15 - three days, ZigZag {ZIGZAG['depth']},{ZIGZAG['deviation']},{ZIGZAG['backstep']}   "
        f"(to {m15.index[-1].tz_convert(TH):%d/%m %H:%M} Thai)",
        fontsize=11,
    )
    fig_a.tight_layout()
    path_a = out_dir / f"{stem}_{step:03d}_a.png"
    fig_a.savefig(path_a)
    plt.close(fig_a)

    fig_b, axes_b = plt.subplots(3, 1, figsize=(21, 13), dpi=100, height_ratios=[3, 1, 1])
    m5 = panel(list(axes_b), "M5", now, "", oscillators=True)
    loc = m5.index.tz_convert(TH)
    axes_b[0].set_title(
        f"M5 - {mid}, +{step} bars ({step * 5} min). Now {loc[-1]:%d/%m %H:%M} Thai, "
        f"last close {m5.close.iloc[-1]:.2f}",
        fontsize=12,
    )
    fig_b.tight_layout()
    path_b = out_dir / f"{stem}_{step:03d}_b.png"
    fig_b.savefig(path_b)
    plt.close(fig_b)

    print(path_a)
    print(path_b)
    print(f"  now {loc[-1]:%d/%m %H:%M} Thai   last close {m5.close.iloc[-1]:.2f}")


if __name__ == "__main__":
    draw(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
