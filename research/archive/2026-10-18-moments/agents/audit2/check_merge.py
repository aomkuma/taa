"""Audit 1(b) / 1(c) on the real stores: gold.bars' OLD / NEW merge and plib.load's filters.

No exam row is read: the NEW store is read with a pyarrow filter open_time < 2026-04-18 into a scratch copy, the OLD
store ends 2023-10-02. The real `gold.bars` / `plib.load` then run on those copies (gold.OLD / gold.NEW patched).
The independent second source is a set-based union of the raw stores (NEW wins on a shared minute).

Run from the repo root: .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_merge.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
MOMENTS = ROOT / "research" / "2026-10-18-moments"
sys.path.insert(0, str(MOMENTS))
sys.path.insert(0, str(MOMENTS / "agents" / "precursors"))
import gold  # noqa: E402
import plib  # noqa: E402

EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
COLS = ["open", "high", "low", "close", "tick_volume", "spread"]


def main() -> int:
    old_raw = pd.read_parquet(ROOT / gold.OLD / "M1.parquet")
    new_raw = pd.read_parquet(ROOT / gold.NEW / "M1.parquet", filters=[("open_time", "<", EXAM_START)])
    with tempfile.TemporaryDirectory() as tmp:
        old_dir, new_dir = Path(tmp) / "old", Path(tmp) / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        old_raw.to_parquet(old_dir / "M1.parquet", index=False)
        new_raw.to_parquet(new_dir / "M1.parquet", index=False)
        gold.OLD, gold.NEW = old_dir, new_dir
        merged = gold.bars("M1")
        loaded = plib.load()

    first_new = new_raw["open_time"].min()
    print(f"OLD: {len(old_raw)} bars {old_raw.open_time.min()} .. {old_raw.open_time.max()}")
    print(f"NEW (< exam): {len(new_raw)} bars {first_new} .. {new_raw.open_time.max()}")
    print(f"gold.bars: {len(merged)} bars {merged.index.min()} .. {merged.index.max()}")
    print(f"  index UTC: {str(merged.index.tz) == 'UTC'}, unique: {merged.index.is_unique}, sorted: "
          f"{merged.index.is_monotonic_increasing}")
    from_old = merged.index < first_new
    print(f"  bars before the first NEW bar: {int(from_old.sum())} (OLD bars before it: "
          f"{int((old_raw.open_time < first_new).sum())})")
    print(f"  bars from the first NEW bar: {int((~from_old).sum())} (NEW bars: {len(new_raw)})")
    # every NEW bar is present with NEW's values
    m_new = merged.loc[~from_old, COLS].reset_index(drop=True)
    n_new = new_raw.set_index(pd.DatetimeIndex(new_raw["open_time"]))[COLS].reset_index(drop=True)
    print(f"  NEW part equal to the NEW store, value by value: {m_new.astype(float).equals(n_new.astype(float))}")
    m_old = merged.loc[from_old, COLS].reset_index(drop=True)
    o_old = old_raw[old_raw.open_time < first_new][COLS].reset_index(drop=True)
    print(f"  OLD part equal to the OLD store before the cut: {m_old.astype(float).equals(o_old.astype(float))}")

    # the joint
    last_old = merged.index[from_old].max()
    print(f"  the joint: last OLD bar {last_old}, first NEW bar {first_new}, "
          f"gap {(first_new - last_old) / pd.Timedelta(minutes=1):.0f} min")

    # the second source: a set union, NEW winning on a shared minute
    o = old_raw.set_index("open_time")[COLS].astype(float)
    n = new_raw.set_index("open_time")[COLS].astype(float)
    o.index, n.index = o.index.as_unit("us"), n.index.as_unit("us")
    union = n.combine_first(o).sort_index()
    shared = o.index.intersection(n.index)
    old_only_after_cut = o.index[(o.index >= first_new) & ~o.index.isin(n.index)]
    new_only_in_overlap = n.index[(n.index <= o.index.max()) & ~n.index.isin(o.index)]
    diff = (o.loc[shared, ["open", "high", "low", "close"]] - n.loc[shared, ["open", "high", "low", "close"]]).abs()
    print(f"overlap {first_new} .. {o.index.max()}: shared minutes {len(shared)}, OHLC equal on "
          f"{int((diff.max(axis=1) < 1e-9).sum())}, max |diff| {diff.to_numpy().max():.5f}; "
          f"tick_volume equal {int((o.loc[shared, 'tick_volume'] == n.loc[shared, 'tick_volume']).sum())}, "
          f"spread equal {int((o.loc[shared, 'spread'] == n.loc[shared, 'spread']).sum())}")
    print(f"  OLD-only minutes after the cut (dropped by gold.bars, kept by the union): {len(old_only_after_cut)}")
    if len(old_only_after_cut):
        print("   ", [str(t) for t in old_only_after_cut[:10]])
    print(f"  NEW-only minutes inside the overlap: {len(new_only_in_overlap)}")
    print(f"  gold.bars vs the union: {len(merged)} vs {len(union)} bars")

    # plib.load
    print(f"plib.load: {len(loaded)} bars {loaded.index.min()} .. {loaded.index.max()}, columns {list(loaded.columns)}")
    print(f"  START {plib.START}: first bar >= START: {loaded.index.min() >= plib.START}; bars of gold.bars before "
          f"START: {int((merged.index < plib.START).sum())}, dropped: "
          f"{int((merged.index < plib.START).sum()) == len(merged) - len(loaded)}")
    print(f"  unique {loaded.index.is_unique}, sorted {loaded.index.is_monotonic_increasing}, dtypes "
          f"{sorted(set(map(str, loaded.dtypes)))}")
    # learning parts' coverage: the minute gaps longer than 10 minutes on weekdays, outside the daily break
    lp = loaded[(loaded.index >= plib.LEARN_START) & (loaded.index < EXAM_START)]
    gaps = pd.Series(lp.index[1:] - lp.index[:-1], index=lp.index[:-1])
    big = gaps[gaps > pd.Timedelta(minutes=10)]
    weekend = big[big > pd.Timedelta(hours=40)]
    daily = big[(big >= pd.Timedelta(minutes=55)) & (big <= pd.Timedelta(minutes=75))]
    other = big.drop(weekend.index).drop(daily.index)
    print(f"learning parts {plib.LEARN_START.date()} .. {EXAM_START.date()}: {len(lp)} bars; gaps > 10 min: "
          f"{len(big)} = weekend {len(weekend)} + daily break (55-75 min) {len(daily)} + other {len(other)}")
    for t, g in other.items():
        print(f"    other gap from {t} for {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
