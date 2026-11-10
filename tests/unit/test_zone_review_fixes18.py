# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 17 of the run-zone runner (eye/ZONE_LIVE.md L5, L6, L11): a setup's outcome is not final until the
bar of its first fill - accepted on the quotes so far - has closed and been judged again on its true extremes, in
the simulation's in-bar order. An exit inside that bar waits for that judgement; a withdrawal then met makes the
setup `no fill`, and the bar's fills and their exits stop being the setup's."""

from __future__ import annotations

import json
from pathlib import Path

from tests.unit.test_zone_handsoff_causes import (
    build,
    decide,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import FILL, ts


def test_a_setup_filled_and_stopped_in_a_bar_that_withdrew_it_unseen_is_no_fill(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    # BUY line 100: withdrawal 105, SL 95. The 10:15 bar reaches 105.5 unseen, fills P1 and P2, stops both.
    rows130 = [FILL, (103.0, 105.5, 94.0, 96.0), FILL, FILL]
    w, _ = build(worlds, tmp_path, exec_rows={130: rows130})
    decide(w)
    w.to("2025-01-06 10:20:00", 97.0)
    w.fake.orders_get()  # P1 (101.32) and P2 (98.03) fill
    w.bid(94.9)
    w.fake.orders_get()  # both stopped at the SL (95)
    assert w.positions() == []
    w.step(2)  # the runner reads the fills and the stops of the forming bar
    buy = w.runner.cands[1]
    assert buy.is_live  # its outcome waits for the bar's close
    w.to("2025-01-06 10:30:05", 96.0)  # the close: the bar's true high withdrew the setup before the fills
    row = w.store.setup(1)
    assert row is not None and row.outcome == "no fill"
    state = json.loads(row.fills_json)
    assert (
        row.exit_how is None and not state["fills"] and not state["closed"]
    )  # its fills and exits are not its
    assert w.runner.res_by.get(buy.id) == ts("2025-01-06 10:30")  # the reservation of `no fill` (L6)
