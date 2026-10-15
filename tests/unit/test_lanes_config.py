"""Entry lanes in the config (owner, 2026-10-15: S1 on M1 next to V1 and F1 on M15; ``config.yaml`` → ``lanes``)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from pydantic import ValidationError

from app.config import AppConfig
from app.core.enums import Timeframe
from app.core.errors import ConfigError

S1 = "setup_breakout_scalp"


def lane(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "s1",
        "timeframes": {"entry": "M1", "higher": "H1", "context": ["M15", "H1"]},
        "symbols": ["XAUUSD"],
        "strategies": {"items": [{"name": S1, "params": {"screen_tide_tf": "H1"}}], "cooldown_bars": 60},
        "max_spread_to_sl_ratio": 1.0,
        "management": {S1: {"break_even": False, "trailing": False, "time_stop_bars": 60}},
    }
    base.update(kw)
    return base


def config(*lanes: dict[str, Any], **kw: Any) -> AppConfig:
    return AppConfig.model_validate({"lanes": list(lanes), **kw})


class TestValidation:
    def test_no_lanes_by_default(self) -> None:
        c = AppConfig()
        assert c.lanes == []
        assert c.management == c.position_management

    def test_a_lane_strategy_cannot_also_be_a_main_one(self) -> None:
        with pytest.raises(ValidationError, match=r"already in strategies\.items"):
            config(lane(), strategies={"items": [{"name": S1}]})

    def test_lane_symbols_must_be_allowed(self) -> None:
        with pytest.raises(ValidationError, match=r"not in symbols\.allowed"):
            config(lane(symbols=["BTCUSD"]))

    def test_lane_names_and_strategies_are_unique(self) -> None:
        with pytest.raises(ValidationError, match="listed twice"):
            config(lane(), lane())
        with pytest.raises(ValidationError, match="listed twice"):
            config(lane(strategies={"items": [{"name": S1}, {"name": S1}]}))

    def test_management_names_its_own_strategies(self) -> None:
        with pytest.raises(ValidationError, match="management names unknown"):
            config(lane(management={"setup_breakout": {"break_even": False}}))

    def test_high_risk_may_name_a_lane_strategy(self) -> None:
        c = config(lane(), high_risk={"setups": [S1]})
        assert c.high_risk is not None and c.high_risk.setups == [S1]

    def test_unknown_lane(self) -> None:
        with pytest.raises(ConfigError):
            config(lane()).lane("nope")


class TestDerived:
    def test_for_lane_is_the_lanes_view(self) -> None:
        c = config(lane())
        v = c.for_lane(c.lane("s1"))
        assert v.timeframes.entry is Timeframe.M1
        assert v.symbols.allowed == ["XAUUSD"]
        assert [i.name for i in v.strategies.items] == [S1]
        assert v.strategies.cooldown_bars == 60
        assert v.risk.max_spread_to_sl_ratio == 1.0
        assert v.lanes == []
        own = v.position_management.for_strategy(S1)
        assert own.time_stop_bars == 60
        assert math.isinf(own.break_even_trigger_r) and math.isinf(own.trailing_start_r)

    def test_management_counts_lane_bars_on_the_lane_timeframe(self) -> None:
        m = config(lane()).management
        assert m.bar_timeframe(S1, Timeframe.M15) is Timeframe.M1
        assert m.bar_timeframe("setup_harmonic_prz", Timeframe.M15) is Timeframe.M15
        assert m.for_strategy("setup_harmonic_prz").time_stop_bars is None

    def test_per_strategy_lookups(self) -> None:
        c = config(lane())
        assert c.spread_ratio_for(S1) == 1.0
        assert c.spread_ratio_for("setup_breakout") is None
        assert c.cooldown_bars_for(S1) == 60
        assert c.cooldown_bars_for("setup_breakout") == c.strategies.cooldown_bars
