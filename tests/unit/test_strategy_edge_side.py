"""Hand-worked H4 lean cases, from close-stamped H1 candles.

The rule measured and frozen on 2026-10-27 (`research/2026-10-26-three-bots/RULES_LOCKED.md`, rule set 2)
is a QUANTITY on the H4 frame, not a D1 label: the close's distance from its own 50-bar mean in its own
14-bar ATR, signed. An earlier version of this module read a D1 regime label; the measurement put D1
last of the three frames (+0.030 against H4's +0.156 correlation with the trade's R).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from app.core.enums import Side, Timeframe
from app.indicators.volatility import atr
from app.strategy import edge_side as module
from app.strategy.edge_side import ATR_BARS, MEAN_BARS, behind, edge_lean, edge_side, resample_from_h1

NEEDED = MEAN_BARS + ATR_BARS  # 64 closed H4 bars


def h1_frame(h4_closes: list[float], *, spread: float = 1.0, forming: float | None = None):
    """H1 candles, CLOSE-stamped as the app's frames are, that resample into the given H4 closes.

    Each H4 bar is four H1 bars: the first three sit at the previous close so the H4 close is the value
    asked for, and every bar spans ``spread`` so the ATR is predictable.
    """
    closes: list[float] = []
    for i, value in enumerate(h4_closes):
        previous = h4_closes[i - 1] if i else value
        closes += [previous, previous, previous, value]
    if forming is not None:
        closes += [forming]  # one extra H1 bar: the H4 bar it belongs to has not closed
    # the first H1 bar CLOSES at 01:00, so it opens at 00:00 and its H4 bar opens at 00:00 too
    index = pd.date_range(datetime(2026, 1, 1, 1, tzinfo=UTC), periods=len(closes), freq="1h")
    frame = pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread / 2 for c in closes],
            "low": [c - spread / 2 for c in closes],
            "close": closes,
        },
        index=index,
    )
    return {Timeframe.H1: frame}, pd.Timestamp(frame.index[-1])


def expected_lean(frames, at) -> float:
    """The same number worked out from the resampled frame, independently of the function under test."""
    bars = resample_from_h1(frames[Timeframe.H1], 4)
    closed = bars[(bars.index + pd.Timedelta(hours=4)) <= at]
    mean = closed.close.rolling(MEAN_BARS).mean().iloc[-1]
    width = atr(closed.high, closed.low, closed.close, ATR_BARS).iloc[-1]
    return float((closed.close.iloc[-1] - mean) / width)


class TestTheLean:
    def test_a_rising_frame_leans_up_and_a_falling_one_leans_down(self):
        up, at_up = h1_frame([100.0 + i for i in range(NEEDED)])
        down, at_down = h1_frame([100.0 - i for i in range(NEEDED)])
        assert edge_lean(up, at_up, Timeframe.M5) > 0
        assert edge_lean(down, at_down, Timeframe.M5) < 0

    def test_a_flat_frame_leans_neither_way(self):
        frames, at = h1_frame([100.0] * NEEDED)
        assert edge_lean(frames, at, Timeframe.M5) == pytest.approx(0.0)
        assert edge_side(frames, at, Timeframe.M5) is None  # exactly zero is on neither side

    def test_the_number_is_the_distance_from_the_mean_in_atrs(self):
        frames, at = h1_frame([100.0 + i for i in range(NEEDED)])
        assert edge_lean(frames, at, Timeframe.M5) == pytest.approx(expected_lean(frames, at))

    def test_a_bar_that_has_not_closed_is_not_read(self):
        # the forming H4 bar carries a huge close; reading it would swamp a flat 64-bar history
        flat, at = h1_frame([100.0] * NEEDED)
        with_forming, at_forming = h1_frame([100.0] * NEEDED, forming=10_000.0)
        assert edge_lean(with_forming, at_forming, Timeframe.M5) == pytest.approx(
            edge_lean(flat, at, Timeframe.M5)
        )

    def test_too_little_history_is_no_answer_rather_than_a_guess(self):
        frames, at = h1_frame([100.0 + i for i in range(NEEDED - 1)])
        assert edge_lean(frames, at, Timeframe.M5) is None
        assert edge_side(frames, at, Timeframe.M5) is None

    def test_a_missing_h1_frame_is_no_answer(self):
        assert edge_lean({}, pd.Timestamp("2026-01-01", tz="UTC"), Timeframe.M5) is None


class TestTheGuardrails:
    def test_the_frame_read_must_be_larger_than_the_entry_frame(self):
        frames, at = h1_frame([100.0] * NEEDED)
        with pytest.raises(ValueError, match="must be smaller"):
            edge_lean(frames, at, Timeframe.H4)  # the rule is meaningless read on the entry frame
        with pytest.raises(ValueError, match="must be smaller"):
            edge_lean(frames, at, Timeframe.D1, frame=Timeframe.H4)

    def test_h1_and_d1_can_be_read_too_so_the_frame_can_be_re_measured(self):
        frames, at = h1_frame([100.0 + i for i in range(NEEDED * 7)])
        assert edge_lean(frames, at, Timeframe.M5, frame=Timeframe.H1) is not None
        assert edge_lean(frames, at, Timeframe.M5, frame=Timeframe.D1) is not None


class TestBehind:
    def test_a_buy_wants_the_lean_up_and_a_sell_wants_it_down(self):
        assert behind(1.5, Side.BUY) == 1.5
        assert behind(1.5, Side.SELL) == -1.5
        assert behind(-1.5, Side.SELL) == 1.5

    def test_no_lean_stays_no_lean(self):
        assert behind(None, Side.BUY) is None


class TestTheSideShortcut:
    def test_it_follows_the_sign_of_the_lean(self):
        up, at_up = h1_frame([100.0 + i for i in range(NEEDED)])
        down, at_down = h1_frame([100.0 - i for i in range(NEEDED)])
        assert edge_side(up, at_up, Timeframe.M5) is Side.BUY
        assert edge_side(down, at_down, Timeframe.M5) is Side.SELL


class TestNothingNonFiniteEscapes:
    """`nan < 0` is False, so a NaN lean would sail through a gate written as "refuse when negative" and
    open a trade on no evidence. Found by the developer session reviewing this gate while it was live on
    the DEMO account (2026-10-27); it was right, and the gate was switched off until this was closed."""

    def test_a_non_finite_width_gives_no_lean(self, monkeypatch: pytest.MonkeyPatch):
        # the guard is tested directly: the data that would reach it is hard to build on purpose, because
        # the resample drops NaN buckets and the ATR's first true range is NaN anyway - two accidental
        # defences that this test must not be allowed to hide behind
        frames, at = h1_frame([100.0 + i for i in range(NEEDED)])
        assert edge_lean(frames, at, Timeframe.M5) is not None  # finite before the ruler is broken
        for bad in (float("inf"), float("nan")):
            monkeypatch.setattr(module, "atr", lambda *_a, bad=bad, **_k: pd.Series([bad] * 200))
            assert edge_lean(frames, at, Timeframe.M5) is None, bad

    def test_a_non_finite_mean_gives_no_lean(self, monkeypatch: pytest.MonkeyPatch):
        frames, at = h1_frame([100.0 + i for i in range(NEEDED)])
        h1 = frames[Timeframe.H1]
        # an infinite CLOSE inside the last 50 H4 buckets (bucket 60 = H1 bars 240-243): inf survives the
        # dropna, unlike NaN, and poisons the 50-bar mean. Bucket 10 would not - it is outside the window.
        h1.iloc[243, h1.columns.get_loc("close")] = float("inf")
        assert edge_lean(frames, at, Timeframe.M5) is None

    def test_a_zero_width_frame_gives_no_lean(self):
        # every bar identical: the ATR is 0, so the distance in ATRs is not a number
        frames, at = h1_frame([100.0] * NEEDED, spread=0.0)
        assert edge_lean(frames, at, Timeframe.M5) is None


def test_the_h4_buckets_are_hand_worked_without_the_production_resampler():
    """The developer session called `expected_lean` partly circular: it reuses `resample_from_h1`, so it
    cannot prove the one-hour shift is in the right direction. This checks the timestamps by hand.

    App H1 bars are stamped at the CLOSE. A bar stamped 01:00 covers 00:00-01:00 and belongs to the H4
    bar that OPENS at 00:00 and CLOSES at 04:00. So the four bars stamped 01:00, 02:00, 03:00, 04:00 are
    one H4 bar, indexed 00:00, and it may not be read before 04:00.
    """
    closes = pd.date_range(datetime(2026, 3, 2, 1, tzinfo=UTC), periods=8, freq="1h")  # 01:00 .. 08:00
    h1 = pd.DataFrame(
        {"open": 10.0, "high": [11, 12, 13, 14, 15, 16, 17, 18.0], "low": 9.0, "close": 10.0}, index=closes
    )
    bars = resample_from_h1(h1, 4)
    assert list(bars.index) == [
        pd.Timestamp("2026-03-02 00:00", tz="UTC"),
        pd.Timestamp("2026-03-02 04:00", tz="UTC"),
    ]
    # the first H4 bar holds the H1 bars stamped 01:00-04:00, whose highs are 11, 12, 13, 14
    assert list(bars.high) == [14.0, 18.0]
    # and it is readable at 04:00, not a minute before
    assert bars.index[0] + pd.Timedelta(hours=4) == pd.Timestamp("2026-03-02 04:00", tz="UTC")


def test_a_tiny_atr_overflows_to_infinity_and_is_refused(monkeypatch: pytest.MonkeyPatch):
    """The developer session was right and I was wrong (2026-10-27).

    I wrote that the final `isfinite` guard was unreachable, because the mean and width guards stop every
    non-finite input. They do - but a FINITE, positive, tiny ATR (1e-320) passes both and then overflows
    the division to infinity. `inf < 0` is False, so a gate written as "refuse when the lean is negative"
    would open on no evidence at all. The guard is live code, and this is the input that reaches it.
    """
    frames, at = h1_frame([100.0 + i for i in range(NEEDED)])
    monkeypatch.setattr(module, "atr", lambda *_a, **_k: pd.Series([1e-320] * 200))
    assert edge_lean(frames, at, Timeframe.M5) is None
