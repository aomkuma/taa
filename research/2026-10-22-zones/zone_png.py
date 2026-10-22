"""PNG version of the zone grid v1 charts (owner 2026-10-22: send pictures, not HTML)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zone_grid_v1 as Z  # noqa: E402


def png(h4: pd.DataFrame, g: pd.DataFrame, s: str, e: str, title: str, out: Path) -> Path:
    x = h4[(h4.index >= s) & (h4.index < e)]
    k = g.index.searchsorted(x.index, side="right") - 1
    anc, stp = g.anchor.values[k], g.step.values[k]
    fig, ax = plt.subplots(figsize=(16, 7), facecolor="black")
    ax.set_facecolor("black")
    i = np.arange(len(x))
    lo, hi = x.low.min(), x.high.max()
    for kk in range(-60, 61):
        y = anc + kk * stp
        ax.plot(i, np.where((y > lo - 20) & (y < hi + 20), y, np.nan), color="#ff9900", lw=0.9)
    col = np.where(x.close >= x.open, "#00e000", "#00e000")
    ax.vlines(i, x.low, x.high, color=col, lw=0.8)
    ax.vlines(i, np.minimum(x.open, x.close), np.maximum(x.open, x.close), color=col, lw=2.5)
    for t, r in g[(g.index >= s) & (g.index < e) & (g["shift"] != "")].iterrows():
        j = x.index.searchsorted(t)
        ax.axvline(j, color="#5b8cff", lw=1, ls="--")
        ax.text(j, hi, f" shift {r['shift']} {r.anchor:.0f}\n step {r.step:.0f}", color="#5b8cff", fontsize=9, va="top")
    last = len(x) - 1
    for kk in range(-60, 61):
        y = anc[last] + kk * stp[last]
        if lo - 20 < y < hi + 20:
            ax.text(last + 1, y, f"{y:.2f}", color="#ff9900", fontsize=9, va="center")
    ticks = i[:: max(1, len(i) // 10)]
    ax.set_xticks(ticks, [x.index[t].tz_convert("Asia/Bangkok").strftime("%d %b") for t in ticks], color="white")
    ax.tick_params(colors="white")
    ax.set_xlim(0, len(x) + 12)
    ax.set_ylim(lo - 25, hi + 25)
    ax.grid(color="#333", ls="--", lw=0.5)
    ax.set_title(title, color="white")
    fig.savefig(out, dpi=80, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    return out


if __name__ == "__main__":
    d, h4 = Z.bars("D1"), Z.bars("H4")
    g = Z.daily_grid(d)
    o = Path(__file__).resolve().parent / "charts"
    print(png(h4, g, "2026-08-10", "2026-10-23", "XAUUSD H4 - zone grid v1 vs the owner's chart (Aug-Oct 2026)", o / "zone_owner_check.png"))
    for a, b in (("2025-10-01", "2025-11-15"), ("2025-11-15", "2026-01-01"), ("2026-01-01", "2026-02-15"), ("2026-02-15", "2026-04-18")):
        print(png(h4, g, a, b, f"XAUUSD H4 - zone grid v1, {a} .. {b}", o / f"zone_{a}.png"))
