"""One picture per decision minute: H4, H1, M30 / M15, M5, M1 with EMA20 / EMA50 and the fractal swings, the
decision marked (dashed), the bars after it shaded (the future: only M5 / M1 show it)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import plib  # noqa: E402

PANELS = [("H4", "4h", 120, 0), ("H1", "1h", 120, 0), ("M30", "30min", 120, 0), ("M15", "15min", 120, 2),
          ("M5", "5min", 120, 6), ("M1", None, 120, 30)]


def candles(ax, b: pd.DataFrame, future_from: int) -> None:
    x = np.arange(len(b))
    o, h, lo, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    up = c >= o
    fut = x >= future_from
    for mask, col in ((up & ~fut, "#1a9b77"), (~up & ~fut, "#d6492f"), (fut, "#b8b8b8")):
        ax.vlines(x[mask], lo[mask], h[mask], color=col, linewidth=0.7)
        ax.vlines(x[mask], np.minimum(o, c)[mask], np.maximum(o, c)[mask], color=col, linewidth=2.6)


def panel(ax, name: str, b: pd.DataFrame, n_past: int, n_fut: int, t_dec: pd.Timestamp) -> None:
    past = b[b["avail"] <= t_dec]
    fut = b[b["avail"] > t_dec].head(n_fut)
    full = pd.concat([past, fut])
    cs = full.close
    e20 = cs.ewm(span=20, adjust=False).mean()
    e50 = cs.ewm(span=50, adjust=False).mean()
    show = pd.concat([past.tail(n_past), fut])
    k0 = len(full) - len(show)
    candles(ax, show, len(past.tail(n_past)))
    x = np.arange(len(show))
    ax.plot(x, e20.iloc[k0:].to_numpy(), color="#3b6fd8", linewidth=0.8)
    ax.plot(x, e50.iloc[k0:].to_numpy(), color="#9a59c9", linewidth=0.8)
    # confirmed fractal swings (3 each side) as of the decision
    h, lo = past.high.to_numpy(), past.low.to_numpy()
    ph, pl = plib.pivots(h, lo, 3)
    off = len(past) - len(past.tail(n_past))
    for p in ph:
        if p + 3 < len(past) and p >= off:
            ax.plot(p - off, h[p], "v", color="#555", markersize=3)
    for p in pl:
        if p + 3 < len(past) and p >= off:
            ax.plot(p - off, lo[p], "^", color="#555", markersize=3)
    ax.axvline(len(past.tail(n_past)) - 0.5, color="k", linestyle="--", linewidth=0.7)
    ax.set_title(name, fontsize=8, loc="left")
    ax.tick_params(labelsize=6)
    ax.set_xticks([])


def draw(m: pd.DataFrame, t_bar: pd.Timestamp, path, title: str) -> None:
    """t_bar = the decision M1 bar's open time (the decision at its close)."""
    t_dec = t_bar + pd.Timedelta(minutes=1)
    sl = m[(m.index >= t_bar - pd.Timedelta(days=45)) & (m.index <= t_bar + pd.Timedelta(hours=3))]
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.2))
    for ax, (name, rule, n_past, n_fut) in zip(axes.ravel(), PANELS):
        if rule is None:
            b = sl[sl.index >= t_bar - pd.Timedelta(hours=6)].rename(columns={"tick_volume": "tv"}).copy()
            b["avail"] = b.index + pd.Timedelta(minutes=1)
            b = b.reset_index(drop=True)
        else:
            b = plib.tf_bars(sl, rule)
        panel(ax, name, b, n_past, n_fut, t_dec)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)
