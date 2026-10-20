"""Item 4 (the measurer, 2026-10-20): `plib.load_learning()`, a loader that stops before the exam (2026-04-18 00:00 UTC).

`plib.load()` ends at 2026-10-17, so it hands every caller the exam rows and only the caller's own filter keeps them
out. `load_learning()` reads the stores through `gold.bars(tf, before=EXAM_START)`, a row filter applied while the
parquet files are read, so no bar from the exam's first minute on is ever returned.

Synthetic stores in a temp folder (gold.OLD / gold.NEW point at them); every expected value is written out by hand.
The last test reads the real stores (pre-exam rows only, through the filter) against the counts of
`audit2/out_check_merge.txt`, which were made by a separate path (a pyarrow-filtered scratch copy).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent / "precursors"))
import gold  # noqa: E402
import plib  # noqa: E402

ONE = pd.Timedelta(minutes=1)
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
START = pd.Timestamp("2023-08-01", tz="UTC")


def store(times: list[pd.Timestamp], opens: list[float], unit: str = "us") -> pd.DataFrame:
    t = pd.DatetimeIndex(times).as_unit(unit)
    return pd.DataFrame({"open_time": t, "close_time": t + ONE, "time_server": [0] * len(t), "open": opens,
                         "high": [x + 1 for x in opens], "low": [x - 1 for x in opens], "close": [x + 0.5 for x in opens],
                         "tick_volume": [10] * len(t), "spread": [20] * len(t), "real_volume": [0] * len(t)})


@pytest.fixture
def stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    monkeypatch.setattr(gold, "OLD", old)
    monkeypatch.setattr(gold, "NEW", new)
    return old, new


@pytest.fixture
def around_the_exam(stores: tuple[Path, Path]) -> list[pd.Timestamp]:
    """OLD: 2023-07-31 23:58, 23:59 (before START), START (open 3), and an exam-day row (2026-04-20 10:00, open 4: never
    in the merge, as it is after the first NEW bar, but a store read without the filter would return it). NEW: START + 1
    twice (opens 10, 11: the store holds a duplicate), the learning's last minute 2026-04-17 23:59 (12), the exam's
    first minute (13), + 1 min (14), and 2026-05-04 10:00 (15)."""
    old, new = stores
    store([START - 2 * ONE, START - ONE, START, pd.Timestamp("2026-04-20 10:00", tz="UTC")], [1.0, 2.0, 3.0, 4.0],
          "ms").to_parquet(old / "M1.parquet")
    nt = [START + ONE, START + ONE, EXAM - ONE, EXAM, EXAM + ONE, pd.Timestamp("2026-05-04 10:00", tz="UTC")]
    store(nt, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]).to_parquet(new / "M1.parquet")
    return nt


class TestLoadLearning:
    def test_it_ends_before_the_exam_and_keeps_load_s_rules(self, around_the_exam: list[pd.Timestamp]) -> None:
        m = plib.load_learning()
        assert list(m.index) == [START, START + ONE, EXAM - ONE]  # START kept; the exam's first minute and later gone
        assert m["open"].tolist() == [3.0, 11.0, 12.0]  # the duplicate keeps the LAST row (as load)
        assert list(m.columns) == ["open", "high", "low", "close", "tick_volume", "spread"]
        assert all(str(t) == "float64" for t in m.dtypes)
        assert str(m.index.tz) == "UTC"

    def test_it_equals_load_cut_at_the_exam(self, around_the_exam: list[pd.Timestamp]) -> None:
        full = plib.load()
        assert EXAM in full.index  # the measurer's loader still sees the exam
        pd.testing.assert_frame_equal(plib.load_learning(), full[full.index < EXAM])

    def test_a_later_start(self, around_the_exam: list[pd.Timestamp]) -> None:
        assert list(plib.load_learning(start=START + ONE).index) == [START + ONE, EXAM - ONE]

    def test_no_store_read_returns_an_exam_row(
        self, around_the_exam: list[pd.Timestamp], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Not only the result: every frame the stores hand back ends before the exam (the rows are filtered while
        the files are read, not after)."""
        seen: list[pd.DataFrame] = []
        real = pd.read_parquet

        def spy(*a: object, **k: object) -> pd.DataFrame:
            d = real(*a, **k)
            seen.append(d)
            return d

        monkeypatch.setattr(gold.pd, "read_parquet", spy)
        plib.load_learning()
        assert len(seen) == 2  # NEW and OLD
        assert all(pd.to_datetime(d["open_time"], utc=True).max() < EXAM for d in seen)


class TestGoldBarsBefore:
    @pytest.mark.parametrize("cut", ["2023-07-31 23:59", "2023-08-01 00:00", "2023-08-01 00:01", "2023-08-01 00:02",
                                     "2026-04-18 00:00", "2026-04-18 00:01", "2027-01-01 00:00"])
    def test_equals_the_full_merge_cut_at_before(self, around_the_exam: list[pd.Timestamp], cut: str) -> None:
        b = pd.Timestamp(cut, tz="UTC")
        full = gold.bars("M1")
        pd.testing.assert_frame_equal(gold.bars("M1", before=b).reset_index(drop=True),
                                      full[full.index < b].reset_index(drop=True), check_dtype=False)

    def test_before_the_first_new_bar_keeps_the_old_bars_before_it(self, stores: tuple[Path, Path]) -> None:
        """Every NEW bar opens at / after `before`: the NEW part is empty, and every OLD bar before `before` stays
        (they are all before the first NEW bar)."""
        old, new = stores
        t0 = pd.Timestamp("2023-08-31 23:57", tz="UTC")
        store([t0, t0 + ONE, t0 + 2 * ONE, t0 + 3 * ONE], [1.0, 2.0, 3.0, 4.0], "ms").to_parquet(old / "M1.parquet")
        store([t0 + 3 * ONE, t0 + 4 * ONE], [100.0, 101.0]).to_parquet(new / "M1.parquet")
        d = gold.bars("M1", before=t0 + 2 * ONE)
        assert list(d.index) == [t0, t0 + ONE] and d["open"].tolist() == [1.0, 2.0]

    def test_without_before_nothing_changes(self, around_the_exam: list[pd.Timestamp]) -> None:
        d = gold.bars("M1")
        assert len(d) == 3 + 6 and d.index.max() == pd.Timestamp("2026-05-04 10:00", tz="UTC")

    def test_a_naive_before_is_refused(self, around_the_exam: list[pd.Timestamp]) -> None:
        with pytest.raises(TypeError, match="tz-naive"):
            gold.bars("M1", before=pd.Timestamp("2026-04-18"))


@pytest.mark.skipif(not (ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet").exists(), reason="no local history store")
def test_the_real_stores_end_before_the_exam() -> None:
    """The real stores, read through the filter: the numbers of out_check_merge.txt ('plib.load: 954198 bars
    2023-08-01 00:00 .. 2026-04-17 20:54'), made there from a scratch copy of the pre-exam rows."""
    import os  # noqa: PLC0415

    cwd = os.getcwd()
    os.chdir(ROOT)  # gold's store paths are relative to the repo root
    try:
        m = plib.load_learning()
    finally:
        os.chdir(cwd)
    assert len(m) == 954_198
    assert m.index[0] == START and m.index[-1] == pd.Timestamp("2026-04-17 20:54", tz="UTC")
    assert m.index.is_unique and m.index.is_monotonic_increasing


# Round 3: the five group-b callers (they cut the bars before the exam right after `load()`) now read through
# `load_learning()`, so no exam row is ever in their memory. Each keeps its own start date.
GROUP_B = {
    "framework.py": 'pd.Timestamp("2025-06-01", tz="UTC")',
    "framework2.py": 'pd.Timestamp("2025-06-01", tz="UTC")',
    "level_power.py": "START - pd.Timedelta(days=10)",
    "regime.py": 'pd.Timestamp("2025-01-01", tz="UTC")',
    "verify_p2.py": 'pd.Timestamp("2025-09-01", tz="UTC")',
}


def plib_calls(path: Path) -> list[tuple[str, str]]:
    """Every `plib.<name>(...)` call in a file: (name, the source of its `start=` keyword or '')."""
    import ast  # noqa: PLC0415

    src = path.read_text(encoding="utf-8")
    out = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "plib" and node.func.attr in ("load", "load_learning")):
            start = next((ast.get_source_segment(src, k.value) or "" for k in node.keywords if k.arg == "start"), "")
            out.append((node.func.attr, start))
    return out


@pytest.mark.parametrize("name", sorted(GROUP_B))
def test_group_b_reads_only_the_learning_bars(name: str) -> None:
    assert plib_calls(HERE.parent / "precursors" / name) == [("load_learning", GROUP_B[name])]
