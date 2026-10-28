"""The harness's own guards. Run: .venv\\Scripts\\python -m pytest research/2026-10-26-three-bots -q

These exist because of one afternoon, 2026-10-27: a measurement script called ``run(f, P())`` - copied
from this module's own ``main()``, whose title said "defaults" - and produced a day of conclusions about
a setup the app does not ship. Nothing caught it. The script's self-check compared the script to
``bots.run`` *with the parameters the script itself passed in*, which can never fail on a wrong input.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import audit  # noqa: E402
import bots  # noqa: E402


def test_the_bare_defaults_are_refused() -> None:
    with pytest.raises(ValueError, match="bare P\\(\\) defaults"):
        bots.run({}, bots.P())


def test_a_deliberate_variation_is_allowed_through_the_guard() -> None:
    # it must fail on the empty frames, not on the guard: varying a parameter on purpose is normal work
    with pytest.raises((KeyError, AttributeError, IndexError)):
        bots.run({}, replace(bots.P(), box=0.2))


def test_the_shipped_set_is_one_definition_shared_with_audit() -> None:
    assert audit.BEST is bots.SHIPPED


def test_the_shipped_range_bot_breaks_and_does_not_fade() -> None:
    # the difference that cost the afternoon: P()'s default is a different SETUP, not a different value
    assert bots.P().range_mode == "fade"
    assert bots.SHIPPED["RANGE"].range_mode == "break"


def test_the_shipped_set_matches_the_app_strategies() -> None:
    """The harness must carry the app's own numbers, or it measures something we do not run."""
    from app.strategy.range_break import RangeBreakParams
    from app.strategy.trend_box import TrendBoxDownParams, TrendBoxUpParams

    down, up, rng = bots.SHIPPED["DOWN"], bots.SHIPPED["UP"], bots.SHIPPED["RANGE"]
    assert (down.box, down.buffer, down.min_r) == (
        TrendBoxDownParams().box,
        TrendBoxDownParams().buffer,
        TrendBoxDownParams().min_r,
    )
    assert (up.box, up.buffer, up.min_r) == (
        TrendBoxUpParams().box,
        TrendBoxUpParams().buffer,
        TrendBoxUpParams().min_r,
    )
    assert (rng.buffer, rng.tp_range, rng.min_r) == (
        RangeBreakParams().buffer,
        RangeBreakParams().tp_range,
        RangeBreakParams().min_r,
    )


def test_every_bot_set_names_only_its_own_bot() -> None:
    for name, p in bots.SHIPPED.items():
        assert p.bots == (name,), f"{name} would run {p.bots}"


def test_a_dict_holding_the_bare_defaults_is_refused() -> None:
    # the first guard only looked at a single P; {"DOWN": P()} walked straight past it
    with pytest.raises(ValueError, match=r"bare P\(\) defaults for"):
        bots.run({}, {"DOWN": bots.P()})


def test_the_shipped_set_matches_every_app_default_it_shares() -> None:
    """Field by field, so adding one to the app and not here is a failing test, not a silent drift."""
    from app.strategy.range_break import RangeBreakParams
    from app.strategy.trend_box import TrendBoxDownParams, TrendBoxUpParams

    for p, app in (
        (bots.SHIPPED["DOWN"], TrendBoxDownParams()),
        (bots.SHIPPED["UP"], TrendBoxUpParams()),
    ):
        assert (p.box, p.buffer, p.min_r, p.min_tp) == (app.box, app.buffer, app.min_r, app.min_take_profit)
    rng, app_rng = bots.SHIPPED["RANGE"], RangeBreakParams()
    assert (rng.buffer, rng.tp_range, rng.min_r, rng.min_tp) == (
        app_rng.buffer,
        app_rng.tp_range,
        app_rng.min_r,
        app_rng.min_take_profit,
    )
    assert rng.range_tf == "H4"  # app/strategy/range_break.py resamples the H1 frame to H4


def test_a_reading_is_never_taken_from_a_bar_that_has_not_closed() -> None:
    """The mistake the developer session caught: to_frame indexes a bar by its OPEN, and an extra shift
    back made every reading available an hour early and put the buckets an hour out. Hand-worked: a bar
    that OPENS at 00:00 on a 4-hour frame covers 00:00-04:00, so it is readable at 04:00, not at 03:00."""
    import edge_by_condition as ec
    import momentum as mom

    n = 1400  # enough H1 bars for a 50-bucket mean on D1
    idx = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")  # bar i OPENS at idx[i]
    price = pd.Series(range(n), dtype=float) / 10 + 100
    h1 = pd.DataFrame(
        {"open": price.values, "high": price.values + 1, "low": price.values - 1, "close": price.values},
        index=idx,
    )
    h4 = mom.momentum(h1, 4)
    assert len(h4) and (h4.index.hour % 4 == 0).all()  # buckets start on the 4-hour boundary
    assert (h4.readable == h4.index + pd.Timedelta(hours=4)).all()  # readable only once closed
    d1 = ec.regimes(h1)
    assert len(d1) and (d1.index.hour == 0).all()
    assert (d1.closed_at == d1.index + pd.Timedelta(days=1)).all()
    # and the reader never hands back a bar whose close is still ahead of the asking time
    at = pd.Timestamp("2026-01-10 05:30", tz="UTC")
    usable = h4[h4.readable <= at]
    assert usable.index[-1] + pd.Timedelta(hours=4) <= at


def test_a_flat_mean_is_mixed_and_never_bear() -> None:
    import edge_by_condition as ec

    idx = pd.date_range("2026-01-01", periods=60 * 24, freq="1h", tz="UTC")
    flat = pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}, index=idx)
    labels = set(ec.regimes(flat).regime.iloc[55:])  # past the 50-day warmup
    assert labels == {"mixed"}, labels
