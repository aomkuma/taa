from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.core.enums import Timeframe
from app.core.errors import ConfigError
from app.indicators.volatility import atr, atr_percentile, bollinger, historical_volatility, true_range
from tests.indicator_data import mutate_after, random_ohlc


def series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def first_valid_pos(s: pd.Series) -> int:
    return int(np.argmax(s.notna().to_numpy()))


class TestAtr:
    def test_hand_computed_reference(self) -> None:
        high = series([10, 11, 12, 11, 10])
        low = series([8, 9, 9, 8, 7])
        close = series([9, 10, 11, 9, 8])
        np.testing.assert_allclose(true_range(high, low, close), [np.nan, 2, 3, 3, 3])
        # n = 2: seed mean(2, 3) = 2.5; then 0.5*3 + 0.5*2.5 = 2.75; 2.875
        np.testing.assert_allclose(atr(high, low, close, 2), [np.nan, np.nan, 2.5, 2.75, 2.875])

    def test_gap_counts_in_true_range(self) -> None:
        # a gap up: range 1, but the bar is 5 above the previous close
        tr = true_range(series([10, 16]), series([9, 15]), series([10, 15.5]))
        assert tr.iloc[1] == 6

    def test_warmup(self) -> None:
        df = random_ohlc(100)
        out = atr(df["high"], df["low"], df["close"], 14)
        assert first_valid_pos(out) == 14
        assert (out.dropna() > 0).all()


class TestBollinger:
    def test_hand_computed_reference(self) -> None:
        # window [1, 2, 3]: mid 2, population σ = sqrt(2/3)
        out = bollinger(series([1, 2, 3]), 3, 2.0)
        sigma = math.sqrt(2 / 3)
        row = out.iloc[2]
        assert row["mid"] == pytest.approx(2.0)
        assert row["upper"] == pytest.approx(2 + 2 * sigma)
        assert row["lower"] == pytest.approx(2 - 2 * sigma)
        assert row["width"] == pytest.approx(4 * sigma / 2)
        assert row["percent_b"] == pytest.approx((3 - (2 - 2 * sigma)) / (4 * sigma))
        assert out.iloc[:2].isna().all().all()

    def test_flat_window(self) -> None:
        out = bollinger(pd.Series(np.full(30, 1.1)), 20).iloc[19:]
        assert (out["upper"] == out["mid"]).all()
        assert (out["width"] == 0).all()
        assert out["percent_b"].isna().all()

    def test_invalid_k(self) -> None:
        with pytest.raises(ConfigError):
            bollinger(series([1, 2, 3]), 2, 0.0)


class TestHistoricalVolatility:
    def test_hand_computed_reference(self) -> None:
        close = series([100.0, 110.0, 99.0])
        r = np.diff(np.log([100.0, 110.0, 99.0]))
        out = historical_volatility(close, 2, bars_per_year=252)
        assert out.iloc[:2].isna().all()
        assert out.iloc[2] == pytest.approx(np.std(r, ddof=1) * math.sqrt(252))

    def test_constant_drift_has_zero_volatility(self) -> None:
        close = pd.Series(100.0 * np.exp(0.001 * np.arange(50)))
        out = historical_volatility(close, 20, bars_per_year=Timeframe.H1.bars_per_year)
        assert first_valid_pos(out) == 20
        assert np.allclose(out.dropna(), 0.0, atol=1e-9)

    def test_non_positive_price_is_nan(self) -> None:
        out = historical_volatility(series([1, 2, 0, 3, 4]), 2, bars_per_year=252)
        assert out.iloc[2:4].isna().all()

    def test_invalid_bars_per_year(self) -> None:
        with pytest.raises(ConfigError):
            historical_volatility(series([1, 2, 3]), 2, bars_per_year=0)


class TestAtrPercentile:
    def test_reference(self) -> None:
        out = atr_percentile(series([1, 2, 3, 4, 0.5, 3]), 4)
        # windows: [1,2,3,4] -> 3/3; [2,3,4,0.5] -> 0/3; [3,4,0.5,3] -> 2/3 (ties count)
        np.testing.assert_allclose(out.to_numpy(), [np.nan, np.nan, np.nan, 100, 0, 200 / 3])

    def test_warmup_follows_atr(self) -> None:
        df = random_ohlc(300)
        out = atr_percentile(atr(df["high"], df["low"], df["close"], 14), 100)
        assert first_valid_pos(out) == 14 + 100 - 1
        valid = out.dropna()
        assert ((valid >= 0) & (valid <= 100)).all()


@pytest.mark.parametrize("t", [150, 298])
def test_no_look_ahead(t: int) -> None:
    df = random_ohlc(300)
    mutated = mutate_after(df, t)
    for fn in (
        lambda d: atr(d["high"], d["low"], d["close"]).to_frame(),
        lambda d: bollinger(d["close"]),
        lambda d: historical_volatility(d["close"], bars_per_year=6240).to_frame(),
        lambda d: atr_percentile(atr(d["high"], d["low"], d["close"]), 100).to_frame(),
    ):
        before, after = fn(df), fn(mutated)
        pd.testing.assert_frame_equal(before.iloc[: t + 1], after.iloc[: t + 1])
        assert not before.iloc[t + 1 :].equals(after.iloc[t + 1 :])


class TestTalibCrossCheck:
    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return random_ohlc(800, seed=11)

    def test_atr_exact(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        h, lo, c = (df[k].to_numpy() for k in ("high", "low", "close"))
        out = atr(df["high"], df["low"], df["close"], 14)
        np.testing.assert_allclose(out, talib.ATR(h, lo, c, 14), rtol=1e-10, equal_nan=True)
        np.testing.assert_allclose(
            true_range(df["high"], df["low"], df["close"]), talib.TRANGE(h, lo, c), equal_nan=True
        )

    def test_bollinger_exact(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        upper, mid, lower = talib.BBANDS(df["close"].to_numpy(), 20, 2.0, 2.0, 0)
        out = bollinger(df["close"], 20, 2.0)
        np.testing.assert_allclose(out["upper"], upper, rtol=1e-9, equal_nan=True)
        np.testing.assert_allclose(out["mid"], mid, rtol=1e-12, equal_nan=True)
        np.testing.assert_allclose(out["lower"], lower, rtol=1e-9, equal_nan=True)
