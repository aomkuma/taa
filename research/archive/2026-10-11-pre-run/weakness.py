"""Where a setup's backtest trades lose (owner, 2026-10-14: "find it, learn, close the weak spots").

Joins the ``trades.csv`` of the given backtest folders, tags each trade (``filters.tag``: three screens, H4/D1
zones, trigger, New York time, R:R, cost share, stop in ATR) plus the H4/H1 trend strength (ADX of the market
map), the H4 ATR percentile and, for losers, how fast the stop came. Then, per feature group: n, mean R, total R,
and the mean R in the losing months and in the winning months separately, so a weak spot only counts when it is
weak in both kinds of month (not just a bad month).

    .venv/Scripts/python research/2026-10-11-pre-run/weakness.py data/backtests/inv/setup_breakout_w1f_2025-11 ...
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import filters as F  # type: ignore[import-not-found]
from app.indicators.market_map import MapParams, state_frame

HIST = Path("data/history/FBS-Demo")
_maps: dict[tuple[str, str], pd.DataFrame] = {}


def mapped(symbol: str, tf: str) -> pd.DataFrame:
    if (symbol, tf) not in _maps:
        df = pd.read_parquet(HIST / symbol / f"{tf}.parquet").sort_values("close_time")
        df = df.set_index(pd.DatetimeIndex(pd.to_datetime(df["close_time"], utc=True)))
        _maps[(symbol, tf)] = state_frame(df, MapParams())
    return _maps[(symbol, tf)]


def at(frame: pd.DataFrame, when: pd.Timestamp, col: str) -> float:
    i = frame.index.searchsorted(when, side="right") - 1
    return float(frame[col].iloc[i]) if i >= 0 else np.nan


def load(folders: list[str]) -> pd.DataFrame:
    frames = []
    for f in folders:
        t = pd.read_csv(Path(f) / "trades.csv")
        t["month"] = pd.to_datetime(t["entry_time"], utc=True).dt.strftime("%Y-%m").iloc[0] if len(t) else ""
        frames.append(t)
    t = pd.concat(frames, ignore_index=True)
    t["strategy"] = "setup_breakout"
    risk = (t["entry_price"] - t["sl_initial"]).abs()
    t["kind"] = np.where((t["tp_initial"] - t["entry_price"]).abs() < risk, "fade", "with")
    side = t["side"].copy()
    fade = t["kind"] == "fade"
    t.loc[fade, "side"] = t.loc[fade, "side"].map({"BUY": "SELL", "SELL": "BUY"})  # the trigger's own side
    t = F.tag(t)
    t["trigger_side"] = t["side"]
    t["side"] = side.to_numpy()
    for tf in ("H4", "H1"):
        t[f"{tf.lower()}_adx"] = [at(mapped(r.symbol, tf), r.entry_time, "adx") for r in t.itertuples()]
    t["h4_atr_pct"] = [at(mapped(r.symbol, "H4"), r.entry_time, "atr_pct") for r in t.itertuples()]
    t["bars_held"] = (t["exit_time"] - t["entry_time"]) / pd.Timedelta(minutes=15)
    return t


GROUPS = {
    "kind": lambda t: t["kind"],
    "symbol": lambda t: t["symbol"],
    "trigger": lambda t: t["trigger"],
    "NY time": lambda t: t["ny"],
    "M15 vs trigger": lambda t: t["m15"],
    "H4 ATR pct": lambda t: pd.cut(t["h4_atr_pct"], [0, 30, 60, 100.01], include_lowest=True).astype(str),
    "H4 ADX": lambda t: pd.cut(t["h4_adx"], [0, 25, 35, 100], include_lowest=True).astype(str),
    "H1 ADX": lambda t: pd.cut(t["h1_adx"], [0, 25, 35, 100], include_lowest=True).astype(str),
    "stop ATR": lambda t: pd.cut(t["sl_atr"], [0, 1.25, 1.75, 10], include_lowest=True).astype(str),
    "cost share": lambda t: pd.cut(t["cost_share"], [0, 0.05, 0.10, 1], include_lowest=True).astype(str),
    "H4 zone before TP": lambda t: t["h4_zone_before_tp"].astype(str),
    "weekday": lambda t: t["entry_time"].dt.day_name().str[:3],
}


def main(folders: list[str]) -> None:
    t = load(folders)
    by_month = t.groupby("month")["r_multiple"].mean()
    bad = set(by_month[by_month < 0].index)
    t["month_kind"] = np.where(t["month"].isin(bad), "losing", "winning")
    print(f"=== {len(t)} trades, mean {t['r_multiple'].mean():+.3f} R; losing months {sorted(bad)} ===")
    lose = t[t["net"] <= 0]
    print(
        f"losers {len(lose)}: stopped within 2 bars {100 * (lose['bars_held'] <= 2).mean():.0f} %, "
        f"median {lose['bars_held'].median():.0f} bars"
    )
    for name, f in GROUPS.items():
        g = t.assign(group=f(t))
        tab = g.groupby("group").agg(
            n=("r_multiple", "size"), mean=("r_multiple", "mean"), total=("r_multiple", "sum")
        )
        split = g.pivot_table(index="group", columns="month_kind", values="r_multiple", aggfunc="mean")
        print(f"\n-- {name}\n" + tab.join(split).round(3).to_string())
    t.to_csv(Path(folders[0]).parent / "weakness_tagged.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1:])
