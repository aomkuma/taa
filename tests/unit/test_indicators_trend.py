from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.errors import ConfigError, DataQualityError
from app.indicators.common import recursive_smooth, true_range_values
from app.indicators.trend import adx, ema, macd, sma
from tests.indicator_data import mutate_after, random_ohlc


def series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def first_valid_pos(s: pd.Series) -> int:
    return int(np.argmax(s.notna().to_numpy()))


class TestSmaEma:
    def test_sma_reference(self) -> None:
        out = sma(series([1, 2, 3, 4, 5]), 3)
        np.testing.assert_allclose(out.to_numpy(), [np.nan, np.nan, 2, 3, 4])
        assert out.name == "sma_3"

    def test_ema_reference_seeded_with_sma(self) -> None:
        # alpha = 0.5; seed = mean(1, 2, 3) = 2; then 0.5*4 + 0.5*2 = 3, ...
        out = ema(series([1, 2, 3, 4, 5, 6]), 3)
        np.testing.assert_allclose(out.to_numpy(), [np.nan, np.nan, 2, 3, 4, 5])

    def test_ema_skips_leading_nan_warmup(self) -> None:
        out = ema(series([np.nan, np.nan, 1, 2, 3, 4]), 3)
        np.testing.assert_allclose(out.to_numpy(), [np.nan] * 4 + [2, 3])

    def test_interior_nan_fails_closed(self) -> None:
        out = ema(series([1, 2, 3, np.nan, 5, 6]), 2)
        assert np.isfinite(out.iloc[2])
        assert out.iloc[3:].isna().all()

    def test_constant_series(self) -> None:
        s = pd.Series(np.full(50, 1.25))
        assert np.allclose(ema(s, 10).dropna(), 1.25)
        assert np.allclose(sma(s, 10).dropna(), 1.25)

    def test_keeps_index(self) -> None:
        df = random_ohlc(30)
        assert ema(df["close"], 5).index.equals(df.index)

    @pytest.mark.parametrize("bad", [0, -1, 2.5, True])
    def test_invalid_period(self, bad: object) -> None:
        with pytest.raises(ConfigError):
            sma(series([1, 2, 3]), bad)  # type: ignore[arg-type]

    def test_too_short_is_all_nan(self) -> None:
        assert ema(series([1, 2]), 3).isna().all()
        assert sma(series([1, 2]), 3).isna().all()

    def test_wilder_alpha(self) -> None:
        out = recursive_smooth(np.array([2.0, 4.0, 8.0]), 2, 0.5)
        np.testing.assert_allclose(out, [np.nan, 3.0, 5.5])


class TestMacd:
    def test_composition_and_warmup(self) -> None:
        close = random_ohlc(200)["close"]
        out = macd(close, 12, 26, 9)
        assert list(out.columns) == ["macd", "signal", "hist"]
        np.testing.assert_allclose(
            out["macd"].dropna(), (ema(close, 12) - ema(close, 26)).dropna(), rtol=0, atol=1e-15
        )
        assert first_valid_pos(out["macd"]) == 25
        assert first_valid_pos(out["signal"]) == 33
        np.testing.assert_allclose(out["hist"], out["macd"] - out["signal"])

    def test_constant_series_is_zero(self) -> None:
        out = macd(pd.Series(np.full(60, 1.1)))
        assert np.allclose(out.dropna().to_numpy(), 0.0)

    def test_fast_must_be_shorter(self) -> None:
        with pytest.raises(ConfigError):
            macd(series([1.0] * 40), 26, 12)


class TestAdx:
    def test_hand_computed_reference(self) -> None:
        # n = 2. DM/TR by hand: +DM = [_,1,1,0,0], -DM = [_,0,0,1,1], TR = [_,2,3,3,3]
        high = series([10, 11, 12, 11, 10])
        low = series([8, 9, 9, 8, 7])
        close = series([9, 10, 11, 9, 8])
        out = adx(high, low, close, 2)
        tr = np.array([2.5, 2.75, 2.875])
        plus = np.array([1.0, 0.5, 0.25])
        minus = np.array([0.0, 0.5, 0.75])
        np.testing.assert_allclose(out["plus_di"].iloc[2:], 100 * plus / tr)
        np.testing.assert_allclose(out["minus_di"].iloc[2:], 100 * minus / tr)
        # DX = [100, 0, 50] -> ADX seed mean(100, 0) = 50, then 0.5*50 + 0.5*50
        np.testing.assert_allclose(out["adx"].to_numpy(), [np.nan, np.nan, np.nan, 50, 50])

    def test_true_range_uses_previous_close(self) -> None:
        tr = true_range_values(
            np.array([10.0, 11.0, 12.0]), np.array([8.0, 10.5, 9.0]), np.array([9.0, 9.0, 11])
        )
        np.testing.assert_allclose(tr, [np.nan, 2.0, 3.0])

    def test_steady_uptrend(self) -> None:
        c = np.arange(1.0, 61.0)
        out = adx(pd.Series(c + 0.5), pd.Series(c - 0.5), pd.Series(c), 14)
        assert first_valid_pos(out["plus_di"]) == 14
        assert first_valid_pos(out["adx"]) == 27
        np.testing.assert_allclose(out["plus_di"].dropna(), 100 / 1.5)
        assert (out["minus_di"].dropna() == 0).all()
        np.testing.assert_allclose(out["adx"].dropna(), 100.0)

    def test_steady_downtrend(self) -> None:
        c = np.arange(100.0, 40.0, -1.0)
        out = adx(pd.Series(c + 0.5), pd.Series(c - 0.5), pd.Series(c), 14)
        assert (out["plus_di"].dropna() == 0).all()
        np.testing.assert_allclose(out["adx"].dropna(), 100.0)

    def test_flat_market_has_no_direction(self) -> None:
        flat = pd.Series(np.full(40, 1.1))
        out = adx(flat, flat, flat, 5)
        assert out.isna().all().all()

    def test_bounds(self) -> None:
        df = random_ohlc(400)
        out = adx(df["high"], df["low"], df["close"]).dropna()
        assert ((out >= 0) & (out <= 100)).all().all()

    def test_misaligned_inputs_rejected(self) -> None:
        df = random_ohlc(50)
        with pytest.raises(DataQualityError):
            adx(df["high"], df["low"].iloc[1:], df["close"])


class TestNoLookAhead:
    @pytest.mark.parametrize("t", [60, 150, 298])
    def test_future_bars_do_not_change_past(self, t: int) -> None:
        df = random_ohlc(300)
        mutated = mutate_after(df, t)
        for fn in (
            lambda d: sma(d["close"], 20).to_frame(),
            lambda d: ema(d["close"], 20).to_frame(),
            lambda d: macd(d["close"]),
            lambda d: adx(d["high"], d["low"], d["close"]),
        ):
            before, after = fn(df), fn(mutated)
            pd.testing.assert_frame_equal(before.iloc[: t + 1], after.iloc[: t + 1])
            assert not before.iloc[t + 1 :].equals(after.iloc[t + 1 :])


class TestTalibCrossCheck:
    """TA-Lib is a dev-only reference. Wilder seeds differ slightly, so compare after a burn-in."""

    BURN_IN = 300

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        return random_ohlc(800, seed=11)

    def test_sma_ema_exact(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        close = df["close"].to_numpy()
        np.testing.assert_allclose(sma(df["close"], 20), talib.SMA(close, 20), rtol=1e-12, equal_nan=True)
        np.testing.assert_allclose(ema(df["close"], 20), talib.EMA(close, 20), rtol=1e-12, equal_nan=True)

    def test_macd(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        m, s, h = talib.MACD(df["close"].to_numpy(), 12, 26, 9)
        out = macd(df["close"]).iloc[self.BURN_IN :]
        np.testing.assert_allclose(out["macd"], m[self.BURN_IN :], rtol=0, atol=1e-10)
        np.testing.assert_allclose(out["signal"], s[self.BURN_IN :], rtol=0, atol=1e-10)
        np.testing.assert_allclose(out["hist"], h[self.BURN_IN :], rtol=0, atol=1e-10)

    def test_adx_di(self, df: pd.DataFrame) -> None:
        talib = pytest.importorskip("talib")
        h, lo, c = (df[k].to_numpy() for k in ("high", "low", "close"))
        out = adx(df["high"], df["low"], df["close"], 14).iloc[self.BURN_IN :]
        b = self.BURN_IN
        np.testing.assert_allclose(out["plus_di"], talib.PLUS_DI(h, lo, c, 14)[b:], atol=1e-6)
        np.testing.assert_allclose(out["minus_di"], talib.MINUS_DI(h, lo, c, 14)[b:], atol=1e-6)
        np.testing.assert_allclose(out["adx"], talib.ADX(h, lo, c, 14)[b:], atol=1e-6)
