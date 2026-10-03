"""Backtest runs from stored history (PLAN §A17 "Reproducibility"; TAA-506).

A run is reproducible from four values stored with its outputs: the **seed** (slippage), the **config hash**,
the **data hash** (every candle frame and spec snapshot that went in) and the **code version**. Loading fails
closed: a missing timeframe, a missing spec snapshot or a currency that no series can price is an error, not a
silently skipped symbol.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from app import __version__
from app.backtest.conversion import SeriesRates, missing_currencies
from app.backtest.engine import BacktestEngine, BacktestResult, Progress, SymbolData
from app.backtest.report import Provenance, write_reports
from app.config import AppConfig
from app.core.enums import Timeframe
from app.core.errors import DataQualityError
from app.market_data.data_models import SymbolSpec
from app.market_data.history_store import ParquetHistoryStore
from app.strategy.catalog import default_registry

HASH_COLUMNS = ("open_time", "open", "high", "low", "close", "spread")


def frame_digest(df: pd.DataFrame) -> str:
    """SHA-256 of a candle frame's values (column order fixed, independent of the pandas index)."""
    cols = [c for c in HASH_COLUMNS if c in df.columns]
    canonical = df[cols].copy()
    if "open_time" in canonical:
        canonical["open_time"] = pd.to_datetime(canonical["open_time"], utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
    return hashlib.sha256(canonical.to_csv(index=False, float_format="%.10g").encode("utf-8")).hexdigest()


def data_hash(data: Mapping[str, SymbolData], conversion: Mapping[str, pd.DataFrame] | None = None) -> str:
    parts = []
    for symbol in sorted(data):
        d = data[symbol]
        parts.append(f"{symbol}:spec:{json.dumps(_spec_dict(d.spec), sort_keys=True)}")
        for tf in sorted(d.frames, key=lambda t: t.seconds):
            parts.append(f"{symbol}:{tf.value}:{frame_digest(d.frames[tf])}")
    for symbol in sorted(conversion or {}):
        parts.append(f"conversion:{symbol}:{frame_digest((conversion or {})[symbol])}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:32]


def _spec_dict(spec: SymbolSpec) -> dict[str, object]:
    return asdict(spec)


@dataclass(frozen=True)
class LoadedData:
    data: dict[str, SymbolData]
    rates: SeriesRates
    conversion: dict[str, pd.DataFrame]
    digest: str


def load_history(
    store: ParquetHistoryStore,
    server: str,
    symbols: Sequence[str],
    timeframes: Sequence[Timeframe],
    *,
    account_currency: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> LoadedData:
    data: dict[str, SymbolData] = {}
    for symbol in symbols:
        meta = store.spec(server, symbol)
        if meta is None:
            raise DataQualityError(
                f"{symbol}: no spec snapshot in the history store (download it with its spec)"
            )
        spec = SymbolSpec(**meta["spec"])
        frames = {}
        for tf in timeframes:
            df = store.load(server, symbol, tf, start, end)
            if df.empty:
                raise DataQualityError(f"{symbol} {tf}: no history between {start} and {end}")
            frames[tf] = df.reset_index(drop=True)
        data[symbol] = SymbolData(spec, frames)
    # conversion series: every other stored symbol with a spec, on the longest timeframe in use
    conv_tf = max(timeframes, key=lambda t: t.seconds)
    conversion: dict[str, pd.DataFrame] = {}
    specs: dict[str, SymbolSpec] = {}
    for srv, symbol, tf in store.available():
        if srv != server or tf is not conv_tf or symbol in data:
            continue
        meta = store.spec(server, symbol)
        if meta is None:
            continue
        specs[symbol] = SymbolSpec(**meta["spec"])
        conversion[symbol] = store.load(server, symbol, tf, None, end)
    rates = SeriesRates.from_specs(account_currency, specs, conversion)
    missing = missing_currencies([d.spec for d in data.values()], rates, [d.spec for d in data.values()])
    if missing:
        raise DataQualityError(
            f"no conversion series for {missing}: download a pair that prices each of them"
        )
    return LoadedData(data, rates, conversion, data_hash(data, conversion))


def run_backtest(
    config: AppConfig,
    loaded: LoadedData,
    *,
    config_hash: str,
    strategy_names: Sequence[str] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    on_progress: Callable[[Progress], None] | None = None,
) -> tuple[BacktestResult, Provenance]:
    items = [i for i in config.strategies.items if strategy_names is None or i.name in strategy_names]
    if strategy_names is not None:
        unknown = sorted(set(strategy_names) - {i.name for i in items})
        if unknown:
            raise DataQualityError(f"strategies not listed in config.yaml: {unknown}")
        items = [i.model_copy(update={"enabled": True}) for i in items]
    strategies = default_registry().from_config(
        config.strategies.model_copy(update={"items": items}), config.timeframes, config.evidence.confluence
    )
    engine = BacktestEngine(
        config,
        loaded.data,
        strategies,
        loaded.rates,
        start=start,
        end=end,
        on_progress=on_progress,
        config_hash=config_hash,
    )
    result = engine.run()
    provenance = Provenance(
        seed=config.backtest.seed,
        config_hash=config_hash,
        data_hash=loaded.digest,
        code_version=__version__,
        extra={"strategies": strategies.names},
    )
    return result, provenance


def run_and_write(
    config: AppConfig,
    loaded: LoadedData,
    out_dir: Path,
    *,
    config_hash: str,
    strategy_names: Sequence[str] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    on_progress: Callable[[Progress], None] | None = None,
) -> tuple[BacktestResult, dict[str, Path]]:
    result, provenance = run_backtest(
        config,
        loaded,
        config_hash=config_hash,
        strategy_names=strategy_names,
        start=start,
        end=end,
        on_progress=on_progress,
    )
    return result, write_reports(result, provenance, out_dir)
