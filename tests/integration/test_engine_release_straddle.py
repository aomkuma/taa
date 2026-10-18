"""Setup OWN S2 end to end on FakeMT5 (owner, 2026-10-18): the release straddle reads quotes around a release, its
entry goes through the decision engine and the order path under its own magic, and the position leaves at the
first bar close after the release minute."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from pathlib import Path

import pytest

from app.config import LaneConfig, StrategiesConfig, StrategyEntry, StrategyManagement, TimeframesConfig
from app.core.enums import Timeframe
from app.engine.orchestrator import QUOTE_POLL_SECONDS
from app.monitoring.alerts import EventType
from app.news.releases import Release
from app.strategy.registry import StrategySet
from app.strategy.release_straddle import OwnS2
from tests.integration.test_engine_demo import Demo, demo, demo_settings

S2 = "setup_own_s2"


def s2_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Demo, OwnS2]:
    import tests.integration.test_engine_demo as m

    lane = LaneConfig(
        name="news",
        timeframes=TimeframesConfig(entry=Timeframe.M1, higher=Timeframe.H1, warmup_bars=60),
        symbols=["EURUSD"],
        strategies=StrategiesConfig(items=[StrategyEntry(name=S2)], cooldown_bars=0),
        management={S2: StrategyManagement(break_even=False, trailing=False)},
    )
    base = demo_settings(tmp_path)
    with_lane = dataclasses.replace(base, config=base.config.model_copy(update={"lanes": [lane]}))
    monkeypatch.setattr(m, "demo_settings", lambda tmp, **env: with_lane)
    d = demo(tmp_path)
    d.engine.start()
    d.engine.strategies = StrategySet(())  # only the straddle trades
    ((_, s2),) = d.engine._quote_lanes
    return d, s2


def test_the_calendar_is_attached_at_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d, s2 = s2_demo(tmp_path, monkeypatch)
    assert s2.releases and {r.event for r in s2.releases} == {"CPI", "NFP"}  # app/news/us_releases.csv
    d.engine.shutdown()


def test_a_release_entry_trades_under_its_own_magic_and_leaves_after_the_minute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d, s2 = s2_demo(tmp_path, monkeypatch)
    now = d.clock.now_utc()
    release = Release(now + timedelta(seconds=10), "CPI")
    s2.attach_calendar([release])
    assert d.engine.interval() == QUOTE_POLL_SECONDS  # armed: quotes every 0.1 s
    bid, ask = 1.10000, 1.10008
    d.engine._quote_entries("EURUSD", now, bid, ask)  # the reference quote before the release
    d.clock.advance(11)
    jump = 3 * bid / 4000  # past the 2 U buy stop
    d.engine._quote_entries("EURUSD", release.at + timedelta(seconds=1), bid + jump, ask + jump)
    assert EventType.SIGNAL_ACCEPTED in d.types()
    (pos,) = d.engine.gateway.positions()
    assert pos.magic == d.engine.magic[S2]
    assert pos.sl < pos.price_open < pos.tp  # a BUY with its stop and the far cap
    for _ in range(12):  # past the close of the release minute: the lane's bar closes it
        d.clock.advance(15)
        d.engine.cycle()
        if not d.engine.gateway.positions():
            break
    assert not d.engine.gateway.positions()
    assert d.engine.interval() == d.engine.config.engine.monitor_interval_seconds
    d.engine.shutdown()
