"""V3-1's drawings (shape only, no outcomes): 2026-10-19 and 10 learning days picked by the written rule (DEV_LOG.md:
5 per part, the weekday nearest 1/6 .. 5/6 of the part, the earlier on a tie, skipping a day with fewer than 600 M1
bars in the Thai 05:00-24:00 window). M5 candles; the M1 trade-size pivots at their minute; the M5 range box; the M5
lines; the M5 box / line events; the H1 Fibonacci of the last completed leg as known at the window's end; under it,
the label and the bias of every TF at every M5 close.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/dev2/draw_v31.py
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402

TH = "Asia/Bangkok"
OUT = HERE / "charts"
PARTS = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
UPC, DNC = "#2a78d6", "#eb6834"  # structure: up / down
BOXC, SUPC, RESC, FIBC = "#eb6834", "#1baf7a", "#6250d6", "#eda100"
MARK = {"break": ("x", 30), "accepted": ("X", 60), "sweep": ("o", 30), "retest": ("D", 28), "retest_fail": ("D", 55),
        "reclaim": ("P", 55)}
TFS = ("D1", "H4", "H1", "M30", "M15", "M5", "M1")  # the owner: D1 the side, M15-H1 the trend, M1-M5 the entry


def x_of(t, t0) -> np.ndarray:
    return (pd.DatetimeIndex(np.atleast_1d(t)).as_unit("ns").asi8 - pd.Timestamp(t0).as_unit("ns").value) / 6e10


def draw(R: dict, m: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp, title: str, png: Path, marks=()) -> None:
    t0, t1 = pd.Timestamp(t0).tz_convert("UTC"), pd.Timestamp(t1).tz_convert("UTC")
    marks = [(pd.Timestamp(t).tz_convert("UTC"), txt) for t, txt in marks]
    r5 = R["M5"]
    b = r5.bars
    sel = (b.t >= t0) & (b.t < t1)
    B = b[sel]
    if not len(B):
        return
    fig = plt.figure(figsize=(22, 14), dpi=90)
    ax = fig.add_axes([0.06, 0.43, 0.92, 0.49])
    ax2 = fig.add_axes([0.06, 0.04, 0.92, 0.34], sharex=ax)
    x = x_of(B.t, t0)
    for xi, (_, row) in zip(x, B.iterrows()):
        up = row.close >= row.open
        ax.vlines(xi + 2.5, row.low, row.high, color=INK2, lw=0.8, zorder=2)
        ax.add_patch(Rectangle((xi + 0.6, min(row.open, row.close)), 3.8, max(abs(row.close - row.open), 0.05),
                               facecolor="white" if up else INK2, edgecolor=INK2, lw=0.8, zorder=3))
    lo_y, hi_y = B.low.min(), B.high.max()
    pad = (hi_y - lo_y) * 0.06
    # the M1 pivots
    r1 = R["M1"]
    pb, pp, pk, pc = r1.piv
    tp = r1.bars.t.to_numpy()[pb]
    keep = (tp >= t0) & (tp < t1)
    for t_, p_, k_, c_ in zip(tp[keep], pp[keep], pk[keep], pc[keep]):
        xi = x_of(t_, t0)[0] + 0.5
        ax.scatter([xi], [p_ + (pad * 0.25 if k_ == 1 else -pad * 0.25)], marker="v" if k_ == 1 else "^", s=60, color=UPC if k_ == 1 else DNC,
                   zorder=6, edgecolor="white", linewidth=0.8)
        known = r1.bars.avail.iloc[c_]
        ax.annotate(f"{pd.Timestamp(t_).tz_convert(TH):%H:%M} {p_:.2f}\nknown {known.tz_convert(TH):%H:%M}", (xi, p_),
                    xytext=(0, 14 if k_ == 1 else -24), textcoords="offset points", ha="center", fontsize=7, color=INK)
    # the M5 boxes overlapping the window
    for _, bx in r5.boxes.iterrows():
        ta = b.t.iloc[int(bx["first"])]
        te = b.avail.iloc[int(bx.end)] if bx.end >= 0 else b.avail.iloc[-1]
        if te < t0 or ta > t1:
            continue
        born = b.avail.iloc[int(bx.born)]
        xa, xe = x_of(max(ta, t0), t0)[0], x_of(min(te, t1), t0)[0]
        ax.add_patch(Rectangle((xa, bx.bot), xe - xa, bx.top - bx.bot, facecolor=BOXC, alpha=0.07, edgecolor=BOXC, lw=1.4, zorder=1))
        ax.text(xa + 2, bx.top + pad * 0.05, f"M5 box {bx.bot:.2f}-{bx.top:.2f} (from {ta.tz_convert(TH):%H:%M}, known {born.tz_convert(TH):%H:%M},"
                f" end {te.tz_convert(TH):%H:%M} {bx.why or 'live'})", fontsize=8, color=INK2)
    # the M5 lines: each from its first anchor to the next line of its kind (or the window's end)
    L = r5.lines
    if len(L):
        for _, ln in L.iterrows():
            nxt = L[(L.kind == ln.kind) & (L.born > ln.born)]
            ta = b.t.iloc[int(r5.piv[0][int(ln.a)])]
            te = b.avail.iloc[int(nxt.born.iloc[0])] if len(nxt) else t1
            if te < t0 or ta > t1:
                continue
            ts = pd.date_range(max(ta, t0), min(te, t1), freq="5min")
            if len(ts) < 2:
                continue
            v = ln.pa + ln.slope * (pd.DatetimeIndex(ts).as_unit("ns").asi8 // W.NS_MIN - ln.ta)
            ax.plot(x_of(ts, t0), v, color=SUPC if ln.kind == -1 else RESC, lw=1.6, alpha=0.9, zorder=4)
    # the M5 events
    ev = r5.events
    if len(ev):
        ev = ev[(b.t.to_numpy()[ev.bar.to_numpy()] >= t0) & (b.t.to_numpy()[ev.bar.to_numpy()] < t1)]
        for _, e in ev.iterrows():
            mk, sz = MARK[e.kind]
            col = BOXC if e.tag.startswith("box") else SUPC if e.tag == "sup" else RESC
            xi = x_of(b.t.iloc[int(e.bar)], t0)[0] + 2.5
            ax.scatter([xi], [e.price], marker=mk, s=sz, color=col, edgecolor=INK, linewidth=0.5, zorder=7)
            if e.kind in ("accepted", "retest_fail", "reclaim"):
                ax.annotate(e.kind.replace("_", " "), (xi, e.price), xytext=(4, -10), textcoords="offset points", fontsize=7, color=INK2)
    # the H1 Fibonacci known at the window's end
    r60 = R["H1"]
    j = int(r60.at(np.array([pd.Timestamp(t1).as_unit("ns").value]))[0])
    f = W.fib_at(r60, j) if j >= 0 else None
    if f:
        te = r60.bars.t.iloc[f["end_bar"]]
        xa = x_of(max(te, t0), t0)[0]
        for k, lv in f["levels"].items():
            if lo_y - pad <= lv <= hi_y + pad:
                ax.hlines(lv, xa, x_of(t1, t0)[0], color=FIBC, lw=1.0, linestyles="--", zorder=1)
                ax.text(x_of(t1, t0)[0] - 2, lv, f"H1 Fib {k * 100:.1f} % {lv:.2f}", fontsize=7, color=INK2, ha="right", va="bottom")
    for k, (tm, txt) in enumerate(marks):
        xi = x_of(tm, t0)[0]
        ax.axvline(xi, color="#b8b7b2", lw=1.0, ls=":", zorder=0)
        ax.text(xi, hi_y + pad * (1.35 if k % 2 else 0.95), txt, fontsize=8, color=INK, ha="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1))
    ax.set_ylim(lo_y - pad * 1.6, hi_y + pad * 1.6)
    ax.grid(True, color=GRID, lw=0.6)
    fig.suptitle(title, fontsize=12, color=INK, x=0.04, ha="left", y=0.995)
    ax.set_ylabel("price (USD)", color=INK2)
    handles = [Patch(facecolor=BOXC, alpha=0.2, edgecolor=BOXC, label="M5 range box"),
               plt.Line2D([], [], color=SUPC, lw=1.6, label="M5 support line (rising lows)"),
               plt.Line2D([], [], color=RESC, lw=1.6, label="M5 resistance line (falling highs)"),
               plt.Line2D([], [], color=FIBC, lw=1.0, ls="--", label="H1 Fibonacci (last completed leg)"),
               plt.Line2D([], [], marker="v", color=UPC, ls="", label="M1 peak (trade-size swing)"),
               plt.Line2D([], [], marker="^", color=DNC, ls="", label="M1 trough")]
    handles += [plt.Line2D([], [], marker=mk, color=INK2, ls="", markersize=6, label=k.replace("_", " ")) for k, (mk, _) in MARK.items()]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.01), fontsize=7.5, ncol=6, framealpha=0.9)
    # the structure strip
    ts = pd.date_range(t0, t1, freq="5min", inclusive="left")
    t_ns = pd.DatetimeIndex(ts).as_unit("ns").asi8
    rows = []
    for tf in TFS:
        r = R[tf]
        jj = r.at(t_ns)
        for what in ("label", "bias"):
            v = np.where(jj >= 0, r.struct[what].to_numpy()[np.maximum(jj, 0)], np.nan)
            rows.append((f"{tf} {what}", v))
    rd = W.readings_at(R, t_ns)
    rows = [("side (labels)", rd.side.to_numpy()), ("side (biases)", rd.side_bias.to_numpy()),
            ("trend (labels)", rd.trend.to_numpy()), ("trend (biases)", rd.trend_bias.to_numpy())] + rows
    xs = x_of(ts, t0)
    for k, (name, v) in enumerate(rows):
        y = len(rows) - 1 - k
        for xi, vi in zip(xs, v):
            col = UPC if vi == 1 else DNC if vi == -1 else "#d6d5d0" if vi == 0 else "white"
            ax2.add_patch(Rectangle((xi, y + 0.08), 5, 0.5 if (name.endswith("bias") or "biases" in name) else 0.84, facecolor=col, edgecolor="none"))
    ax2.set_yticks([len(rows) - 1 - k + 0.45 for k in range(len(rows))])
    ax2.set_yticklabels([n for n, _ in rows], fontsize=8, color=INK2)
    ax2.set_ylim(0, len(rows))
    ax2.legend(handles=[Patch(color=UPC, label="up (HH + HL) / bias up"), Patch(color=DNC, label="down (LH + LL) / bias down"),
                        Patch(color="#d6d5d0", label="mixed"), Patch(facecolor="white", edgecolor=INK2, label="unknown")],
               loc="lower left", fontsize=7.5, ncol=4, bbox_to_anchor=(0, 1.0), framealpha=0.9)
    hours = pd.date_range(t0.ceil("1h"), t1, freq="1h")
    ax2.set_xticks(x_of(hours, t0))
    ax2.set_xticklabels([f"{h.tz_convert(TH):%H:%M}" for h in hours], fontsize=8)
    ax2.set_xlabel("Thai time (UTC+7)", color=INK2)
    ax2.set_xlim(0, x_of(t1, t0)[0])
    plt.setp(ax.get_xticklabels(), visible=False)
    fig.savefig(png)
    plt.close(fig)


def learning_days(m: pd.DataFrame) -> list[pd.Timestamp]:
    loc = m.index.tz_convert(TH)
    counts = pd.Series(1, index=loc).groupby(loc.date).count()
    hours = pd.Series(loc.hour, index=loc)
    in_win = hours[(hours >= 5)].groupby(loc[hours.values >= 5].date).count()
    out = []
    for a, b in PARTS.values():
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        for q in range(1, 6):
            target = a + (b - a) * q / 6
            cands = pd.date_range(a, b - pd.Timedelta(days=1), freq="D")
            cands = [c for c in cands if c.weekday() < 5 and in_win.get(c.date(), 0) >= 600 and c.date() in counts.index]
            best = min(cands, key=lambda c: (abs((c - target).total_seconds()), c))
            out.append(best)
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with open(HERE / "v31_shape.pkl", "rb") as fh:
        S = pickle.load(fh)
    t0, t1 = pd.Timestamp("2026-10-19 05:00", tz=TH), pd.Timestamp("2026-10-19 22:05", tz=TH)
    marks = [(pd.Timestamp(f"2026-10-19 {h}", tz=TH), txt) for h, txt in
             (("14:33", "14:33 top"), ("17:20", "17:20 break"), ("18:15", "18:15 retest"), ("18:30", "18:30 owner sells"))]
    draw(S["R"], S["m"], t0, t1, "2026-10-19 (after the data end: shape check only) - M5 candles, Thai time", OUT / "v31_2026-10-19.png", marks)
    draw(S["R"], S["m"], pd.Timestamp("2026-10-19 13:00", tz=TH), t1, "2026-10-19 13:00-22:05 Thai, zoomed", OUT / "v31_2026-10-19_pm.png", marks)
    with open(HERE / "v31_learning.pkl", "rb") as fh:
        R = pickle.load(fh)
    m = R["M1"].bars.set_index("t")[["open", "high", "low", "close"]]
    days = learning_days(m)
    print("learning days (rule): " + ", ".join(f"{d:%Y-%m-%d %a}" for d in days))
    items = [("v31_2026-10-19.png", "2026-10-19, the shape day"), ("v31_2026-10-19_pm.png", "2026-10-19 afternoon / evening")]
    for d in days:
        a = pd.Timestamp(f"{d:%Y-%m-%d} 05:00", tz=TH)
        e = a + pd.Timedelta(hours=19)
        name = f"v31_{d:%Y-%m-%d}.png"
        part = "P1" if d < pd.Timestamp("2026-01-16") else "P2"
        draw(R, m, a, e, f"{d:%Y-%m-%d %a} ({part}, learning day by rule) - M5 candles, Thai 05:00-24:00", OUT / name)
        items.append((name, f"{d:%Y-%m-%d %a} ({part})"))
    html = ["<!doctype html><meta charset='utf-8'><title>V3-1 swings and structure</title>",
            "<style>body{font-family:sans-serif;background:#fcfcfb;color:#0b0b0b;margin:16px}img{max-width:100%;border:1px solid #ddd}</style>",
            "<h1>V3-1 - trade-size swings, structure per TF, range box, lines, Fibonacci</h1>",
            "<p>Shape only: no outcome is drawn. Rules: <code>dev2/DEV_LOG.md</code>. Thai time.</p>"]
    for f, cap in items:
        html.append(f"<h2>{cap}</h2><img src='{f}' alt='{cap}'>")
    (OUT / "index_v31.html").write_text("\n".join(html), encoding="utf-8")
    print(f"wrote {len(items)} charts and {OUT / 'index_v31.html'}")


if __name__ == "__main__":
    main()
