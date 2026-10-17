"""Trade charts for the journal: M1 around the entry (60 minutes before, up to 120 after), M5 and H1 context, the
level, entry, stop, target, break-even trigger, exit, session open and US releases.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/journal/charts.py SYM TRADES.parquet TAG [i i ...]

Without indices it draws every trade in the file (keep it to a few dozen).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jlib  # noqa: E402

UP, DN = "#2e7d32", "#c62828"


def candles(ax, x, o, h, lo, c, w=0.6):
    col = np.where(c >= o, UP, DN)
    ax.vlines(x, lo, h, color=col, linewidth=0.8)
    ax.bar(x, np.maximum(np.abs(c - o), 1e-9), bottom=np.minimum(o, c), width=w, color=col, edgecolor=col, linewidth=0.3)


def agg(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule, label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def draw(P: jlib.Instr, r: pd.Series, lv: pd.DataFrame, rel: np.ndarray, out: Path, num: int) -> None:
    e, side = int(r.e), int(r.side)
    t = r.t
    fig = plt.figure(figsize=(16, 8.4), dpi=72)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.55, 1], hspace=0.28, wspace=0.12)
    ax = fig.add_subplot(gs[:, 0])
    a0, a1 = e - 60, min(e + 120, len(P.o))
    xs = np.arange(a0, a1) - e
    candles(ax, xs, P.o[a0:a1], P.h[a0:a1], P.lo[a0:a1], P.c[a0:a1])
    entry = float(r.entry)
    stop, tgt = entry - side * r.sl, entry + side * r.tp
    ax.axhline(r.level, color="#1565c0", ls="--", lw=1.2, label=f"level ({r.level_kind})")
    ax.axhline(entry, color="black", lw=0.9, label="entry")
    ax.axhline(stop, color=DN, lw=1.0, label="stop")
    ax.axhline(tgt, color=UP, lw=1.0, label="target")
    ax.axhline(entry + side * 0.6 * r.tp, color="grey", ls=":", lw=0.9, label="BE trigger")
    ax.axvspan(0, int(r.xj) - e + 0.5, color="#fff59d", alpha=0.35)
    ax.plot([0], [entry], marker="^" if side > 0 else "v", ms=13, color="black")
    xexit = int(r.xj) - e
    ax.plot([xexit], [entry + r.pnl * side], marker="X", ms=11, color=UP if r.pnl > 0 else DN)
    s0 = -int(r.min_in) - 1
    if s0 >= -60:
        ax.axvline(s0, color="#6a1b9a", lw=1.2, ls="-.", label="session open")
    for rt in rel:
        dx = (rt - t) / pd.Timedelta(minutes=1)
        if -60 <= dx <= 120:
            ax.axvline(dx - 1, color="#ff6f00", lw=1.5, label="US release")
    ax.set_xlim(-61, 121)
    seg = slice(a0, a1)
    ymin, ymax = min(P.lo[seg].min(), stop, r.level), max(P.h[seg].max(), tgt, r.level)
    pad = 0.05 * (ymax - ymin)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.set_xlabel("minutes from entry (M1)")
    ax.grid(alpha=0.2)
    sess = jlib.SESS[int(r.session)]
    res = f"{r.exit} {r.pnl:+.2f} ({r.R:+.2f}R)" + (f" kind {r.kind}" if r.kind else "")
    pa = "/".join(k for k, f in (("M1 hammer", r.pa_m1), ("M5 hammer", r.pa_m5), ("engulf", r.engulf), ("reclaim", r.reclaim)) if f)
    ind = " ".join(k for k, f in (("RSI", r.rsi_ok), ("MACD", r.macd_ok), ("Stoch", r.stoch_ok)) if f)
    ax.set_title(f"#{num} {P.sym} {t:%Y-%m-%d %H:%M} UTC  {sess} +{int(r.min_in)}m  {'BUY' if side > 0 else 'SELL'}  -> {res}", fontsize=11)
    txt = (f"level {r.level_kind} {r.dist_atr:.1f} ATR behind, cluster {int(r.cluster)} | PA {pa} | ind {ind}\n"
           f"approach ret15 {r.ret15:+.1f} ret60 {r.ret60:+.1f} ATR | rng15 {r.rng15:.1f} rng60 {r.rng60:.1f} rng240 {r.rng240:.1f} ATR"
           f" | ATR {r.atr1:.2f} (x{r.atr_ratio:.2f} of day median)\n"
           f"H1 struct {int(r.cr_H1_struct):+d} now {int(r.cr_H1_now):+d} | M15 struct {int(r.cr_M15_struct):+d} now {int(r.cr_M15_now):+d}"
           f" | H1 slope {r.h1_e20_slope:+.2f} c-e50 {r.h1_c_e50:+.1f} | room {r.room:.2f} vs tp {r.tp:.2f}"
           f" | day rng/ADR {r.day_rng_adr:.2f} pos {r.day_pos:.2f} | rel since {r.since_rel:.0f}m until {r.until_rel:.0f}m"
           f" | mfe {r.mfe:.2f} mae {r.mae:.2f}")
    fig.text(0.01, 0.005, txt, fontsize=8.5, family="monospace", va="bottom")
    # M5 context: 8 hours before, 2 after
    m = P.m
    win5 = agg(m.loc[t - pd.Timedelta(hours=8) : t + pd.Timedelta(hours=2)], "5min")
    ax5 = fig.add_subplot(gs[0, 1])
    x5 = (win5.index - t) / pd.Timedelta(minutes=60)
    candles(ax5, x5.to_numpy(), *(win5[k].to_numpy() for k in ("open", "high", "low", "close")), w=0.06)
    full5 = agg(m.loc[t - pd.Timedelta(days=3) : t + pd.Timedelta(hours=2)], "5min")
    ema5 = full5.close.ewm(span=20, adjust=False).mean().reindex(win5.index)
    ax5.plot(x5, ema5, color="#1565c0", lw=0.8)
    ax5.axhline(r.level, color="#1565c0", ls="--", lw=1)
    ax5.axhline(stop, color=DN, lw=0.7)
    ax5.axhline(tgt, color=UP, lw=0.7)
    ax5.axvline(0, color="black", lw=0.8)
    ax5.set_title("M5, hours from entry (EMA20)", fontsize=9)
    ax5.grid(alpha=0.2)
    # H1 context: 72 hours before, 3 after, with the H1 chart-read levels at the decision
    win1 = agg(m.loc[t - pd.Timedelta(hours=72) : t + pd.Timedelta(hours=3)], "60min")
    full1 = agg(m.loc[t - pd.Timedelta(days=20) : t + pd.Timedelta(hours=3)], "60min")
    ax1 = fig.add_subplot(gs[1, 1])
    x1 = np.arange(len(win1))
    candles(ax1, x1, *(win1[k].to_numpy() for k in ("open", "high", "low", "close")), w=0.6)
    for span, col in ((20, "#1565c0"), (50, "#6a1b9a")):
        ax1.plot(x1, full1.close.ewm(span=span, adjust=False).mean().reindex(win1.index).to_numpy(), color=col, lw=0.9)
    k_entry = int(win1.index.searchsorted(t, side="right") - 1)
    ax1.axvline(k_entry, color="black", lw=0.8)
    h1l = lv[(lv.tf == "H1") & (lv.close_t <= t)]
    if len(h1l):
        for price in h1l.iloc[-1].levels:
            ax1.axhline(price, color="grey", lw=0.6, ls="--")
    ax1.set_ylim(win1.low.min() - 0.03 * (win1.high.max() - win1.low.min()), win1.high.max() + 0.03 * (win1.high.max() - win1.low.min()))
    ax1.axhline(r.level, color="#1565c0", ls="--", lw=1)
    ax1.set_title("H1, 72 h (EMA20 blue, EMA50 purple, H1 chart-read levels grey)", fontsize=9)
    ax1.grid(alpha=0.2)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    sym, path, tag = sys.argv[1], sys.argv[2], sys.argv[3]
    idx = [int(i) for i in sys.argv[4:]]
    P = jlib.Instr(sym)
    T = pd.read_parquet(HERE / path)
    T["t"] = pd.to_datetime(T.t, utc=True)
    part = "design" if T.t.max() < jlib.DESIGN_END else "test"
    lv = pd.read_parquet(HERE / f"levels_{sym}_{part}.parquet")
    lv["close_t"] = pd.to_datetime(lv.close_t, utc=True)
    lv = lv.sort_values("close_t")
    rel = np.sort(jlib.gold.releases().t.to_numpy())
    rel = pd.DatetimeIndex(rel)
    out = HERE / "charts" / tag
    out.mkdir(parents=True, exist_ok=True)
    for i in idx or range(len(T)):
        r = T.iloc[i]
        near = rel[(rel > r.t - pd.Timedelta(hours=2)) & (rel < r.t + pd.Timedelta(hours=3))]
        draw(P, r, lv, near, out / f"{i:03d}.png", i)
    print("drew", len(idx or T), "charts in", out)


if __name__ == "__main__":
    main()
