from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.errors import ConfigError
from app.indicators.volume import volume_ratio, volume_zscore
from tests.indicator_data import mutate_after, random_ohlc


def test_ratio_reference_excludes_current_bar() -> None:
    vol = pd.Series([100, 200, 300, 600], dtype="int64")
    out = volume_ratio(vol, 3)
    # baseline for position 3 is mean(100, 200, 300) = 200
    np.testing.assert_allclose(out.to_numpy(), [np.nan, np.nan, np.nan, 3.0])
    assert out.name == "volume_ratio_3"


def test_zscore_reference() -> None:
    vol = pd.Series([100.0, 200.0, 300.0, 500.0])
    out = volume_zscore(vol, 3)
    assert out.iloc[3] == pytest.approx((500 - 200) / 100)  # sample stdev of 100, 200, 300 is 100
    assert out.iloc[:3].isna().all()


def test_dead_and_constant_baselines_are_nan() -> None:
    assert np.isnan(volume_ratio(pd.Series([0, 0, 0, 5]), 3).iloc[3])
    assert np.isnan(volume_zscore(pd.Series([7, 7, 7, 9]), 3).iloc[3])


def test_warmup() -> None:
    vol = random_ohlc(100)["tick_volume"]
    assert volume_ratio(vol, 20).iloc[:20].isna().all()
    assert volume_ratio(vol, 20).iloc[20:].notna().all()
    assert volume_zscore(vol, 20).iloc[20:].notna().all()


def test_invalid_period() -> None:
    with pytest.raises(ConfigError):
        volume_zscore(pd.Series([1.0, 2.0]), 1)


@pytest.mark.parametrize("t", [60, 298])
def test_no_look_ahead(t: int) -> None:
    df = random_ohlc(300)
    mutated = mutate_after(df, t)
    for fn in (volume_ratio, volume_zscore):
        before, after = fn(df["tick_volume"]), fn(mutated["tick_volume"])
        pd.testing.assert_series_equal(before.iloc[: t + 1], after.iloc[: t + 1])
        assert not before.iloc[t + 1 :].equals(after.iloc[t + 1 :])
