"""Behavior report on manual trades: early exits, moved stops, revenge, overtrading, off-plan (TAA-L808)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.core.enums import Side
from app.learning.behavior import (
    BehaviorParams,
    ManualTrade,
    Pattern,
    early_exit,
    report,
    stop_moved,
)
from tests.analytics_data import T0

M15 = timedelta(minutes=15)


def bars(start: datetime, rows: Sequence[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime([start + i * M15 for i in range(len(rows))], utc=True),
            "high": [r[0] for r in rows],
            "low": [r[1] for r in rows],
            "close": [(r[0] + r[1]) / 2 for r in rows],
        }
    )


def manual(i: int = 1, **kw: object) -> ManualTrade:
    """BUY EURUSD at 1.1000, stop 1.0950 (risk 0.0050), plan TP 1.1100 (2R); closed at +1R after 2 h."""
    base = ManualTrade(
        position_id=i,
        symbol="EURUSD",
        side=Side.BUY,
        opened_at=T0,
        closed_at=T0 + timedelta(hours=2),
        price_open=1.1000,
        close_price=1.1050,
        r_multiple=1.0,
        sl_initial=1.0950,
        tp_plan=1.1100,
        matched=True,
        risk_money=50.0,
        asset_class="FOREX_MAJOR",
    )
    return dataclasses.replace(base, **kw)  # type: ignore[arg-type]


AFTER = T0 + timedelta(hours=2)


class TestEarlyExit:
    def test_target_reached_after_a_profitable_close(self) -> None:
        assert early_exit(manual(), bars(AFTER, [(1.1060, 1.1040), (1.1105, 1.1060)]), timedelta(hours=72))

    def test_stop_first_or_target_taken_or_a_loss(self) -> None:
        assert early_exit(manual(), bars(AFTER, [(1.1060, 1.0945)]), timedelta(hours=72)) is False
        assert early_exit(manual(r_multiple=2.0), None, timedelta(hours=72)) is False
        assert early_exit(manual(r_multiple=-1.0), None, timedelta(hours=72)) is False

    def test_unknown_without_plan_or_bars(self) -> None:
        assert early_exit(manual(tp_plan=None), None, timedelta(hours=72)) is None
        assert early_exit(manual(), None, timedelta(hours=72)) is None
        assert early_exit(manual(), bars(AFTER, [(1.1060, 1.1040)]), timedelta(hours=72)) is None


class TestStopMoved:
    def test_widened_or_removed_counts_tightened_does_not(self) -> None:
        assert stop_moved(manual(stop_history=[1.0950, 1.0930])) is True
        assert stop_moved(manual(stop_history=[None])) is True
        assert stop_moved(manual(stop_history=[1.0970, 1.1000])) is False
        assert stop_moved(manual()) is None
        sell = manual(side=Side.SELL, sl_initial=1.1050, stop_history=[1.1070])
        assert stop_moved(sell) is True


class TestReport:
    def test_patterns_counts_and_deltas(self) -> None:
        loss = manual(1, r_multiple=-1.0, closed_at=T0 + timedelta(hours=1), risk_money=50.0)
        revenge_fast = manual(
            2,
            opened_at=T0 + timedelta(hours=1, minutes=10),
            closed_at=T0 + timedelta(hours=3),
            r_multiple=-1.0,
        )
        revenge_big = manual(
            3,
            opened_at=T0 + timedelta(hours=5),
            closed_at=T0 + timedelta(hours=6),
            r_multiple=0.5,
            risk_money=80.0,
        )
        own_idea = manual(
            4,
            opened_at=T0 + timedelta(hours=7),
            closed_at=T0 + timedelta(hours=8),
            matched=False,
            r_multiple=-0.5,
        )
        moved = manual(
            5,
            opened_at=T0 + timedelta(hours=9),
            closed_at=T0 + timedelta(hours=10),
            r_multiple=-1.6,
            stop_history=[1.0920],
        )
        early = manual(6, opened_at=T0 + timedelta(hours=11), closed_at=T0 + timedelta(hours=12))
        paths = {6: bars(T0 + timedelta(hours=12), [(1.1105, 1.1040)])}
        rep = report(
            [loss, revenge_fast, revenge_big, own_idea, moved, early],
            lambda t: paths.get(t.position_id),
            params=BehaviorParams(max_trades_per_day=4),
            opportunity_classes=["FOREX_MAJOR", "INDEX", "INDEX", "METAL"],
        )
        p = rep.patterns
        assert rep.trades == 6
        assert p[Pattern.EARLY_EXIT].position_ids == (6,) and p[Pattern.EARLY_EXIT].delta_r == pytest.approx(
            1.0
        )
        assert p[Pattern.STOP_MOVED].position_ids == (5,) and p[Pattern.STOP_MOVED].considered == 1
        assert p[Pattern.STOP_MOVED].delta_r == pytest.approx(0.6)
        # 2: 10 min after the loss of 1; 3: more money at risk than the last loss (2)
        assert p[Pattern.REVENGE].position_ids == (2, 3)
        assert p[Pattern.OFF_PLAN].position_ids == (4,) and p[Pattern.OFF_PLAN].delta_r == pytest.approx(0.5)
        assert p[Pattern.OVERTRADING].position_ids == (5, 6)
        assert rep.class_mix == {"FOREX_MAJOR": 1.0}
        assert rep.comfort_distance == pytest.approx(0.75)

    def test_overtrading_not_checked_without_a_limit(self) -> None:
        rep = report([manual(1), manual(2)], lambda t: None)
        stat = rep.patterns[Pattern.OVERTRADING]
        assert stat.count == 0 and stat.considered == 0
        assert rep.comfort_distance is None

    def test_unrated_trades_are_ignored(self) -> None:
        rep = report([manual(1, r_multiple=None)], lambda t: None)
        assert rep.trades == 0 and rep.patterns[Pattern.OFF_PLAN].considered == 0
