"""Outcomes of the v7-zone entries with the M5 turn and the structure stop - a simulation on stored bars, no orders.

The owner's choices (METHOD 2e "The run zones", 2026-11-01): the M5 turn at the zone, SL beyond the zone's own low /
high before the turn plus a little (B), TP the opposite edge, held until SL or TP. One position at a time. Bars are
bid; BUY fills at ask (close + spread), exits on bid; SELL fills at bid, exits on ask. Cost = the spread only. If one
M5 bar holds both SL and TP, SL is taken first.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
TH, PT, B = "Asia/Bangkok", 0.01, 2.0

m5 = pd.read_parquet(f"{D}/M5.parquet")
m5["th"] = pd.to_datetime(m5.open_time, utc=True).dt.tz_convert(TH)
m5["ct"] = pd.to_datetime(m5.close_time, utc=True).dt.tz_convert(TH)
m5 = m5.reset_index(drop=True)
SUFFIX = sys.argv[1] if len(sys.argv) > 1 else ""
e = pd.read_csv(HERE / f"entries_m5{SUFFIX}.csv", parse_dates=["t", "visit"])
e = e[e.kind == "entry"].sort_values("t").reset_index(drop=True)

rows, busy_until = [], None
for r in e.itertuples():
    if busy_until is not None and r.t < busy_until:
        continue
    j = int(m5.ct.searchsorted(r.t))  # the trigger bar closes at r.t
    trig = m5.iloc[j]
    w = m5[(m5.th >= r.visit) & (m5.ct <= r.t)]
    if r.side == "BUY":
        entry = trig.close + trig.spread * PT
        sl = w.low.min() - B
    else:
        entry = trig.close
        sl = w.high.max() + B
    risk = abs(entry - sl)
    plan_R = ((r.tp - entry) if r.side == "BUY" else (entry - r.tp)) / risk
    if plan_R < 2:  # the owner's 1:2 - "no trade, for now"
        continue
    out = None
    for q in range(j + 1, len(m5)):
        b = m5.iloc[q]
        sp = b.spread * PT
        if r.side == "BUY":
            if b.low <= sl:
                out = (q, sl, "SL")
            elif b.high >= r.tp:
                out = (q, r.tp, "TP")
        else:
            if b.high + sp >= sl:
                out = (q, sl, "SL")
            elif b.low + sp <= r.tp:
                out = (q, r.tp, "TP")
        if out:
            break
    if out is None:
        q, px, how = len(m5) - 1, m5.close.iloc[-1], "open"
    else:
        q, px, how = out
    pnl = (px - entry) if r.side == "BUY" else (entry - px)
    R = pnl / risk
    if how == "SL":
        assert R < 0, (r, entry, sl, px)
    rows.append({"entry_t": m5.ct[j], "exit_t": m5.ct[q], "side": r.side, "line": r.line, "entry": round(entry, 2),
                 "sl": round(sl, 2), "tp": r.tp, "exit": round(px, 2), "how": how, "risk": round(risk, 2), "R": round(R, 3),
                 "usd_001": round(pnl, 2), "hours": round((m5.ct[q] - m5.ct[j]).total_seconds() / 3600, 1)})
    busy_until = m5.ct[q]

t = pd.DataFrame(rows)
t.to_csv(HERE / f"trades_m5{SUFFIX}.csv", index=False)
print(f"{len(t)} trades, TP {(t.how == 'TP').sum()} ({(t.how == 'TP').mean():.0%}), sum R {t.R.sum():+.2f}, {t.R.mean():+.3f} R a trade, USD at 0.01 lot {t.usd_001.sum():+.2f}")
print(t.groupby(t.entry_t.dt.strftime("%Y-%m")).R.agg(["count", "sum"]).round(2).to_string())
raise SystemExit
print(t[["entry_t", "side", "line", "entry", "sl", "tp", "how", "risk", "R", "hours"]].to_string())

# every trade drawn on M5, the losers first in the file names
(HERE / "trades").mkdir(exist_ok=True)
for n, r in t.iterrows():
    a = m5[(m5.ct >= r.entry_t - pd.Timedelta(hours=10)) & (m5.ct <= r.exit_t + pd.Timedelta(hours=3))].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(14, 6))
    for k, b in a.iterrows():
        c = "#26a69a" if b.close >= b.open else "#ef5350"
        ax.vlines(k, b.low, b.high, color=c, lw=0.6)
        ax.add_patch(plt.Rectangle((k - 0.35, min(b.open, b.close)), 0.7, max(abs(b.close - b.open), 0.01), color=c))
    xe = int(a.ct.searchsorted(r.entry_t))
    xx = int(a.ct.searchsorted(r.exit_t))
    ax.axhline(r.line, color="orange", lw=1.2)
    ax.hlines(r.sl, xe, xx, color="black", lw=1.5)
    ax.hlines(r.tp, xe, xx, color="#2e7d32", lw=1.5)
    ax.plot(xe, r.entry, marker="^" if r.side == "BUY" else "v", color="#1565c0" if r.side == "BUY" else "#c62828", ms=12)
    ax.plot(xx, r.exit, marker="o", color="black", ms=7)
    ticks = list(range(0, len(a), 24))
    ax.set_xticks(ticks, [a.ct[i].strftime("%d/%m %H:%M") for i in ticks], fontsize=7)
    ax.grid(alpha=0.15)
    ax.set_title(f"#{n+1} {r.side} at {r.entry} ({r.entry_t:%d/%m %H:%M} Thai), line {r.line:.0f} orange, SL {r.sl} black, TP {r.tp:.0f} green -> {r.how} {r.R:+.2f} R ({r.hours} h)", fontsize=9)
    fig.tight_layout()
    tag = "loss" if r.R < 0 else "win"
    fig.savefig(HERE / "trades" / f"{tag}_{n+1:02d}_{r.entry_t:%m%d}.png", dpi=90)
    plt.close(fig)
