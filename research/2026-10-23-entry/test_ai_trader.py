"""The research wrapper's own filter (the rest moved to tests/unit/test_ai_trader.py with app/ai/trader.py).

    .venv/Scripts/python -m pytest research/2026-10-23-entry/test_ai_trader.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_trader as at  # noqa: E402


def test_trim_reads_keeps_reading_lines_only():
    text = "# Every timeframe\nM15 ATR 11 | big trend DOWN | rhythm DOWN\n    swings: H 1, L 2\n  SWEEP under it at 21:40\nnoise"
    assert at.trim_reads(text) == "M15 ATR 11 | big trend DOWN | rhythm DOWN\nSWEEP under it at 21:40"
