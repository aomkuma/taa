# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 19 of the run-zone runner (eye/ZONE_LIVE.md L2, L8; ZONE_RULES 3).

G. The grid in force at the hour (ZONE_RULES 3) is built through the decision hour: a Thai month that starts while
   the market is closed is in force at the reopening, though no H1 bar has closed in it yet.
T. Every L8 timer starts where its condition begins, whatever a later read gives: an owed close is timed from the
   moment it is owed, though no quote can be read to send it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.zone import live
from app.zone.core import Bars, Grid
from app.zone.params import ZoneParams
from tests.unit.test_zone_handsoff_causes import (
    build,
    decide,
    vanish_order,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import GRID, World, make_world, ts


def fail(*_a: Any, **_k: Any) -> Any:
    raise OSError("unavailable")


FEB = ts("2025-01-31 17:00")  # 2025-02-01 00:00 Thai: a month start (ZONE_RULES 3)
CLOSED = (ts("2025-01-31 12:00"), FEB)  # the market closed: no bar of any frame opens in it


def month_grids(bars: Bars, params: ZoneParams, end: pd.Timestamp) -> list[Grid]:
    """Like ``default_grids``: a grid per Thai month start up to ``end`` (exclusive) - the February remake has its
    own step."""
    return [GRID] + ([Grid(FEB, 100.0, 20.0, "month")] if end > FEB else [])


def closed_market(w: World) -> None:
    """The broker has no bar opening while the market was closed (every frame)."""
    real_closed = w.src.closed_bars

    def keep(df: pd.DataFrame) -> pd.DataFrame:
        o = df["open_time"]
        return df[(o < CLOSED[0]) | (o >= CLOSED[1])].reset_index(drop=True)

    def closed_bars(tf: str, after: pd.Timestamp | None) -> pd.DataFrame:
        return keep(real_closed(tf, after))

    def last_closed_open(tf: str) -> pd.Timestamp | None:
        df = keep(real_closed(tf, None))
        return None if df.empty else pd.Timestamp(df["open_time"].iloc[-1])

    w.src.closed_bars = closed_bars  # type: ignore[method-assign]
    w.src.last_closed_open = last_closed_open  # type: ignore[method-assign]


def test_g_a_month_starting_while_the_market_is_closed_is_the_grid_in_force_at_the_reopening(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w = make_world(tmp_path, now="2025-01-31 11:59:50", last_hour=745, start=False, spread=20)
    worlds.append(w)
    w.runner.grids_fn = month_grids
    closed_market(w)
    w.runner.start()  # the last quote before the close; the last H1 bar closed is 11:00
    w.to("2025-01-31 17:00:05", 103.0)  # the reopening hour: the first of February (Thai)
    hour = w.runner.hour
    assert hour is not None and hour.open == FEB
    g = live.grid_at(w.runner.grids, w.runner.gstart, hour.open.value)
    assert g is not None and g.step == 20.0  # the February remake, not January's grid
    for cand in w.runner.cands.values():
        assert cand.visit.step == 20.0


def test_t_an_owed_close_is_timed_from_when_it_is_owed_though_no_quote_can_be_read(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    # the 10:15 bar's low reaches the BUY's zone: a missed BUY touch in the bar of the SELL's visit, nearer the open
    rows130 = [(103.0, 104.0, 102.0, 103.0), (103.0, 108.8, 101.0, 103.0), (103.0, 104.0, 102.0, 103.0)]
    rows130.append((103.0, 104.0, 102.0, 103.0))
    w, _ = build(worlds, tmp_path, exec_rows={130: rows130})
    decide(w)
    w.to("2025-01-06 10:20:00", 108.75)  # the SELL's visit: its P1 fills, it is the hour's setup
    w.step(2, 106.0)
    assert w.runner.cands[2].chosen and "P1" in w.runner.cands[2].fills
    real_tick = w.runner.gw.tick

    def no_quote(symbol: str) -> Any:
        return None

    w.runner.gw.tick = no_quote  # type: ignore[method-assign]  # no quote from now on
    w.to("2025-01-06 10:30:05")  # the BUY's missed touch takes the hour: the SELL's position is owed a close
    assert w.runner.hour is not None and w.runner.hour.chosen is w.runner.cands[1]
    assert w.runner.close_since  # timed from now, though it cannot be sent
    w.to("2025-01-06 10:46:00")
    assert w.runner.hands_off is not None and "close" in w.runner.hands_off
    w.runner.gw.tick = real_tick  # type: ignore[method-assign]


def test_t_an_order_of_ours_gone_is_timed_from_the_orders_read_though_the_later_reads_fail(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.runner.gw.positions = fail  # type: ignore[method-assign]  # the later reads fail
    vanish_order(w, "Z1-P1-0")
    w.step(2)
    assert w.runner.gone_since  # timed from the orders read that shows it gone (L8 cause 2)
