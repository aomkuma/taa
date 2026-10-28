"""Pictures of LV cases for the eye check (design): H1 (the trend), M5 (the swings, the start T, the level L) and M1 (the
entry, stop, target, exit), Thai time.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/lvl_pics.py lvl_design_stall_0.5_T1.parquet 12
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
import jlib  # noqa: E402
import plib  # noqa: E402

TH = "Asia/Bangkok"


def candles(ax, t, o, h, lo, c, w):
    up = c >= o
    for m, col in ((up, "#1a9b77"), (~up, "#d6492f")):
        ax.vlines(t[m], lo[m], h[m], color=col, lw=0.7)
        ax.vlines(t[m], np.minimum(o, c)[m], np.maximum(o, c)[m], color=col, lw=w)


def main() -> None:
    f, n = sys.argv[1], int(sys.argv[2])
    T = pd.read_parquet(HERE / f)
    m = jlib.m1_frame("XAUUSD")
    out = HERE / "png" / "lvl" / f.replace(".parquet", "")
    out.mkdir(parents=True, exist_ok=True)
    pick = T.sample(min(n, len(T)), random_state=11).sort_values("t")
    for i, r in enumerate(pick.itertuples()):
        t_dec = r.t + pd.Timedelta(minutes=1)
        sl_ = m[(m.index >= t_dec - pd.Timedelta(days=4)) & (m.index <= t_dec + pd.Timedelta(hours=3))]
        fig, axes = plt.subplots(1, 3, figsize=(17, 4.6), gridspec_kw={"width_ratios": [1, 1.3, 1.3]})
        for ax, rule, back, fwd, w in ((axes[0], "1h", pd.Timedelta(days=3), pd.Timedelta(0), 2.0),
                                       (axes[1], "5min", pd.Timedelta(hours=9), pd.Timedelta(hours=1), 1.6),
                                       (axes[2], None, pd.Timedelta(hours=1.5), pd.Timedelta(hours=1.5), 1.2)):
            if rule:
                b = plib.tf_bars(sl_, rule)
                b = b[(b["last"] >= t_dec - back) & (b["last"] < t_dec + fwd)]
                tt = (b["last"] - pd.Timedelta(rule) + pd.Timedelta(minutes=1)).dt.tz_convert(TH)
            else:
                b = sl_[(sl_.index >= t_dec - back) & (sl_.index < t_dec + fwd)]
                tt = b.index.tz_convert(TH)
            x = np.arange(len(b))
            candles(ax, x, *(b[k].to_numpy(float) for k in ("open", "high", "low", "close")), w)
            cut = int(np.searchsorted(tt.to_numpy() if hasattr(tt, "to_numpy") else tt, t_dec.tz_convert(TH)))
            ax.axvline(cut - 0.5, color="k", ls="--", lw=0.8)
            ax.axhline(r.level, color="#d6492f", lw=0.9)
            ax.axhline(r.start, color="#3b6fd8", lw=0.8, ls=":")
            if rule is None:
                j0 = int(np.searchsorted(b.index, m.index[r.j0]))
                xj = int(np.searchsorted(b.index, m.index[min(r.xj, len(m) - 1)]))
                ax.axhline(r.entry, color="#555", lw=0.8)
                ax.axhline(r.entry - r.side * r.sl, color="#d6492f", lw=0.8, ls="--")
                ax.axhline(r.entry + r.side * r.tp, color="#1a9b77", lw=0.8, ls="--")
                ax.axvline(j0, color="#555", lw=0.6)
                ax.axvline(xj, color="#9a59c9", lw=0.6)
            ticks = np.linspace(0, len(b) - 1, 6).astype(int)
            ax.set_xticks(ticks)
            ax.set_xticklabels([pd.Timestamp(tt.iloc[k] if hasattr(tt, "iloc") else tt[k]).strftime("%d %H:%M")
                                for k in ticks], fontsize=6)
            ax.set_title({"1h": "H1 (trend)", "5min": "M5 (swings: blue = start T, red = level L)",
                          None: "M1 (grey entry, red dashed stop, green dashed target)"}[rule], fontsize=8, loc="left")
            ax.tick_params(labelsize=6)
        when = r.t.tz_convert(TH).strftime("%Y-%m-%d %H:%M")
        fig.suptitle(f"{when} TH  {'SELL' if r.side < 0 else 'BUY'} at level {r.lkind} {r.level:.2f} (start {r.start:.2f}), "
                     f"entry TF {r.etf}, ATR {r.atr:.1f}  ->  {r.exit} {r.pnl:+.2f} USD", fontsize=9)
        fig.tight_layout()
        fig.savefig(out / f"{i:02d}.png", dpi=72)
        plt.close(fig)
    print("saved", out)


if __name__ == "__main__":
    main()
