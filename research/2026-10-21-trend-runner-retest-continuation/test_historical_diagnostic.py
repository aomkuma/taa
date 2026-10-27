# ruff: noqa: E501
"""The M1-approximation diagnostic is retired (2026-10-22); the guarded simulator is tested in test_candidate.py."""

from __future__ import annotations

import pytest
from historical_diagnostic import main


def test_superseded_diagnostic_refuses_to_run():
    with pytest.raises(SystemExit, match="Superseded"):
        main()
