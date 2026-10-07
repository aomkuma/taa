"""Research harness (TAA-L707): synthetic paths with known outcomes, and the market re-simulation against the
shadow resolver."""

from __future__ import annotations

import argparse
import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.advisory.shadow import advance, bars_from_frame, new_state
from app.cli.research import cmd_research_replay_family
from app.core.enums import Side, Timeframe
from app.learning.research import (
    MIN_N,
    PricePath,
    ResearchError,
    Retest,
    Row,
    Rules,
    Signal,
    build_path,
    context_frame,
    context_rules,
    default_hypotheses,
    evaluate,
    research,
    simulate,
    simulate_reentry,
    simulate_retest,
    summarize,
    walk_forward,
)
from app.learning.research_data import load_inputs, load_signals
from app.market_data.history_store import ParquetHistoryStore
from app.storage.database import Database
from app.storage.models import ShadowTradeRow

T0 = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
M5 = timedelta(minutes=5)
POINT = 0.00001


def frame(
    rows: list[tuple[float, float, float, float]], *, start: datetime = T0, spread: float = 0.0
) -> pd.DataFrame:
    """Bid M5 bars (open, high, low, close); spread in points."""
    n = len(rows)
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime([start + i * M5 for i in range(n)], utc=True),
            "close_time": pd.to_datetime([start + (i + 1) * M5 for i in range(n)], utc=True),
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "spread": [spread] * n,
        }
    )


def signal(
    side: Side = Side.BUY,
    *,
    entry: float = 1.1000,
    risk: float = 0.0010,
    target: float | None = 2.0,
    spread: float = 0.0,
    cost_r: float = 0.0,
    at: datetime = T0,
    sid: str = "s1",
    timeframe: Timeframe = Timeframe.M15,
    symbol: str = "EURUSD",
) -> Signal:
    sign = side.sign
    tp = None if target is None else entry + sign * target * risk
    return Signal(
        sid,
        "setup_x",
        symbol,
        timeframe,
        side,
        at,
        at,
        entry,
        entry - sign * risk,
        tp,
        risk,
        spread,
        cost_r,
        0.0,
        {},
    )


def path(
    values: list[tuple[float, float, float, float]], *, target: float | None = 2.0, **kw: object
) -> PricePath:
    """A path straight from (open, fav, adv, close) in risks."""
    arr = np.array(values, dtype=float)
    return PricePath(
        arr[:, 0],
        arr[:, 1],
        arr[:, 2],
        arr[:, 3],
        kw.get("end"),  # type: ignore[arg-type]
        target,
        float(kw.get("spread_r", 0.0)),  # type: ignore[arg-type]
        float(kw.get("cost_r", 0.0)),  # type: ignore[arg-type]
        int(kw.get("per_bar", 3)),  # type: ignore[arg-type]
    )


class TestBuildPath:
    def test_buy_uses_bid_bars_relative_to_the_fill(self) -> None:
        bars = frame([(1.1000, 1.1015, 1.0995, 1.1010)], spread=10)
        p = build_path(signal(entry=1.1000), bars, point=POINT)
        assert p.open[0] == pytest.approx(0.0)
        assert p.fav[0] == pytest.approx(1.5)
        assert p.adv[0] == pytest.approx(-0.5)
        assert p.close[0] == pytest.approx(1.0)
        assert p.target == pytest.approx(2.0)
        assert p.per_bar == 3
        assert p.end is None

    def test_sell_exits_at_the_ask(self) -> None:
        bars = frame([(1.1000, 1.1005, 1.0980, 1.0990)], spread=10)  # ask = bid + 0.0001
        p = build_path(signal(Side.SELL, entry=1.1000), bars, point=POINT)
        assert p.open[0] == pytest.approx(-0.1)
        assert p.fav[0] == pytest.approx(1.9)  # low 1.0980 + spread
        assert p.adv[0] == pytest.approx(-0.6)  # high 1.1005 + spread

    def test_window_starts_at_the_entry_and_ends_at_the_time_stop(self) -> None:
        bars = frame([(1.1, 1.1, 1.1, 1.1)] * 4 + [(1.1012, 1.1012, 1.1012, 1.1012)], start=T0 - M5)
        p = build_path(signal(), bars, point=POINT, horizon=3 * M5)
        assert len(p) == 3  # the bar before the entry is not part of it
        assert p.end == pytest.approx(1.2)

    def test_invalid_geometry_fails_closed(self) -> None:
        bad = dataclasses.replace(signal(), initial_sl=1.1010)
        with pytest.raises(ResearchError):
            build_path(bad, frame([(1.1, 1.1, 1.1, 1.1)]), point=POINT)

    def test_mirrored_takes_the_other_side_of_the_spread(self) -> None:
        s = signal(entry=1.1001, spread=0.0001)
        m = s.mirrored()
        assert m.side is Side.SELL
        assert m.entry == pytest.approx(1.1000)
        assert m.risk == pytest.approx(s.risk)
        assert m.tp == pytest.approx(1.1000 - 0.0020)


class TestSimulate:
    def test_target_and_stop(self) -> None:
        assert simulate(path([(0, 0.5, -0.5, 0), (0, 2.1, -0.2, 2)])) == pytest.approx(2.0)
        assert simulate(path([(0, 0.5, -1.2, -1)])) == pytest.approx(-1.0)

    def test_both_in_one_bar_counts_the_stop(self) -> None:
        assert simulate(path([(0, 2.5, -1.5, 0)])) == pytest.approx(-1.0)

    def test_gap_beyond_the_stop_fills_at_the_open(self) -> None:
        assert simulate(path([(0, 0.2, -0.2, 0), (-1.6, -1.5, -1.8, -1.6)])) == pytest.approx(-1.6)

    def test_open_beyond_the_target_fills_at_the_target(self) -> None:
        assert simulate(path([(0, 0.2, -0.2, 0), (2.5, 2.6, 2.4, 2.5)])) == pytest.approx(2.0)

    def test_costs_and_a_wider_stop_keep_the_risk_percent(self) -> None:
        p = path([(0, 0.5, -1.5, -1)], cost_r=0.1)
        assert simulate(p) == pytest.approx(-1.1)
        assert simulate(p, Rules(stop_mult=2.0)) == pytest.approx((-1.0 - 0.1) / 2)  # closed at the end: -1

    def test_end_of_path_closes_at_the_time_stop_open(self) -> None:
        assert simulate(path([(0, 0.5, -0.5, 0.3)], end=0.4)) == pytest.approx(0.4)
        assert simulate(path([(0, 0.5, -0.5, 0.3)])) == pytest.approx(0.3)  # censored: the last close

    def test_break_even_trail_partial_and_time_stop(self) -> None:
        p = path([(0, 1.2, -0.2, 1), (1, 1.1, -0.5, -0.4)])
        assert simulate(p, Rules(break_even=(1.0, 0.05))) == pytest.approx(0.05)
        assert simulate(p, Rules(trail=(1.0, 0.5))) == pytest.approx(0.7)
        assert simulate(
            path([(0, 1.2, -0.2, 1), (1, 1.1, -1.5, -1)]), Rules(partial=(0.5, 1.0))
        ) == pytest.approx(0.5 - 0.5)
        flat = path([(0, 0.2, -0.2, 0.1)] * 6, per_bar=3)
        assert simulate(flat, Rules(time_bars=1)) == pytest.approx(0.1)

    def test_target_override(self) -> None:
        assert simulate(path([(0, 1.1, -0.2, 1)]), Rules(target=1.0)) == pytest.approx(1.0)

    def test_empty_path_is_none(self) -> None:
        empty = np.array([])
        assert simulate(PricePath(empty, empty, empty, empty, None, 2.0, 0.0, 0.0, 3)) is None


class TestRetest:
    def test_fills_only_when_the_entry_side_reaches_the_limit(self) -> None:
        p = path([(0, 0.1, -0.45, 0), (0, 3.0, -0.2, 2.5)], spread_r=0.1)
        assert simulate_retest(p, Retest(0.5, 2.0, 4)) is None  # bid -0.45 + spread 0.1 = -0.35 > -0.5
        p = path([(0, 0.1, -0.6, 0), (0, 3.0, -0.2, 2.5)], spread_r=0.1)
        assert simulate_retest(p, Retest(0.5, 2.0, 4)) == pytest.approx((2.0 + 0.5) / 1.5)

    def test_fill_bar_high_does_not_count_and_stop_from_the_signal_entry(self) -> None:
        p = path([(0, 2.5, -0.6, 0), (0, 0.2, -2.1, -2)])
        assert simulate_retest(p, Retest(0.5, 2.0, 4)) == pytest.approx(-1.0)

    def test_window_and_validation(self) -> None:
        p = path([(0, 0.1, -0.1, 0)] * 3 + [(0, 0.1, -0.7, 0)], per_bar=3)
        assert simulate_retest(p, Retest(0.5, 2.0, 1)) is None
        with pytest.raises(ResearchError):
            simulate_retest(p, Retest(1.0, 1.0, 4))


def test_reentry_after_a_stop() -> None:
    p = path(
        [(0, 0.2, -1.1, -1), (-1, 0.1, -1.2, 0), (0, 2.2, -0.1, 2)], per_bar=1
    )  # bar 1: low before the touch
    assert simulate_reentry(p, 4) == pytest.approx(-1.0 + 2.0)
    assert simulate_reentry(p, 0) == pytest.approx(-1.0)


class TestMatchesTheShadowResolver:
    @pytest.mark.parametrize("seed", range(8))
    @pytest.mark.parametrize("side", [Side.BUY, Side.SELL])
    def test_random_walks(self, seed: int, side: Side) -> None:
        rng = np.random.default_rng(seed)
        n = 400
        closes = 1.1 + np.cumsum(rng.normal(0, 0.0004, n))
        opens = np.concatenate([[1.1], closes[:-1]]) + rng.normal(0, 0.0001, n)  # small gaps
        highs = np.maximum(opens, closes) + rng.uniform(0, 0.0004, n)
        lows = np.minimum(opens, closes) - rng.uniform(0, 0.0004, n)
        bars = frame(list(zip(opens, highs, lows, closes, strict=True)), start=T0, spread=8)
        ask = opens[0] + 8 * POINT
        entry = ask if side is Side.BUY else opens[0]
        s = signal(side, entry=entry, risk=0.0015, target=1.5, spread=8 * POINT)
        horizon = timedelta(hours=12)
        state = new_state(side=side, entry=entry, entry_at=T0, sl=s.initial_sl, tp=s.tp, time_stop=horizon)
        exit_ = advance(state, bars_from_frame(bars, POINT), slippage=0.0)
        assert exit_ is not None
        expected = (exit_.price - entry) * side.sign / s.risk
        assert simulate(build_path(s, bars, point=POINT, horizon=horizon)) == pytest.approx(
            expected, abs=1e-9
        )


class TestStatistics:
    def test_summarize_is_seeded_and_needs_enough_values(self) -> None:
        values = list(np.linspace(-1, 1.2, 50))
        a, b = summarize(values, seed=3), summarize(values, seed=3)
        assert a == b
        assert a.low is not None and a.high is not None and a.low < a.mean < a.high  # type: ignore[operator]
        small = summarize([1.0] * (MIN_N - 1))
        assert small.low is None and small.mean == 1.0
        assert summarize([]).n == 0

    def test_paired_counts_an_unfilled_variant_as_zero(self) -> None:
        losers = [
            (signal(sid=f"a{i}", at=T0 + timedelta(days=i)), path([(0, 0.1, -1.2, -1)])) for i in range(30)
        ]
        hyp = [h for h in default_hypotheses() if h.label.startswith("retest -0.5 R, stop -2 R, 4")]
        rows = evaluate([(s, p, None) for s, p in losers], hyp, split_at=T0 + timedelta(days=15))
        row = rows[0]
        assert row.filled == 30  # -1.2 reaches the -0.5 limit
        never = [(s, path([(0, 0.1, -0.1, -0.05)] * 2)) for s, _ in losers]
        row = evaluate([(s, p, None) for s, p in never], hyp, split_at=T0 + timedelta(days=15))[0]
        assert row.filled == 0
        assert row.paired is not None and row.paired.all.mean == pytest.approx(0.05)

    def test_walk_forward_reports_the_other_half_only(self) -> None:
        def halves(first: float, second: float) -> object:
            from app.learning.research import Halves, Stat

            return Halves(
                Stat(400, (first + second) / 2, None, None, None),
                Stat(200, first, None, None, None),
                Stat(200, second, None, None, None),
            )

        rows = [
            Row("g", "fits the first half", 400, 400, halves(0.3, -0.2), None),  # type: ignore[arg-type]
            Row("g", "steady", 400, 400, halves(0.1, 0.1), None),  # type: ignore[arg-type]
        ]
        first, second = walk_forward(rows)
        assert (first.chosen_on, first.label, first.judged.mean, first.candidates) == (
            "first",
            "fits the first half",
            -0.2,
            2,
        )
        assert (second.label, second.judged.mean) == ("steady", 0.1)

    def test_context_rules_are_judged_on_the_other_half(self) -> None:
        values = {f"s{i}": (i < 300, 1.0 if i % 2 else -1.0) for i in range(600)}
        context = {f"s{i}": {"x": float(i % 2)} for i in range(600)}
        rules, candidates = context_rules(values, context, top=1, min_n=50)
        assert candidates > 0
        assert all(r.judged.mean == pytest.approx(1.0) for r in rules if r.op == ">")


def test_context_frame_has_no_look_ahead() -> None:
    rng = np.random.default_rng(1)
    closes = 1.1 + np.cumsum(rng.normal(0, 0.001, 300))
    rows = [(c, c + 0.001, c - 0.001, c) for c in closes]
    a = context_frame(frame(rows))
    changed = rows[:200] + [(c * 1.05, c * 1.06, c * 1.04, c * 1.05) for c, *_ in rows[200:]]
    b = context_frame(frame(changed))
    pd.testing.assert_frame_equal(a.iloc[:200], b.iloc[:200])


def test_research_report_end_to_end() -> None:
    rng = np.random.default_rng(4)
    signals, paths, mirrors = [], {}, {}
    for i in range(120):
        s = signal(sid=f"s{i}", at=T0 + timedelta(hours=6 * i))
        fav = float(rng.uniform(0, 3))
        adv = float(rng.uniform(-1.5, 0))
        signals.append(s)
        paths[s.shadow_id] = path([(0, fav, adv, fav + adv)])
        mirrors[s.shadow_id] = path([(0, -adv, -fav, -(fav + adv))])
    rows = [(1.1, 1.101, 1.099, 1.1)] * 3000
    report = research(signals, paths, mirrors, {"EURUSD": frame(rows, start=T0 - 1000 * M5)}, resamples=200)
    data = report.to_dict()
    assert data["signals"] == 120 and data["with_path"] == 120
    assert {r["group"] for r in data["rows"]} >= {"baseline", "exit", "stop", "retest", "reentry"}
    assert "past results do not predict" in data["notes"][0]


class TestLoading:
    def test_signals_and_paths_from_a_database_and_the_store(self, tmp_path: Path) -> None:
        db = Database("sqlite://")
        db.create_all()
        with db.session() as sess:
            for i, status in enumerate(["CLOSED", "OPEN"]):
                sess.add(_row(f"o{i}", status))
        found = load_signals(db, strategy="setup_x")
        assert [s.shadow_id for _, s in found] == ["o0:PLAN"]
        store = ParquetHistoryStore(tmp_path)
        bars = frame([(1.1, 1.1015, 1.0995, 1.101)] * 40, start=T0 - 4 * M5)
        bars["time_server"] = bars["open_time"]
        bars["tick_volume"] = 1
        bars["real_volume"] = 0
        store.save("FBS-Demo", "EURUSD", Timeframe.M5, bars)
        store.save("FBS-Demo", "EURUSD", Timeframe.M15, bars)
        (tmp_path / "FBS-Demo" / "EURUSD" / "spec.json").write_text(
            '{"spec": {"point": 1e-05}}', encoding="utf-8"
        )
        inputs = load_inputs(found, store)
        assert inputs.resolution == {"EURUSD": "M5"}
        (s,) = inputs.signals
        assert s.spread == pytest.approx(12 * POINT)
        assert inputs.paths[s.shadow_id].cost_r == pytest.approx(0.02)
        assert inputs.mirrors[s.shadow_id] is not None

    def test_missing_spec_fails_closed(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchError):
            load_inputs([("FBS-Demo", signal())], ParquetHistoryStore(tmp_path))


def _row(oid: str, status: str) -> ShadowTradeRow:
    return ShadowTradeRow(
        shadow_id=f"{oid}:PLAN",
        opportunity_id=oid,
        variant="PLAN",
        source="REPLAY",
        server="FBS-Demo",
        strategy="setup_x",
        symbol="EURUSD",
        asset_class="FX_MAJOR",
        timeframe="M15",
        side="BUY",
        session="LONDON",
        setup_strength=50.0,
        rr=2.0,
        features={"ctx:htf_aligned": 1.0},
        atr=0.001,
        alerted=False,
        followed=False,
        status=status,
        signal_at=T0,
        created_at=T0,
        updated_at=T0,
        entry_at=T0,
        entry_price=1.1,
        bid=1.09988,
        ask=1.1,
        spread_points=12.0,
        slippage_points=0.0,
        initial_sl=1.099,
        sl=1.099,
        tp=1.102,
        stop_kind="SL",
        deadline=T0,
        cursor=T0,
        lot=0.1,
        equity=1000.0,
        currency="USD",
        flags=[],
        r_multiple=1.0 if status == "CLOSED" else None,
        r_net=0.98 if status == "CLOSED" else None,
    )


class TestReplayFamily:
    def _args(self, tmp_path: Path, **kw: object) -> argparse.Namespace:
        base = {
            "name": "t",
            "strategies": "setup_x",
            "detectors": "none",
            "symbols": "EURUSD,GBPUSD,USDJPY",
            "server": "FBS-Demo",
            "start": "2025-10-15",
            "end": "2026-10-05",
            "family_config": "config.yaml",
            "out": str(tmp_path),
            "parallel": 2,
            "min_free_gb": 3.0,
            "poll": 0.0,
        }
        return argparse.Namespace(**{**base, **kw})

    def test_waits_for_memory_and_limits_the_parallel_runs(self, tmp_path: Path) -> None:
        free = iter([1.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0])
        started: list[str] = []
        live: list[_Proc] = []

        class _Proc:
            def __init__(self) -> None:
                self.polls = 0

            def poll(self) -> int | None:
                self.polls += 1
                return 0 if self.polls > 2 else None

        def popen(cmd: list[str], env: dict[str, str], log: Path) -> _Proc:
            started.append(cmd[cmd.index("--symbols") + 1])
            assert env["TRADING_MODE"] == "PAPER"
            assert env["ENGINE_DB_URL"].endswith(f"fam_t_{started[-1]}.db")
            assert sum(p.polls <= 2 for p in live) < 2  # never more than --parallel at once
            proc = _Proc()
            live.append(proc)
            return proc

        code = cmd_research_replay_family(
            self._args(tmp_path), popen=popen, free_gb=lambda: next(free, 4.0), sleep=lambda _: None
        )
        assert code == 0
        assert started == ["EURUSD", "GBPUSD", "USDJPY"]

    def test_a_failed_replay_fails_the_family(self, tmp_path: Path) -> None:
        class _Bad:
            def poll(self) -> int:
                return 1

        code = cmd_research_replay_family(
            self._args(tmp_path, symbols="EURUSD"),
            popen=lambda *_: _Bad(),
            free_gb=lambda: None,
            sleep=lambda _: None,
        )
        assert code == 1


def test_random_direction_is_the_mean_of_both_directions() -> None:
    (rand,) = [h for h in default_hypotheses() if h.label == "random direction"]
    p, m = path([(0, 2.1, -0.2, 2)]), path([(0, 0.2, -2.1, -2)])
    assert rand.run(signal(), p, m) == pytest.approx((2.0 - 1.0) / 2)
    assert rand.run(signal(), p, None) is None
