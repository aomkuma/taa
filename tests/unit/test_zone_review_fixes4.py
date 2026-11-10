# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""The runner after Sol's fourth review of piece 2a (eye/ZONE_LIVE.md L4): the finding that holds under the
spec of 2026-11-04 (a start carries nothing over, L8 - the restart findings of this review went with it)."""

from __future__ import annotations

from pathlib import Path

from tests.unit.test_zone_trader import (
    bar,
    cands,
    hour_rows,
    world,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import World, ts

# --- 5: no decision at a bar uses a later bar ---------------------------------------------------------------------------------


def test_a_revival_replays_only_the_bars_up_to_its_own(worlds: list[World], tmp_path: Path) -> None:
    rows = hour_rows(bar(103, 104, 101.2, 103), bar(103, 105.5, 101.2, 105.0))  # bar 521 withdraws the BUY
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    cand = cands(w)["BUY"]
    w.clock.set(ts("2025-01-06 10:30:05").to_pydatetime())
    w.runner._update_bars()  # the bars 520 and 521 are in; nothing has judged them yet
    w.runner._replay_life(cand, 520)
    assert cand.status == "live"  # the withdrawal of bar 521 is not looked at
    w.runner._replay_life(cand, 521)
    assert cand.status == "ended" and cand.outcome == "no fill"
