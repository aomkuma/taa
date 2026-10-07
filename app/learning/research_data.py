"""Inputs of the research harness (TAA-L707): closed ``PLAN`` shadow trades and the stored bars after them.

Read-only. Shadow trades come from any engine-schema database (the engine's own, or a scratch replay database
under ``data/research/``); bars come from the Parquet history store (the finest of M1/M5 for the paths, the
entry timeframe for the context at the signal bar).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import timedelta

import pandas as pd
from sqlalchemy import select

from app.advisory.replay import load_resolution
from app.core.clock import ensure_utc
from app.core.enums import Side, Timeframe
from app.learning.research import HORIZON, PricePath, ResearchError, Signal, build_path
from app.market_data.history_store import ParquetHistoryStore
from app.storage.database import Database
from app.storage.models import ShadowTradeRow

log = logging.getLogger(__name__)

PLAN = "PLAN"
CLOSED = "CLOSED"


def load_signals(
    db: Database, *, strategy: str, source: str | None = None, timeframe: str | None = None
) -> list[tuple[str, Signal]]:
    """(server, signal) for each closed PLAN shadow trade of *strategy* (optionally one source/timeframe)."""
    query = select(ShadowTradeRow).where(
        ShadowTradeRow.strategy == strategy,
        ShadowTradeRow.variant == PLAN,
        ShadowTradeRow.status == CLOSED,
    )
    if source is not None:
        query = query.where(ShadowTradeRow.source == source)
    if timeframe is not None:
        query = query.where(ShadowTradeRow.timeframe == timeframe)
    out = []
    with db.session() as sess:
        for row in sess.scalars(query):
            if row.r_net is None or row.r_multiple is None:
                continue
            out.append((row.server, _signal(row)))
    return out


def _signal(row: ShadowTradeRow) -> Signal:
    return Signal(
        shadow_id=row.shadow_id,
        strategy=row.strategy,
        symbol=row.symbol,
        timeframe=Timeframe(row.timeframe),
        side=Side(row.side),
        signal_at=ensure_utc(row.signal_at),
        entry_at=ensure_utc(row.entry_at),
        entry=row.entry_price,
        initial_sl=row.initial_sl,
        tp=row.tp,
        atr=row.atr,
        spread=float(row.spread_points or 0.0),  # points until with_point() converts it
        cost_r=float((row.r_multiple or 0.0) - (row.r_net or 0.0)),
        r_net=float(row.r_net or 0.0),
        features=dict(row.features or {}),
    )


def with_point(signal: Signal, point: float) -> Signal:
    """The signal with its spread in price units (rows store points)."""
    return replace(signal, spread=signal.spread * point)


@dataclass(frozen=True, slots=True)
class ResearchInputs:
    signals: list[Signal]  # spreads in price units
    paths: dict[str, PricePath]
    mirrors: dict[str, PricePath]
    frames: dict[str, pd.DataFrame]  # entry timeframe bars by symbol
    resolution: dict[str, str]  # symbol -> M1/M5
    skipped: int  # signals without a usable path (no bars, invalid geometry)


def load_inputs(
    found: Sequence[tuple[str, Signal]], store: ParquetHistoryStore, *, horizon: timedelta = HORIZON
) -> ResearchInputs:
    """Paths (and mirrored paths) of every signal from the stored bars; fails closed without a symbol spec."""
    by_symbol: dict[tuple[str, str], list[Signal]] = defaultdict(list)
    for server, signal in found:
        by_symbol[(server, signal.symbol)].append(signal)
    signals: list[Signal] = []
    paths: dict[str, PricePath] = {}
    mirrors: dict[str, PricePath] = {}
    frames: dict[str, pd.DataFrame] = {}
    resolution: dict[str, str] = {}
    skipped = 0
    for (server, symbol), group in sorted(by_symbol.items()):
        meta = store.spec(server, symbol)
        if meta is None:
            raise ResearchError(f"{server}/{symbol}: no spec.json in the history store")
        point = float(meta["spec"]["point"])
        start = min(s.entry_at for s in group) - timedelta(days=1)
        end = max(s.entry_at for s in group) + horizon + timedelta(days=1)
        res = load_resolution(store, server, symbol, start=start, end=end)
        bars = res.frame.sort_values("open_time").reset_index(drop=True)
        resolution[symbol] = res.timeframe.value
        tfs = {s.timeframe for s in group}
        if len(tfs) != 1:
            raise ResearchError(f"{symbol}: one entry timeframe per run, got {sorted(t.value for t in tfs)}")
        frames[symbol] = store.load(server, symbol, tfs.pop(), start - timedelta(days=30), end)
        for raw in group:
            signal = with_point(raw, point)
            if not signal.risk > 0:
                skipped += 1
                continue
            path = build_path(signal, bars, point=point, horizon=horizon)
            if len(path) == 0:
                skipped += 1
                continue
            signals.append(signal)
            paths[signal.shadow_id] = path
            mirrors[signal.shadow_id] = build_path(signal.mirrored(), bars, point=point, horizon=horizon)
    log.info("research inputs: %d signals with a path, %d skipped", len(signals), skipped)
    return ResearchInputs(signals, paths, mirrors, frames, resolution, skipped)
