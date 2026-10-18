"""Does the bot read the chart the way a trader does? (owner, 2026-10-19: "focus on whether the bot interprets the
trading screen correctly"). For a sample of decision moments, every timeframe's 120 bars with what the bot measured
drawn on them: the range and where the close sits, the last confirmed top / bottom (the break test) and the swing
still forming, the thirds and the way read in each, the last leg, the deepest pullback - and the bot's reading in
words above each chart, to be checked by eye.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/reading_audit.py
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
import plib  # noqa: E402
from picture import WIN, features  # noqa: E402
from wf_library_compare import Charts  # noqa: E402

TH = "Asia/Bangkok"
TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
WAY = {1: "UP", -1: "DOWN", 0: "FLAT"}
ARROW = {1: "up", -1: "down", 0: "flat"}
STRUCT = {1: "HH/HL (up)", -1: "LH/LL (down)", 0: "mixed", 9: "too few swings"}
BRK = {1: "ABOVE its last top", -1: "BELOW its last bottom", 0: "between its last top and bottom", 9: "no top/bottom yet"}


def draw(ax, C: Charts, tf: str, t_dec: pd.Timestamp) -> None:
    d = C.tf[tf]
    b, R, piv = d["b"], d["R"], d["piv"]
    bi = int(np.searchsorted(d["avail"], pd.Timestamp(t_dec).as_unit("ns").value, side="right")) - 1
    a0 = max(bi - WIN + 1, 0)
    f = features(R["h"], R["lo"], R["c"], R["atr"], piv, bi)
    x = np.arange(bi - a0 + 1)
    o, h, lo, c = (b[k].to_numpy(float)[a0:bi + 1] for k in ("open", "high", "low", "close"))
    up = c >= o
    for msk, col in ((up, "#1a9b77"), (~up, "#d6492f")):
        ax.vlines(x[msk], lo[msk], h[msk], color=col, linewidth=0.6)
        ax.vlines(x[msk], np.minimum(o, c)[msk], np.maximum(o, c)[msk], color=col, linewidth=1.8)
    hi_w, lo_w = h.max(), lo.min()
    ax.axhline(hi_w, color="#999", linestyle=":", linewidth=0.8)
    ax.axhline(lo_w, color="#999", linestyle=":", linewidth=0.8)
    # the swings the bot knows (confirmed by the decision bar) and the one still forming
    pidx, pval, ptyp, pconf = piv
    k = int(np.searchsorted(pconf, bi, side="right")) - 1
    known = np.arange(k + 1)
    known = known[pidx[known] >= a0]
    if len(known):
        ax.plot(pidx[known] - a0, pval[known], color="#333", linewidth=0.8)
        for j in known:
            ax.plot(pidx[j] - a0, pval[j], "v" if ptyp[j] > 0 else "^", color="#111", markersize=5)
        tops, bots = known[ptyp[known] == 1], known[ptyp[known] == -1]
        if len(tops):
            ax.axhline(pval[tops[-1]], color="#d6492f", linestyle="--", linewidth=1.0)
        if len(bots):
            ax.axhline(pval[bots[-1]], color="#1a9b77", linestyle="--", linewidth=1.0)
        last = known[-1]
        if k >= 0 and pidx[k] >= a0:  # the forming swing: the extreme since the last confirmed one
            seg = slice(pidx[k] - a0, bi - a0 + 1)
            if ptyp[k] == -1:
                j = int(np.argmax(h[seg])) + pidx[k] - a0
                ax.plot(j, h[j], "*", color="#9a59c9", markersize=11)
            else:
                j = int(np.argmin(lo[seg])) + pidx[k] - a0
                ax.plot(j, lo[j], "*", color="#9a59c9", markersize=11)
        ax.plot([pidx[last] - a0, bi - a0], [pval[last], c[-1]], color="#3b6fd8", linewidth=1.6)  # the last leg
    n = bi - a0 + 1
    for j in (1, 2):
        ax.axvline((j * n) // 3 - 0.5, color="#bbb", linewidth=0.8)
    for j in range(3):
        ax.text(((2 * j + 1) * n) // 6, hi_w, ARROW[int(f[f"seg{j}"])], ha="center", va="bottom", fontsize=8, color="#555")
    ax.set_xticks([])
    ax.tick_params(labelsize=6)
    ax.set_title(f"{tf}: {WAY[int(f['net_way'])]} (thirds {'/'.join(ARROW[int(f[f'seg{j}'])] for j in range(3))}), "
                 f"{STRUCT[int(f['struct'])]}, close {BRK[int(f['brk'])]}\n"
                 f"size {f['size']:.0f} ATR, at {f['pos']:.2f} of the range, last leg {ARROW.get(int(f['leg_way']), '?')} "
                 f"{f['leg']:.1f} ATR, deepest pullback {f['retr']:.1f} ATR, smoothness {f['er']:.2f}", fontsize=7.5, loc="left")


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    C = Charts(plib.load())
    rng = np.random.default_rng(23)
    pick = np.sort(rng.choice(np.nonzero(np.asarray(S.S < plib.EXAM_START))[0], size=8, replace=False))
    out = HERE / "png" / "reading_audit"
    out.mkdir(parents=True, exist_ok=True)
    for n, e in enumerate(pick):
        fig, axes = plt.subplots(3, 2, figsize=(18, 13))
        for ax, tf in zip(axes.ravel(), TFS):
            draw(ax, C, tf, S.S.iloc[e])
        when = S.S.iloc[e].tz_convert(TH)
        fig.suptitle(f"How the bot reads the chart at the snap {when:%Y-%m-%d %H:%M} TH ({S.name.iloc[e]})  |  dotted grey: the "
                     "120-bar range; red / green dashed: the last confirmed top / bottom; purple star: the swing still forming; "
                     "blue: the last leg; grey lines: the thirds", fontsize=9)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        f = out / f"{n:02d}_{when:%Y%m%d_%H%M}.png"
        fig.savefig(f, dpi=64)
        plt.close(fig)
        print(f, flush=True)


if __name__ == "__main__":
    main()
