"""Clean charts for reading by eye (owner, 2026-10-19: "make yourself the bot - check the pictures"): for a random
sample of the present library's moments, M5 and M1 - the 120 bars closed by the decision, candles only, nothing the
bot measured drawn on them - so the reading by eye is written down first and compared with the bot's afterwards
(`eye_check.py compare`).

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/eye_check.py
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
from bot_eye import make_bars  # noqa: E402
import plib  # noqa: E402

PICK_SEED, N = 77, 6


def main() -> None:
    P = pd.read_parquet(HERE / "present_3y.parquet")
    pick = np.sort(np.random.default_rng(PICK_SEED).choice(len(P), size=N, replace=False))
    m1 = plib.load()
    bars = {tf: make_bars(m1, tf) for tf in ("M5", "M1")}
    out = HERE / "png" / "eye_check"
    out.mkdir(parents=True, exist_ok=True)
    for n, e in enumerate(pick):
        t = pd.Timestamp(P.t_dec.iloc[e])
        fig, axes = plt.subplots(1, 2, figsize=(19, 6))
        for ax, tf in zip(axes, ("M5", "M1")):
            b = bars[tf]
            bi = int(np.searchsorted(b.done.to_numpy(), t.as_unit("ns").value, side="right")) - 1
            w = b.iloc[max(bi - 119, 0):bi + 1]
            x = np.arange(len(w))
            o, h, lo, c = (w[k].to_numpy() for k in ("open", "high", "low", "close"))
            up = c >= o
            for msk, col in ((up, "#1a9b77"), (~up, "#d6492f")):
                ax.vlines(x[msk], lo[msk], h[msk], color=col, linewidth=0.6)
                ax.vlines(x[msk], np.minimum(o, c)[msk], np.maximum(o, c)[msk], color=col, linewidth=1.8)
            ax.set_xticks([0, 40, 80, 119])
            ax.grid(alpha=0.25)
            ax.set_title(f"{tf}: the 120 bars closed by the decision (the last close {c[-1]:.2f})", fontsize=9, loc="left")
        fig.suptitle(f"Moment {n + 1}: {t.tz_convert('Asia/Bangkok'):%Y-%m-%d %H:%M} TH", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        f = out / f"{n:02d}.png"
        fig.savefig(f, dpi=64)
        plt.close(fig)
        print(f, flush=True)


def compare() -> None:
    P = pd.read_parquet(HERE / "present_3y.parquet")
    pick = np.sort(np.random.default_rng(PICK_SEED).choice(len(P), size=N, replace=False))
    for n, e in enumerate(pick):
        for tf in ("M5", "M1"):
            r = {k: P[f"{tf}_{k}"].iloc[e] for k in ("net_way", "seg0", "seg1", "seg2", "struct", "brk", "pos", "leg_way")}
            print(f"moment {n + 1} {tf}: way {int(r['net_way']):+d}, thirds {int(r['seg0']):+d}/{int(r['seg1']):+d}/"
                  f"{int(r['seg2']):+d}, structure {int(r['struct'])}, close vs last top/bottom {int(r['brk']):+d}, position "
                  f"{r['pos']:.2f}, last leg {int(r['leg_way']):+d}")


if __name__ == "__main__":
    compare() if sys.argv[1:] == ["compare"] else main()
