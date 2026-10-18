"""Charts of two losers the owner asked about (2026-10-18): F1 2026-04-08 07:03 Thai BUY and S2 CPI 2026-08-12
19:30 Thai BUY. M1 around the entry with the stop / target / exit, M5 and H1 context; for S2 also the ticks.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/two_trades.py
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

OUT = "research/2026-10-18-moments/shadow"
TH = "Asia/Bangkok"


def candles(ax, d: pd.DataFrame, width: float) -> None:
    for t, r in d.iterrows():
        col = "tab:green" if r.close >= r.open else "tab:red"
        ax.vlines(t, r.low, r.high, color=col, lw=0.8)
        ax.vlines(t, min(r.open, r.close), max(r.open, r.close), color=col, lw=width)


def chart(m1: pd.DataFrame, t_entry: pd.Timestamp, side: int, fill: float, sl: float, tp: float, title: str,
          path: str, ticks: pd.DataFrame | None = None) -> None:
    fig = plt.figure(figsize=(15, 8))
    a1 = fig.add_axes([0.05, 0.08, 0.55, 0.85])
    a2 = fig.add_axes([0.66, 0.55, 0.32, 0.38])
    a3 = fig.add_axes([0.66, 0.08, 0.32, 0.38])
    w = m1.loc[t_entry - pd.Timedelta(minutes=60): t_entry + pd.Timedelta(minutes=120)]
    w = w.set_index(w.index.tz_convert(TH))
    candles(a1, w, 3)
    te = t_entry.tz_convert(TH)
    a1.axvline(te, color="k", lw=0.6)
    a1.axhline(fill, color="k", lw=1, label=f"entry {fill:.2f}")
    a1.axhline(fill - side * sl, color="tab:red", lw=1, label=f"stop {fill - side * sl:.2f}")
    a1.axhline(fill + side * tp, color="tab:green", lw=1, label=f"target {fill + side * tp:.2f}")
    for k in (1, 2, 3):
        a1.axvline(te + pd.Timedelta(minutes=k), color="tab:blue", lw=0.5, ls=":")
    a1.legend(loc="upper left", fontsize=8)
    a1.set_title(title, fontsize=10)
    m5 = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    w5 = m5.loc[t_entry - pd.Timedelta(hours=8): t_entry + pd.Timedelta(hours=2)]
    w5 = w5.set_index(w5.index.tz_convert(TH))
    candles(a2, w5, 2)
    a2.axvline(te, color="k", lw=0.6)
    a2.axhline(fill, color="k", lw=0.6)
    a2.set_title("M5, 8 h before .. 2 h after (EMA20)", fontsize=9)
    a2.plot(w5.index, w5.close.ewm(span=20).mean(), lw=0.8)
    h1 = m1.resample("60min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    w1 = h1.loc[t_entry - pd.Timedelta(hours=72): t_entry + pd.Timedelta(hours=3)]
    e20, e50 = h1.close.ewm(span=20).mean(), h1.close.ewm(span=50).mean()
    w1 = w1.set_index(w1.index.tz_convert(TH))
    candles(a3, w1, 2)
    a3.plot(w1.index, e20.reindex(h1.loc[w1.index.tz_convert("UTC")[0]:w1.index.tz_convert("UTC")[-1]].index).to_numpy(), lw=0.8, label="EMA20")
    a3.plot(w1.index, e50.reindex(h1.loc[w1.index.tz_convert("UTC")[0]:w1.index.tz_convert("UTC")[-1]].index).to_numpy(), lw=0.8, label="EMA50")
    a3.axvline(te, color="k", lw=0.6)
    a3.legend(fontsize=7)
    a3.set_title("H1, 72 h", fontsize=9)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    if ticks is not None:
        fig, ax = plt.subplots(figsize=(12, 5))
        tk = ticks[(ticks.t >= t_entry - pd.Timedelta(seconds=30)) & (ticks.t <= t_entry + pd.Timedelta(minutes=10))]
        ax.plot((tk.t - t_entry).dt.total_seconds(), tk.bid, lw=0.6, label="bid")
        ax.axhline(fill, color="k", lw=1, label="fill")
        ax.axhline(fill - side * sl, color="tab:red", lw=1, label="stop")
        for s in (60, 120, 180):
            ax.axvline(s, color="tab:blue", lw=0.5, ls=":")
        ax.set_xlabel("seconds after 08:30:00 ET")
        ax.legend(fontsize=8)
        ax.set_title(title + " - ticks", fontsize=10)
        fig.savefig(path.replace(".png", "_ticks.png"), dpi=110)
        plt.close(fig)


def main() -> None:
    m1 = gold.bars("M1")
    m1 = m1[m1.index >= pd.Timestamp("2026-03-25", tz="UTC")]
    # F1 2026-04-08 07:03 Thai (00:03 UTC), BUY, stop 7.99, target 9.47 (pf_F1_test)
    f1 = pd.read_parquet("research/2026-10-18-moments/agents/portfolio/pf_F1_test.parquet")
    f1["t"] = pd.to_datetime(f1.t, utc=True)
    r = f1[f1.t == pd.Timestamp("2026-04-08 00:03", tz="UTC")].iloc[0]
    fill = m1.loc[r.t, "open"] + m1.loc[r.t, "spread"] * 0.01 + 0.08 + 0.07
    chart(m1, r.t, 1, fill, r.sl, r.tp, f"F1 2026-04-08 07:03 Thai BUY - {r.exit} {r.pnl:+.2f} USD after {int(r.mins)} min",
          f"{OUT}/f1_2026-04-08.png")
    # S2 CPI 2026-08-12 08:30 ET = 12:30 UTC, BUY (s2_ticks_test_h60_d2)
    tk = pd.read_parquet("data/ticks/XAUUSD/2026-08-12.parquet")
    tk["t"] = pd.to_datetime(tk.time_utc, utc=True).dt.as_unit("ns")
    tk = tk.sort_values("t")
    t0 = pd.Timestamp("2026-08-12 12:30", tz="UTC")
    pre = tk[tk.t < t0].iloc[-1]
    k = pre.ask / 4000
    fill = pre.ask + 2 * k
    chart(m1, t0, 1, fill, 8 * k, 8.0, "S2 CPI 2026-08-12 19:30 Thai BUY - stopped -10.56 USD", f"{OUT}/s2_2026-08-12.png", ticks=tk)
    print("charts written")


if __name__ == "__main__":
    main()
