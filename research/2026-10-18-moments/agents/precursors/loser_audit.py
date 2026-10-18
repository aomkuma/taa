"""V2s's losing trades by eye (owner, 2026-10-19: "before fixing - is the picture the bot sees right, and is its
reading right? Something must still be wrong"). For a sample of the exam's losers (each of the owner's three kinds):
the M5 and M1 pictures at the decision with the bot's stored readings (moments_3y.parquet, the zoom included), what
happened next on M1 (the entry, the stop, the target, the exit), and two of the earlier days the bot counted as the
same situation (its evidence) with what followed them.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/loser_audit.py
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
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import plib  # noqa: E402
from picture import EPISODE_DAYS, KEYS, as_arrays  # noqa: E402
from rarity import part_masks, thirds  # noqa: E402
from reading_audit import ARROW, BRK, STRUCT, WAY, draw  # noqa: E402
from v2_loser_kinds import kind_of  # noqa: E402
from v2s import LEVELS, TRG  # noqa: E402
from wf_library_compare import Charts  # noqa: E402

TH = "Asia/Bangkok"


def stored_title(T: pd.DataFrame, row: int, tf: str, extra: str = "") -> str:
    f = {k: T[f"{tf}_{k}"].iloc[row] for k in KEYS}
    z = " (read from the smaller TF)" if int(T[f"{tf}_zoomed"].iloc[row]) else ""
    return (f"{tf}{extra}: {WAY[int(f['net_way'])]} (thirds {'/'.join(ARROW[int(f[f'seg{j}'])] for j in range(3))}), "
            f"{STRUCT[int(f['struct'])]}{z}, close {BRK[int(f['brk'])]}\nsize {f['size']:.0f} ATR, at {f['pos']:.2f} of "
            f"the range, last leg {ARROW.get(int(f['leg_way']), '?')} {f['leg']:.1f} ATR, deepest pullback {f['retr']:.1f} "
            f"ATR, smoothness {f['er']:.2f}")


def main() -> None:
    import jlib  # noqa: PLC0415
    from v2b import TFS  # noqa: PLC0415

    T = pd.read_parquet(HERE / "moments_3y.parquet")
    SH = np.load(HERE / "moment_shapes_3y.npy").astype(float)
    W = pd.read_parquet(HERE / "v2s_wf_trades.parquet")
    m = jlib.m1_frame("XAUUSD")
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    C = Charts(plib.load())
    t = pd.DatetimeIndex(T.t_dec)
    day0 = pd.Timestamp("2000-01-01", tz=TH)
    day = ((t.tz_convert(TH).normalize() - day0).days).to_numpy()
    A = as_arrays([[{k: T[f"{tf}_{k}"].iloc[i] for k in KEYS} for tf in TRG] for i in range(len(T))])
    shp = SH[:, [TFS.index(tf) for tf in TRG]]
    segs = thirds(shp)
    ex = W[(W.t >= plib.EXAM_START) & (W.pnl < 0)].copy()
    kinds = []
    for r in ex.itertuples():
        entry = o[r.j0] + sp[r.j0] + 0.07 if r.side > 0 else o[r.j0] - 0.07
        kinds.append(kind_of(h, lo, sp, int(r.j0), int(r.xj), int(r.side), entry, float(r.tp))["kind"] if r.exit == "stop"
                     else "time exit at a loss")
    ex["kind"] = kinds
    rng = np.random.default_rng(31)
    pick = []
    for k, nmax in (("1 wrong way", 3), ("3 entered too early", 3), ("2 fell short", 2)):
        cand = np.nonzero((ex.kind == k).to_numpy())[0]
        pick += list(rng.choice(cand, size=min(nmax, len(cand)), replace=False))
    out = HERE / "png" / "loser_audit"
    out.mkdir(parents=True, exist_ok=True)
    for n, i in enumerate(pick):
        r = ex.iloc[i]
        row, level = int(r.row), r.cell.split("_")[0]
        t_dec = pd.Timestamp(T.t_dec.iloc[row])
        # the evidence: the earlier moments (>= 7 days before) in the same M5 + M1 situation, each day's first
        cand = np.nonzero(day <= day[row] - EPISODE_DAYS)[0]
        mk = part_masks(A, shp, segs, row, cand)
        acc = np.logical_and.reduce([mk[p].all(axis=1) for p in LEVELS[level]])
        hits = cand[acc]
        _, first = np.unique(day[hits], return_index=True)
        ev = hits[first]
        assert len(ev) == int(r.n_days), (row, len(ev), r.n_days)  # the same evidence as the trade's record
        show = ev[-2:]  # the two latest
        fig = plt.figure(figsize=(20, 17))
        gs = fig.add_gridspec(3, 2, height_ratios=(1, 0.8, 1))
        for j, tf in enumerate(TRG):
            ax = fig.add_subplot(gs[0, j])
            draw(ax, C, tf, t_dec)
            ax.set_title(stored_title(T, row, tf, " - what the bot saw"), fontsize=8, loc="left")
        # what happened next on M1
        ax = fig.add_subplot(gs[1, :])
        j0, xj = int(r.j0), int(r.xj)
        a0, a1 = max(j0 - 45, 0), min(xj + 30, len(o) - 1)
        x = np.arange(a1 - a0 + 1)
        oo, hh, ll, cc = o[a0:a1 + 1], h[a0:a1 + 1], lo[a0:a1 + 1], c[a0:a1 + 1]
        up = cc >= oo
        for msk, col in ((up, "#1a9b77"), (~up, "#d6492f")):
            ax.vlines(x[msk], ll[msk], hh[msk], color=col, linewidth=0.7)
            ax.vlines(x[msk], np.minimum(oo, cc)[msk], np.maximum(oo, cc)[msk], color=col, linewidth=2.2)
        entry = o[j0] + sp[j0] + 0.07 if r.side > 0 else o[j0] - 0.07
        for y, col, lab in ((entry, "#3b6fd8", "entry"), (entry - r.side * r.sl, "#d6492f", "stop"),
                            (entry + r.side * r.tp, "#1a9b77", "target")):
            ax.axhline(y, color=col, linestyle="--", linewidth=1.0)
            ax.text(x[-1], y, f" {lab} {y:.2f}", color=col, fontsize=8, va="center")
        ax.axvline(j0 - a0 - 0.5, color="#555", linewidth=0.8)
        ax.plot(xj - a0, (entry + r.pnl * r.side) if r.exit != "stop" else entry - r.side * r.sl, "x", color="#111", markersize=10)
        ax.set_title(f"M1 around the trade: {'BUY' if r.side > 0 else 'SELL'} at {entry:.2f}, stop {r.sl:.2f} USD ({r.etf} ATR), "
                     f"target {r.tp:.2f} USD, out by {r.exit} after {xj - j0 + 1} min, {r.pnl:+.2f} USD | the vertical line: the "
                     "decision", fontsize=9, loc="left")
        ax.set_xticks([])
        for j, e in enumerate(show):
            ax = fig.add_subplot(gs[2, j])
            draw(ax, C, "M5", pd.Timestamp(T.t_dec.iloc[e]))
            when = pd.Timestamp(T.t_dec.iloc[e]).tz_convert(TH)
            ax.set_title(stored_title(T, int(e), "M5", f" - the evidence {when:%Y-%m-%d %H:%M} TH ({T.kind.iloc[e]}), what "
                                      f"followed: {T.cls.iloc[e]}"), fontsize=8, loc="left")
        when = t_dec.tz_convert(TH)
        evc = pd.Series(T.cls.to_numpy()[ev]).value_counts().to_dict()
        fig.suptitle(f"Exam loser {n + 1}: {when:%Y-%m-%d %H:%M} TH ({r.snap}) - {r.kind} | cell {r.cell}: {int(r.n_days)} earlier "
                     f"days in the same situation, lean {r.lean:+.2f} ({evc})", fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        f = out / f"{n:02d}_{r.kind[0]}_{when:%Y%m%d_%H%M}.png"
        fig.savefig(f, dpi=60)
        plt.close(fig)
        print(f, flush=True)


if __name__ == "__main__":
    main()
