# ruff: noqa: S101
from __future__ import annotations

import pandas as pd
import pytest
from tr1.windows import Window, anchor


def test_thai_anchors_are_fixed_in_thai_time() -> None:
    assert anchor("2025-10-20", Window.ASIA) == pd.Timestamp("2025-10-20 00:00", tz="UTC")
    assert anchor("2025-10-20", Window.LONDON) == pd.Timestamp("2025-10-20 06:00", tz="UTC")


def test_new_york_anchor_obeys_dst() -> None:
    assert anchor("2025-10-20", Window.NY0830) == pd.Timestamp("2025-10-20 12:30", tz="UTC")
    assert anchor("2025-11-03", Window.NY0830) == pd.Timestamp("2025-11-03 13:30", tz="UTC")
    assert anchor("2026-03-09", Window.NY0830) == pd.Timestamp("2026-03-09 12:30", tz="UTC")


def test_anchor_rejects_a_zoned_calendar_day() -> None:
    with pytest.raises(ValueError, match="timezone-naive"):
        anchor(pd.Timestamp("2025-10-20", tz="UTC"), Window.ASIA)
