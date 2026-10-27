# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def test_independent_exit_verifier_does_not_import_producer_modules() -> None:
    source = (HERE / "verify_exits.py").read_text(encoding="utf-8")
    assert "from tr1.exits import" not in source
    assert "from tr1.structure import" not in source
    assert "from exit_study import" not in source
