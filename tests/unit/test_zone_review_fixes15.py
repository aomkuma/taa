# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 15 of the run-zone runner, batch 1 - the normal case (eye/ZONE_LIVE.md L2, L4, L5, L10).

Q. The exec bar a quote belongs to is known by the quote's own server time: while a bar before it is missing, the
   quote judges nothing (no latch, no visit, no forming extremes) - the steps run in bar order.
D. A candidate dropped for the other's visit keeps its life (its latches, its close steps, its outcome) while it has
   no orders; its drop is final only at the hour's close; until then its row has no outcome (the start ends it
   `restart`), and every --now exit ends it `interrupted`."""

from __future__ import annotations

import json
from pathlib import Path

from app.zone.params import ZoneParams
from tests.unit.test_zone_handsoff_causes import (
    HOUR0,
    build,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.test_zone_review_fixes12 import late_bars
from tests.unit.zone_live_support import FILL, World, ts

# the 9:00 bar opens 104.5: the BUY P1 (101.32) is blocked in the 10:00 bar (rule 3, cancel_frac 0.2), not after
BLOCKED_AT_J0 = {129: [(104.5, 105.0, 102.5, 103.0), FILL, FILL, FILL]}


# --- Q: the exec bar of a quote -------------------------------------------------------------------------------------


def test_q_a_quote_whose_bar_has_a_missing_predecessor_latches_nothing(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path, exec_rows=BLOCKED_AT_J0, params=ZoneParams(cancel_frac=0.2), spread=50)
    w.to(HOUR0, 103.0)
    w.step(2)
    buy = w.runner.cands[1]
    late = late_bars(w, "M15", ts("2025-01-06 10:00"))  # the 10:00 bar is delayed
    w.to("2025-01-06 10:15:05", 100.9)  # a 10:15 quote: the ask under the P1 - blocked in 10:00, not in 10:15
    assert buy.cancel_seen is None  # not judged against the 10:00 bar
    late["on"] = False
    w.step(2, 103.0)  # the 10:00 bar is read; its close finds no cancel (its own extremes)
    w.step(2)
    assert buy.cancel_seen is None and w.store.setup(1).outcome != "cancel"


# --- D: the life of a candidate dropped for the other's visit -------------------------------------------------------


def test_d_a_dropped_candidates_blocked_touch_is_latched_and_kept_when_a_missed_touch_gives_it_the_hour(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    # the 9:15 bar opens 104: the BUY P1 is blocked in the 10:15 bar; that bar's low (100.9) reaches the BUY's zone
    # but its spread (0.50) hides the P1 fill test from the closed bar - only the quotes saw the ask under P1
    rows129 = [(103.0, 103.6, 102.6, 103.5), (104.0, 104.2, 102.6, 103.0), FILL, FILL]
    rows130 = [(103.0, 103.6, 102.6, 103.0), (103.0, 108.8, 100.9, 103.0), FILL, FILL]
    w, ex = build(
        worlds,
        tmp_path,
        exec_rows={129: rows129, 130: rows130},
        params=ZoneParams(cancel_frac=0.2, away_frac=2.0),
        spread=50,
    )
    w.to(HOUR0, 103.0)
    w.step(2)
    buy, sell = w.runner.cands[1], w.runner.cands[2]
    w.to("2025-01-06 10:20:00", 108.75)  # the SELL's visit: the hour's setup; the BUY dropped (not final)
    assert w.runner.hour is not None and w.runner.hour.chosen is sell and buy.dropped
    w.to("2025-01-06 10:22:00", 100.9)  # the BUY's blocked P1 met by the ask: latched though it is dropped
    assert buy.cancel_seen is not None
    places = len(ex.places("Z1-"))
    w.to(
        "2025-01-06 10:30:05", 103.0
    )  # the bar's close: the BUY's missed touch takes the hour, with its cancel
    assert w.runner.hour.chosen is buy
    assert buy.outcome == "cancel"
    w.step(2)
    assert len(ex.places("Z1-")) == places  # nothing placed for a setup ended `cancel`


def cancel_then_dropped(worlds: list, tmp_path: Path) -> World:  # type: ignore[type-arg]
    """The BUY ends `cancel` (10:30), then the SELL's visit (10:35) takes the hour: the BUY is dropped, not final."""
    rows129 = [(103.0, 103.6, 102.6, 103.5), (103.5, 103.6, 102.6, 103.0), FILL, FILL]
    rows130 = [
        (103.0, 103.2, 101.35, 101.4),
        (101.4, 102.0, 101.35, 101.8),
        (101.8, 108.8, 101.4, 103.0),
        FILL,
    ]
    w, _ = build(
        worlds,
        tmp_path,
        exec_rows={129: rows129, 130: rows130},
        params=ZoneParams(cancel_frac=0.2, away_frac=2.0),
    )
    w.to(HOUR0, 103.0)
    w.step(2)
    w.to("2025-01-06 10:30:05", 103.0)
    assert w.runner.cands[1].outcome == "cancel"
    w.to("2025-01-06 10:35:00", 108.75)
    assert (
        w.runner.hour is not None and w.runner.hour.chosen is w.runner.cands[2] and w.runner.cands[1].dropped
    )
    return w


def test_d_the_row_of_a_dropped_candidate_has_no_outcome_before_the_hours_close(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w = cancel_then_dropped(worlds, tmp_path)
    row = w.store.setup(1)
    assert row is not None and (row.state, row.outcome) == ("dropped", None)
    assert 1 in w.store.end_unfinished(w.clock.now_utc(), "restart", "a new zone run")  # the start's test


def test_d_a_stop_now_exit_ends_a_dropped_candidate_with_a_life_outcome_interrupted(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w = cancel_then_dropped(worlds, tmp_path)
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2, 103.0)
    w.step(2)
    assert w.runner.finished
    assert w.store.setup(1).outcome == "interrupted"


def test_d_a_dropped_candidates_close_steps_run_its_life_to_its_outcome(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    rows129 = [(103.0, 103.6, 102.6, 103.5), (103.5, 103.6, 102.6, 103.0), FILL, FILL]
    rows130 = [(103.0, 103.2, 101.35, 101.4), (101.4, 102.0, 101.35, 101.8), FILL, FILL]
    w, _ = build(
        worlds,
        tmp_path,
        exec_rows={129: rows129, 130: rows130},
        params=ZoneParams(cancel_frac=0.2, away_frac=2.0),
    )
    w.to(HOUR0, 103.0)
    w.step(2)
    buy = w.runner.cands[1]
    w.to("2025-01-06 10:05:00", 108.75)  # the SELL's visit: the hour's setup; the BUY dropped, not final
    assert buy.dropped and buy.outcome is None
    w.to("2025-01-06 10:30:05", 103.0)  # the 10:15 bar's close decides the BUY's closed-hour cancel
    assert buy.dropped and buy.outcome == "cancel"  # its life ran on while it had no orders (L4)
    row = w.store.setup(1)
    assert row is not None and row.outcome is None  # not final before the hour's close
    assert json.loads(row.fills_json)["life_outcome"] == "cancel"
