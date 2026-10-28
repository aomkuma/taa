"""M1 candle charts around runs or trades (a grid of panels per PNG).

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/runs/charts.py runs R SEED N OUT
    data/venv-research/Scripts/python research/2026-10-18-moments/agents/runs/charts.py trades FILE.parquet N OUT [SEED]
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
sys.path.insert(0, str(HERE.parents[1]))
import gold  # noqa: E402

THAI = pd.Timedelta(hours=7)


def candles(ax, d: pd.DataFrame) -> None:
    x = np.arange(len(d))
    up = d.close >= d.open
    ax.vlines(x, d.low, d.high, color="#555", lw=0.6)
    ax.bar(x[up], (d.close - d.open)[up], bottom=d.open[up], color="#2a9d8f", width=0.7)
    ax.bar(x[~up], (d.open - d.close)[~up], bottom=d.close[~up], color="#e76f51", width=0.7)
    ticks = x[:: max(1, len(x) // 6)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([(d.index[i] + THAI).strftime("%H:%M") for i in ticks], fontsize=6)
    ax.tick_params(axis="y", labelsize=6)


def panel(ax, m: pd.DataFrame, t0: pd.Timestamp, before: int, after: int, title: str, marks: list) -> None:
    d = m[(m.index >= t0 - pd.Timedelta(minutes=before)) & (m.index <= t0 + pd.Timedelta(minutes=after))]
    candles(ax, d)
    for kind, t, y, col in marks:
        if kind == "v":
            k = d.index.searchsorted(t)
            ax.axvline(k, color=col, lw=0.8, ls="--")
        elif kind == "h":
            ax.axhline(y, color=col, lw=0.8, ls=":")
        elif kind == "pt":
            k = d.index.searchsorted(t)
            ax.plot([k], [y], marker="o", ms=3, color=col)
    ax.set_title(title, fontsize=7)


def main() -> None:
    m = gold.bars("M1")
    m = m[m.index >= pd.Timestamp("2023-10-01", tz="UTC")][["open", "high", "low", "close"]]
    mode = sys.argv[1]
    if mode == "runs":
        R, seed, n, out = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
        C = pd.read_parquet(HERE / "catalogue.parquet")
        C = C[(C.R == R) & (C.part == "design") & (C.t.dt.hour < 20)].sample(n, random_state=seed).sort_values("t")
        rows = [(r.t, f"{'UP' if r.side > 0 else 'DOWN'} {r.size:.1f} in {r.dur}m  {(r.t + THAI):%Y-%m-%d %H:%M} TH",
                 [("v", r.t, None, "blue"), ("pt", r.t_ext, r.start_px + r.side * r.size, "blue")]) for r in C.itertuples()]
        before, after = 120, 60
    else:
        f, n, out = sys.argv[2], int(sys.argv[3]), sys.argv[4]
        seed = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        T = pd.read_parquet(f)
        if len(T) > n:
            T = T.sample(n, random_state=seed)
        T = T.sort_values("t")
        rows = []
        for r in T.itertuples():
            col = "green" if r.pnl > 0 else "red"
            lab = f"{'BUY' if r.side > 0 else 'SELL'} {r.exit} {r.pnl:+.1f}  {(r.t + THAI):%Y-%m-%d %H:%M} TH"
            if hasattr(r, "why"):
                lab += f"\n{r.why}"
            mk = [("v", r.t, None, col), ("h", None, r.entry, "black"), ("h", None, r.entry - r.side * r.sl, "red"),
                  ("h", None, r.entry + r.side * r.tp, "green")]
            if hasattr(r, "lvl") and np.isfinite(r.lvl):
                mk.append(("h", None, r.lvl, "purple"))
            rows.append((r.t, lab, mk))
        before, after = 120, 90
    k = len(rows)
    cols = 3
    fig, axes = plt.subplots((k + cols - 1) // cols, cols, figsize=(15, 3.2 * ((k + cols - 1) // cols)))
    for ax, (t, title, mk) in zip(np.ravel(axes), rows, strict=False):
        panel(ax, m, t, before, after, title, mk)
    for ax in np.ravel(axes)[k:]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out, dpi=90)
    print(out)


if __name__ == "__main__":
    main()
