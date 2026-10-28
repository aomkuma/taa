"""AI chart reader, images v2 (owner, 2026-10-18: "too little price structure in the images?"). The same moments and
panels as render.py plus the structure a trader reads: H1 over 7 days (168 bars), the 72-hour high and low (purple
dashes), the round numbers xx00 / xx50 (grey), yesterday's broker-day high / low and today's Asian range (brown
dots), and a scale bar on the M1 panel: the target (about one M15 ATR) and the stop (about 0.6 of it). Still no
dates, times or prices. Flipped twins as before. Only the ids listed in the sample file.

    data/venv-research/Scripts/python research/2026-10-18-moments/ai_charts/render_v2.py data/research/ai_charts_w/opus_sample.txt
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/2026-10-18-moments"))
import gold  # noqa: E402

DIR = ROOT / "data/research/ai_charts_w"
ids = Path(sys.argv[1]).read_text(encoding="utf-8").split()
man = pd.read_parquet(DIR / "manifest.parquet").set_index("id").loc[ids]
m1 = gold.bars("M1")[["open", "high", "low", "close"]]
m1 = m1[m1.index >= pd.Timestamp("2026-02-01", tz="UTC")]
PANELS = [("H1", 60, 168), ("M15", 15, 96), ("M5", 5, 72), ("M1", 1, 90)]
tfs = {}
for name, mins, _ in PANELS:
    b = m1 if mins == 1 else m1.resample(f"{mins}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    b = b.copy()
    b["close_t"] = b.index + pd.Timedelta(minutes=mins)
    b["e20"] = b.close.ewm(span=20, adjust=False).mean()
    b["e50"] = b.close.ewm(span=50, adjust=False).mean()
    tfs[name] = b.reset_index()
m15 = tfs["M15"]
tr = pd.concat([m15.high - m15.low, (m15.high - m15.close.shift()).abs(), (m15.low - m15.close.shift()).abs()], axis=1).max(axis=1)
m15["a15"] = tr.rolling(14).mean()
athens = m1.index.tz_convert("Europe/Athens").date


def levels(t):
    w = m1[(m1.index < t) & (m1.index >= t - pd.Timedelta(hours=72))]
    out = {"72h": (w.high.max(), w.low.min())}
    k = m1.index.searchsorted(t) - 1
    today = athens[k]
    prev_days = sorted({d for d in athens[max(0, k - 3000):k + 1] if d < today})
    if prev_days:
        y = m1[athens == prev_days[-1]]
        out["yday"] = (y.high.max(), y.low.min())
    day0 = t.normalize()
    asia = m1[(m1.index >= day0) & (m1.index < min(t, day0 + pd.Timedelta(hours=7)))]
    if len(asia):
        out["asia"] = (asia.high.max(), asia.low.min())
    return out


def draw(ax, b, flip, ema, lv, scale=None):
    s = -1.0 if flip else 1.0
    o, c = s * b.open.to_numpy(), s * b.close.to_numpy()
    hi = -b.low.to_numpy() if flip else b.high.to_numpy()
    lo = -b.high.to_numpy() if flip else b.low.to_numpy()
    x = np.arange(len(b))
    up = c >= o
    col = np.where(up, "#1a9850", "#d73027")
    ax.vlines(x, lo, hi, color=col, linewidth=0.8)
    ax.bar(x, np.maximum(np.abs(c - o), 1e-9), bottom=np.minimum(o, c), color=col, width=0.7, linewidth=0)
    for e, cl in (("e20", "orange"), ("e50", "#3060c0")):
        if e in ema:
            ax.plot(x, s * b[e].to_numpy(), color=cl, linewidth=1.1)
    ymin, ymax = lo.min(), hi.max()
    pad = 0.08 * (ymax - ymin)
    ax.set_ylim(ymin - pad, ymax + pad)
    for r in np.arange(np.floor(min(abs(ymin), abs(ymax)) / 50) * 50 - 50, max(abs(ymin), abs(ymax)) + 100, 50):
        y = s * r
        if ymin - pad < y < ymax + pad:
            ax.axhline(y, color="#999999", linewidth=0.9, alpha=0.8)
    for key, (h, l_), style, colr in (("72h", lv.get("72h", (np.nan, np.nan)), "--", "#7b3294"),
                                       ("yday", lv.get("yday", (np.nan, np.nan)), ":", "#8c510a"),
                                       ("asia", lv.get("asia", (np.nan, np.nan)), ":", "#bf812d")):
        for y in (s * h, s * l_):
            if np.isfinite(y) and ymin - pad < y < ymax + pad:
                ax.axhline(y, color=colr, linestyle=style, linewidth=1.2)
    if scale is not None:
        tgt, stp = scale
        y0 = c[-1]
        ax.plot([len(b) + 1.5] * 2, [y0, y0 + tgt], color="black", linewidth=3)
        ax.plot([len(b) + 3.5] * 2, [y0, y0 - stp], color="#555555", linewidth=3)
        ax.set_xlim(-1, len(b) + 5)
    else:
        ax.set_xlim(-1, len(b) + 1)
    ax.set_xticks([])
    ax.set_yticks([])


for mid, r in man.iterrows():
    t = pd.Timestamp(r.t)
    lv = levels(t)
    k15 = int(m15.close_t.searchsorted(t, side="right")) - 1
    a15 = float(m15.a15.iloc[k15])
    for flip in (False, True):
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=75)
        for ax, (name, mins, n) in zip(axes.ravel(), PANELS):
            b = tfs[name]
            k = int(b.close_t.searchsorted(t, side="right"))
            ema = ("e20", "e50") if name == "H1" else ("e20",) if name == "M15" else ()
            draw(ax, b.iloc[max(0, k - n):k], flip, ema, lv, (a15, 0.6 * a15) if name == "M1" else None)
            ax.set_title(name, fontsize=11, loc="left")
        fig.text(0.5, 0.005, "purple dashes: 72-hour high/low   grey: round numbers (every 50)   brown dots: yesterday's "
                 "high/low, today's Asian range   M1 bars at right: target size (black), stop size (grey)",
                 ha="center", fontsize=8)
        fig.tight_layout(rect=(0, 0.02, 1, 1))
        fig.savefig(DIR / f"{mid}{'_flip' if flip else ''}_v2.png")
        plt.close(fig)
print(len(man), "moments rendered (v2)")
