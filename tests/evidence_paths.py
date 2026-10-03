"""Synthetic price paths for detector golden tests: straight legs between given turning points."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from itertools import pairwise

import numpy as np
import pandas as pd

from app.evidence.framework import EvidenceContext
from tests.evidence_harness import context

START = datetime(2026, 9, 1, 0, tzinfo=UTC)


def path_frame(
    vertices: Sequence[float],
    bars_per_leg: int | Sequence[int] = 6,
    *,
    warmup: int = 20,
    wick: float = 0.1,
    volume: Sequence[float] | None = None,
) -> pd.DataFrame:
    """Closes move linearly from vertex to vertex; each bar opens at the previous close with *wick* beyond its
    body. ``warmup`` flat bars at the first vertex come first (ATR settles there)."""
    legs = [bars_per_leg] * (len(vertices) - 1) if isinstance(bars_per_leg, int) else list(bars_per_leg)
    closes = [float(vertices[0])] * warmup
    for (a, b), n in zip(pairwise(vertices), legs, strict=True):
        closes += list(np.linspace(a, b, n + 1)[1:])
    c = np.array(closes)
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame(
        {
            "open": o,
            "high": np.maximum(o, c) + wick,
            "low": np.minimum(o, c) - wick,
            "close": c,
            "tick_volume": np.asarray(volume, dtype=float) if volume is not None else np.full(len(c), 100.0),
        },
        index=pd.date_range(START, periods=len(c), freq="h"),
    )
    return df


def path(vertices: Sequence[float], bars_per_leg: int | Sequence[int] = 6, **kw: object) -> EvidenceContext:
    return context(path_frame(vertices, bars_per_leg, **kw))  # type: ignore[arg-type]


def path_rows(
    vertices: Sequence[float], bars_per_leg: int | Sequence[int] = 6, **kw: object
) -> list[tuple[float, float, float, float]]:
    """The (open, high, low, close) rows of :func:`path_frame`, to extend with hand-made bars for :func:`bars`."""
    df = path_frame(vertices, bars_per_leg, **kw)  # type: ignore[arg-type]
    return list(df[["open", "high", "low", "close"]].itertuples(index=False, name=None))


def bars(rows: Sequence[tuple[float, float, float, float]], start: datetime = START) -> EvidenceContext:
    """A context from explicit (open, high, low, close) rows, hourly from *start*."""
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df.index = pd.date_range(start, periods=len(rows), freq="h")
    df["tick_volume"] = 100.0
    return context(df)
