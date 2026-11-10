"""Each run-zone trade drawn twice: H1 over about a week with every zone line (the wider view the owner asked for,
2026-11-01) and M5 close up with the same lines. Reads trades_m5.csv; writes trades_wide/."""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
TH, S = "Asia/Bangkok", 76.0
only = int(sys.argv[1]) if len(sys.argv) > 1 else None


def load(tf):
    df = pd.read_parquet(f"{D}/{tf}.parquet")
    df["th"] = pd.to_datetime(df.open_time, utc=True).dt.tz_convert(TH)
    df["ct"] = pd.to_datetime(df.close_time, utc=True).dt.tz_convert(TH)
    return df


h1, m5 = load("H1"), load("M5")
SRC = sys.argv[2] if len(sys.argv) > 2 else "trades_m5"
t = pd.read_csv(HERE / f"{SRC}.csv", parse_dates=["entry_t", "exit_t"])
OUTD = HERE / ("trades_wide" if SRC == "trades_m5" else f"wide_{SRC}")
OUTD.mkdir(exist_ok=True)


def candles(ax, a):
    for k, b in a.iterrows():
        c = "#26a69a" if b.close >= b.open else "#ef5350"
        ax.vlines(k, b.low, b.high, color=c, lw=0.6)
        ax.add_patch(plt.Rectangle((k - 0.35, min(b.open, b.close)), 0.7, max(abs(b.close - b.open), 0.01), color=c))


def panel(ax, a, r, step_label):
    a = a.reset_index(drop=True)
    candles(ax, a)
    lo, hi = min(a.low.min(), r.sl, r.tp) - 10, max(a.high.max(), r.sl, r.tp) + 10
    n = int((lo - r.line) // S)
    while r.line + n * S <= hi:
        y = r.line + n * S
        if y >= lo:
            ax.axhline(y, color="orange", lw=1.6 if n == 0 else 1.0)
            ax.text(len(a) - 1, y + 1.5, f"{y:.0f}", fontsize=7, color="#e65100", ha="right")
        n += 1
    xe = int(a.ct.searchsorted(r.entry_t))
    xx = int(a.ct.searchsorted(r.exit_t))
    span = max(xx, xe + len(a) // 6)  # at least a sixth of the panel wide, so a fast stop is still visible
    ax.hlines(r.sl, xe, span, color="black", lw=1.8)
    ax.hlines(r.tp, xe, span, color="#2e7d32", lw=1.8)
    ax.text(span, r.sl, f" SL {abs(r.sl - r.entry):.1f}", fontsize=8, va="center")
    ax.text(span, r.tp, f" TP {abs(r.tp - r.entry):.1f}", fontsize=8, va="center", color="#2e7d32")
    ax.plot(xe, r.entry, marker="^" if r.side == "BUY" else "v", color="#1565c0" if r.side == "BUY" else "#c62828", ms=12, zorder=5)
    ax.plot(xx, r.exit, marker="o", color="black", ms=7, zorder=5)
    every = max(1, len(a) // 10)
    ticks = list(range(0, len(a), every))
    ax.set_xticks(ticks, [a.ct[i].strftime("%d/%m %H:%M") for i in ticks], fontsize=7, rotation=20)
    ax.set_ylim(lo, hi)
    ax.grid(alpha=0.15)
    ax.set_title(step_label, fontsize=9)


for n, r in t.iterrows():
    if only and n + 1 != only:
        continue
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(20, 7), gridspec_kw={"width_ratios": [1.3, 1]})
    w1 = h1[(h1.ct >= r.entry_t - pd.Timedelta(days=6)) & (h1.ct <= r.exit_t + pd.Timedelta(days=1))]
    w5 = m5[(m5.ct >= r.entry_t - pd.Timedelta(hours=10)) & (m5.ct <= r.exit_t + pd.Timedelta(hours=3))]
    panel(a1, w1, r, "H1 - about 6 days before to 1 day after; orange = the zones (thick = the line traded)")
    panel(a2, w5, r, "M5 close up")
    fig.suptitle(f"#{n+1} {r.side} at {r.entry} ({r.entry_t:%d/%m %H:%M} Thai), line {r.line:.0f}, SL {r.sl} (black), TP {r.tp:.0f} (green) -> {r.how} {r.R:+.2f} R in {r.hours} h", fontsize=11)
    fig.tight_layout()
    tag = "loss" if r.R < 0 else "win"
    fig.savefig(OUTD / f"{n+1:02d}_{tag}_{r.entry_t:%m%d}.png", dpi=90)
    plt.close(fig)
