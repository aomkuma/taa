"""Planted bugs for audit 1(b) / 1(c): gold.bars and plib.load against audit2/test_pipeline.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_pipeline
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MOMENTS = ROOT / "research" / "2026-10-18-moments"
TEST = ["research/2026-10-18-moments/agents/audit2/test_pipeline.py"]

GOLD = [
    ("the cut keeps the OLD bar at the first NEW minute", "utc=True) < first_new]", "utc=True) <= first_new]"),
    ("the cut at the LAST NEW bar", 'new["open_time"], utc=True).min()', 'new["open_time"], utc=True).max()'),
    ("no sort", "    return d.sort_index()", "    return d"),
    ("indexed by the close time", 'pd.to_datetime(d["open_time"], utc=True))', 'pd.to_datetime(d["close_time"], utc=True))'),
    ("the OLD store ignored", '    if (OLD / f"{tf}.parquet").exists():', "    if False:"),
    ("releases read as UTC", '.dt.tz_localize(NY)', '.dt.tz_localize("UTC")'),
    ("releases at a fixed -5 h", '.dt.tz_localize(NY)', '.dt.tz_localize("Etc/GMT+5")'),
    ("releases on the server clock", '.dt.tz_localize(NY)', '.dt.tz_localize("Europe/Athens")'),
]
PLIB = [
    ("START exclusive", "m = m[(m.index >= START) & (m.index < END)]", "m = m[(m.index > START) & (m.index < END)]"),
    ("END inclusive", "m = m[(m.index >= START) & (m.index < END)]", "m = m[(m.index >= START) & (m.index <= END)]"),
    ("duplicates keep the first", 'm = m[~m.index.duplicated(keep="last")]', 'm = m[~m.index.duplicated(keep="first")]'),
    ("no duplicate removal", '    m = m[~m.index.duplicated(keep="last")]\n', ""),
    ("the spread column dropped", 'm[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)',
     'm[["open", "high", "low", "close", "tick_volume"]].astype(float)'),
]

TARGETS = [
    ("gold", MOMENTS / "gold.py", TEST, GOLD),
    ("plib", MOMENTS / "agents" / "precursors" / "plib.py", TEST, PLIB),
]
