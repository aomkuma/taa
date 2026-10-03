from __future__ import annotations

from itertools import pairwise

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import ConfigError
from app.evidence.zigzag import zigzag
from app.indicators.price_action import SwingKind, label_structure
from app.indicators.volatility import atr
from tests.indicator_data import mutate_after, random_ohlc


def run(highs: list[float], multiple: float = 2.0) -> list[tuple[SwingKind, int, int, float]]:
    h = pd.Series(highs, dtype=float)
    out = zigzag(h, h - 0.5, pd.Series(np.ones(len(h))), multiple)
    return [(p.kind, p.pivot_pos, p.confirm_pos, p.price) for p in out]


def test_hand_computed_reference() -> None:
    # ATR = 1, multiple 2 -> a 2.0 move against the running extreme confirms it
    assert run([10, 11, 12, 11, 9.5, 9, 10, 12, 11]) == [
        (SwingKind.LOW, 0, 2, 9.5),  # 12 - 9.5 >= 2 at bar 2
        (SwingKind.HIGH, 2, 4, 12.0),  # 12 - 9.0 >= 2 at bar 4
        (SwingKind.LOW, 5, 7, 8.5),  # 12 - 8.5 >= 2 at bar 7
    ]


def test_running_extreme_is_never_a_pivot() -> None:
    # a steady rise never reverses: the low that started it is the only pivot
    pivots = run([float(x) for x in range(10, 30)])
    assert pivots == [(SwingKind.LOW, 0, 2, 9.5)]


def test_no_reversal_before_atr_warmup() -> None:
    h = pd.Series([10, 14, 9, 14, 9.0])
    a = pd.Series([np.nan, np.nan, np.nan, 1.0, 1.0])
    out = zigzag(h, h - 0.5, a, 2.0)
    assert out and min(p.confirm_pos for p in out) >= 3


def test_invalid_multiple() -> None:
    h = pd.Series([1.0, 2.0])
    with pytest.raises(ConfigError):
        zigzag(h, h, h, 0.0)


def test_pivot_labels_are_close_times_and_feed_structure() -> None:
    df = random_ohlc(400, seed=8)
    a = atr(df["high"], df["low"], df["close"])
    out = zigzag(df["high"], df["low"], a, 1.5)
    assert len(out) > 10
    assert all(p.pivot_at == df.index[p.pivot_pos] for p in out)
    labels = label_structure(out)
    assert {lab.label for lab in labels[2:]} <= {"HH", "LH", "HL", "LL", "EQH", "EQL"}


def test_larger_degree_is_coarser() -> None:
    df = random_ohlc(600, seed=8)
    a = atr(df["high"], df["low"], df["close"])
    counts = [len(zigzag(df["high"], df["low"], a, m)) for m in (1.5, 3.0, 6.0)]
    assert counts[0] > counts[1] > counts[2] > 0


@pytest.mark.parametrize("t", [120, 333, 598])
def test_prefix_and_mutation_consistency(t: int) -> None:
    df = random_ohlc(600, seed=8)

    def pivots(d: pd.DataFrame) -> list[tuple[object, ...]]:
        a = atr(d["high"], d["low"], d["close"])
        return [(p.kind, p.pivot_pos, p.confirm_pos, p.price) for p in zigzag(d["high"], d["low"], a, 1.5)]

    full = [p for p in pivots(df) if p[2] <= t]
    assert pivots(df.iloc[: t + 1]) == full
    assert [p for p in pivots(mutate_after(df, t)) if p[2] <= t] == full


@settings(max_examples=80, deadline=None)
@given(
    st.lists(st.floats(-3.0, 3.0), min_size=5, max_size=150),
    st.floats(0.5, 4.0),
)
def test_properties(steps: list[float], multiple: float) -> None:
    close = 100 + np.cumsum(steps)
    high, low = pd.Series(close + 0.5), pd.Series(close - 0.5)
    a = pd.Series(np.ones(len(close)))
    out = zigzag(high, low, a, multiple)
    h, lo = high.to_numpy(), low.to_numpy()
    for prev, cur in pairwise(out):
        assert prev.kind != cur.kind  # strictly alternating
        assert prev.confirm_pos < cur.confirm_pos
        assert prev.pivot_pos < cur.pivot_pos <= cur.confirm_pos
    for i, p in enumerate(out):
        start = out[i - 1].pivot_pos + 1 if i else 0
        window = slice(start, p.confirm_pos + 1)
        if p.kind is SwingKind.HIGH:
            assert p.price == h[window].max()  # the leg's extreme
            assert p.price - lo[p.confirm_pos] >= multiple - 1e-9  # confirmed by a full reversal
        else:
            assert p.price == lo[window].min()
            assert h[p.confirm_pos] - p.price >= multiple - 1e-9
    # prefix consistency on arbitrary data
    for t in (len(close) // 2, len(close) - 1):
        cut = zigzag(high.iloc[: t + 1], low.iloc[: t + 1], a.iloc[: t + 1], multiple)
        assert cut == [p for p in out if p.confirm_pos <= t]
