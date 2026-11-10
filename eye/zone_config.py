"""The run-zone setup's parameters in a database (eye/ZONE_RULES.md, rule 1).

SQLite, ``data/bot_config.db`` by default (the *file* is shared with the Fibonacci bot; the table is not). A
*set* is a full set of every ``ZoneParams`` field, named by market and set name. The table
``zone_config_change`` is append-only: one row per value written; a set's current values are, per name,
the row with the highest ``id``, and its version is the highest ``id`` among its rows.

    python eye/zone_config.py seed --market XAUUSD --set default --by me
    python eye/zone_config.py set --market XAUUSD --set default --by me --note "why" abn_atr=2.5
    python eye/zone_config.py copy --market XAUUSD --set default --to-market XAUUSD --to-set alt --by me
    python eye/zone_config.py upgrade --market XAUUSD --set default --by me   (adds fields the set lacks)
    python eye/zone_config.py show|list|history ...   (every command takes --db PATH)

Reading never creates the file. Every write is one transaction opened with ``BEGIN IMMEDIATE``; the set as it
would be after the write is checked through ``ZoneParams`` inside that transaction, so an invalid write writes
nothing. The time of a write is an argument (read once in ``main``).

This module is independent of the Fibonacci bot (rule 0): it imports nothing from ``bot2e``, ``bot_config`` or
``bot_research`` and never touches the table ``config_change``.

The logic lives in ``app/zone/params.py`` (ZONE_LIVE L0); this file is its command line and re-exports it. The
wall clock is read here, in ``_now`` and nowhere else.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.zone.params import (  # noqa: E402, F401
    _INSERT,
    DEFAULT_DB,
    FIELD_NAMES,
    SCHEMA,
    SEED_NOTE,
    ConfigError,
    ZoneParams,
    build_params,
    check_name,
    copy_set,
    history,
    list_sets,
    load_params,
    param_from_text,
    param_to_text,
    run,
    seed,
    seed_command,
    set_values,
    upgrade,
)


def _now() -> datetime:
    """The wall clock; read only by ``main`` (the write functions take the time as an argument)."""
    return datetime.now(UTC)


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv, _now)


if __name__ == "__main__":
    raise SystemExit(main())
