"""Whole-day gold ticks 2021-09 .. 2025-09 for the 5-year tick history (owner's go-ahead 2026-10-21 12:0x Thai), read-only
from MT5 via research/2026-10-18-moments/download_ticks.py, written to D:/taa-data/ticks/XAUUSD (C: has little room).
Days already there are skipped; run from the repo root.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/fetch_ticks_d.py 2021-09-01 2025-10-01
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import download_ticks as D  # noqa: E402

D.OUT = Path("D:/taa-data/ticks") / D.SYMBOL

if __name__ == "__main__":
    D.main()
