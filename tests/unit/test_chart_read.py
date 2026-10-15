"""Chart read (TAA-L813, docs/CHART_READ.md §10): the MT5 ZigZag port, structure, levels with roles,
trendlines, events, scenarios, no look-ahead and serialization."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.core.errors import ConfigError
from app.indicators.chart_read import (
    ChartRead,
    ChartReadFrame,
    ChartReadParams,
    EventKind,
    LevelRole,
    ScenarioKind,
    Structure,
    _zigzag_maps,
    retrace_into,
    with_major,
    zigzag_pivots,
)
from app.indicators.price_action import StructureLabel, SwingKind

T0 = datetime(2026, 1, 5, tzinfo=UTC)
H1 = timedelta(hours=1)
POINT = 0.01
WICK = 0.05


def path(points: list[float], step: float = 0.25) -> pd.DataFrame:
    """Closes along straight legs through *points* (``step`` per bar); each bar's wicks are ``WICK``."""
    closes = [points[0]]
    for a, b in pairwise(points):
        bars = max(1, round(abs(b - a) / step))
        closes.extend(a + (b - a) * (i + 1) / bars for i in range(bars))
    c = np.round(np.array(closes), 6)
    o = np.concatenate([[c[0]], c[:-1]])
    return frame(o, np.maximum(o, c) + WICK, np.minimum(o, c) - WICK, c)


def frame(o: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> pd.DataFrame:
    index = pd.DatetimeIndex([T0 + (i + 1) * H1 for i in range(len(c))])
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=index)


def append(df: pd.DataFrame, bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    o, h, lo, c = (np.array([b[i] for b in bars]) for i in range(4))
    extra = frame(o, h, lo, c)
    extra.index = pd.DatetimeIndex([df.index[-1] + (i + 1) * H1 for i in range(len(bars))])
    return pd.concat([df, extra])


def read_last(df: pd.DataFrame, params: ChartReadParams | None = None) -> ChartRead:
    r = ChartReadFrame("H1", df, POINT, params).at(len(df) - 1)
    assert r is not None
    return r


def random_walk(n: int = 1200, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    c = 100 + rng.normal(0, 0.3, n).cumsum()
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + rng.uniform(0.02, 0.3, n)
    lo = np.minimum(o, c) - rng.uniform(0.02, 0.3, n)
    return frame(o, np.round(h, 2), np.round(lo, 2), np.round(c, 2))


class TestZigZag:
    def test_pivots_sit_on_the_turns_and_alternate(self) -> None:
        df = path([100, 110, 100, 110, 100, 105, 103], step=0.5)
        piv = zigzag_pivots(df["high"].to_numpy(), df["low"].to_numpy(), POINT)
        assert [(s.kind, s.pivot_pos) for s in piv] == [
            (SwingKind.HIGH, 20),
            (SwingKind.LOW, 40),
            (SwingKind.HIGH, 60),
            (SwingKind.LOW, 80),
        ]
        assert [s.price for s in piv] == pytest.approx([110.05, 99.95, 110.05, 99.95])
        assert all(s.confirm_pos > s.pivot_pos for s in piv)

    def test_a_pivot_is_known_only_backstep_bars_after_the_opposite_candidate(self) -> None:
        df = path([100, 110, 100, 110, 100, 105, 102], step=0.5)
        hi, lo = df["high"].to_numpy(), df["low"].to_numpy()
        for backstep in (1, 3, 5):
            piv = zigzag_pivots(hi, lo, POINT, backstep=backstep)
            # the same pivots for every backstep here, known later the larger it is
            assert [s.pivot_pos for s in piv] == [20, 40, 60, 80]
        b1 = zigzag_pivots(hi, lo, POINT, backstep=1)[0]
        b5 = zigzag_pivots(hi, lo, POINT, backstep=5)[0]
        assert b5.confirm_pos - b1.confirm_pos == 4

    def test_rejects_a_bad_point(self) -> None:
        with pytest.raises(ConfigError):
            zigzag_pivots(np.ones(30), np.ones(30), 0.0)


class TestNoLookAhead:
    def test_the_read_on_data_cut_at_t_equals_the_read_at_t(self) -> None:
        df = random_walk()
        full = ChartReadFrame("H1", df, POINT)
        rng = np.random.default_rng(3)
        for t in sorted(rng.choice(np.arange(60, len(df)), 30, replace=False)):
            cut = ChartReadFrame("H1", df.iloc[: t + 1], POINT)
            assert cut.at(int(t)) == full.at(int(t)), t
            known = [s for s in full.pivots if s.confirm_pos <= t]
            assert cut.pivots == known, t

    def test_the_display_read_has_no_look_ahead_either(self) -> None:
        df = random_walk()
        p = ChartReadParams().for_display()
        full = ChartReadFrame("H1", df, POINT, p)
        rng = np.random.default_rng(4)
        for t in sorted(rng.choice(np.arange(60, len(df)), 30, replace=False)):
            assert ChartReadFrame("H1", df.iloc[: t + 1], POINT, p).at(int(t)) == full.at(int(t)), t

    def test_changing_future_bars_never_changes_a_past_read(self) -> None:
        df = random_walk(seed=11)
        t = 700
        before = ChartReadFrame("H1", df, POINT).at(t)
        mutated = df.copy()
        mutated.iloc[t + 1 :, :] = mutated.iloc[t + 1 :, :] * 1.05
        assert ChartReadFrame("H1", mutated, POINT).at(t) == before

    def test_no_read_during_the_atr_warm_up(self) -> None:
        f = ChartReadFrame("H1", random_walk(n=40), POINT)
        assert f.at(5) is None
        assert f.at(999) is None


# a staircase down (highs 112 > 110 > 107 > 104, lows 106 > 103 > 100), then a pause that fixes the 104 high
DOWN = [100, 112, 106, 110, 103, 107, 100, 104, 101, 102]


class TestStructure:
    def test_a_staircase_down_is_down_with_the_invalidation_at_the_last_lower_high(self) -> None:
        r = read_last(path(DOWN))
        assert r.structure is Structure.DOWN
        highs = [p for p in r.pivots if p.kind is SwingKind.HIGH]
        assert highs[-1].label is StructureLabel.LH
        assert r.invalidation == pytest.approx(104.05)
        assert not r.broken
        lines = {tl.kind: tl for tl in r.trendlines}
        assert set(lines) == {SwingKind.HIGH}
        assert lines[SwingKind.HIGH].slope_atr < 0
        assert lines[SwingKind.HIGH].b_price == pytest.approx(104.05)

    def test_a_staircase_up_is_up_with_the_invalidation_at_the_last_higher_low(self) -> None:
        r = read_last(path([110, 98, 104, 100, 107, 103, 110, 106, 109, 108]))
        assert r.structure is Structure.UP
        assert r.invalidation == pytest.approx(105.95)
        assert {tl.kind for tl in r.trendlines} == {SwingKind.LOW}

    def test_a_triangle_is_contracting_with_both_lines(self) -> None:
        r = read_last(path([100, 112, 102, 110, 104, 108, 105.5, 107, 106.25]))
        assert r.structure is Structure.CONTRACTING
        assert r.invalidation is None
        assert {tl.kind for tl in r.trendlines} == {SwingKind.HIGH, SwingKind.LOW}

    def test_a_megaphone_is_broadening_without_lines(self) -> None:
        r = read_last(path([106, 108, 104, 110, 102, 112, 100, 103, 102]))
        assert r.structure is Structure.BROADENING
        assert r.trendlines == ()

    def test_equal_highs_are_flat(self) -> None:
        r = read_last(path([100, 110, 104, 110, 103, 106, 105]))
        assert r.structure is Structure.FLAT
        assert any(p.label is StructureLabel.EQH for p in r.pivots)

    def test_too_few_pivots_is_none(self) -> None:
        r = read_last(path([100, 110, 104, 107, 106]))
        assert r.structure is Structure.NONE

    def test_a_close_above_the_last_lower_high_breaks_the_down_trend_before_a_new_pivot(self) -> None:
        r = read_last(path([100, 112, 106, 110, 103, 107, 100, 104, 97, 106]))
        assert r.structure is Structure.DOWN
        assert r.broken

    def test_age_counts_the_pivots_since_the_structure_changed(self) -> None:
        r = read_last(path(DOWN))
        assert r.structure is Structure.DOWN
        # the first DOWN: the 103 low (LL after the 110 LH); then 107, 100 and 104 follow
        assert r.age_legs == 3


class TestLegAndPosition:
    def test_the_leg_in_progress_runs_from_the_last_pivot(self) -> None:
        r = read_last(path(DOWN))
        assert r.leg is not None
        assert r.leg.direction == -1
        assert r.leg.start == pytest.approx(104.05)
        assert r.leg.extreme == pytest.approx(100.95)
        assert r.leg.from_pivot_atr > 0
        # the close inside the previous leg 99.95 -> 104.05
        assert r.leg.retrace == pytest.approx((104.05 - r.close) / (104.05 - 99.95), abs=1e-4)

    def test_retrace_into_and_the_higher_timeframe(self) -> None:
        assert retrace_into(100.0, 110.0, 103.2) == pytest.approx(0.68)
        assert retrace_into(110.0, 100.0, 110.0) == pytest.approx(1.0)
        assert retrace_into(100.0, 100.0, 1.0) is None
        low = read_last(path(DOWN))
        high = read_last(path([100, 112, 106, 110, 103, 107]))
        mixed = with_major(low, high)
        p0, p1 = high.pivots[-2].price, high.pivots[-1].price
        assert mixed.retrace_major == pytest.approx((p1 - low.close) / (p1 - p0), abs=1e-4)
        assert with_major(low, None) is low


BASE = [104, 106, 101, 106, 101, 105]  # two lows at 100.95: a support


class TestLevels:
    def test_two_equal_lows_make_one_support_with_two_touches(self) -> None:
        r = read_last(path([*BASE, 102.5]))
        support = r.nearest(above=False)
        assert support is not None
        assert support.price == pytest.approx(100.95)
        assert support.role is LevelRole.SUPPORT
        assert support.touches == 2

    def test_a_support_closed_through_is_flipped_and_a_later_touch_is_a_retest(self) -> None:
        df = path([*BASE, 95, 100.7])
        df = append(df, [(100.7, 100.98, 100.45, 100.5)])  # probes 100.95 from below, closes away, red
        r = read_last(df)
        level = next(lv for lv in r.levels if lv.price == pytest.approx(100.95))
        assert level.role is LevelRole.FLIPPED
        assert level.above
        assert level.retests == 1
        retest = [e for e in r.events if e.kind is EventKind.RETEST]
        assert [(e.direction, e.at) for e in retest] == [(-1, r.at)]

    def test_a_level_closed_through_both_ways_is_spent(self) -> None:
        r = read_last(path([*BASE, 95, 103, 102]))
        assert all(lv.price != pytest.approx(100.95) for lv in r.levels)

    def test_the_display_keeps_a_level_crossed_twice_with_its_role_by_side(self) -> None:
        r = read_last(path([*BASE, 95, 103, 102]), ChartReadParams(spent_crossings=4))
        level = next(lv for lv in r.levels if lv.price == pytest.approx(100.95))
        assert level.role is LevelRole.SUPPORT
        assert not level.above

    def test_minor_swings_add_levels_near_the_price(self) -> None:
        df = random_walk()
        rules = read_last(df)
        shown = read_last(df, ChartReadParams().for_display())
        assert not any(lv.minor for lv in rules.levels)
        minor = [lv for lv in shown.levels if lv.minor]
        assert minor
        assert min(abs(lv.dist_atr) for lv in shown.levels) <= min(abs(lv.dist_atr) for lv in rules.levels)

    def test_levels_keep_max_levels_per_side(self) -> None:
        r = read_last(random_walk(), ChartReadParams(max_levels=2))
        assert sum(lv.above for lv in r.levels) <= 2
        assert sum(not lv.above for lv in r.levels) <= 2
        prices = [lv.price for lv in r.levels]
        assert prices == sorted(prices, reverse=True)


class TestEvents:
    def test_a_wick_through_the_support_that_closes_back_is_a_sweep_reclaim(self) -> None:
        df = path([*BASE, 101.6])
        df = append(df, [(101.6, 101.7, 100.6, 101.3)])
        r = read_last(df)
        sweeps = [e for e in r.events if e.kind is EventKind.SWEEP_RECLAIM]
        assert [(e.direction, e.price) for e in sweeps] == [(1, pytest.approx(100.95))]
        assert r.nearest(above=False) is not None
        assert r.nearest(above=False).role is LevelRole.SUPPORT  # type: ignore[union-attr]

    def test_two_closes_below_the_support_are_a_break_that_holds(self) -> None:
        df = path([*BASE, 101.4])
        df = append(df, [(101.4, 101.45, 100.4, 100.5), (100.5, 100.6, 100.3, 100.4)])
        r = read_last(df)
        breaks = [e for e in r.events if e.kind is EventKind.BREAK_HOLD and not e.trendline]
        assert [(e.direction, e.price) for e in breaks] == [(-1, pytest.approx(100.95))]
        assert breaks[0].at == r.at - H1
        assert breaks[0].known_at == r.at

    def test_a_break_that_closes_back_is_a_sweep_and_keeps_the_level(self) -> None:
        df = path([*BASE, 101.4])
        df = append(df, [(101.4, 101.45, 100.4, 100.5), (100.5, 101.3, 100.45, 101.2)])
        r = read_last(df)
        assert not [e for e in r.events if e.kind is EventKind.BREAK_HOLD and not e.trendline]
        assert [e.direction for e in r.events if e.kind is EventKind.SWEEP_RECLAIM] == [1]
        support = r.nearest(above=False)
        assert support is not None
        assert (support.price, support.role) == (pytest.approx(100.95), LevelRole.SUPPORT)

    def test_events_older_than_event_bars_drop_out(self) -> None:
        df = path([*BASE, 101.4])
        df = append(df, [(101.4, 101.45, 100.4, 100.5), (100.5, 100.6, 100.3, 100.4)])
        df = append(df, [(100.4, 100.5, 100.2, 100.3)] * 3)
        r = read_last(df)
        assert not [e for e in r.events if e.kind is EventKind.BREAK_HOLD and not e.trendline]


class TestReadNow:
    def test_a_pullback_from_the_leg_extreme_is_a_provisional_pivot(self) -> None:
        # a staircase down, then a fresh low well below the last one and a bounce of more than prov_atr ATR
        r = read_last(path([*DOWN, 96, 98.5]))
        assert r.provisional is not None
        assert r.provisional.kind is SwingKind.LOW
        assert r.provisional.label is StructureLabel.LL
        assert r.provisional.price == pytest.approx(96 - WICK)
        assert r.structure_now is Structure.DOWN
        assert r.invalidation_now is not None

    def test_no_provisional_pivot_while_price_sits_at_the_extreme(self) -> None:
        r = read_last(path([*DOWN, 96]))
        assert r.provisional is None
        assert r.structure_now is r.structure

    def test_a_new_high_in_progress_is_a_provisional_pivot_on_break(self) -> None:
        # an uptrend that pulled back to a confirmed low, then runs through the last high (114.05) at the close
        pts = [100, 112, 104, 110, 106, 114, 108, 116, 115, 117]
        assert read_last(path(pts)).provisional is None
        r = read_last(path(pts), ChartReadParams(prov_on_break=True))
        assert r.provisional is not None and r.provisional.kind is SwingKind.HIGH
        assert r.provisional.label is StructureLabel.HH and r.provisional.price == pytest.approx(117 + WICK)

    def test_mixed_swings_read_now_as_the_side_the_close_broke(self) -> None:
        # a megaphone (HH then LL), then the close runs above the last high: broadening, read now as up
        pts = [106, 108, 104, 110, 102, 112, 100, 113]
        plain = read_last(path(pts))
        assert plain.structure_now is Structure.BROADENING
        r = read_last(path(pts), ChartReadParams(now_by_break=True))
        assert r.structure_now is Structure.UP
        assert r.structure is plain.structure  # the confirmed read is unchanged

    def test_the_provisional_pivot_is_off_with_a_large_prov_atr(self) -> None:
        r = read_last(path([*DOWN, 96, 98.5]), ChartReadParams(prov_atr=100.0))
        assert r.provisional is None


class TestScenarios:
    def test_at_a_support_the_scenarios_are_a_break_down_and_a_bounce(self) -> None:
        r = read_last(path([*BASE, 101.3]))
        brk, rej = r.scenarios
        assert (brk.kind, brk.direction, brk.trigger) == (ScenarioKind.BREAK, -1, pytest.approx(100.95))
        assert (rej.kind, rej.direction) == (ScenarioKind.REJECT, 1)
        assert rej.target is not None
        assert rej.target > r.close
        text = r.scenario_text()
        assert "break below 100.95 that holds" in text

    def test_the_text_names_the_trend_s_end(self) -> None:
        r = read_last(path(DOWN))
        assert "the down trend ends above 104.05" in r.scenario_text()


class TestSerialization:
    def test_round_trip_through_json(self) -> None:
        df = path([*BASE, 95, 100.7])
        df = append(df, [(100.7, 100.98, 100.45, 100.5)])
        r = with_major(read_last(df), read_last(path([100, 112, 106, 110, 103, 107])))
        d = json.loads(json.dumps(r.to_dict()))
        assert ChartRead.from_dict(d) == r
        assert d["text"] == r.scenario_text()

    def test_every_random_walk_read_round_trips(self) -> None:
        f = ChartReadFrame("H1", random_walk(n=600, seed=5), POINT)
        for pos in range(100, 600, 37):
            r = f.at(pos)
            assert r is not None
            assert ChartRead.from_dict(json.loads(json.dumps(r.to_dict()))) == r


class TestParams:
    def test_backstep_must_be_below_depth(self) -> None:
        with pytest.raises(ConfigError):
            ChartReadParams(depth=3, backstep=3)

    def test_negative_tolerance_is_refused(self) -> None:
        with pytest.raises(ConfigError):
            ChartReadParams(tol_atr=-0.1)

    def test_config_block_defaults_and_checks(self) -> None:
        from pydantic import ValidationError

        from app.config import ChartReadConfig, ContextMapConfig

        c = ContextMapConfig().chart_read
        assert (c.enabled, c.depth, c.deviation, c.backstep) == (True, 12, 5, 3)
        with pytest.raises(ValidationError):
            ChartReadConfig.model_validate({"depth": 3, "backstep": 3})
        with pytest.raises(ValidationError):
            ChartReadConfig.model_validate({"by_timeframe": {"M1": {"depth": 2}}})
        with pytest.raises(ValidationError):
            ChartReadConfig.model_validate({"unknown": 1})
        ok = ChartReadConfig.model_validate({"by_timeframe": {"M1": {"depth": 24}}})
        assert ok.by_timeframe


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "mt5_zigzag"


@pytest.mark.parametrize("name", ["TAA_zigzag_XAUUSD_H1.csv", "TAA_zigzag_EURUSD_M15.csv"])
def test_the_port_matches_the_terminal_s_zigzag(name: str) -> None:
    """800 closed bars exported from the FBS demo terminal (scripts/mt5/TAA_ExportZigZag.mq5, 2026-10-14):
    the candidate maps and every fixed pivot equal MT5's, past the warm-up and before its redrawn last leg."""
    df = pd.read_csv(FIXTURES / name)
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    point = float(df["point"].iloc[0])
    hmap, lmap = _zigzag_maps(hi, lo, point, 12, 5, 3)
    span = slice(24, len(df) - 3)
    assert np.allclose(hmap[span], df["high_map"].to_numpy(float)[span])
    assert np.allclose(lmap[span], df["low_map"].to_numpy(float)[span])
    mine = zigzag_pivots(hi, lo, point)
    theirs = np.flatnonzero(df["zigzag"].to_numpy(float) != 0)
    first, last = mine[2].pivot_pos, int(theirs[-3])
    assert [s.pivot_pos for s in mine if first <= s.pivot_pos <= last] == [
        int(p) for p in theirs if first <= p <= last
    ]
    assert len(theirs) > 30
