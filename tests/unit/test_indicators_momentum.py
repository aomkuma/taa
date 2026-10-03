from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.errors import ConfigError, DataQualityError
from app.indicators.momentum import cci, rsi, stochastic
from tests.indicator_data import mutate_after, random_ohlc


def series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def first_valid_pos(s: pd.Series) -> int:
    return int(np.argmax(s.notna().to_numpy()))


class TestRsi:
    def test_hand_computed_reference(self) -> None:
        # n = 2; changes [_, +1, -2, +3, +1]
        # seed (pos 2): gain = mean(1, 0) = 0.5, loss = mean(0, 2) = 1   -> RSI = 100 * 0.5 / 1.5
        # pos 3: gain = 0.5*3 + 0.5*0.5 = 1.75, loss = 0.5             -> RSI = 100 * 1.75 / 2.25
        # pos 4: gain = 0.5*1 + 0.5*1.75 = 1.375, loss = 0.25          -> RSI = 100 * 1.375 / 1.625
        out = rsi(series([10, 11, 9, 12, 13]), 2)
        expected = [np.nan, np.nan, 100 * 0.5 / 1.5, 100 * 1.75 / 2.25, 100 * 1.375 / 1.625]
        np.testing.assert_allclose(out.to_numpy(), expected)
        assert out.name == "rsi_2"

    def test_only_gains_is_100_only_losses_is_0(self) -> None:
        assert np.allclose(rsi(pd.Series(np.arange(1.0, 40.0)), 14).dropna(), 100.0)
        assert np.allclose(rsi(pd.Series(np.arange(40.0, 1.0, -1.0)), 14).dropna(), 0.0)

    def test_flat_is_undefined(self) -> None:
        assert rsi(pd.Series(np.full(40, 1.1)), 14).isna().all()

    def test_warmup_and_bounds(self) -> None:
        out = rsi(random_ohlc(300)["close"], 14)
        assert first_valid_pos(out) == 14
        valid = out.dropna()
        assert len(valid) == 300 - 14
        assert ((valid >= 0) & (valid <= 100)).all()


class TestStochastic:
    def test_hand_computed_reference(self) -> None:
        high = series([10, 12, 11, 13, 14])
        low = series([8, 9, 9, 10, 12])
        close = series([9, 11, 10, 12, 13])
        out = stochastic(high, low, close, k=3, k_smooth=1, d=2)
        # raw %K at pos 2: (10 - 8)/(12 - 8) = 50; pos 3: (12 - 9)/(13 - 9) = 75; pos 4: (13 - 9)/(14 - 9) = 80
        np.testing.assert_allclose(out["k"].to_numpy(), [np.nan, np.nan, 50, 75, 80])
        np.testing.assert_allclose(out["d"].to_numpy(), [np.nan, np.nan, np.nan, 62.5, 77.5])

    def test_warmup_and_bounds(self) -> None:
        df = random_ohlc(200)
        out = stochastic(df["high"], df["low"], df["close"], 14, 3, 3)
        assert first_valid_pos(out["k"]) == 15
        assert first_valid_pos(out["d"]) == 17
        valid = out.dropna()
        assert ((valid >= 0) & (valid <= 100)).all().all()

    def test_zero_range_is_undefined(self) -> None:
        flat = pd.Series(np.full(30, 1.1))
        assert stochastic(flat, flat, flat).isna().all().all()

    def test_misaligned_inputs_rejected(self) -> None:
        df = random_ohlc(50)
        with pytest.raises(DataQualityError):
            stochastic(df["high"], df["low"], df["close"].iloc[:-1])


class TestCci:
    def test_hand_computed_reference(self) -> None:
        # TP = [2, 4, 6]; mean = 4; MAD = (2 + 0 + 2) / 3; CCI = (6 - 4) / (0.015 * 4/3) = 100
        price = series([2, 4, 6])
        out = cci(price, price, price, 3)
        np.testing.assert_allclose(out.to_numpy(), [np.nan, np.nan, 100.0])

    def test_warmup(self) -> None:
        df = random_ohlc(100)
        assert first_valid_pos(cci(df["high"], df["low"], df["close"], 20)) == 19

    def test_flat_is_undefined_and_short_is_nan(self) -> None:
        flat = pd.Series(np.full(30, 1.1))
        assert cci(flat, flat, flat).isna().all()
        assert cci(flat.iloc[:5], flat.iloc[:5], flat.iloc[:5], 20).isna().all()

    def test_invalid_period(self) -> None:
        price = series([1, 2, 3])
        with pytest.raises(ConfigError):
            cci(price, price, price, 1)


@pytest.mark.parametrize("t", [60, 150, 298])
def test_no_look_ahead(t: int) -> None:
    df = random_ohlc(300)
    mutated = mutate_after(df, t)
    for fn in (
        lambda d: rsi(d["close"]).to_frame(),
        lambda d: stochastic(d["high"], d["low"], d["close"]),
        lambda d: cci(d["high"], d["low"], d["close"]).to_frame(),
    ):
        before, after = fn(df), fn(mutated)
        pd.testing.assert_frame_equal(before.iloc[: t + 1], after.iloc[: t + 1])
        assert not before.iloc[t + 1 :].equals(after.iloc[t + 1 :])


class TestTalibCrossCheck:
    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return random_ohlc(800, seed=11)

    def test_rsi_exact(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        expected = talib.RSI(df["close"].to_numpy(), 14)
        np.testing.assert_allclose(rsi(df["close"], 14), expected, rtol=1e-10, equal_nan=True)

    def test_stochastic_exact(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        h, lo, c = (df[k].to_numpy() for k in ("high", "low", "close"))
        k_ref, d_ref = talib.STOCH(h, lo, c, 14, 3, 0, 3, 0)
        out = stochastic(df["high"], df["low"], df["close"], 14, 3, 3)
        # TA-Lib also blanks slow %K until %D is defined (position 17); ours is defined two bars earlier
        np.testing.assert_allclose(out["k"].iloc[17:], k_ref[17:], rtol=1e-10)
        np.testing.assert_allclose(out["d"], d_ref, rtol=1e-10, equal_nan=True)

    def test_cci_exact(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        h, lo, c = (df[k].to_numpy() for k in ("high", "low", "close"))
        out = cci(df["high"], df["low"], df["close"], 20)
        np.testing.assert_allclose(out, talib.CCI(h, lo, c, 20), rtol=1e-8, equal_nan=True)
