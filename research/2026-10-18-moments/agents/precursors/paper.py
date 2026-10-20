"""Paper trading the rule by hand (owner, 2026-10-19: "try what you propose, but paper trade it yourself first"): the
rule - with the H1 trend (the 120 bars' way and the swing structure agree), after M5 has pulled back against it (M5's
last leg against the trend, the close not at the trend-side extreme), when M1 turns the trend's way (M1's last leg
with it). A scanner lists the moments where the readings fit (5-minute moments inside the windows, 30 minutes apart);
I look at each (H1, M5, M1 - nothing after it) and decide take / skip and the side, written to paper_decisions.csv
before any outcome is read; the trade is V2's (the labels), one position at a time; `paper.py score` reads it back.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/paper.py draw START END
    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/paper.py score START END
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def candidates(P: pd.DataFrame, start: str, end: str) -> tuple[np.ndarray, np.ndarray]:
    """The scanner: (rows, the trend side) 30 minutes apart between start and end."""
    t = pd.DatetimeIndex(P.t_dec)
    win = np.asarray((t >= pd.Timestamp(start, tz="UTC")) & (t < pd.Timestamp(end, tz="UTC"))) & P.buy_R.notna().to_numpy()
    side = np.where((P.H1_net_way == P.H1_struct) & (P.H1_net_way != 0), P.H1_net_way, 0).astype(int)
    pull = ((P.M5_leg_way == -side) & np.where(side > 0, P.M5_pos <= 0.6, P.M5_pos >= 0.4)).to_numpy()
    turn = (P.M1_leg_way == side).to_numpy()
    keep, last = [], None
    for r in np.nonzero(win & (side != 0) & pull & turn)[0]:
        if last is None or t[r] - t[last] >= pd.Timedelta(minutes=30):
            keep.append(r)
            last = r
    keep = np.array(keep, int)
    return keep, side[keep]


def draw(start: str, end: str) -> None:
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    import plib  # noqa: PLC0415
    from bot_eye import make_bars  # noqa: PLC0415

    P = pd.read_parquet(HERE / "present_3y.parquet")
    rows, side = candidates(P, start, end)
    m1 = plib.load()
    bars = {tf: make_bars(m1, tf) for tf in ("H1", "M5", "M1")}
    out = HERE / "png" / f"paper_{start}"
    out.mkdir(parents=True, exist_ok=True)
    for g in range(0, len(rows), 4):
        fig, axes = plt.subplots(4, 3, figsize=(21, 18))
        for i in range(4):
            if g + i >= len(rows):
                for ax in axes[i]:
                    ax.axis("off")
                continue
            e = rows[g + i]
            t = pd.Timestamp(P.t_dec.iloc[e])
            for j, tf in enumerate(("H1", "M5", "M1")):
                ax = axes[i, j]
                b = bars[tf]
                bi = int(np.searchsorted(b.done.to_numpy(), t.as_unit("ns").value, side="right")) - 1
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
                    title += f" | {t.tz_convert('Asia/Bangkok'):%a %d %b %H:%M} TH | the scanner's side: {'BUY' if side[g + i] > 0 else 'SELL'}"
                ax.set_title(title, fontsize=8.5, loc="left")
        fig.tight_layout()
        f = out / f"{g // 4:02d}.png"
        fig.savefig(f, dpi=62)
        plt.close(fig)
        print(f, flush=True)
    print(len(rows), "candidates")


def score(start: str, end: str) -> None:
    import wf  # noqa: PLC0415

    P = pd.read_parquet(HERE / "present_3y.parquet")
    rows, side = candidates(P, start, end)
    D = pd.read_csv(HERE / f"paper_decisions_{start}.csv")
    assert len(D) == len(rows) and (D.n.to_numpy() == np.arange(1, len(rows) + 1)).all()
    col = {1: "buy", -1: "sell"}
    busy, out = -1, []
    for n, (r, s_scan) in enumerate(zip(rows, side)):
        s = int(D.side.iloc[n])
        if s == 0 or P.j0.iloc[r] <= busy:
            continue
        out.append(dict(n=n + 1, t=pd.Timestamp(P.t_dec.iloc[r]), side=s, scanner=int(s_scan), R=P[f"{col[s]}_R"].iloc[r],
                        pnl=P[f"{col[s]}_pnl"].iloc[r], exit=P[f"{col[s]}_exit"].iloc[r]))
        busy = int(P[f"{col[s]}_xj"].iloc[r])
    T = pd.DataFrame(out)
    print(f"my paper trades {start} .. {end}: {len(T)} trades, win {(T.pnl > 0).mean():.3f}, R {T.R.mean():+.3f}, USD {T.pnl.sum():+.1f}, "
          f"worst {T.pnl.min():+.2f}, longest losing streak {wf.longest_run(T.pnl.to_numpy() < 0)}")
    print(T.to_string(index=False))
    T.to_csv(HERE / f"paper_trades_{start}.csv", index=False)


if __name__ == "__main__":
    {"draw": draw, "score": score}[sys.argv[1]](sys.argv[2], sys.argv[3])
