# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from frozen_round import execution_path, require_frozen_manifest
from tr1.boundaries import P1, DataBoundaryError
from tr1.data import TickStore

HERE = Path(__file__).resolve().parents[1]


def test_validation_needs_a_frozen_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("frozen_round.MANIFEST", tmp_path / "missing.json")
    with pytest.raises(DataBoundaryError, match="does not exist"):
        require_frozen_manifest()


def test_execution_path_never_opens_after_period_end(tmp_path: Path) -> None:
    store = TickStore(tmp_path, P1)
    result = execution_path(
        store,
        pd.Timestamp("2026-01-15 23:00", tz="UTC"),
        pd.Timestamp("2026-01-16 07:00", tz="UTC"),
    )
    assert result.empty
    assert not store.opened
