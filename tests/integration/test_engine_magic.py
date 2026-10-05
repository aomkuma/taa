"""The engine takes its magic numbers from the stable registry, not from the config order (TAA-L901)."""

from __future__ import annotations

from pathlib import Path

from app.core.clock import ManualClock
from app.engine.magic_registry import MagicRegistry
from app.monitoring.alerts import MemorySink
from tests.integration.test_engine_paper import START
from tests.integration.test_engine_restart import fresh_db, make_engine


def test_engine_magic_survives_a_changed_strategy_order(tmp_path: Path) -> None:
    db, clock = fresh_db(), ManualClock(START)
    first = make_engine(tmp_path, db, clock, MemorySink())
    first.start()
    names = [s.name for s in first.strategies.strategies]
    base = first.settings.env.MAGIC_NUMBER_BASE
    assert first.magic == {n: base + i for i, n in enumerate(names)}  # first start: the old numbers

    # an earlier config had another strategy first: its slot stays taken and the others keep theirs
    db2 = fresh_db()
    MagicRegistry(db2, base, clock).ensure(["retired_strategy", *reversed(names)])
    second = make_engine(tmp_path, db2, clock, MemorySink())
    second.start()
    expected = {n: base + 1 + i for i, n in enumerate(reversed(names))}
    assert second.magic == expected
    first.shutdown()
    second.shutdown()
