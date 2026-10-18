"""Charts of OWN-RT trades (round 13) for the eye check: M1 from 2 h before the break to 2 h after the entry, the
broken level L, the impulse extreme, the entry / stop / target, and the H1 context.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/rt_charts.py N
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

TH = "Asia/Bangkok"
OUT = "research/2026-10-18-moments/shadow/rt"


def candles(ax, d: pd.DataFrame, width: float) -> None:
    for t, r in d.iterrows():
        col = "tab:green" if r.close >= r.open else "tab:red"
        ax.vlines(t, r.low, r.high, color=col, lw=0.7)
        ax.vlines(t, min(r.open, r.close), max(r.open, r.close), color=col, lw=width)


def main() -> None:
    import os

    os.makedirs(OUT, exist_ok=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    m1 = gold.bars("M1")
    m1 = m1[m1.index >= pd.Timestamp("2026-02-20", tz="UTC")]
    z = pd.read_parquet("data/research/own_rt_test.parquet")
    z["t"] = pd.to_datetime(z.t, utc=True)
    pick = pd.concat([z[z.exit == "stop"].iloc[:: max(1, len(z[z.exit == "stop"]) // n)].head(n), z[z.exit == "win"].head(3)])
    for k, r in enumerate(pick.itertuples()):
        s = int(r.side)
        fig = plt.figure(figsize=(15, 7))
        a1 = fig.add_axes([0.04, 0.08, 0.62, 0.84])
        a2 = fig.add_axes([0.70, 0.08, 0.28, 0.84])
        w = m1.loc[r.t - pd.Timedelta(minutes=150): r.t + pd.Timedelta(minutes=120)]
        w = w.set_index(w.index.tz_convert(TH))
        candles(a1, w, 2.5)
        te = r.t.tz_convert(TH)
        a1.axvline(te, color="k", lw=0.6)
        a1.axhline(r.L, color="tab:blue", lw=1, ls="--", label=f"broken level L {r.L:.2f}")
        a1.axhline(r.imp, color="tab:purple", lw=0.8, ls=":", label=f"impulse extreme {r.imp:.2f}")
        a1.axhline(r.entry, color="k", lw=1, label=f"entry {r.entry:.2f}")
        a1.axhline(r.entry - s * r.sl, color="tab:red", lw=1, label="stop")
        a1.axhline(r.entry + s * r.tp, color="tab:green", lw=1, label="target")
        a1.legend(fontsize=7, loc="upper left")
        a1.set_title(f"OWN-RT {te:%Y-%m-%d %H:%M} Thai {'BUY' if s > 0 else 'SELL'} -> {r.exit} {r.pnl:+.2f} USD (kind {r.kind or '-'})", fontsize=10)
        h1 = m1.resample("60min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        w1 = h1.loc[r.t - pd.Timedelta(hours=60): r.t + pd.Timedelta(hours=4)]
        w1 = w1.set_index(w1.index.tz_convert(TH))
        candles(a2, w1, 2)
        a2.plot(w1.index, h1.close.ewm(span=20).mean().loc[w1.index.tz_convert("UTC")].to_numpy(), lw=0.8, label="EMA20")
        a2.plot(w1.index, h1.close.ewm(span=50).mean().loc[w1.index.tz_convert("UTC")].to_numpy(), lw=0.8, label="EMA50")
        a2.axvline(te, color="k", lw=0.6)
        a2.legend(fontsize=7)
        a2.set_title("H1, 60 h", fontsize=9)
        fig.savefig(f"{OUT}/{k:02d}_{r.exit}.png", dpi=100)
        plt.close(fig)
    print(len(pick), "charts")


if __name__ == "__main__":
    main()
