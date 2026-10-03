"""Backtest outputs (PLAN §A17 "Reproducibility and outputs"; TAA-504): a JSON summary, a trades CSV and an
equity/drawdown series, the files the PWA renders. Every summary repeats the run's provenance (seed, config
hash, data hash, code version) and the limitations of a bar-based simulation.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.backtest.engine import BacktestResult
from app.backtest.metrics import compute_metrics, equity_frame
from app.execution.simulated_broker import ClosedTrade

LIMITATIONS = (
    "bar-based approximation: the order of prices inside a bar is unknown (SL assumed first)",
    "spread from the bar field or a fixed model, not tick-accurate",
    "no requotes, partial fills or rejections other than margin",
    "news gaps and weekend gaps are only seen at the next bar's open",
    "past results do not predict future results",
)

TRADE_COLUMNS = (
    "ticket",
    "symbol",
    "side",
    "volume",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "exit_reason",
    "sl_initial",
    "tp_initial",
    "profit",
    "commission",
    "swap",
    "net",
    "risk_money",
    "r_multiple",
    "mae",
    "mfe",
    "strategy",
    "signal_id",
)


@dataclass(frozen=True)
class Provenance:
    seed: int
    config_hash: str
    data_hash: str
    code_version: str
    started_at: datetime | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


def trade_row(t: ClosedTrade) -> dict[str, Any]:
    return {
        "ticket": t.ticket,
        "symbol": t.symbol,
        "side": t.side.value,
        "volume": t.volume,
        "entry_time": t.entry_time.isoformat(),
        "entry_price": t.entry_price,
        "exit_time": t.exit_time.isoformat(),
        "exit_price": t.exit_price,
        "exit_reason": t.exit_reason.value,
        "sl_initial": t.sl_initial,
        "tp_initial": t.tp_initial,
        "profit": round(t.profit, 2),
        "commission": round(t.commission, 2),
        "swap": round(t.swap, 2),
        "net": round(t.net, 2),
        "risk_money": round(t.risk_money, 2),
        "r_multiple": None if t.r_multiple is None else round(t.r_multiple, 4),
        "mae": t.mae,
        "mfe": t.mfe,
        "strategy": t.strategy,
        "signal_id": t.signal_id,
    }


def summary(result: BacktestResult, provenance: Provenance) -> dict[str, Any]:
    metrics = compute_metrics(result.trades, result.equity_curve, result.initial_balance)
    return {
        "provenance": {
            "seed": provenance.seed,
            "config_hash": provenance.config_hash,
            "data_hash": provenance.data_hash,
            "code_version": provenance.code_version,
            **dict(provenance.extra),
        },
        "period": {
            "start": None if result.start is None else result.start.isoformat(),
            "end": None if result.end is None else result.end.isoformat(),
        },
        "symbols": list(result.symbols),
        "signals": result.signals,
        "decisions": dict(sorted(result.decisions.items())),
        "rejections": dict(result.rejections.most_common()),
        "metrics": metrics.to_dict(),
        "limitations": list(LIMITATIONS),
    }


def write_reports(result: BacktestResult, provenance: Provenance, out_dir: Path) -> dict[str, Path]:
    """Write ``summary.json``, ``trades.csv`` and ``equity.csv`` into *out_dir*; return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": out_dir / "summary.json",
        "trades": out_dir / "trades.csv",
        "equity": out_dir / "equity.csv",
    }
    paths["summary"].write_text(
        json.dumps(summary(result, provenance), indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    write_trades_csv(result.trades, paths["trades"])
    frame = equity_frame(result.equity_curve)
    frame.reset_index().to_csv(paths["equity"], index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return paths


def write_trades_csv(trades: Sequence[ClosedTrade], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRADE_COLUMNS)
        writer.writeheader()
        for t in trades:
            writer.writerow(trade_row(t))
