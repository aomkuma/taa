"""The zoom by eye (owner, 2026-10-19: "look at the smaller timeframe - M5 should show the swings"): moments where a
timeframe's own swings were too few to read (structure or break 9) and the bot read them from the next smaller one
over the same span (moments.zoom_all). Left: the timeframe's 120 bars and the swings it knows; right: the smaller
timeframe's bars over the same span, its swings, and the reading taken from them.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/zoom_audit.py
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
# before plib: plib puts the research folder first on the path, and its own moments.py would shadow this one
from moments import M1F_K, SMALLER, TFS, small_span  # noqa: E402, I001
import plib  # noqa: E402
from fingerprint import zigzag  # noqa: E402
from picture import WIN, struct_brk  # noqa: E402
from reading_audit import BRK, STRUCT  # noqa: E402
from wf_library_compare import Charts  # noqa: E402

TH = "Asia/Bangkok"


def panel(ax, d: dict, a0: int, bi: int, close: float, title: str) -> tuple[int, int]:
    """Bars a0 .. bi, the swings known at bi inside them (black), the swing still forming (purple star), the last
    confirmed top / bottom (red / green dashed), the close used (blue dotted); returns the reading (struct, brk)."""
    b, R, piv = d["b"], d["R"], d["piv"]
    o, h, lo, c = (b[k].to_numpy(float)[a0:bi + 1] for k in ("open", "high", "low", "close"))
    x = np.arange(bi - a0 + 1)
    up = c >= o
    lw = 1.8 if len(x) <= 150 else (0.9 if len(x) <= 400 else 0.5)
    for msk, col in ((up, "#1a9b77"), (~up, "#d6492f")):
        ax.vlines(x[msk], lo[msk], h[msk], color=col, linewidth=0.5)
        ax.vlines(x[msk], np.minimum(o, c)[msk], np.maximum(o, c)[msk], color=col, linewidth=lw)
    pidx, pval, ptyp, pconf = piv
    k = int(np.searchsorted(pconf, bi, side="right")) - 1
    known = np.arange(k + 1)
    known = known[pidx[known] >= a0]
    if len(known):
        ax.plot(pidx[known] - a0, pval[known], color="#333", linewidth=0.9)
        for j in known:
            ax.plot(pidx[j] - a0, pval[j], "v" if ptyp[j] > 0 else "^", color="#111", markersize=6)
        tops, bots = known[ptyp[known] == 1], known[ptyp[known] == -1]
        if len(tops):
            ax.axhline(pval[tops[-1]], color="#d6492f", linestyle="--", linewidth=1.0)
        if len(bots):
            ax.axhline(pval[bots[-1]], color="#1a9b77", linestyle="--", linewidth=1.0)
    if k >= 0 and pidx[k] >= a0:  # the forming swing: the extreme since the last confirmed one
        seg = slice(pidx[k] - a0, bi - a0 + 1)
        if ptyp[k] == -1:
            j = int(np.argmax(h[seg])) + pidx[k] - a0
            ax.plot(j, h[j], "*", color="#9a59c9", markersize=12)
        else:
            j = int(np.argmin(lo[seg])) + pidx[k] - a0
            ax.plot(j, lo[j], "*", color="#9a59c9", markersize=12)
    ax.axhline(close, color="#3b6fd8", linestyle=":", linewidth=1.0)
    s, br = struct_brk(R["h"], R["lo"], close, piv, bi, a0)
    ax.set_xticks([])
    ax.tick_params(labelsize=7)
    ax.set_title(f"{title}\n{len(known)} confirmed swings: {STRUCT[s]}, close {BRK[br]}", fontsize=9, loc="left")
    return s, br


def main() -> None:
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    C = Charts(plib.load())
    m1 = C.tf["M1"]
    C.tf["M1f"] = dict(m1, piv=zigzag(m1["R"]["h"], m1["R"]["lo"], m1["R"]["atr"], M1F_K))
    rng = np.random.default_rng(19)
    learn = np.asarray((T.kind == "snap") & (pd.DatetimeIndex(T.t_dec) < plib.EXAM_START))
    out = HERE / "png" / "zoom_audit"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for tf in TFS:
        cand = np.nonzero(learn & (T[f"{tf}_zoomed"].to_numpy() == 1))[0]
        print(tf, "zoomed snaps in the learning half:", len(cand), flush=True)
        for e in rng.choice(cand, size=min(2 if tf in ("M15", "M5") else 1, len(cand)), replace=False):
            t_dec = pd.Timestamp(T.t_dec.iloc[e])
            big, sm = C.tf[tf], C.tf[SMALLER[tf]]
            bi = int(np.searchsorted(big["avail"], t_dec.as_unit("ns").value, side="right")) - 1
            close = float(big["R"]["c"][bi])
            s0, s1 = small_span(big["avail"], sm["avail"], bi, WIN)
            fig, axes = plt.subplots(1, 2, figsize=(19, 6.5), gridspec_kw={"width_ratios": (1, 1.6)})
            own = panel(axes[0], big, max(bi - WIN + 1, 0), bi, close, f"{tf}: its own 120 bars")
            small = "M1 with a finer ZigZag (1.5 ATR)" if tf == "M1" else SMALLER[tf]
            got = panel(axes[1], sm, s0, s1, close, f"{small}: the same span ({s1 - s0 + 1} bars)")
            stored = (int(T[f"{tf}_struct"].iloc[e]), int(T[f"{tf}_brk"].iloc[e]))
            want = (got[0] if own[0] == 9 else own[0], got[1] if own[1] == 9 else own[1])
            assert stored == want, (tf, e, stored, want)  # the library holds what the panels show
            when = t_dec.tz_convert(TH)
            fig.suptitle(f"The zoom at the snap {when:%Y-%m-%d %H:%M} TH ({T.name.iloc[e]}): {tf} reads "
                         f"structure {STRUCT[stored[0]]}, close {BRK[stored[1]]}  |  black: the swings known at the decision; "
                         "purple star: the swing still forming; red / green dashed: the last confirmed top / bottom; blue "
                         "dotted: the close", fontsize=9)
            fig.tight_layout(rect=(0, 0, 1, 0.95))
            f = out / f"{n:02d}_{tf}_{when:%Y%m%d_%H%M}.png"
            fig.savefig(f, dpi=64)
            plt.close(fig)
            print(f, flush=True)
            n += 1


if __name__ == "__main__":
    main()
