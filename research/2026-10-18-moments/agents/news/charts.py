"""Charts of the test trades (learn like a trader): S2 on ticks (-20 s .. +180 s), P1 on M1 (14:00 .. 17:00 ET).

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/news/charts.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path("research/2026-10-18-moments/agents/news")
OUT = HERE / "charts"
OUT.mkdir(exist_ok=True)


def s2() -> None:
    d = pd.read_parquet(HERE / "s2_ticks_test_h60_d2.parquet")
    d = d[d.who == "rule"]
    fig, axes = plt.subplots(4, 4, figsize=(20, 15))
    for ax, r in zip(axes.flat, d.itertuples(), strict=False):
        t = pd.read_parquet(f"data/ticks/XAUUSD/{r.t.strftime('%Y-%m-%d')}.parquet")
        t["ts"] = pd.to_datetime(t.time_utc, utc=True)
        w = t[(t.ts >= r.t - pd.Timedelta(seconds=20)) & (t.ts < r.t + pd.Timedelta(seconds=180))]
        sec = (w.ts - r.t).dt.total_seconds()
        ax.plot(sec, w.bid, lw=0.8, color="tab:blue")
        ref = w[sec < 0].bid.iloc[-1]
        k = ref / 4000
        ax.axhline(ref + 2 * k, color="green", ls=":", lw=0.8)
        ax.axhline(ref - 2 * k, color="red", ls=":", lw=0.8)
        entry = ref + r.side * (2 * k + r.gap)
        ax.scatter([r.fill_s], [entry], color="green" if r.side > 0 else "red", zorder=3)
        ax.axhline(entry - r.side * r.sl, color="black", ls="--", lw=0.7)
        ax.axvline(60, color="grey", lw=0.7)
        ax.set_title(f"{r.t:%Y-%m-%d} {r.main} {'BUY' if r.side > 0 else 'SELL'} {r.usd:+.1f} ({r.exit})", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "s2_test.png", dpi=70)


def p1() -> None:
    import sys

    sys.path.insert(0, "research/2026-10-18-moments")
    import gold

    m = gold.bars("M1")
    d = pd.read_parquet(HERE / "cand_test.parquet")
    d = d[(d.rule == "P1") & (d.who == "rule")]
    fig, axes = plt.subplots(1, len(d), figsize=(5 * len(d), 4.5))
    for ax, r in zip(axes, d.itertuples(), strict=False):
        t30 = r.t
        w = m[(m.index >= t30 - pd.Timedelta(minutes=40)) & (m.index < t30 + pd.Timedelta(minutes=140))]
        mins = (w.index - t30).total_seconds() / 60
        ax.vlines(mins, w.low, w.high, color="grey", lw=0.6)
        ax.plot(mins, w.close, lw=0.8)
        e = w.index.get_loc(t30 + pd.Timedelta(minutes=10))
        entry = w.open.iloc[e]
        ax.scatter([10], [entry], color="green" if r.side > 0 else "red", zorder=3)
        ax.axhline(entry - r.side * r.sl, color="black", ls="--", lw=0.7)
        ax.axvline(-30, color="orange", lw=0.7)
        ax.axvline(0, color="purple", lw=0.7)
        ax.set_title(f"{t30:%Y-%m-%d} {'BUY' if r.side > 0 else 'SELL'} {r.usd:+.1f} ({r.exit})", fontsize=10)
        ax.set_xlabel("minutes from the presser (14:30 ET); orange = statement")
    fig.tight_layout()
    fig.savefig(OUT / "p1_test.png", dpi=70)


if __name__ == "__main__":
    s2()
    p1()
