"""Contract shared by every indicator (docs/INDICATORS.md): exact warm-up, no look-ahead, short input is NaN.

Add every new indicator to ``REGISTRY`` with the first defined position of each output column.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from app.core.enums import Timeframe
from app.indicators.momentum import cci, rsi, stochastic
from app.indicators.price_action import candle_anatomy
from app.indicators.trend import adx, ema, macd, sma
from app.indicators.volatility import atr, atr_percentile, bollinger, historical_volatility, true_range
from app.indicators.volume import volume_ratio, volume_zscore
from tests.indicator_data import mutate_after, random_ohlc


@dataclass(frozen=True)
class Spec:
    fn: Callable[[pd.DataFrame], pd.DataFrame | pd.Series]
    first: dict[str, int]  # column -> first defined position (0-based)

    def frame(self, df: pd.DataFrame) -> pd.DataFrame:
        out = self.fn(df)
        return out.to_frame() if isinstance(out, pd.Series) else out


def hlc(d: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    return d["high"], d["low"], d["close"]


HV_BARS = Timeframe.H1.bars_per_year

REGISTRY: dict[str, Spec] = {
    "sma": Spec(lambda d: sma(d["close"], 20), {"sma_20": 19}),
    "ema": Spec(lambda d: ema(d["close"], 20), {"ema_20": 19}),
    "macd": Spec(lambda d: macd(d["close"], 12, 26, 9), {"macd": 25, "signal": 33, "hist": 33}),
    "adx": Spec(lambda d: adx(*hlc(d), 14), {"plus_di": 14, "minus_di": 14, "adx": 27}),
    "rsi": Spec(lambda d: rsi(d["close"], 14), {"rsi_14": 14}),
    "stochastic": Spec(lambda d: stochastic(*hlc(d), 14, 3, 3), {"k": 15, "d": 17}),
    "cci": Spec(lambda d: cci(*hlc(d), 20), {"cci_20": 19}),
    "true_range": Spec(lambda d: true_range(*hlc(d)), {"true_range": 1}),
    "atr": Spec(lambda d: atr(*hlc(d), 14), {"atr_14": 14}),
    "bollinger": Spec(
        lambda d: bollinger(d["close"], 20, 2.0),
        {"mid": 19, "upper": 19, "lower": 19, "width": 19, "percent_b": 19},
    ),
    "historical_volatility": Spec(
        lambda d: historical_volatility(d["close"], 20, bars_per_year=HV_BARS), {"hv_20": 20}
    ),
    "atr_percentile": Spec(lambda d: atr_percentile(atr(*hlc(d), 14), 100), {"atr_pct_100": 113}),
    "volume_ratio": Spec(lambda d: volume_ratio(d["tick_volume"], 20), {"volume_ratio_20": 20}),
    "volume_zscore": Spec(lambda d: volume_zscore(d["tick_volume"], 20), {"volume_z_20": 20}),
    "candle_anatomy": Spec(
        lambda d: candle_anatomy(d["open"], *hlc(d)),
        {
            "body": 0,
            "range": 0,
            "body_ratio": 0,
            "upper_wick_ratio": 0,
            "lower_wick_ratio": 0,
            "direction": 0,
        },
    ),
}

NAMES = sorted(REGISTRY)


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return random_ohlc(400, seed=21)


@pytest.mark.parametrize("name", NAMES)
def test_columns_and_index(name: str, df: pd.DataFrame) -> None:
    out = REGISTRY[name].frame(df)
    assert list(out.columns) == list(REGISTRY[name].first)
    assert out.index.equals(df.index)
    assert all(dtype == np.float64 for dtype in out.dtypes)


@pytest.mark.parametrize("name", NAMES)
def test_warmup_is_exactly_nan(name: str, df: pd.DataFrame) -> None:
    out = REGISTRY[name].frame(df)
    for col, first in REGISTRY[name].first.items():
        values = out[col].to_numpy()
        assert np.isnan(values[:first]).all(), f"{name}.{col}: value before position {first}"
        assert np.isfinite(values[first:]).all(), f"{name}.{col}: NaN after warm-up on clean data"


@pytest.mark.parametrize("name", NAMES)
def test_short_input_is_all_nan_not_an_error(name: str, df: pd.DataFrame) -> None:
    spec = REGISTRY[name]
    shortest = min(spec.first.values())
    if shortest == 0:
        pytest.skip("defined from the first bar")
    out = spec.frame(df.iloc[:shortest])
    assert out.isna().all().all()


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("t", [120, 250, 398])
def test_no_look_ahead(name: str, t: int, df: pd.DataFrame) -> None:
    spec = REGISTRY[name]
    before = spec.frame(df)
    after = spec.frame(mutate_after(df, t))
    pd.testing.assert_frame_equal(before.iloc[: t + 1], after.iloc[: t + 1])
    assert not before.iloc[t + 1 :].equals(after.iloc[t + 1 :]), "mutation had no effect; test is vacuous"


@pytest.mark.parametrize("name", NAMES)
def test_empty_input_gives_empty_output(name: str, df: pd.DataFrame) -> None:
    out = REGISTRY[name].frame(df.iloc[:0])
    assert out.empty
    assert list(out.columns) == list(REGISTRY[name].first)
