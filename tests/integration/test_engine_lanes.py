"""Entry lanes end to end on FakeMT5 (owner, 2026-10-15: S1 on M1 next to V1 and F1 on M15): a lane trades on
its own timeframe through the shared decision engine and its time stop counts its own bars."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import LaneConfig, StrategiesConfig, StrategyEntry, StrategyManagement, TimeframesConfig
from app.core.enums import Timeframe
from app.engine.lanes import MAIN
from app.monitoring.alerts import EventType
from app.storage.models import DecisionRecordRow
from app.strategy.registry import StrategySet
from tests.integration.test_engine_demo import Demo, demo, demo_settings, run_until
from tests.integration.test_engine_paper import BuyEveryBar

LANE = "setup_breakout_scalp"


class BuyEveryM5Bar(BuyEveryBar):
    name = LANE


def lane_config(time_stop_bars: int = 3) -> LaneConfig:
    return LaneConfig(
        name="fast",
        timeframes=TimeframesConfig(entry=Timeframe.M5, higher=Timeframe.H1),
        symbols=["EURUSD"],
        strategies=StrategiesConfig(items=[StrategyEntry(name=LANE)], cooldown_bars=0),
        max_spread_to_sl_ratio=1.0,
        management={
            LANE: StrategyManagement(break_even=False, trailing=False, time_stop_bars=time_stop_bars)
        },
    )


def lane_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, time_stop_bars: int = 3) -> Demo:
    import tests.integration.test_engine_demo as m

    base = demo_settings(tmp_path)
    with_lane = dataclasses.replace(
        base, config=base.config.model_copy(update={"lanes": [lane_config(time_stop_bars)]})
    )
    monkeypatch.setattr(m, "demo_settings", lambda tmp, **env: with_lane)
    d = demo(tmp_path)
    d.engine.start()
    d.engine.strategies = StrategySet(())  # the main lane opens nothing: only the lane trades
    d.engine.extra_lanes[0].strategies = StrategySet((BuyEveryM5Bar(BuyEveryM5Bar.Params()),))
    return d


def test_a_lane_trades_on_its_own_timeframe_with_its_own_magic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = lane_demo(tmp_path, monkeypatch)
    assert [lane.name for lane in d.engine.lanes] == [MAIN, "fast"]
    assert d.engine.strategy_names[-1] == LANE
    run_until(d, EventType.POSITION_OPENED)
    with d.db.session() as sess:
        row = (
            sess.execute(select(DecisionRecordRow).where(DecisionRecordRow.decision == "ACCEPT"))
            .scalars()
            .first()
        )
    assert row is not None and row.strategy == LANE and row.timeframe == "M5"
    (pos,) = d.engine.gateway.positions()
    assert pos.magic == d.engine.magic[LANE]
    d.engine.shutdown()


def test_the_lane_time_stop_counts_the_lanes_bars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = lane_demo(tmp_path, monkeypatch)
    run_until(d, EventType.POSITION_OPENED)
    d.engine.extra_lanes[0].strategies = StrategySet(())  # no new entries after the first
    for _ in range(60):  # 3 M5 bars are 15 minutes: 30 s cycles, well within 30 minutes
        d.engine.cycle()
        d.clock.advance(30)
        if not d.engine.gateway.positions():
            break
    assert d.engine.gateway.positions() == []
    closed = [e for e in d.sink.events if e.type is EventType.POSITION_CLOSED]
    assert [e.params.get("reason") for e in closed] == ["TIME"]  # within 30 minutes: 3 M15 bars would take 45
    d.engine.shutdown()


class CloseEveryM5Bar(BuyEveryM5Bar):
    """Opens nothing and asks to close on a bar of its OWN lane only. The main lane's on_bar asks every
    position's strategy, this lane's included, so a strategy that always says yes would be closed by the
    main lane and prove nothing. M5 is this lane's entry frame; the main lane runs on M15."""

    def evaluate(self, ctx):  # type: ignore[no-untyped-def]
        return self.hold(ctx)

    def should_close(self, ctx, side) -> bool:  # type: ignore[no-untyped-def]
        return ctx.market.entry_timeframe is Timeframe.M5


def test_a_lane_strategy_closes_its_own_position(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Found in review 2026-10-27: ``should_close`` is asked in ``on_bar``, which the engine calls only for
    the main lane, so a lane strategy's own exit (the three bots' daily flatten) never fired live although
    the backtest engine honoured it. The time stop is set far out of reach, so only the strategy's own
    exit can close this position, and the reason must be SIGNAL."""
    d = lane_demo(tmp_path, monkeypatch, time_stop_bars=999)
    run_until(d, EventType.POSITION_OPENED)
    closer = CloseEveryM5Bar(CloseEveryM5Bar.Params())
    d.engine.extra_lanes[0].strategies = StrategySet((closer,))
    # the position manager keeps its own magic -> strategy snapshot from start-up
    d.engine.broker_positions.strategies_by_magic[d.engine.magic[LANE]] = closer
    for _ in range(60):  # the time stop test needs 60 cycles for three M5 bars
        d.engine.cycle()
        d.clock.advance(30)
        if not d.engine.gateway.positions():
            break
    assert d.engine.gateway.positions() == []
    closed = [e for e in d.sink.events if e.type is EventType.POSITION_CLOSED]
    assert [e.params.get("reason") for e in closed] == ["SIGNAL"]
    d.engine.shutdown()
