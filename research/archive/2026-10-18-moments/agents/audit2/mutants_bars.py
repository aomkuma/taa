"""Planted bugs for audit 2: indicators.bars against audit2/test_bars.py and precursors/test_indicators.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_bars
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PRE = ROOT / "research" / "2026-10-18-moments" / "agents" / "precursors"
TESTS = [
    "research/2026-10-18-moments/agents/audit2/test_bars.py",
    "research/2026-10-18-moments/agents/precursors/test_indicators.py",
]
BARS = [
    ("D1 on the UTC day", 'if rule in ("4h", "1D"):', 'if rule in ("4h",):'),
    ("H4 on the UTC clock", 'if rule in ("4h", "1D"):', 'if rule in ("1D",):'),
    ("the server day in London", 'tz_convert("Europe/Athens")', 'tz_convert("Europe/London")'),
    ("the server day at a fixed UTC+2", 'tz_convert("Europe/Athens")', 'tz_convert("Etc/GMT-2")'),
    ("avail = the last minute", 'b["avail"] = b["last"] + pd.Timedelta(minutes=1)', 'b["avail"] = b["last"]'),
    ("avail = the last minute + 2", 'b["last"] + pd.Timedelta(minutes=1)', 'b["last"] + pd.Timedelta(minutes=2)'),
    ("the open is the last open", '"open": g.open.first()', '"open": g.open.last()'),
    ("the high from the closes", '"high": g.high.max()', '"high": g.close.max()'),
    ("the low is the max", '"low": g.low.min()', '"low": g.low.max()'),
    ("the close is the first", '"close": g.close.last()', '"close": g.close.first()'),
    ("the last is the first minute", '"last": g._t.max()', '"last": g._t.min()'),
]
TARGETS = [("indicators", PRE / "indicators.py", TESTS, BARS)]
