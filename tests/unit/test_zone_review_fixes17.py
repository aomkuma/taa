# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 16 of the run-zone runner, batch 1b - the normal case (eye/ZONE_LIVE.md L4, L5, L11).

W. A first fill accepted on the quotes so far is judged again on its closed bar's true extremes, in the simulation's
   in-bar order: a withdrawal level reached between two cycles makes the setup `no fill`, its fills closed at
   market (L5 "any other fill"; an explained difference, L11).
T. A touch before the hour's decision (the simulation's setup visit in the decision bar, where no missed touch is
   looked for) is an explained difference: recorded and logged at WARNING, never as a fault."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.broker import mt5_constants as c
from tests.unit.test_zone_handsoff_causes import (
    build,
    decide,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import FILL, ts


def test_w_a_first_fill_on_a_bar_that_reached_the_withdrawal_level_unseen_is_no_fill_and_closed(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    # the 10:15 bar's high reaches the BUY's withdrawal level (L + away = 105) between two cycles; then P1 fills
    rows130 = [FILL, (103.0, 105.5, 101.0, 102.0), FILL, FILL]
    w, ex = build(worlds, tmp_path, exec_rows={130: rows130})
    decide(w)
    w.to("2025-01-06 10:20:00", 101.0)
    w.fake.orders_get()  # the BUY P1 fills; the quotes the runner read in the bar never reached 105
    w.step(2)
    buy = w.runner.cands[1]
    assert "P1" in buy.fills and buy.fills["P1"].j == 521
    w.to("2025-01-06 10:30:05", 102.0)  # the bar's close: its true high withdrew the setup before the fill
    assert w.store.setup(1).outcome == "no fill" and "P1" not in buy.fills
    w.step(2)
    closes = [r for r in ex.sent if r.get("action") == c.TRADE_ACTION_DEAL and r.get("position")]
    assert closes  # the position is not the setup's: closed at market
    assert w.runner.res_by.get(buy.id) == ts("2025-01-06 10:30")  # the reservation of its `no fill` (L6)


def test_t_a_touch_before_the_decision_is_recorded_as_an_explained_difference(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # the 10:00 bar's low reaches the BUY's zone - before the decision; the quotes never show it after
    rows130 = [(103.0, 104.0, 101.0, 103.0), FILL, FILL, FILL]
    w, _ = build(worlds, tmp_path, exec_rows={130: rows130})
    decide(w)
    with caplog.at_level(logging.WARNING, logger="app.zone.trader"):
        w.to("2025-01-06 11:00:05", 103.0)  # the H1 close: the visit records
    [rec] = [r for r in w.store.visits(ts("2025-01-06 10:00").to_pydatetime()) if r.side == "BUY"]
    assert rec.classification == "setup" and rec.note == "touch before the decision"
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
