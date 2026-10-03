"""Correlation ids carried through logs via context variables."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
cycle_id: ContextVar[str | None] = ContextVar("cycle_id", default=None)
signal_id: ContextVar[str | None] = ContextVar("signal_id", default=None)
intent_id: ContextVar[str | None] = ContextVar("intent_id", default=None)
command_id: ContextVar[str | None] = ContextVar("command_id", default=None)

ALL_VARS: dict[str, ContextVar[str | None]] = {
    "run_id": run_id,
    "cycle_id": cycle_id,
    "signal_id": signal_id,
    "intent_id": intent_id,
    "command_id": command_id,
}


def current_ids() -> dict[str, str]:
    """Non-empty correlation ids for the current context."""
    return {name: value for name, var in ALL_VARS.items() if (value := var.get()) is not None}


@contextmanager
def bind(**ids: str) -> Iterator[None]:
    """Temporarily bind correlation ids, e.g. ``with bind(signal_id=sid): ...``."""
    tokens = []
    for name, value in ids.items():
        if name not in ALL_VARS:
            raise KeyError(f"unknown correlation id {name!r}")
        tokens.append((ALL_VARS[name], ALL_VARS[name].set(value)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
