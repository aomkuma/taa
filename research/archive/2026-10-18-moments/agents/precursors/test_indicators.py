"""indicators.py by hand, and a second computation on the bars cut at the moment (nothing after a moment can change its
readings).

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_indicators.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indicators import at, bars, features, series  # noqa: E402


def minutes(start: str, n: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    c = 2000 + np.cumsum(rng.normal(0, 0.4, n))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + rng.random(n) * 0.3, "low": np.minimum(o, c) - rng.random(n) * 0.3,
                         "close": c, "tick_volume": 1.0, "spread": 20.0}, index=idx)


def test_d1_and_h4_on_the_server_day():
    # 2026-09-30 is summer time in Athens (UTC+3): the server day starts at 21:00 UTC, the H4 bars at 21, 01, 05 .. UTC
    m = minutes("2026-09-30 19:00", 6 * 60)
    d = bars(m, "1D")
    assert d["last"].iloc[0] == pd.Timestamp("2026-09-30 20:59", tz="UTC") and d["avail"].iloc[0] == pd.Timestamp("2026-09-30 21:00", tz="UTC")
    h4 = bars(m, "4h")
    assert h4["last"].tolist()[:2] == [pd.Timestamp("2026-09-30 20:59", tz="UTC"), pd.Timestamp("2026-10-01 00:59", tz="UTC")]
    assert h4["high"].iloc[1] == m.loc["2026-09-30 21:00":"2026-10-01 00:59", "high"].max()


def test_the_last_bar_complete_by_the_moment():
    av = pd.to_datetime(["2026-05-04 08:05", "2026-05-04 08:10", "2026-05-04 08:15"], utc=True).as_unit("ns").asi8
    t = pd.to_datetime(["2026-05-04 08:04", "2026-05-04 08:10", "2026-05-04 08:14"], utc=True).as_unit("ns").asi8
    assert at(av, t).tolist() == [-1, 1, 1]


def test_series_on_a_steady_rise():
    n = 400
    c = 100.0 + np.arange(n)
    b = pd.DataFrame({"high": c + 0.5, "low": c - 0.5, "close": c})
    s = series(b)
    # every bar: true range 1.5 (from the previous close 1 below to the high 0.5 above) -> ATR 1.5; no loss -> RSI 100
    assert s["rsi"][-1] == 100.0 and s["di"][-1] > 0
    assert np.isnan(s["ema200"][198]) and not np.isnan(s["ema200"][199])
    # an EMA of a steady rise climbs 1 a bar once settled: 5 bars = 5 / 1.5 ATR; the close stays (n - 1) / 2 above it
    assert s["ema20_slope"][-1] == pytest.approx(5 / 1.5, rel=1e-6) and s["ema20"][-1] == pytest.approx(9.5 / 1.5, rel=1e-6)
    assert s["atr_rel"][-1] == pytest.approx(1.0)
    # MACD: EMA 12 lags 5.5, EMA 26 lags 12.5 -> the line 7 (in ATRs 7 / 1.5), its 9-bar average the same
    assert s["macd"][-1] == pytest.approx(7 / 1.5, rel=1e-6) and s["macd_sig"][-1] == pytest.approx(0.0, abs=1e-6)
    # Stochastic: the close 13.5 above the 14-bar low, the range 14 -> 96.43 every bar, its signal the same
    assert s["stoch"][-1] == pytest.approx(100 * 13.5 / 14) and s["stoch_sig"][-1] == pytest.approx(0.0, abs=1e-9)
    # ADX: every bar +DM 1 of a true range 1.5, no -DM -> +DI 66.7, -DI 0, DX 100
    assert s["di"][-1] == pytest.approx(100 / 1.5, rel=1e-6) and s["adx"][-1] == pytest.approx(100.0, rel=1e-6)
    # Bollinger on 20 steps of 1: the middle 9.5 below the close, 2 population sd = 2 * sqrt(33.25)
    sd2 = 2 * np.sqrt(33.25)
    assert s["bb_pos"][-1] == pytest.approx((9.5 + sd2) / (2 * sd2)) and s["bb_width"][-1] == pytest.approx(2 * sd2 / 1.5)


def test_nothing_after_the_moment_changes_a_reading():
    from indicators import TFS  # noqa: PLC0415

    m = minutes("2026-08-31 00:00", 20 * 24 * 60, seed=7)
    rng = np.random.default_rng(3)
    t = pd.DatetimeIndex(sorted(m.index[rng.integers(15 * 24 * 60, len(m) - 1, 12)] + pd.Timedelta(minutes=1)))
    X = features(m, t)
    for k, tk in enumerate(t):
        cut = m[m.index < tk]  # only the M1 bars complete by the moment
        for tf, rule in TFS.items():
            full, part = bars(m, rule), bars(cut, rule)
            bi = int(at(pd.DatetimeIndex(full["avail"]).as_unit("ns").asi8, np.array([tk.value]))[0])
            # the bar used is complete by the moment: the same bar, the same prices, in the cut data
            assert full.iloc[bi][["open", "high", "low", "close"]].equals(part.iloc[bi][["open", "high", "low", "close"]]), (tf, str(tk))
            S = series(part)  # every reading recomputed from the bars known at the moment (plus the forming one)
            for key, v in S.items():
                a, b = X[f"{tf}_{key}"].iloc[k], v[bi]
                assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b, rel=1e-9, abs=1e-9), (str(tk), tf, key, a, b)


def test_the_previous_day_and_todays_open():
    # three server days (Athens summer: days start 21:00 UTC); a moment on day 3 at 05:00 UTC
    m = minutes("2026-09-28 21:00", 3 * 24 * 60, seed=5)
    tk = pd.Timestamp("2026-09-30 22:00", tz="UTC")  # day 3 began 2026-09-30 21:00 UTC
    X = features(m, pd.DatetimeIndex([tk]))
    prev = m.loc["2026-09-29 21:00":"2026-09-30 20:59"]
    px = m.loc[: tk - pd.Timedelta(minutes=1), "close"].iloc[-1]
    assert X["D1_prev_pos"].iloc[0] == pytest.approx((px - prev.low.min()) / (prev.high.max() - prev.low.min()))
    d = bars(m, "1D")
    import foundation as F  # noqa: PLC0415

    a = F.atr(d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy(), 14)[1]  # too few days: NaN, as MT5 draws nothing
    assert np.isnan(a) and np.isnan(X["D1_from_open"].iloc[0])


def test_the_differences_point_the_right_way():
    import foundation as F  # noqa: PLC0415

    rng = np.random.default_rng(11)
    c = 100 + np.cumsum(rng.normal(0, 1, 600))
    b = pd.DataFrame({"high": c + 0.4, "low": c - 0.4, "close": c})
    s = series(b)
    a = F.atr(b.high.to_numpy(), b.low.to_numpy(), c, 14)
    line, sig = F.macd(c)
    main, ssig = F.stochastic(b.high.to_numpy(), b.low.to_numpy(), c)
    # line above its signal -> positive; the main line above its signal -> positive
    assert np.allclose(s["macd_sig"][100:], ((line - sig) / a)[100:]) and np.allclose(s["stoch_sig"][100:], (main - ssig)[100:])
    k = np.nonzero(line[100:] - sig[100:] > 0)[0][0] + 100
    assert s["macd_sig"][k] > 0
