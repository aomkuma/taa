"""The research hypothesis set on a backtest's own trades (owner, 2026-10-11: "don't waste the backtest").

Each trade of ``trades.csv`` (``app.cli backtest``) becomes a research :class:`Signal` (entry, initial stop,
target, the M5 spread at the entry, costs from profit - net), and ``app.learning.research.research`` runs the
usual set on its M5 path: entries (retests), stops, exits, re-entries and context rules (incl. the New York-time
and pre-run features), each chosen on one half and judged on the other half and on the hold-out symbols.

    .venv/Scripts/python research/2026-10-11-pre-run/backtest_hypotheses.py data/backtests/inv/setup_harmonic_prz_4m \
        [--holdout AUDUSD,XAUUSD] [--timeframe M15]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from app.cli.research import _print_report
from app.core.enums import Side, Timeframe
from app.learning.research import Signal, research
from app.learning.research_data import load_inputs
from app.market_data.history_store import ParquetHistoryStore

SERVER = "FBS-Demo"
HIST = Path("data/history")


def spread_points(symbol: str, at: pd.Timestamp, cache: dict[str, pd.DataFrame]) -> float:
    if symbol not in cache:
        cache[symbol] = pd.read_parquet(HIST / SERVER / symbol / "M5.parquet").sort_values("open_time")
    bars = cache[symbol]
    i = max(0, int(pd.DatetimeIndex(bars["open_time"]).searchsorted(at, side="right")) - 1)
    return float(bars["spread"].iloc[i])


def signals(trades: pd.DataFrame, timeframe: Timeframe) -> list[tuple[str, Signal]]:
    cache: dict[str, pd.DataFrame] = {}
    out = []
    for _, t in trades.iterrows():
        risk_money = float(t["risk_money"])
        if not risk_money > 0:
            continue
        at = pd.Timestamp(t["entry_time"])
        r_net = float(t["net"]) / risk_money
        cost_r = (float(t["profit"]) - float(t["net"])) / risk_money
        out.append(
            (
                SERVER,
                Signal(
                    shadow_id=f"bt{t['ticket']}",
                    strategy=str(t["strategy"]),
                    symbol=str(t["symbol"]),
                    timeframe=timeframe,
                    side=Side(t["side"]),
                    signal_at=at.to_pydatetime(),
                    entry_at=at.to_pydatetime(),
                    entry=float(t["entry_price"]),
                    initial_sl=float(t["sl_initial"]),
                    tp=None if pd.isna(t["tp_initial"]) else float(t["tp_initial"]),
                    atr=None,
                    spread=spread_points(str(t["symbol"]), at, cache),  # points: load_inputs converts
                    cost_r=cost_r,
                    r_net=r_net,
                ),
            )
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--holdout", default="AUDUSD,XAUUSD")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--resamples", type=int, default=1000)
    args = ap.parse_args()
    trades = pd.read_csv(Path(args.folder) / "trades.csv")
    found = signals(trades, Timeframe(args.timeframe))
    inputs = load_inputs(found, ParquetHistoryStore(HIST))
    report = research(
        inputs.signals,
        inputs.paths,
        inputs.mirrors,
        inputs.frames,
        resamples=args.resamples,
        holdout_symbols=frozenset(x for x in args.holdout.split(",") if x),
    )
    data = report.to_dict()
    data["resolution"] = inputs.resolution
    data["skipped"] = inputs.skipped
    print(f"backtest trades from {args.folder} ({len(trades)} trades, {inputs.skipped} skipped)")
    _print_report(data)


if __name__ == "__main__":
    main()
