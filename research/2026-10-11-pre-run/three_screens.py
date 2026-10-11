"""Which market phase suits a setup, read on three screens (owner, 2026-10-11: Elder's triple screen on
H4 / H1 / M15; every timeframe has its own trend, so a sideways H4 can hold an H1 trend).

For every trade of a two-world backtest pair, the state of H4, H1 and M15 at the last bar closed before the
entry (``app.indicators.market_map.state_frame``: UP / DOWN / RANGE / TRANSITION, no look-ahead), relative to
the trade's side: WITH, AGAINST, RANGE, TRANS. Trades are grouped into a few phases (enough trades per group):

- ``aligned``: H4 and H1 with the trade;
- ``pullback``: H4 with, the M15 against or ranging (the triple-screen entry: the wave against the tide);
- ``range_h1_with``: H4 ranging, H1 with the trade (a trend inside the range);
- ``range_h1_other``: H4 ranging, H1 not with the trade;
- ``against_h4``: H4 against the trade;
- ``other``: the rest (transitions).

Per world and phase: n, mean R, win rate, and the mean R in each half and on the hold-out symbols, so a phase
only counts when it holds in both halves and outside the symbols it was read on.

    .venv/Scripts/python research/2026-10-11-pre-run/three_screens.py setup_harmonic_prz 4m [8m ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.indicators.market_map import MapParams, state_frame

HIST = Path("data/history/FBS-Demo")
ROOT = Path("data/backtests/inv")
HOLDOUT = {"AUDUSD", "XAUUSD"}
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")
TFS = ("H4", "H1", "M15")
_states: dict[tuple[str, str], pd.Series] = {}


def states(symbol: str, tf: str) -> pd.Series:
    key = (symbol, tf)
    if key not in _states:
        df = pd.read_parquet(HIST / symbol / f"{tf}.parquet").sort_values("close_time")
        df = df.set_index(pd.DatetimeIndex(df["close_time"]))
        _states[key] = state_frame(df, MapParams())["state"].astype(str)
    return _states[key]


def relative(state: str, side: str) -> str:
    if state in ("UP", "DOWN"):
        return "WITH" if (state == "UP") == (side == "BUY") else "AGAINST"
    return "RANGE" if state == "RANGE" else "TRANS"


def phase(h4: str, h1: str, m15: str) -> str:
    if h4 == "WITH" and m15 in ("AGAINST", "RANGE"):
        return "pullback"
    if h4 == "WITH" and h1 == "WITH":
        return "aligned"
    if h4 == "RANGE":
        return "range_h1_with" if h1 == "WITH" else "range_h1_other"
    if h4 == "AGAINST":
        return "against_h4"
    return "other"


def load(setup: str, periods: list[str]) -> pd.DataFrame:
    frames = []
    for world, name in (("normal", setup), ("inverted", f"{setup}_inverted")):
        for period in periods:
            f = ROOT / f"{name}_{period}" / "trades.csv"
            if f.exists():
                t = pd.read_csv(f)
                t["world"] = world
                frames.append(t)
    t = pd.concat(frames, ignore_index=True)
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    rows = []
    for _, r in t.iterrows():
        rel = []
        for tf in TFS:
            s = states(r["symbol"], tf)
            i = s.index.searchsorted(r["entry_time"], side="right") - 1
            rel.append(relative(s.iloc[i], r["side"]) if i >= 0 else "TRANS")
        rows.append((*rel, phase(*rel)))
    t[["h4", "h1", "m15", "phase"]] = pd.DataFrame(rows, index=t.index)
    return t


def stat(x: pd.Series) -> str:
    return f"{x.mean():+.3f} (n={len(x)})" if len(x) else "-"


def main(setup: str, periods: list[str]) -> None:
    t = load(setup, periods)
    print(f"=== {setup}: market phase on three screens (H4/H1/M15), periods {','.join(periods)} ===")
    for world in ("normal", "inverted"):
        w = t[t["world"] == world]
        print(f"\n{world}: {len(w)} trades, mean {w['r_multiple'].mean():+.3f} R")
        print(f"  {'phase':16} {'n':>5} {'share':>6} {'mean R':>8} {'win%':>5} | {'1st half':>16} {'2nd half':>16} {'hold-out':>16}")
        for ph, g in w.groupby("phase"):
            first, second = g[g["entry_time"] < SPLIT], g[g["entry_time"] >= SPLIT]
            hold = g[g["symbol"].isin(HOLDOUT)]
            print(
                f"  {ph:16} {len(g):>5} {100 * len(g) / len(w):>5.0f}% {g['r_multiple'].mean():>+8.3f} "
                f"{100 * (g['net'] > 0).mean():>5.0f} | {stat(first['r_multiple']):>16} "
                f"{stat(second['r_multiple']):>16} {stat(hold['r_multiple']):>16}"
            )
    both = t.pivot_table(index="phase", columns="world", values="r_multiple", aggfunc="mean").round(3)
    print("\nmean R per phase, side by side:\n" + both.to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or ["4m"])
