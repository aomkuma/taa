"""Look-ahead harness for evidence detectors (PLAN §A29: evidence at bar T uses only bars <= T).

For each probe position t it checks two things:
1. Prefix consistency: scanning the frame cut at t yields exactly the full-frame records with
   ``detected_at <= t``. A detector that peeks at later bars reports different (or extra) early records.
2. Mutation invariance: replacing every bar after t leaves all records with ``detected_at <= t`` unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd

from app.core.enums import Timeframe
from app.evidence.framework import Detector, DetectorParams, Evidence, EvidenceContext
from app.evidence.registry import DetectorRegistry, EvidenceEngine
from tests.indicator_data import mutate_after, random_ohlc


def candles(df: pd.DataFrame, tf: Timeframe = Timeframe.H1) -> pd.DataFrame:
    """An OHLCV frame (index = open time) as closed candles with ``open_time``/``close_time`` columns."""
    out = df.reset_index(names="open_time")
    out["close_time"] = out["open_time"] + pd.Timedelta(seconds=tf.seconds)
    return out


def context(df: pd.DataFrame, symbol: str = "EURUSD", tf: Timeframe = Timeframe.H1) -> EvidenceContext:
    return EvidenceContext(symbol, tf, candles(df, tf))


def scan_one(
    detector: Detector,
    ctx: EvidenceContext,
    catalog: Iterable[Detector] = (),
    params: DetectorParams | None = None,
) -> list[Evidence]:
    registry = DetectorRegistry({detector.id: detector, **{d.id: d for d in catalog}}.values())
    plan = registry.plan([detector.id], {detector.id: params} if params else None)
    return EvidenceEngine(registry, plan).scan(ctx).get(detector.id, [])


def _key(records: Iterable[Evidence]) -> list[dict[str, object]]:
    return sorted(
        (e.to_dict() for e in records), key=lambda d: (str(d["detected_at"]), str(d["evidence_id"]))
    )


def assert_no_lookahead(
    detector: Detector,
    df: pd.DataFrame | None = None,
    positions: Sequence[int] = (150, 300, 450),
    *,
    catalog: Iterable[Detector] = (),
    params: DetectorParams | None = None,
) -> list[Evidence]:
    """Run both checks and return the full-frame records (so callers can assert they are not vacuous)."""
    df = random_ohlc(600, seed=5) if df is None else df
    catalog = tuple(catalog)
    full_ctx = context(df)
    full = scan_one(detector, full_ctx, catalog, params)
    for t in positions:
        cutoff = full_ctx.time_at(t)
        known = [e for e in full if e.detected_at <= cutoff]
        prefix = scan_one(detector, full_ctx.prefix(t), catalog, params)
        assert _key(prefix) == _key(known), f"{detector.id}: records up to bar {t} depend on later bars"
        mutated = scan_one(detector, context(mutate_after(df, t)), catalog, params)
        assert _key(e for e in mutated if e.detected_at <= cutoff) == _key(known), (
            f"{detector.id}: changing bars after {t} changed earlier records"
        )
    return full
