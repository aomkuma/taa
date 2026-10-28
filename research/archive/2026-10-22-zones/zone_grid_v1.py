"""The owner's zone grid, v1 (owner 2026-10-22, confirmed "about this"; zone shift rules given in chat):
- impulse: a closed D1 bar whose body |close - open| >= IMPULSE x ATR20 (MT5 ATR of the closed D1 bars);
- anchor (the shift / re-anchor): the base the move left - the highest body (max open/close) of the BASE_N D1 bars before
  a down impulse, the lowest body of them before an up impulse (fits the owner's 4293.03 = the 2026-09-23 open);
- the step breathes: ATR20 of the last closed D1 bar, every day; lines = anchor + k x step (carried along);
- inside the grid: an H4 close beyond a line moves the active zone; the broken line flips role (for the trading tests).
Draws H4 candles with the grid in force at each bar into PNGs for the owner's visual check.

    .venv/Scripts/python research/2026-10-22-zones/zone_grid_v1.py 2025-10-01 2026-04-18
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

IMPULSE, BASE_N = 1.5, 2
OUT = Path(__file__).resolve().parent / "charts"


def bars(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(f"data/history/FBS-Demo/XAUUSD/{tf}.parquet")
    d["t"] = pd.to_datetime(d.open_time, utc=True)
    return d.drop_duplicates("t", keep="last").set_index("t").sort_index()


def daily_grid(d: pd.DataFrame) -> pd.DataFrame:
    """Per closed D1 bar: the anchor and step in force from the next bar on."""
    pc = d.close.shift(1)
    atr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean()
    anchor, rows = np.nan, []
    for i in range(len(d)):
        a = atr.iloc[i]
        body = d.close.iloc[i] - d.open.iloc[i]
        shift = ""
        if np.isfinite(a) and abs(body) >= IMPULSE * a and i >= BASE_N:
            base = d.iloc[i - BASE_N : i]
            hi_b, lo_b = np.maximum(base.open, base.close), np.minimum(base.open, base.close)
            anchor = float(hi_b.max() if body < 0 else lo_b.min())
            shift = "down" if body < 0 else "up"
        rows.append(dict(t=d.index[i], anchor=anchor, step=a, shift=shift, close=d.close.iloc[i]))
    g = pd.DataFrame(rows).set_index("t")
    g.index = g.index + pd.Timedelta(days=1)  # known once the D1 bar has closed
    return g


def draw(h4: pd.DataFrame, g: pd.DataFrame, s: str, e: str, title: str) -> str:
    """One H4 chart as inline SVG: candles, the grid lines in force at each bar, the zone shifts."""
    x = h4[(h4.index >= s) & (h4.index < e)]
    if not len(x):
        return ""
    k = g.index.searchsorted(x.index, side="right") - 1
    anc, stp = g.anchor.values[k], g.step.values[k]
    W, H, L, R, T, B = 1400, 520, 10, 70, 30, 30
    lo, hi = float(x.low.min()), float(x.high.max())
    pad = 0.06 * (hi - lo)
    lo, hi = lo - pad, hi + pad
    n = len(x)
    xs = lambda i: L + (i + 0.5) * (W - L - R) / n  # noqa: E731
    ys = lambda v: T + (hi - v) * (H - T - B) / (hi - lo)  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" style="background:#0d1117">']
    for kk in range(-60, 61):  # the lines: one segment per bar (they breathe with the ATR and jump on a shift)
        pts = []
        for i in range(n):
            y = anc[i] + kk * stp[i]
            if np.isfinite(y) and lo < y < hi:
                pts.append(f"{xs(i):.1f},{ys(y):.1f}")
            elif pts:
                out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#e08a00" stroke-width="1" opacity="0.8"/>')
                pts = []
        if len(pts) > 1:
            out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#e08a00" stroke-width="1" opacity="0.8"/>')
    bw = max(1.0, 0.6 * (W - L - R) / n)
    for i, r in enumerate(x.itertuples()):
        c = "#2ecc71" if r.close >= r.open else "#e74c3c"
        out.append(f'<line x1="{xs(i):.1f}" x2="{xs(i):.1f}" y1="{ys(r.high):.1f}" y2="{ys(r.low):.1f}" stroke="{c}"/>')
        y0, y1 = ys(max(r.open, r.close)), ys(min(r.open, r.close))
        out.append(f'<rect x="{xs(i) - bw / 2:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{max(1, y1 - y0):.1f}" fill="{c}"/>')
    for t, r in g[(g.index >= s) & (g.index < e) & (g["shift"] != "")].iterrows():
        j = int(x.index.searchsorted(t))
        out.append(f'<line x1="{xs(j):.1f}" x2="{xs(j):.1f}" y1="{T}" y2="{H - B}" stroke="#5b8cff" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{xs(j) + 3:.1f}" y="{T + 12}" fill="#5b8cff" font-size="11">shift {r["shift"]} {r.anchor:.0f} / step {r.step:.0f}</text>')
    for v in np.linspace(lo, hi, 8):
        out.append(f'<text x="{W - R + 5}" y="{ys(v):.1f}" fill="#8b949e" font-size="11">{v:.0f}</text>')
    for i in range(0, n, max(1, n // 10)):
        out.append(f'<text x="{xs(i):.1f}" y="{H - 8}" fill="#8b949e" font-size="11">{x.index[i].tz_convert("Asia/Bangkok"):%d %b}</text>')
    out.append("</svg>")
    return f"<h3>{title}</h3>" + "".join(out)


if __name__ == "__main__":
    s, e = sys.argv[1], sys.argv[2]
    d, h4 = bars("D1"), bars("H4")
    g = daily_grid(d)
    sh = g[(g.index >= s) & (g.index < e) & (g["shift"] != "")]
    print(sh[["anchor", "step", "shift", "close"]].round(2).to_string())
    parts = [draw(h4, g, "2026-08-15", "2026-10-22", "Check against the owner's chart: 2026-08-15 .. 10-22 (owner's lines 4293.24 / 4217.25 / 4141.83 / 4066.41)")]
    months = pd.date_range(s, e, freq="MS", tz="UTC")
    for a, b in zip(months[:-1], months[1:]):
        parts.append(draw(h4, g, str(a.date()), str(b.date()), f"{a:%B %Y}"))
    html = ("<!doctype html><meta charset=utf-8><title>Zone grid v1</title><body style='background:#0d1117;color:#c9d1d9;"
            "font-family:sans-serif;margin:16px'><h2>XAUUSD H4 - the zone grid v1</h2><p>Orange: anchor + k x D1 ATR(20), "
            "redrawn daily; blue dashed: a zone shift (a D1 body >= 1.5 ATR re-anchors at the base it left).</p>" + "".join(parts))
    OUT.mkdir(exist_ok=True)
    (OUT / "zone_grid_v1.html").write_text(html, encoding="utf-8")
    print(OUT / "zone_grid_v1.html")
