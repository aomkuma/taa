"""The AI trader end to end on FakeMT5 (TAA-1806): the AI's decision, handed over on the engine loop, waits for its
price on quotes, goes through the decision engine and the order path under the ai_trader strategy's own magic with
the AI's stop and target, its reasons recorded with the decision; an EXIT closes it at the lane's next bar; a WAIT
withdraws a waiting order."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.config import LaneConfig, StrategiesConfig, StrategyEntry, StrategyManagement, TimeframesConfig
from app.core.enums import Timeframe
from app.engine.ai_trader import hand_over
from app.monitoring.alerts import EventType
from app.storage.models import DecisionRecordRow
from app.strategy.ai_lane import AITrader
from app.strategy.registry import StrategySet
from tests.integration.test_engine_demo import Demo, demo, demo_settings

AI = "ai_trader"


def ai_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Demo, AITrader]:
    import tests.integration.test_engine_demo as m

    lane = LaneConfig(
        name="ai",
        timeframes=TimeframesConfig(entry=Timeframe.M1, higher=Timeframe.H1, warmup_bars=60),
        symbols=["EURUSD"],
        strategies=StrategiesConfig(
            items=[StrategyEntry(name=AI, params={"market_tolerance": 0.0005})],
            cooldown_bars=0,
            signal_expiry_bars=2,
        ),
        management={AI: StrategyManagement(break_even=False, trailing=False)},
    )
    base = demo_settings(tmp_path)
    with_lane = dataclasses.replace(base, config=base.config.model_copy(update={"lanes": [lane]}))
    monkeypatch.setattr(m, "demo_settings", lambda tmp, **env: with_lane)
    d = demo(tmp_path)
    d.engine.start()
    d.engine.strategies = StrategySet(())  # only the AI lane trades
    ((_, ai),) = d.engine._quote_lanes
    assert isinstance(ai, AITrader)
    return d, ai


def quote(d: Demo) -> tuple[float, float]:
    """FakeMT5's quote as the lane's context reads it."""
    lane = d.engine._quote_lanes[0][0]
    market = lane.builder.build("EURUSD", d.engine.symbols["EURUSD"]).market
    assert market.bid is not None and market.ask is not None
    return market.bid, market.ask


def rec(d: Demo, decision: str, size: str = "half", above: float = 0.0) -> dict[str, Any]:
    """A sell at the quote (``above`` it to wait), the stop 20 pips over it, the target 40 pips under."""
    bid, _ = quote(d)
    entry = round(bid + above, 5)
    return {
        "as_of": d.clock.now_utc().isoformat(),
        "final_size": size,
        "decision": {
            "decision": decision,
            "setup": "a lower high under the broken floor",
            "entry": entry,
            "stop": round(entry + 0.0020, 5),
            "target": round(entry - 0.0040, 5),
            "reasons": ["every frame down", "the bounce stalled"],
            "kb_ids": ["P19", "L15"],
            "confidence": 66,
        },
    }


def test_an_ai_sell_trades_under_its_own_magic_with_its_stop_target_and_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d, ai = ai_demo(tmp_path, monkeypatch)
    order = rec(d, "SELL")
    assert hand_over(ai, "EURUSD", order, 30) == "order"
    bid, ask = quote(d)
    d.engine._quote_entries("EURUSD", d.clock.now_utc(), bid, ask)
    assert EventType.SIGNAL_ACCEPTED in d.types()
    (pos,) = d.engine.gateway.positions()
    assert pos.magic == d.engine.magic[AI]
    assert (pos.sl, pos.tp) == (order["decision"]["stop"], order["decision"]["target"])
    with d.db.session() as sess:
        row = sess.execute(select(DecisionRecordRow).where(DecisionRecordRow.strategy == AI)).scalar_one()
    signal = row.signal
    assert signal["explanation"] == "every frame down | the bounce stalled"  # the AI's reasons ride along
    assert signal["risk_scale"] == 0.5  # the AI's half size
    names = {c["name"]: c["detail"] for c in signal["conditions"]}
    assert names["ai_knowledge"] == "P19, L15"
    assert names["ai_decision"].startswith("a lower high under the broken floor (confidence 66")
    hand_over(ai, "EURUSD", rec(d, "EXIT"), 30)
    for _ in range(8):  # the lane's next bar applies the AI's exit
        d.clock.advance(15)
        d.engine.cycle()
        if not d.engine.gateway.positions():
            break
    assert not d.engine.gateway.positions()
    d.engine.shutdown()


def test_a_wait_withdraws_the_waiting_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d, ai = ai_demo(tmp_path, monkeypatch)
    hand_over(ai, "EURUSD", rec(d, "SELL", above=0.0050), 30)  # 50 pips above the quote: it waits
    bid, ask = quote(d)
    d.engine._quote_entries("EURUSD", d.clock.now_utc(), bid, ask)
    assert ai.pending("EURUSD") is not None
    assert hand_over(ai, "EURUSD", rec(d, "WAIT"), 30) == "cancel"
    d.engine._quote_entries("EURUSD", d.clock.now_utc(), bid + 0.0050, ask + 0.0050)
    assert not d.engine.gateway.positions()
    d.engine.shutdown()


def test_a_vetoed_entry_never_reaches_the_order_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d, ai = ai_demo(tmp_path, monkeypatch)
    assert hand_over(ai, "EURUSD", rec(d, "SELL", size="none"), 30) == "cancel"
    bid, ask = quote(d)
    d.engine._quote_entries("EURUSD", d.clock.now_utc(), bid, ask)
    assert EventType.SIGNAL_ACCEPTED not in d.types()
    assert not d.engine.gateway.positions()
    d.engine.shutdown()


def test_the_engine_hands_the_lanes_decision_to_the_ai_strategy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    d, ai = ai_demo(tmp_path, monkeypatch)
    lane = SimpleNamespace(cfg=SimpleNamespace(symbol="EURUSD"))
    d.engine._ai_hand_over(lane, rec(d, "SELL", above=0.0050))  # type: ignore[arg-type]
    assert ai.pending("EURUSD") is not None
    other = SimpleNamespace(cfg=SimpleNamespace(symbol="XAUUSD"))  # no lane trades it: logged, not traded
    d.engine._ai_hand_over(other, rec(d, "SELL"))  # type: ignore[arg-type]
    assert ai.pending("XAUUSD") is None
    d.engine.shutdown()
