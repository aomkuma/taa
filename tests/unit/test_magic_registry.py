"""Stable magic numbers: old values kept, never re-mapped or reused, per-bot blocks (TAA-L901)."""

from __future__ import annotations

import pytest

from app.core.clock import ManualClock
from app.core.errors import ConfigError
from app.engine.magic_registry import SLOTS_PER_BOT, MagicRegistry
from app.storage.database import Database
from tests.analytics_data import T0

BASE = 7_310_000


@pytest.fixture
def registry() -> MagicRegistry:
    db = Database("sqlite://")
    db.create_all()
    return MagicRegistry(db, BASE, ManualClock(T0))


def test_first_start_reproduces_the_old_index_numbers(registry: MagicRegistry) -> None:
    names = ["example_trend_pullback", "setup_neckline_break", "setup_fib_pullback"]
    assert registry.ensure(names) == {n: BASE + i for i, n in enumerate(names)}


def test_reorder_disable_and_add_never_re_map(registry: MagicRegistry) -> None:
    first = registry.ensure(["a", "b", "c"])
    # reordered and "a" disabled: b and c keep their numbers
    assert registry.ensure(["c", "b"]) == {"c": first["c"], "b": first["b"]}
    # a new strategy gets the next slot, not a's freed one
    assert registry.ensure(["c", "d"])["d"] == BASE + 3
    # a comes back with its old number
    assert registry.ensure(["a"])["a"] == first["a"]
    assert registry.all() == {
        BASE: ("default", "a"),
        BASE + 1: ("default", "b"),
        BASE + 2: ("default", "c"),
        BASE + 3: ("default", "d"),
    }


def test_bots_get_their_own_blocks(registry: MagicRegistry) -> None:
    registry.ensure(["a"])
    assert registry.ensure(["a", "b"], bot_id="trend_rider") == {
        "a": BASE + SLOTS_PER_BOT,
        "b": BASE + SLOTS_PER_BOT + 1,
    }
    assert registry.ensure(["x"], bot_id="range_sniper") == {"x": BASE + 2 * SLOTS_PER_BOT}


def test_a_new_base_moves_the_block(registry: MagicRegistry) -> None:
    registry.ensure(["a", "b"])
    moved = MagicRegistry(registry.db, 9_000_000, registry.clock)
    assert moved.ensure(["b"]) == {"b": 9_000_001}


def test_limits_and_duplicates(registry: MagicRegistry) -> None:
    with pytest.raises(ConfigError):
        registry.ensure(["a", "a"])
    registry.ensure([f"s{i}" for i in range(SLOTS_PER_BOT)])
    with pytest.raises(ConfigError):
        registry.ensure(["one_too_many"])
