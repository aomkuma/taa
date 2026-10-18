"""Me trading by eye on the latest six months (notes.md "Me trading by eye", written before any decision). For each
trading day of the exam, the New York 09:30 moment of the present library: H1, M5 and M1 - the 120 bars closed by the
decision, candles only, no date, nothing after it - and the library's evidence; four moments a picture. My decisions
go to by_eye_decisions.csv before any outcome is read; `by_eye.py score` then compares them with the bot.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/by_eye.py [score]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def moments(bot: bool = False) -> tuple[pd.DataFrame, np.ndarray]:
    """The New York 09:30 moments of the exam; with bot=True a random 160 of the bot's exam trades (present_wf.py)."""
    import plib  # noqa: PLC0415

    P = pd.read_parquet(HERE / "present_3y.parquet")
    t = pd.DatetimeIndex(P.t_dec)
    if bot:
        W = pd.read_parquet(HERE / "present_wf_trades.parquet")
        W = W[(W.t >= plib.EXAM_START) & (W.t < plib.EXAM_END)]
        return P, np.sort(np.random.default_rng(160).choice(W.row.to_numpy(), size=160, replace=False))
    k = np.asarray((t >= plib.EXAM_START) & (t < plib.EXAM_END) & (t.hour == 13) & (t.minute == 30)) & P.buy_R.notna().to_numpy()
    return P, np.nonzero(k)[0]


def draw(bot: bool = False) -> None:
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    import plib  # noqa: PLC0415
    from bot_eye import make_bars  # noqa: PLC0415

    P, rows = moments(bot)
    E = pd.read_parquet(HERE / "present_evidence.parquet")
    ev = {(r.layer, r.level, r.row): (r.n, r.mb, r.ms) for r in E.itertuples() if r.row in set(rows)}
    m1 = plib.load()
    bars = {tf: make_bars(m1, tf) for tf in ("H1", "M5", "M1")}
    out = HERE / "png" / ("by_eye_bot" if bot else "by_eye")
    out.mkdir(parents=True, exist_ok=True)
    for g in range(0, len(rows), 4):
        fig, axes = plt.subplots(4, 3, figsize=(21, 18))
        for i, e in enumerate(rows[g:g + 4]):
            t = pd.Timestamp(P.t_dec.iloc[e]).as_unit("ns").value
            for j, tf in enumerate(("H1", "M5", "M1")):
                ax = axes[i, j]
                b = bars[tf]
                bi = int(np.searchsorted(b.done.to_numpy(), t, side="right")) - 1
                w = b.iloc[max(bi - 119, 0):bi + 1]
                x = np.arange(len(w))
                o, h, lo, c = (w[k].to_numpy() for k in ("open", "high", "low", "close"))
                up = c >= o
                for msk, col in ((up, "#1a9b77"), (~up, "#d6492f")):
                    ax.vlines(x[msk], lo[msk], h[msk], color=col, linewidth=0.6)
                    ax.vlines(x[msk], np.minimum(o, c)[msk], np.maximum(o, c)[msk], color=col, linewidth=1.6)
                ax.axhline(c[-1], color="#3b6fd8", linewidth=0.6, linestyle=":")
                ax.grid(alpha=0.25)
                ax.tick_params(labelsize=7)
                ax.set_xticks([0, 40, 80, 119])
                title = f"#{g + i + 1} {tf} (close {c[-1]:.2f})"
                if j == 0:
                    tl, cl = ev[("trg", "L6", e)], ev[("ctx", "L3", e)]
                    title += (f" | library: trigger L6 {tl[0]:.0f} days buy {tl[1]:+.2f} sell {tl[2]:+.2f}; context L3 "
                              f"{cl[0]:.0f} days buy {cl[1]:+.2f} sell {cl[2]:+.2f}")
                ax.set_title(title, fontsize=8.5, loc="left")
        fig.tight_layout()
        f = out / f"{g // 4:02d}.png"
        fig.savefig(f, dpi=62)
        plt.close(fig)
        print(f, flush=True)
    print(len(rows), "moments")


if __name__ == "__main__":
    draw(bot=sys.argv[1:] == ["bot"])
