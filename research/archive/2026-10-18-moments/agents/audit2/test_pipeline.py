"""Audit 1(b) / 1(c): gold.bars (the OLD / NEW merge) and plib.load (START / END, duplicates), hand-worked.

Synthetic stores in a temp folder; gold.OLD / gold.NEW point at them. Every expected value is written out by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent / "precursors"))
import gold  # noqa: E402
import plib  # noqa: E402

T0 = pd.Timestamp("2023-08-31 23:55", tz="UTC")


def store(times: list[pd.Timestamp], base: float, unit: str) -> pd.DataFrame:
    """A store frame: open = base + i, high = open + 1, low = open - 1, close = open + 0.5."""
    t = pd.DatetimeIndex(times).as_unit(unit)
    o = [base + i for i in range(len(times))]
    return pd.DataFrame(
        {
            "open_time": t,
            "close_time": t + pd.Timedelta(minutes=1),
            "time_server": [0] * len(times),
            "open": o,
            "high": [x + 1 for x in o],
            "low": [x - 1 for x in o],
            "close": [x + 0.5 for x in o],
            "tick_volume": [10] * len(times),
            "spread": [20] * len(times),
            "real_volume": [0] * len(times),
        }
    )


def minutes(a: int, b: int) -> list[pd.Timestamp]:
    """T0 + a .. T0 + b minutes, inclusive."""
    return [T0 + pd.Timedelta(minutes=k) for k in range(a, b + 1)]


@pytest.fixture
def stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    monkeypatch.setattr(gold, "OLD", old)
    monkeypatch.setattr(gold, "NEW", new)
    return old, new


class TestGoldBars:
    def test_cut_at_the_first_new_bar_new_wins(self, stores: tuple[Path, Path]) -> None:
        old, new = stores
        store(minutes(0, 9), 1.0, "ms").to_parquet(old / "M1.parquet")  # 23:55 .. 00:04, open 1..10
        store(minutes(5, 12), 100.0, "us").to_parquet(new / "M1.parquet")  # 00:00 .. 00:07, open 100..107
        d = gold.bars("M1")
        assert list(d.index) == minutes(0, 12)  # 13 bars, no duplicate, sorted
        assert d["open"].tolist() == [1, 2, 3, 4, 5, 100, 101, 102, 103, 104, 105, 106, 107]
        assert str(d.index.tz) == "UTC"
        assert d.index[5] == pd.Timestamp("2023-09-01 00:00", tz="UTC")  # ms + us units: no shift

    def test_old_bar_inside_a_new_gap_after_the_cut_is_dropped(self, stores: tuple[Path, Path]) -> None:
        """The rule as written: the cut is at the first NEW bar; OLD never fills a NEW gap after it."""
        old, new = stores
        store(minutes(0, 9), 1.0, "ms").to_parquet(old / "M1.parquet")
        store(minutes(5, 6) + minutes(8, 9), 100.0, "us").to_parquet(new / "M1.parquet")  # NEW lacks 00:02
        d = gold.bars("M1")
        assert list(d.index) == minutes(0, 6) + minutes(8, 9)
        assert d["open"].tolist() == [1, 2, 3, 4, 5, 100, 101, 102, 103]

    def test_no_old_store(self, stores: tuple[Path, Path]) -> None:
        _, new = stores
        store(minutes(3, 5), 7.0, "us").to_parquet(new / "M1.parquet")
        d = gold.bars("M1")
        assert list(d.index) == minutes(3, 5) and d["open"].tolist() == [7, 8, 9]

    def test_unsorted_new_comes_out_sorted(self, stores: tuple[Path, Path]) -> None:
        _, new = stores
        f = store(minutes(0, 3), 1.0, "us").iloc[[2, 0, 3, 1]]
        f.to_parquet(new / "M1.parquet")
        d = gold.bars("M1")
        assert list(d.index) == minutes(0, 3) and d["open"].tolist() == [1, 2, 3, 4]


class TestPlibLoad:
    def test_start_inclusive_end_exclusive_duplicates_keep_last(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        s, e = plib.START, plib.END
        one = pd.Timedelta(minutes=1)
        idx = pd.DatetimeIndex([s - one, s, s + one, s + one, e - one, e], tz="UTC")
        frame = pd.DataFrame(
            {
                "open": [1, 2, 3, 33, 4, 5],
                "high": [1, 2, 3, 33, 4, 5],
                "low": [1, 2, 3, 33, 4, 5],
                "close": [1, 2, 3, 33, 4, 5],
                "tick_volume": [1, 1, 1, 1, 1, 1],
                "spread": [9, 9, 9, 9, 9, 9],
                "real_volume": [0] * 6,
            },
            index=idx,
        )
        monkeypatch.setattr(gold, "bars", lambda tf="M1": frame)
        m = plib.load()
        assert list(m.index) == [s, s + one, e - one]  # START kept, START - 1 and END dropped
        assert m["open"].tolist() == [2.0, 33.0, 4.0]  # the duplicate keeps the LAST row
        assert list(m.columns) == ["open", "high", "low", "close", "tick_volume", "spread"]
        assert all(str(t) == "float64" for t in m.dtypes)

    def test_the_constants(self) -> None:
        """The learning parts and the exam as the brief gives them."""
        assert plib.LEARN_START == pd.Timestamp("2025-10-18", tz="UTC")
        assert plib.EXAM_START == pd.Timestamp("2026-04-18", tz="UTC")
        assert plib.EXAM_END == pd.Timestamp("2026-10-17", tz="UTC")
        assert plib.START == pd.Timestamp("2023-08-01", tz="UTC")
        assert plib.END == pd.Timestamp("2026-10-17", tz="UTC")


class TestReleases:
    def test_new_york_time_to_utc_across_both_dst_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """08:30 New York = 13:30 UTC in US winter, 12:30 UTC in US summer; the EU change does not matter."""
        cal = tmp_path / "cal.csv"
        cal.write_text(
            "date,time_et,event,note\n"
            "2026-03-06,08:30,NFP,\n"  # Friday before the US change (2026-03-08): EST
            "2026-03-09,08:30,X,\n"  # Monday after it: EDT, while Europe is still on winter time
            "2026-03-30,08:30,X,\n"  # after the EU change (2026-03-29)
            "2025-10-27,08:30,X,\n"  # after the EU change (2025-10-26), the US still on summer time
            "2025-11-03,08:30,X,\n"  # after the US change (2025-11-02)
            "2025-10-29,14:00,FOMC,\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gold, "CALENDAR", cal)
        r = gold.releases()
        want = [
            "2026-03-06 13:30",
            "2026-03-09 12:30",
            "2026-03-30 12:30",
            "2025-10-27 12:30",
            "2025-11-03 13:30",
            "2025-10-29 18:00",
        ]
        assert list(r["t"]) == [pd.Timestamp(w, tz="UTC") for w in want]
