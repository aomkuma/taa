"""Planted bugs for item 4: gold.bars(before=...) and plib.load_learning against audit2/test_learning_loader.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_loader
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MOMENTS = ROOT / "research" / "2026-10-18-moments"
# the real-store test is left out: a mutant without the filter would load exam rows
TEST = ["research/2026-10-18-moments/agents/audit2/test_learning_loader.py", "-k", "not real_stores"]

GOLD = [
    ("the filter keeps the bar at `before`", '[("open_time", "<", ', '[("open_time", "<=", '),
    ("NEW read without the filter", 'pd.read_parquet(NEW / f"{tf}.parquet", filters=flt)', 'pd.read_parquet(NEW / f"{tf}.parquet")'),
    ("OLD read without the filter", 'pd.read_parquet(OLD / f"{tf}.parquet", filters=flt)', 'pd.read_parquet(OLD / f"{tf}.parquet")'),
    ("no fallback when NEW is empty", "        if pd.isna(first_new) and before is not None:", "        if False:"),
    ("a naive `before` taken as UTC", 'flt = None if before is None else [("open_time", "<", pd.Timestamp(before).tz_convert("UTC"))]',
     'flt = None if before is None else [("open_time", "<", pd.Timestamp(before).tz_localize("UTC") if pd.Timestamp(before).tz is None else pd.Timestamp(before))]'),
]
PLIB = [
    ("the stores read to the end (filtered after)", 'learn = gold.bars("M1", before=EXAM_START)', 'learn = gold.bars("M1")'),
    ("the learning ends at EXAM_END", 'learn = gold.bars("M1", before=EXAM_START)\n    learn = learn.loc[(learn.index >= start) & (learn.index < EXAM_START)]',
     'learn = gold.bars("M1", before=EXAM_END)\n    learn = learn.loc[(learn.index >= start) & (learn.index < EXAM_END)]'),
    ("the start argument ignored", "learn.loc[(learn.index >= start)", "learn.loc[(learn.index >= START)"),
    ("START exclusive", "learn.loc[(learn.index >= start)", "learn.loc[(learn.index > start)"),
    ("duplicates keep the first", 'learn.loc[~learn.index.duplicated(keep="last")]', 'learn.loc[~learn.index.duplicated(keep="first")]'),
    ("no duplicate removal", '    learn = learn.loc[~learn.index.duplicated(keep="last")]\n', ""),
    ("the spread column dropped", 'learn.loc[:, ["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)',
     'learn.loc[:, ["open", "high", "low", "close", "tick_volume"]].astype(float)'),
    ("not converted to float", 'learn.loc[:, ["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)',
     'learn.loc[:, ["open", "high", "low", "close", "tick_volume", "spread"]]'),
]

TARGETS = [
    ("gold", MOMENTS / "gold.py", TEST, GOLD),
    ("plib", MOMENTS / "agents" / "precursors" / "plib.py", TEST, PLIB),
]
