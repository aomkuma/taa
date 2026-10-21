"""b2_tf_history by hand: the tick path (D: before 2025-10-01, data/ticks after, nothing from 2026-04-18), the tick
reader, the M1 loader's cut (fake readers), the year cut, the tiles, "M5 only" in the stream, the stats and the pass.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_b2_tf_history.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b2_tf_history as B  # noqa: E402
from sweep_detector import ExamPeriodError  # noqa: E402


def ts(x: str) -> pd.Timestamp:
    return pd.Timestamp(x, tz="UTC")


def _never(*a, **k):
    raise AssertionError("the reader was called")


# ---------------------------------------------------------------- the readers
def test_tick_path_switch_and_the_cut():
    assert B.OLD_TICKS == Path("D:/taa-data/ticks/XAUUSD")
    assert B.tick_path(ts("2021-09-01")) == Path("D:/taa-data/ticks/XAUUSD/2021-09-01.parquet")
    assert B.tick_path(ts("2025-09-30 23:59")) == B.OLD_TICKS / "2025-09-30.parquet"
    assert B.tick_path(ts("2025-10-01")) == B.NEW_TICKS / "2025-10-01.parquet"
    assert B.tick_path(pd.Timestamp("2026-04-17 12:00")) == B.NEW_TICKS / "2026-04-17.parquet"  # naive = UTC
    with pytest.raises(ExamPeriodError):
        B.tick_path(ts("2026-04-18"))
    with pytest.raises(ExamPeriodError):
        B.tick_path(ts("2026-10-19"))


def test_day_ticks_sorted_and_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "OLD_TICKS", tmp_path)
    (tmp_path / "2022-03-01.parquet").write_text("x")
    frame = pd.DataFrame({"time_utc": pd.to_datetime(["2022-03-01 00:00:02", "2022-03-01 00:00:01"], utc=True),
                          "bid": [2.0, 1.0], "ask": [2.5, 1.5]})
    t, bid, ask = B.day_ticks(ts("2022-03-01"), read=lambda f: frame)
    assert t.tolist() == [ts("2022-03-01 00:00:01").value, ts("2022-03-01 00:00:02").value]
    assert bid.tolist() == [1.0, 2.0] and ask.tolist() == [1.5, 2.5]
    assert B.day_ticks(ts("2022-03-02"), read=_never) is None
    with pytest.raises(ExamPeriodError):  # refused before the file is looked for
        B.day_ticks(ts("2026-05-01"), read=_never)


def _bars(times: list[str]) -> pd.DataFrame:
    idx = pd.DatetimeIndex(pd.to_datetime(times, utc=True))
    n = len(idx)
    return pd.DataFrame(dict(open_time=idx, open=np.arange(n, dtype=float), high=2.0, low=0.5, close=1.5, tick_volume=3,
                             spread=20, real_volume=0), index=idx)


def test_load_m1_cut_and_form():
    seen = {}

    def bars(tf, before):
        seen["args"] = (tf, before)
        return _bars(["2021-08-31 23:59", "2021-09-01 00:00", "2021-09-01 00:00", "2026-04-17 20:59"])

    m = B.load_m1(bars=bars)
    assert seen["args"] == ("M1", ts("2026-04-18"))
    assert list(m.columns) == ["open", "high", "low", "close", "tick_volume", "spread"]
    assert len(m) == 3 and m.loc[ts("2021-09-01"), "open"] == 2.0  # the duplicate keeps the last
    assert str(m.index.tz) == "UTC" and m.index.is_monotonic_increasing
    with pytest.raises(ExamPeriodError):
        B.load_m1(ts("2026-04-18") + pd.Timedelta(minutes=1), bars=_never)
    with pytest.raises(ExamPeriodError):  # a reader leaking a row at the cut
        B.load_m1(bars=lambda tf, before: _bars(["2026-04-18 00:00"]))


# ---------------------------------------------------------------- the years and the tiles
def test_year_cut():
    t = [ts("2021-08-31 23:59").value, ts("2021-09-01").value, ts("2022-09-01").value - 1, ts("2022-09-01").value,
         ts("2025-09-30 23:59").value, ts("2025-10-01").value, ts("2025-10-18").value, ts("2026-04-17 23:00").value]
    assert B.year_of(t).tolist() == ["", "2021-22", "2021-22", "2022-23", "2024-25", "", "P1+P2", "P1+P2"]
    assert B.YEARS["2024-25"] == (ts("2024-09-01"), ts("2025-10-01"))
    assert B.YEARS["P1+P2"] == (ts("2025-10-18"), ts("2026-04-18"))


def test_tiles():
    T = B.tiles(ts("2021-09-01"), ts("2021-11-10"))  # a Wednesday: the first Saturday is 09-04
    assert T == [(ts("2021-09-01"), ts("2021-09-04")), (ts("2021-09-04"), ts("2021-10-02")),
                 (ts("2021-10-02"), ts("2021-10-30")), (ts("2021-10-30"), ts("2021-11-10"))]
    T = B.tiles(ts("2025-10-18"), ts("2025-11-20"))  # a Saturday start: the next cut a week later
    assert T == [(ts("2025-10-18"), ts("2025-10-25")), (ts("2025-10-25"), ts("2025-11-20"))]


def test_m5_only_reaches_the_stream_and_the_tf_is_kept(monkeypatch):
    import p3_trades as T3
    import patterns as P
    import plan1 as L

    cands = pd.DataFrame(dict(t_entry=[10, 20, 30], tf=["M1", "M5", "M1"]))
    seen = {}

    class TF:
        avail = np.array([0, 5], np.int64)
        c = np.array([1.0, 1.0])

        def __init__(self, m, minutes):
            pass

        def scan(self, a, b):
            return []

    def stream(c, tfs, ticks, news, cost, mode):
        seen["tfs"] = c.tf.tolist()
        return pd.DataFrame(dict(t_entry=c.t_entry, entry_t=c.t_entry + 1, exit_t=c.t_entry + 2, side=1, entry=1.0,
                                 stop=0.5, risk=0.5, pnl=0.1, R=0.2, exit="time", tf=c.tf))

    monkeypatch.setattr(P, "level_inputs", lambda m: None)
    monkeypatch.setattr(P, "TF", TF)
    monkeypatch.setattr(P, "locate", lambda *a: pd.DataFrame(dict(entry=[1.0])))
    monkeypatch.setattr(P, "agree", lambda A, Bx, other: A)
    monkeypatch.setattr(T3, "candidates3", lambda C, tfs, s: cands)
    monkeypatch.setattr(L, "asia_candidates", lambda c: c)
    monkeypatch.setattr(T3, "run_stream3", stream)
    start, end = pd.Timestamp(0, tz="UTC"), pd.Timestamp(25, tz="UTC")
    X = B.asia_b2_tf(None, start, end, None, "M5")
    assert seen["tfs"] == ["M5"] and X.tf.tolist() == ["M5"]
    X = B.asia_b2_tf(None, start, end, None)
    assert seen["tfs"] == ["M1", "M5", "M1"]
    assert X.tf.tolist() == ["M1", "M5"]  # the entry decision at 30 is past the end
    assert X.t_dec.tolist() == [10, 20] and X.t_in.tolist() == [11, 21]


# ---------------------------------------------------------------- the report
def test_stats_by_hand():
    s = B.stats(np.array([1.0, -1.0, 0.5, 0.0]), np.array([10.0, -8.0, 4.0, 0.0]))
    half = 1.96 * np.std([1.0, -1.0, 0.5, 0.0], ddof=1) / 2
    assert (s["n"], s["R"], s["win"], s["usd"]) == (4, 0.125, 0.5, 6.0)  # a 0 is not a win
    assert s["lo"] == pytest.approx(0.125 - half) and s["hi"] == pytest.approx(0.125 + half)
    assert B.stats(np.array([]), np.array([]))["n"] == 0


def _tab(m5_r: list[float], m1_r: list[float], pooled: tuple[float, int, float]) -> pd.DataFrame:
    rows = []
    for name, rs in (("M5 only", m5_r), ("W: M5", m5_r), ("W: M1", m1_r)):
        for y, r in zip(B.YEARS, rs, strict=True):
            rows.append(dict(reading=name, year=y, band="all", n=10, R=r, lo=r - 0.3))
        R, n, lo = pooled
        rows.append(dict(reading=name, year="pooled", band="all", n=n, R=R, lo=lo))
    return pd.DataFrame(rows)


def test_verdict_by_hand():
    v = B.verdict(_tab([0.2, 0.1, 0.3, -0.1, 0.5], [0.1, 0.2, 0.0, 0.0, 0.0], (0.2, 50, 0.01)))
    assert v["M5 only"] == dict(R=0.2, n=50, lo=0.01, better_years=3, passed=True)
    assert not B.verdict(_tab([0.2, 0.1, 0.3, -0.1, 0.0], [0.1, 0.2, 0.0, 0.0, 0.0], (0.2, 50, 0.01)))["M5 only"]["passed"]
    assert not B.verdict(_tab([0.2, 0.1, 0.3, -0.1, 0.5], [0.1, 0.2, 0.0, 0.0, 0.0], (0.149, 50, 0.01)))["M5 only"]["passed"]
    assert not B.verdict(_tab([0.2, 0.1, 0.3, -0.1, 0.5], [0.1, 0.2, 0.0, 0.0, 0.0], (0.2, 39, 0.01)))["M5 only"]["passed"]
    assert not B.verdict(_tab([0.2, 0.1, 0.3, -0.1, 0.5], [0.1, 0.2, 0.0, 0.0, 0.0], (0.2, 50, 0.0)))["M5 only"]["passed"]
    assert B.verdict(_tab([0.2, 0.1, 0.3, -0.1, 0.5], [0.1, 0.2, 0.0, 0.0, 0.0], (0.15, 40, 0.01)))["M5 only"]["passed"]


def test_table_groups_and_bands():
    T = pd.DataFrame(dict(stream=["W", "W", "M5 only"], tf=["M1", "M5", "M5"], band=[True, False, False],
                          t_in=[ts("2022-01-03").value, ts("2023-01-03").value, ts("2023-01-03").value],
                          R=[1.0, -1.0, 0.5], pnl=[5.0, -5.0, 2.0]))
    Tab = B.table(T).set_index(["reading", "year", "band"])
    assert Tab.loc[("W: M1", "2021-22", "in"), "n"] == 1 and Tab.loc[("W: M1", "2021-22", "out"), "n"] == 0
    assert Tab.loc[("W: M5", "2022-23", "out"), "R"] == -1.0
    assert Tab.loc[("W: all", "pooled", "all"), "n"] == 2
    assert Tab.loc[("M5 only", "pooled", "all"), "R"] == 0.5


def test_commands():
    with pytest.raises(SystemExit):
        B.main([])
    with pytest.raises(SystemExit):
        B.main(["run", "2026-27"])  # not a year: refused before anything is read
    with pytest.raises(SystemExit):
        B.main(["run"])


def test_run_period_warm_up_locate_back_and_streams(monkeypatch):
    idx = pd.date_range("2021-08-10", "2021-10-10", freq="1h", tz="UTC")
    m_all = pd.DataFrame(dict(open=1.0, high=2.0, low=0.5, close=1.5, tick_volume=1.0, spread=20.0), index=idx)
    calls = []

    def fake(m, start, end, ticks, tf_only=None):
        calls.append((m.index.min(), start, end, ticks.start, ticks.end, tf_only))
        t = [x for x in (start.value, (start + pd.Timedelta(days=4)).value) if x < end.value]  # as asia_b2_tf
        return pd.DataFrame(dict(piece="Asia B2", t_dec=t, t_in=t, t_out=t, side=1, entry=1.0, stop=0.5, risk=0.5,
                                 pnl=0.1, R=0.2, exit="time", tf="M5"))

    monkeypatch.setattr(B, "asia_b2_tf", fake)
    T = B.run_period(m_all, ts("2021-09-01"), ts("2021-09-10"), pd.Timedelta(0))
    # tiles 09-01 .. 09-04 and 09-04 .. 09-10; M1 from 14 days before each; B2 located from the tile (first) / 3 days back
    assert [c[0] for c in calls] == [ts("2021-08-18"), ts("2021-08-18"), ts("2021-08-21"), ts("2021-08-21")]
    assert [c[1] for c in calls] == [ts("2021-09-01"), ts("2021-09-01"), ts("2021-09-01"), ts("2021-09-01")]
    assert [c[3:5] for c in calls][2] == (ts("2021-09-04"), ts("2021-09-10"))
    assert [c[5] for c in calls] == [None, "M5", None, "M5"]
    assert sorted(T.stream.unique()) == ["M5 only", "W"]
    assert (T.t_dec >= ts("2021-09-01").value).all()
    assert len(T[T.t_dec < ts("2021-09-04").value]) == 2  # tile 1: the decision at its start kept (W + M5 only)
    assert len(T) == 4  # tile 2: its 09-01 decision (located 3 days back, before the tile) dropped, 09-05 kept
    assert "band" in T and "atr_h1" in T
