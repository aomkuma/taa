"""Hand-worked tests of row 57's fold logic (wf_process.py): no fold sees its own trading months."""

import numpy as np
import pandas as pd
import pytest

import wf_process as W

U = "UTC"


def test_folds_quarters_and_cut():
    F = W.folds(pd.Timestamp("2022-10-01", tz=U), pd.Timestamp("2023-05-15", tz=U))
    assert [(f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}", f"{c:%Y-%m-%d}") for a, b, c in F] == [
        ("2021-10-01", "2022-10-01", "2023-01-01"), ("2022-01-01", "2023-01-01", "2023-04-01"),
        ("2022-04-01", "2023-04-01", "2023-05-15")]


def test_default_folds_end_before_the_exam():
    F = W.folds()
    assert F[0][1] == pd.Timestamp("2022-10-01", tz=U) and F[-1][2] == W.EXAM
    for (_, s1, e1), (_, s2, _) in zip(F, F[1:], strict=False):
        assert e1 == s2  # contiguous trading windows


def test_fit_never_sees_its_own_months():
    T = pd.DataFrame({"t_in": pd.to_datetime(["2022-09-30 23:00", "2022-09-30 23:50", "2022-10-01 00:10", "2021-09-30 00:00"], utc=True),
                      "t_exit": pd.to_datetime(["2022-09-30 23:30", "2022-10-01 00:20", "2022-10-01 00:40", "2021-09-30 01:00"],
                                               utc=True)})
    fs, ts, te = pd.Timestamp("2021-10-01", tz=U), pd.Timestamp("2022-10-01", tz=U), pd.Timestamp("2023-01-01", tz=U)
    # row 0 exits before the start -> fit; row 1 exits after the start -> not fit (and not traded: entered before);
    # row 2 is a trading-month trade; row 3 is older than 12 months
    assert W.fit_mask(T, fs, ts).tolist() == [True, False, False, False]
    assert W.trade_mask(T, ts, te).tolist() == [False, False, True, False]


def test_candidate_bands():
    B = W.candidate_bands(np.arange(1.0, 101.0))  # quartiles 25.75, 50.5, 75.25
    assert len(B) == 10
    assert B[0] == (-np.inf, pytest.approx(25.75)) and B[3] == (pytest.approx(75.25), np.inf)
    assert (-np.inf, np.inf) in B
    assert B[4] == (-np.inf, pytest.approx(50.5))  # the first adjacent pair


def test_choose_band_best_and_stand_aside():
    atr = np.arange(1.0, 101.0)
    R = np.where(atr >= 75.25, 0.5, -0.1)  # only the top quartile pays
    band, r, n = W.choose_band(atr, R)
    assert band[0] == pytest.approx(75.25) and band[1] == np.inf and r == pytest.approx(0.5) and n == 25
    # nothing reaches +0.10 -> stand aside
    band, r, n = W.choose_band(atr, np.full(100, 0.05))
    assert band is None
    # too few trades for any band of >= 20 except the wider ones: 30 trades -> quartiles of 7-8 are ineligible
    band, r, n = W.choose_band(np.arange(30.0), np.full(30, 0.2))
    assert n >= 20
    assert W.choose_band(np.array([]), np.array([]))[0] is None


def test_tie_goes_to_more_trades():
    atr = np.arange(1.0, 101.0)
    band, r, n = W.choose_band(atr, np.full(100, 0.3))  # every band ties at +0.3 -> the whole range (100 trades)
    assert n == 100 and band == (-np.inf, np.inf)


def test_in_band_open_edges():
    a = np.array([0.5, 12.0, 15.99, 16.0, 99.0])
    assert W.in_band(a, (12.0, 16.0)).tolist() == [False, True, True, False, False]
    assert W.in_band(a, (-np.inf, 12.0)).tolist() == [True, False, False, False, False]
    assert not W.in_band(a, None).any()


def test_year_of():
    t = pd.Series(pd.to_datetime(["2023-09-30", "2023-10-01", "2026-04-17"], utc=True))
    assert W.year_of(t).tolist() == ["2022-23", "2023-24", "2025-26"]


def test_small_bands_are_not_eligible():
    atr = np.arange(60.0)  # quartile bands of 15 trades each (< 20), pairs of 30
    R = np.where(atr >= np.quantile(atr, 0.75), 1.0, 0.2)
    band, r, n = W.choose_band(atr, R)
    # the top quartile alone (+1.0 on 15) is not eligible; the best eligible is the top pair: (15 x 0.2 + 15 x 1.0) / 30
    assert n == 30 and r == pytest.approx(0.6)
