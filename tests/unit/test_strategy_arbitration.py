from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.enums import Action
from app.strategy.arbitration import Outcome, SignalArbiter, rank
from app.strategy.signal_models import ReasonCode, Signal, SignalError
from tests.unit.test_strategy_models import BAR, make_signal

M15 = timedelta(minutes=15)


def sig(
    strategy: str, action: Action = Action.BUY, score: float = 50.0, bar: int = 0, **kw: object
) -> Signal:
    at = BAR + bar * M15
    base: dict[str, object] = {
        "signal_id": f"{strategy}-{bar}-{action}",
        "strategy": strategy,
        "action": action,
        "score": score,
        "data_timestamp_utc": at,
        "created_at_utc": at,
        "expires_at_utc": at + M15,
        "evidence": (),
    }
    if action is Action.SELL:
        base.update(entry_price=1.1, stop_loss=1.102, take_profit=1.096)
    if action is Action.HOLD:
        base.update(entry_price=None, stop_loss=None, take_profit=None)
    base.update(kw)
    return make_signal(**base)


def outcomes(arb: object) -> list[tuple[str, Outcome, ReasonCode | None]]:
    return [(r.signal.strategy, r.outcome, r.reason) for r in arb.results]  # type: ignore[attr-defined]


class TestArbitration:
    def test_highest_score_wins_same_direction(self) -> None:
        arb = SignalArbiter(cooldown_bars=0).arbitrate([sig("a", score=40), sig("b", score=70), sig("c")])
        assert arb.selected is not None and arb.selected.strategy == "b"
        assert outcomes(arb) == [
            ("a", Outcome.SUPPRESSED, ReasonCode.LOWER_RANK),
            ("b", Outcome.SELECTED, None),
            ("c", Outcome.SUPPRESSED, ReasonCode.LOWER_RANK),
        ]
        assert arb.reason_codes == ()

    def test_ties_break_on_strength_then_name(self) -> None:
        arb = SignalArbiter(0).arbitrate([sig("b"), sig("a"), sig("c", setup_strength=90.0)])
        assert arb.selected is not None and arb.selected.strategy == "c"
        arb = SignalArbiter(0).arbitrate([sig("b"), sig("a")])
        assert arb.selected is not None and arb.selected.strategy == "a"

    def test_opposite_signals_conflict(self) -> None:
        arb = SignalArbiter(0).arbitrate(
            [sig("a", score=90), sig("b", Action.SELL, score=10), sig("h", Action.HOLD)]
        )
        assert arb.selected is None
        assert outcomes(arb) == [
            ("a", Outcome.SUPPRESSED, ReasonCode.CONFLICT),
            ("b", Outcome.SUPPRESSED, ReasonCode.CONFLICT),
            ("h", Outcome.HOLD, None),
        ]
        assert arb.reason_codes == ("CONFLICT",)

    def test_only_holds_selects_nothing(self) -> None:
        arb = SignalArbiter(0).arbitrate([sig("a", Action.HOLD)])
        assert arb.selected is None
        assert arb.reason_codes == ("NO_SETUP",)

    def test_one_signal_per_strategy_and_bar(self) -> None:
        arb = SignalArbiter(0).arbitrate([sig("a", score=10), sig("a", Action.SELL, score=99)])
        assert arb.selected is not None and arb.selected.action is Action.BUY
        assert outcomes(arb)[1] == ("a", Outcome.SUPPRESSED, ReasonCode.DUPLICATE_SIGNAL)

    def test_re_arbitrating_the_same_bar_is_duplicate(self) -> None:
        arbiter = SignalArbiter(0)
        assert arbiter.arbitrate([sig("a")]).selected is not None
        again = arbiter.arbitrate([sig("a", signal_id="restart")])
        assert again.selected is None
        assert again.reason_codes == ("DUPLICATE_SIGNAL",)

    def test_mixed_bars_are_a_programming_error(self) -> None:
        with pytest.raises(SignalError):
            SignalArbiter(0).arbitrate([sig("a"), sig("b", bar=1)])


class TestCooldown:
    def test_cooldown_blocks_same_strategy_and_symbol_for_n_bars(self) -> None:
        arbiter = SignalArbiter(cooldown_bars=4)
        assert arbiter.arbitrate([sig("a", bar=0)]).selected is not None
        for bar in (1, 2, 3):
            other = f"b{bar}"
            arb = arbiter.arbitrate([sig("a", bar=bar), sig(other, bar=bar, score=10)])
            assert outcomes(arb)[0] == ("a", Outcome.SUPPRESSED, ReasonCode.COOLDOWN_ACTIVE)
            assert arb.selected is not None and arb.selected.strategy == other  # other strategies unaffected
        assert arbiter.arbitrate([sig("a", bar=4)]).selected is not None

    def test_cooldown_is_per_symbol(self) -> None:
        arbiter = SignalArbiter(cooldown_bars=4)
        arbiter.arbitrate([sig("a")])
        assert arbiter.arbitrate([sig("a", bar=1, symbol="GBPUSD")]).selected is not None

    def test_suppressed_signals_do_not_start_a_cooldown(self) -> None:
        arbiter = SignalArbiter(cooldown_bars=4)
        arbiter.arbitrate([sig("a"), sig("b", Action.SELL)])  # conflict: nothing selected
        assert arbiter.arbitrate([sig("a", bar=1)]).selected is not None

    def test_holds_pass_during_cooldown(self) -> None:
        arbiter = SignalArbiter(cooldown_bars=4)
        arbiter.arbitrate([sig("a")])
        assert outcomes(arbiter.arbitrate([sig("a", Action.HOLD, bar=1)]))[0][1] is Outcome.HOLD

    def test_state_survives_restart(self) -> None:
        arbiter = SignalArbiter(cooldown_bars=4)
        arbiter.arbitrate([sig("a")])
        restored = SignalArbiter(cooldown_bars=4)
        restored.restore_cooldowns(arbiter.cooldown_state())
        assert restored.in_cooldown(sig("a", bar=2))
        assert not restored.in_cooldown(sig("a", bar=4))


def test_rank_orders_entries_best_first() -> None:
    signals = [sig("a", score=10), sig("h", Action.HOLD), sig("b", score=80), sig("c", score=50)]
    assert [s.strategy for s in rank(signals)] == ["b", "c", "a"]
