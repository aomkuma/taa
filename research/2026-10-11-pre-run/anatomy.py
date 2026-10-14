"""Why a backtest's trades lose (owner, 2026-10-13: "entry too early, or the stop too close?").

Per trade of ``trades.csv`` (``app.cli backtest``), read on the M5 history (bar-based, no look-ahead into the
decision; after the exit only to describe what price did next):

- ``bars_held``: M15 bars from entry to exit; losers stopped within 1 / 2 / 4 bars;
- ``sl_atr``: stop distance in M15 ATR(14); ``cost_share``: the M5 spread at the entry / the stop distance;
- losers: the best excursion toward the target before the stop, in R (+0.25 / +0.5 / +1 R reached first);
- losers: **target reached after the stop** within 72 h (the stop sat inside the noise, the direction was
  right), and the stop-side extreme before that (how wide a stop would have survived, in R);
- winners: the worst excursion against the trade before the target, in R.

Prints the overall figures and per half and per symbol, so a pattern only counts when it holds in both halves.

    .venv/Scripts/python research/2026-10-11-pre-run/anatomy.py data/backtests/inv/setup_breakout_1y
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HIST = Path("data/history/FBS-Demo")
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")
AFTER = pd.Timedelta(hours=72)
_m5: dict[str, pd.DataFrame] = {}
_m15: dict[str, pd.DataFrame] = {}


def m5(symbol: str) -> pd.DataFrame:
    if symbol not in _m5:
        df = pd.read_parquet(HIST / symbol / "M5.parquet").sort_values("open_time").reset_index(drop=True)
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        _m5[symbol] = df
    return _m5[symbol]


def atr15(symbol: str) -> pd.Series:
    if symbol not in _m15:
        df = pd.read_parquet(HIST / symbol / "M15.parquet").sort_values("close_time")
        prev = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1)
        _m15[symbol] = pd.Series(
            tr.max(axis=1).rolling(14).mean().to_numpy(), index=pd.to_datetime(df["close_time"], utc=True)
        )
    return _m15[symbol]


POINT = {"XAUUSD": 0.01, "USDJPY": 0.001}


def describe(r: pd.Series) -> dict[str, float]:
    sym = str(r["symbol"])
    bars = m5(sym)
    entry, sl, tp = float(r["entry_price"]), float(r["sl_initial"]), float(r["tp_initial"])
    sign = 1.0 if r["side"] == "BUY" else -1.0
    risk = abs(entry - sl)
    t_in, t_out = r["entry_time"], r["exit_time"]
    times = bars["open_time"]
    i0 = int(times.searchsorted(t_in, side="left"))
    i1 = int(times.searchsorted(t_out, side="right"))
    i2 = int(times.searchsorted(t_out + AFTER, side="right"))
    a = atr15(sym)
    j = int(a.index.searchsorted(t_in, side="right")) - 1
    atr = float(a.iloc[j]) if j >= 0 else np.nan
    spread = float(bars["spread"].iloc[max(0, i0 - 1)]) * POINT.get(sym, 0.00001)
    out = {
        "bars_held": (t_out - t_in) / pd.Timedelta(minutes=15),
        "sl_atr": risk / atr if atr > 0 else np.nan,
        "cost_share": spread / risk if risk > 0 else np.nan,
        "rr": abs(tp - entry) / risk if risk > 0 else np.nan,
    }
    hi = bars["high"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    fav = (hi if sign > 0 else lo)[i0:i1]
    adv = (lo if sign > 0 else hi)[i0:i1]
    out["mfe_r"] = float(np.max((fav - entry) * sign)) / risk if len(fav) and risk > 0 else np.nan
    out["mae_r"] = float(np.max((entry - adv) * sign)) / risk if len(adv) and risk > 0 else np.nan
    # after the exit: did price reach the original target within 72 h, and how far against it first?
    fav2 = (hi if sign > 0 else lo)[i1:i2]
    adv2 = (lo if sign > 0 else hi)[i1:i2]
    hit = np.flatnonzero((fav2 - tp) * sign >= 0)
    out["tp_after"] = float(len(hit) > 0)
    k = int(hit[0]) + 1 if len(hit) else len(adv2)
    worst = np.max((entry - adv2[:k]) * sign) if k else np.nan
    out["stop_needed_r"] = float(worst) / risk if len(hit) and risk > 0 else np.nan
    return out


def report(t: pd.DataFrame, title: str) -> None:
    lose, win = t[t["net"] <= 0], t[t["net"] > 0]
    print(f"\n--- {title}: {len(t)} trades, mean {t['r_multiple'].mean():+.3f} R, win {100 * len(win) / max(1, len(t)):.0f} % ---")
    print(
        f"  stop: median {t['sl_atr'].median():.2f} ATR (p25 {t['sl_atr'].quantile(0.25):.2f}, p75 "
        f"{t['sl_atr'].quantile(0.75):.2f}); spread share of the stop median {t['cost_share'].median():.3f} "
        f"(p75 {t['cost_share'].quantile(0.75):.3f}); planned R:R median {t['rr'].median():.2f}"
    )
    if len(lose):
        b = lose["bars_held"]
        print(
            f"  losers ({len(lose)}): stopped within 1 bar {100 * (b <= 1).mean():.0f} %, 2 bars "
            f"{100 * (b <= 2).mean():.0f} %, 4 bars {100 * (b <= 4).mean():.0f} %; median {b.median():.1f} bars"
        )
        m = lose["mfe_r"]
        print(
            f"  losers first went toward the target: +0.25 R {100 * (m >= 0.25).mean():.0f} %, +0.5 R "
            f"{100 * (m >= 0.5).mean():.0f} %, +1 R {100 * (m >= 1).mean():.0f} %"
        )
        tp_after = lose["tp_after"].mean()
        need = lose["stop_needed_r"].dropna()
        print(
            f"  losers whose target was reached within 72 h after the stop: {100 * tp_after:.0f} %; the stop that "
            f"would have survived to it: median {need.median():.2f} R, <= 1.5 R {100 * (need <= 1.5).mean():.0f} %, "
            f"<= 2 R {100 * (need <= 2).mean():.0f} %, <= 3 R {100 * (need <= 3).mean():.0f} % (of those)"
        )
    if len(win):
        h = win["mae_r"]
        print(
            f"  winners ({len(win)}): heat against them median {h.median():.2f} R; >= 0.5 R "
            f"{100 * (h >= 0.5).mean():.0f} %, >= 0.8 R {100 * (h >= 0.8).mean():.0f} %; median {win['bars_held'].median():.1f} bars"
        )


def main(folder: str) -> None:
    t = pd.read_csv(Path(folder) / "trades.csv")
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    t["exit_time"] = pd.to_datetime(t["exit_time"], utc=True)
    t = t[t["exit_reason"] != "END_OF_DATA"]
    extra = pd.DataFrame([describe(r) for _, r in t.iterrows()], index=t.index)
    t = pd.concat([t, extra], axis=1)
    print(f"=== anatomy of {folder} ===")
    report(t, "all")
    report(t[t["entry_time"] < SPLIT], "first half")
    report(t[t["entry_time"] >= SPLIT], "second half")
    print("\nby symbol (n, mean R, stop ATR, spread share, losers stopped <= 2 bars, TP after stop):")
    for sym, g in t.groupby("symbol"):
        lose = g[g["net"] <= 0]
        print(
            f"  {sym:7} {len(g):>5} {g['r_multiple'].mean():+.3f}  {g['sl_atr'].median():.2f} ATR  "
            f"{g['cost_share'].median():.3f}  {100 * (lose['bars_held'] <= 2).mean():>3.0f} %  "
            f"{100 * lose['tp_after'].mean():>3.0f} %"
        )


if __name__ == "__main__":
    main(sys.argv[1])
