"""AI chart reader, stage 0-1 (docs/AI_CHART_READER.md; owner, 2026-10-18: "do it"). Renders the pilot's charts and
their answer key (research venv: matplotlib).

Moments: the first minute of every F1 base-confluence episode (H1 tide + level + price action + 2/3 M5 + a 3-10 U
stop; one per side per 15 minutes) from 2026-07-01 to 2026-10-14 (after the model's knowledge cutoff), plus 100
random window minutes (wide windows, weekdays) of the same months. Each: one 1200 x 800 image of four panels from
closed bars only - H1 (120 bars, EMA 20 orange / 50 blue), M15 (96, EMA 20), M5 (72), M1 (90); no dates, times or
prices - and the same image upside down (prices negated: the flip test).
Answer key (never shown to the model): for a BUY and for a SELL entered at the next bar's open, real costs, target
8 U, stop 0.6 M15 ATR clipped to 3-10 U, break-even at 0.6 of the target, 60 minutes (jlib.Instr.trade).

    data/venv-research/Scripts/python research/2026-10-18-moments/ai_charts/render.py

The clear-signal set (owner, 2026-10-18): only moments that pass F1's C4 (the 72-hour extreme), from the design
candidates, after Haiku's knowledge cutoff:

    AI_PART=wdesign AI_END=2026-03-01 AI_C4ONLY=1 data/venv-research/Scripts/python \n        research/2026-10-18-moments/ai_charts/render.py 2025-03-01 _c4
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
A = ROOT / "research/2026-10-18-moments/agents"
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402

OUT = ROOT / ("data/research/ai_charts" + (sys.argv[2] if len(sys.argv) > 2 else ""))
OUT.mkdir(parents=True, exist_ok=True)
START = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else "2026-07-01", tz="UTC")
END = pd.Timestamp(__import__("os").environ.get("AI_END", "2026-10-14"), tz="UTC")
C4ONLY = __import__("os").environ.get("AI_C4ONLY") == "1"
PANELS = [("H1", 60, 120), ("M15", 15, 96), ("M5", 5, 72), ("M1", 1, 90)]

P, D = plib.load(__import__("os").environ.get("AI_PART", "wtest"))
D = D.reset_index(drop=True)
D["tt"] = pd.to_datetime(D.t, utc=True)
side = D.side.to_numpy()
sl0 = (P.fill(D.e.to_numpy(), side) - (D.level.to_numpy() - side * D.atr1.to_numpy())) * side
pa = (D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim).to_numpy()
ind = ((D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2).to_numpy()
base = D.tide.to_numpy(bool) & D.at_level.to_numpy(bool) & pa & ind & (sl0 >= 3 * D.unit) & (sl0 <= 10 * D.unit)
B = D[base & (D.tt >= START).to_numpy() & (D.tt < END).to_numpy()].sort_values(["side", "tt"])
B = B[((B.tt.diff() > pd.Timedelta(minutes=15)) | (B.side.diff() != 0)).to_numpy()]
B = B.assign(kind="base", c4=plib.MENU["C4 72-h extreme near/behind"](B).to_numpy(bool))
R = D[(D.tt >= START).to_numpy() & (D.tt < END).to_numpy() & (D.side > 0).to_numpy()].sample(100, random_state=7)
R = R.assign(kind="random", c4=False)
if C4ONLY:
    B, R = B[B.c4], R.iloc[:0]
M = pd.concat([B, R]).sort_values("tt").reset_index(drop=True)

m1 = P.m
tfs = {}
for name, mins, _ in PANELS:
    b = m1 if mins == 1 else m1.resample(f"{mins}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b = b[["open", "high", "low", "close"]].copy()
    b["close_t"] = b.index + pd.Timedelta(minutes=mins)
    b["e20"] = b.close.ewm(span=20, adjust=False).mean()
    b["e50"] = b.close.ewm(span=50, adjust=False).mean()
    tfs[name] = b.reset_index(drop=True)
m15 = tfs["M15"]
tr = pd.concat([m15.high - m15.low, (m15.high - m15.close.shift()).abs(), (m15.low - m15.close.shift()).abs()], axis=1).max(axis=1)
m15["a15"] = tr.rolling(14).mean()


def draw(ax, b, flip, ema):
    s = -1.0 if flip else 1.0
    o, c = s * b.open.to_numpy(), s * b.close.to_numpy()
    hi = np.where(flip, -b.low.to_numpy(), b.high.to_numpy())
    lo = np.where(flip, -b.high.to_numpy(), b.low.to_numpy())
    x = np.arange(len(b))
    up = c >= o
    ax.vlines(x, lo, hi, color=np.where(up, "#1a9850", "#d73027"), linewidth=0.8)
    ax.bar(x, np.maximum(np.abs(c - o), 1e-9), bottom=np.minimum(o, c), color=np.where(up, "#1a9850", "#d73027"),
           width=0.7, linewidth=0)
    if "e20" in ema:
        ax.plot(x, s * b.e20.to_numpy(), color="orange", linewidth=1.1)
    if "e50" in ema:
        ax.plot(x, s * b.e50.to_numpy(), color="#3060c0", linewidth=1.1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ax.set_xlim(-1, len(b) + 1)


def render(t, path, flip):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=100)
    for ax, (name, mins, n) in zip(axes.ravel(), PANELS):
        b = tfs[name]
        k = int(b.close_t.searchsorted(t, side="right"))  # bars closed at or before t
        draw(ax, b.iloc[max(0, k - n):k], flip, ("e20", "e50") if name == "H1" else ("e20",) if name == "M15" else ())
        ax.set_title(name, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


rows = []
for i, r in enumerate(M.itertuples()):
    t = r.tt  # the decision bar closes at t; the trade would enter at the bar opening at t
    e = int(r.e)
    k = int(m15.close_t.searchsorted(t, side="right")) - 1
    u = float(r.unit)
    sl = float(np.clip(0.6 * m15.a15.iloc[k], 3 * u, 10 * u))
    res = {}
    for sd, nm in ((1, "buy"), (-1, "sell")):
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        o = P.trade(e, sd, 8 * u, sl, 0.6, 60, ss)
        res[f"usd_{nm}"], res[f"R_{nm}"], res[f"exit_{nm}"] = o["pnl"], o["pnl"] / (sl + ss), o["exit"]
    mid = f"m{i:04d}"
    render(t, OUT / f"{mid}.png", False)
    render(t, OUT / f"{mid}_flip.png", True)
    rows.append(dict(id=mid, t=t, kind=r.kind, base_side=int(r.side) if r.kind == "base" else 0, c4=bool(r.c4),
                     session=int(r.session), sl=sl, **res))
man = pd.DataFrame(rows)
man.to_parquet(OUT / "manifest.parquet")
print(man.kind.value_counts().to_dict(), "images in", OUT)
b = man[man.kind == "base"]
print(f"base moments: following the base side R {np.where(b.base_side > 0, b.R_buy, b.R_sell).mean():+.3f};"
      f" always BUY {b.R_buy.mean():+.3f}, always SELL {b.R_sell.mean():+.3f}; C4 among them {b.c4.sum()}")
