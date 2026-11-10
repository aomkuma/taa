"""Each variant-C setup drawn: H1 about 6 days with every zone line, and M5 close up; P1 / P2 entries, the shared SL
and TP. Usage: draw_two.py <trades csv stem> [setup number]. Writes setups_<stem>/."""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
TH, S = "Asia/Bangkok", 76.0
STEM = sys.argv[1]
ONLY = int(sys.argv[2]) if len(sys.argv) > 2 else None


def load(tf):
    df = pd.read_parquet(f"{D}/{tf}.parquet")
    df["th"] = pd.to_datetime(df.open_time, utc=True).dt.tz_convert(TH)
    df["ct"] = pd.to_datetime(df.close_time, utc=True).dt.tz_convert(TH)
    return df


h1, m5 = load("H1"), load("M5")
t = pd.read_csv(HERE / f"{STEM}.csv", parse_dates=["visit", "entry_t", "exit_t"])
OUT = HERE / f"setups_{STEM}"
OUT.mkdir(exist_ok=True)


def panel(ax, a, g, title):
    a = a.reset_index(drop=True)
    for k, b in a.iterrows():
        c = "#26a69a" if b.close >= b.open else "#ef5350"
        ax.vlines(k, b.low, b.high, color=c, lw=0.6)
        ax.add_patch(plt.Rectangle((k - 0.35, min(b.open, b.close)), 0.7, max(abs(b.close - b.open), 0.01), color=c))
    r0 = g.iloc[0]
    lo, hi = min(a.low.min(), r0.sl, r0.tp) - 10, max(a.high.max(), r0.sl, r0.tp) + 10
    n = int((lo - r0.line) // S)
    while r0.line + n * S <= hi:
        y = r0.line + n * S
        if y >= lo:
            ax.axhline(y, color="orange", lw=1.6 if n == 0 else 1.0)
            ax.text(len(a) - 1, y + 1.5, f"{y:.0f}", fontsize=7, color="#e65100", ha="right")
        n += 1
    x0 = int(a.ct.searchsorted(g.entry_t.min()))
    xx = int(a.ct.searchsorted(r0.exit_t))
    span = max(xx, x0 + len(a) // 6)
    ax.hlines(r0.sl, x0, span, color="black", lw=1.8)
    ax.hlines(r0.tp, x0, span, color="#2e7d32", lw=1.8)
    ax.text(span, r0.sl, " SL", fontsize=8, va="center")
    ax.text(span, r0.tp, " TP", fontsize=8, va="center", color="#2e7d32")
    for r in g.itertuples():
        xe = int(a.ct.searchsorted(r.entry_t))
        ax.plot(xe, r.entry, marker="^" if r.side == "BUY" else "v", color="#1565c0" if r.side == "BUY" else "#c62828", ms=11, zorder=5)
        ax.text(xe + 1, r.entry, f" {r.pos} {r.entry:.0f}", fontsize=8, va="center")
    ax.plot(xx, r0.tp if r0.how == "TP" else r0.sl, marker="o", color="black", ms=7, zorder=5)
    every = max(1, len(a) // 10)
    ticks = list(range(0, len(a), every))
    ax.set_xticks(ticks, [a.ct[i].strftime("%d/%m %H:%M") for i in ticks], fontsize=7, rotation=20)
    ax.set_ylim(lo, hi)
    ax.grid(alpha=0.15)
    ax.set_title(title, fontsize=9)


for n, (visit, g) in enumerate(t.groupby("visit", sort=True)):
    if ONLY and n + 1 != ONLY:
        continue
    r0 = g.iloc[0]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(20, 7), gridspec_kw={"width_ratios": [1.3, 1]})
    w1 = h1[(h1.ct >= g.entry_t.min() - pd.Timedelta(days=6)) & (h1.ct <= r0.exit_t + pd.Timedelta(days=1))]
    w5 = m5[(m5.ct >= g.entry_t.min() - pd.Timedelta(hours=10)) & (m5.ct <= min(r0.exit_t, g.entry_t.max() + pd.Timedelta(hours=30)) + pd.Timedelta(hours=3))]
    panel(a1, w1, g, "H1 - about 6 days before to 1 day after; orange = the zones (thick = the line traded)")
    panel(a2, w5, g, "M5 close up")
    usd = g.pnl.sum()
    fig.suptitle(f"#{n+1} {r0.side} at the {r0.line:.0f} line ({visit:%d/%m/%Y %H:%M} Thai): {len(g)} position(s) "
                 f"{', '.join(f'{p} {e:.1f}' for p, e in zip(g.pos, g.entry))}; SL {r0.sl:.1f}, TP {r0.tp:.0f} -> {r0.how}, {usd:+.0f} USD at 0.01 lot each", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / f"{n+1:02d}_{'loss' if usd < 0 else 'win'}_{visit:%Y%m%d}.png", dpi=90)
    plt.close(fig)
