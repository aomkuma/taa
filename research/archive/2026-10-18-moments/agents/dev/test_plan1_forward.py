"""plan1_forward by hand: the band's edges, the last closed H1 bar and its ATR, the three variants with one position at
a time, the forward period's end, what is read (fake readers: no forward or exam data is opened), the pieces' start,
the Thai weeks, the trade table, the switches.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_plan1_forward.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan1_forward as F  # noqa: E402
from sweep_detector import ExamPeriodError  # noqa: E402

S = 10**9
MN = 60 * S


def ts(x: str) -> pd.Timestamp:
    return pd.Timestamp(x, tz="UTC")


# ---------------------------------------------------------------- the band and the H1 ATR
def test_band_edges():
    a = [11.99, 11.999999, 12.0, 12.000001, 15.999999, 16.0, 16.000001, np.nan, 25.0]
    assert F.in_band(a).tolist() == [False, False, True, True, True, False, False, False, False]
    assert (F.BAND_LO, F.BAND_HI) == (12.0, 16.0)


def _hours(ranges: list[float], start: str = "2025-11-05 00:00", drop_after: dict | None = None) -> pd.DataFrame:
    """Hour i: 60 M1 bars with open = close = 100, high 100 + r_i / 2, low 100 - r_i / 2 (so TR_i = r_i from hour 1:
    the previous close 100 lies inside the range). drop_after {hour: minute}: that hour's M1 bars stop at the minute."""
    rows = []
    for i, r in enumerate(ranges):
        last = (drop_after or {}).get(i, 60)
        for k in range(last):
            rows.append((ts(start) + pd.Timedelta(hours=i, minutes=k), 100.0, 100 + r / 2, 100 - r / 2, 100.0))
    m = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"]).set_index("t")
    m.index.name = None
    m["tick_volume"], m["spread"] = 1.0, 20.0
    return m


def test_the_atr_of_the_last_closed_h1_bar_by_hand():
    r = [float(i + 1) for i in range(17)]  # hour i has range i + 1
    av, a = F.h1_atr(_hours(r))
    # bar 0 has no previous close (MT5): the first ATR is bar 14's, the mean of TR_1 .. TR_14 = (2 + ... + 15) / 14 = 8.5
    assert np.isnan(a[13]) and a[14] == pytest.approx(8.5)
    assert a[16] == pytest.approx(10.5)  # (4 + ... + 17) / 14
    t = lambda s: ts(f"2025-11-05 {s}").value  # noqa: E731
    got = F.atr_at(av, a, [t("14:59:59.999"), t("15:00"), t("15:30"), t("16:00"), t("17:00"), t("23:00")])
    assert np.isnan(got[0])  # bar 14 (14:00-15:00) is not closed one ns before 15:00
    assert got[1:].tolist() == pytest.approx([8.5, 8.5, 9.5, 10.5, 10.5])  # closed at 15:00; the forming bar not read
    assert np.isnan(F.atr_at(av, a, [ts("2025-11-04 23:00").value])[0])  # before any bar


def test_the_forming_bar_is_never_read_and_an_hour_closes_on_the_clock():
    r = [float(i + 1) for i in range(17)]
    m = _hours(r)
    av, a = F.h1_atr(m)
    m2 = m.copy()
    k = m2.index >= ts("2025-11-05 15:00")
    m2.loc[k, ["high", "low"]] = [[200.0, 1.0]] * int(k.sum())  # the forming bar 15:00 and later changed
    av2, a2 = F.h1_atr(m2)
    t = ts("2025-11-05 15:59").value
    assert F.atr_at(av, a, [t])[0] == F.atr_at(av2, a2, [t])[0] == pytest.approx(8.5)
    # an hour whose last M1 bars are missing still closes at its open + 60 min, not at its last bar
    av3, a3 = F.h1_atr(_hours(r, drop_after={14: 30}))
    assert np.isnan(F.atr_at(av3, a3, [ts("2025-11-05 14:31").value])[0])
    assert F.atr_at(av3, a3, [ts("2025-11-05 15:00").value])[0] == pytest.approx(8.5)


def test_the_atr_against_the_independent_re_derivation_with_a_weekend_gap():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-11-06 18:00", "2025-11-07 20:59", freq="1min", tz="UTC").append(
        pd.date_range("2025-11-09 23:00", "2025-11-10 12:00", freq="1min", tz="UTC"))
    idx = idx.delete(rng.choice(len(idx), 300, replace=False))  # missing minutes
    c = 4000 + np.cumsum(rng.normal(0, 0.8, len(idx)))
    o = np.r_[c[0], c[:-1]]
    h, lo = np.maximum(o, c) + rng.uniform(0, 1, len(idx)), np.minimum(o, c) - rng.uniform(0, 1, len(idx))
    m = pd.DataFrame(dict(open=o, high=h, low=lo, close=c, tick_volume=1.0, spread=20.0), index=idx)
    t = np.arange(ts("2025-11-07 10:00").value, ts("2025-11-10 12:00").value, 7 * MN, dtype=np.int64)
    av, a = F.h1_atr(m)
    mine, other = F.atr_at(av, a, t), F.independent_atr(m, t)
    assert np.isfinite(mine).sum() > 300
    assert np.array_equal(np.isnan(mine), np.isnan(other))
    assert np.allclose(mine[np.isfinite(mine)], other[np.isfinite(other)], rtol=0, atol=1e-9)


def _every(rows):
    """Trades with the plan1 columns: (piece, t_dec, t_in) by hand, out one minute after the fill."""
    import plan1 as L

    return pd.concat([L.piece_rows(pc, [dict(t_dec=a, t_in=b, t_out=b + MN, side=1, entry=100.0, stop=99.0, risk=1.0,
                                             pnl=0.5, R=0.5, exit="time")]) for pc, a, b in rows], ignore_index=True)


def test_tag_reads_the_atr_at_the_decision_not_the_fill():
    m = _hours([2.0 * i for i in range(17)])  # TR_i = 2 i: ATR bar 14 = (2 + .. + 28) / 14 = 15, bar 15 = 17
    t = lambda s: ts(f"2025-11-05 {s}").value  # noqa: E731
    T = F.tag(_every([("Asia B2", t("15:59"), t("16:00:30")),       # decided in the band (15), filled after 16:00 (17)
                      ("NY straddle", t("16:10"), t("16:10:20")),   # 17: outside; the straddle
                      ("London ORB", t("14:30"), t("14:31"))]), m)  # no closed bar 14 yet: NaN, outside
    assert T.atr_h1.tolist()[:2] == pytest.approx([15.0, 17.0]) and np.isnan(T.atr_h1[2])
    assert T.band.tolist() == [True, False, False]
    assert T["take_VOL-16"].tolist() == [True, False, False]
    assert T["take_VOL-16b"].tolist() == [True, True, False]
    assert T.take_unfiltered.all()


def test_tag_band_edges_from_the_bars():
    t = ts("2025-11-05 16:30").value
    for r, want in ((12.0, True), (16.0, False)):  # a constant range: the ATR is exactly r
        T = F.tag(_every([("Asia B2", t, t)]), _hours([r] * 17))
        assert T.atr_h1[0] == r and T.band[0] == want and T["take_VOL-16"][0] == want


# ---------------------------------------------------------------- the variants
def _trades(rows):
    T = pd.DataFrame(rows, columns=["piece", "t_in", "t_out", "atr_h1"])
    T["t_dec"] = T.t_in
    for c in ("t_in", "t_out", "t_dec"):
        T[c] = T[c].astype(np.int64)
    T["band"] = F.in_band(T.atr_h1)
    return F.take_variants(T)


def test_the_variants_by_hand():
    T = _trades([
        ("Asia B2", 1, 2, 12.0),        # a: the lower edge is in -> every variant
        ("London ORB", 3, 4, 16.0),     # b: the upper edge is out -> unfiltered only
        ("NY straddle", 5, 6, 20.0),    # c: out, the straddle -> unfiltered and VOL-16b
        ("London ORB", 7, 10, 18.0),    # d: out; it holds the position in the unfiltered plan ...
        ("Asia B2", 8, 9, 13.0),        # e: ... so this in-band trade is dropped there, taken by VOL-16 / VOL-16b
        ("NY straddle", 11, 12, np.nan),  # f: no ATR -> outside the band
        ("Asia B2", 12, 13, 15.0),      # g: fills at f's exit: kept where f is kept (a fill at the exit is allowed)
    ])
    got = {v: T[f"take_{v}"].tolist() for v in F.VARIANTS}
    assert got["unfiltered"] == [True, True, True, True, False, True, True]
    assert got["VOL-16"] == [True, False, False, False, True, False, True]
    assert got["VOL-16b"] == [True, False, True, False, True, True, True]
    assert F.variant(T, "VOL-16").t_in.tolist() == [1, 8, 12]


def test_variants_with_an_index_out_of_order():
    T = _trades([("Asia B2", 5, 9, 13.0), ("NY straddle", 1, 6, 17.0)])  # rows not in time order
    assert T.take_unfiltered.tolist() == [False, True]  # the straddle fills first and holds until 6
    assert T["take_VOL-16"].tolist() == [True, False]
    assert T["take_VOL-16b"].tolist() == [False, True]


# ---------------------------------------------------------------- the period and what is read
def test_forward_end():
    days = [ts("2026-10-19"), ts("2026-10-20"), ts("2026-10-21")]
    assert F.forward_end(days, ts("2026-10-21 05:07")) == ts("2026-10-21")  # today's file may still be filling
    assert F.forward_end(days, ts("2026-10-25 01:00")) == ts("2026-10-22")  # the day after the newest file
    assert F.forward_end(days, ts("2026-10-25"), ts("2026-10-20")) == ts("2026-10-20")
    with pytest.raises(ValueError):
        F.forward_end([], ts("2026-10-25"))
    with pytest.raises(ValueError):  # 10-18 .. 10-19 exclusive has no weekday
        F.forward_end([ts("2026-10-18")], ts("2026-10-25"))
    assert F.FWD_START == ts("2026-10-18")


def _table(times: list[str]) -> pa.Table:
    t = pd.to_datetime(times, utc=True)
    n = len(t)
    return pa.table(dict(open_time=t, open=[1.0] * n, high=[2.0] * n, low=[0.5] * n, close=[1.5] * n,
                         tick_volume=[3.0] * n, spread=[20.0] * n))


def _never(*a, **k):
    raise AssertionError("the reader was called")


def test_read_m1_forward_reads_the_warm_up_and_nothing_earlier():
    seen = {}

    def reader(path, columns, filters):
        seen["filters"] = filters
        return _table(["2026-10-04 00:00", "2026-10-19 01:00", "2026-10-19 01:00"])

    m = F.read_m1(F.FWD_START, ts("2026-10-21"), reader=reader)
    assert F.WARM_DAYS == 14
    assert seen["filters"] == [("open_time", ">=", ts("2026-10-04")), ("open_time", "<", ts("2026-10-21"))]
    assert len(m) == 2 and str(m.index.tz) == "UTC"
    with pytest.raises(ExamPeriodError):  # a leaked row before the warm-up
        F.read_m1(F.FWD_START, ts("2026-10-21"), reader=lambda *a, **k: _table(["2026-10-03 23:59"]))
    with pytest.raises(ExamPeriodError):  # a leaked row at the end
        F.read_m1(F.FWD_START, ts("2026-10-21"), reader=lambda *a, **k: _table(["2026-10-21 00:00"]))
    with pytest.raises(ValueError):  # the forward period starts on 2026-10-18 only
        F.read_m1(ts("2026-10-19"), ts("2026-10-21"), reader=_never)


def test_read_m1_learning_never_reaches_the_exam():
    with pytest.raises(ExamPeriodError):
        F.read_m1(ts("2026-04-04"), ts("2026-04-18") + pd.Timedelta(minutes=1), reader=_never)
    with pytest.raises(ExamPeriodError):  # an exam-period start is not the forward start either
        F.read_m1(ts("2026-05-01"), ts("2026-06-01"), reader=_never)
    seen = {}

    def reader(path, columns, filters):
        seen["filters"] = filters
        return _table(["2026-03-01 00:00"])

    F.read_m1(ts("2026-03-07"), ts("2026-04-04"), reader=reader, warm_days=10)
    assert seen["filters"][0] == ("open_time", ">=", ts("2026-02-25"))


def test_ticks_never_open_a_day_outside_the_period():
    opened = []

    def read(d):
        opened.append(d)
        return np.array([d.value + S], np.int64), np.array([1.0]), np.array([1.2])

    tk = F.SpanTicks(ts("2026-10-18"), ts("2026-10-21"), read=read)
    assert len(tk.day(ts("2026-10-17"))[0]) == 0  # the exam's last day: never opened
    assert len(tk.day(pd.Timestamp("2026-10-16 12:00"))[0]) == 0  # a naive time is UTC
    t, _, _ = tk.span(ts("2026-10-17 23:00").value)  # Saturday 10-17 joined to Sunday 10-18: only 10-18's tick
    assert len(t) == 1
    assert len(tk.day(ts("2026-10-20"))[0]) == 1
    assert len(tk.day(ts("2026-10-21"))[0]) == 0  # the end: never opened
    assert opened == [ts("2026-10-18"), ts("2026-10-20")]


def test_tick_days_from_the_names(tmp_path):
    for n in ("2026-10-19.parquet", "2026-10-20.parquet", "notes.parquet", "2026-10-2x.parquet"):
        (tmp_path / n).write_text("not read")
    assert F.tick_days(tmp_path) == [ts("2026-10-19"), ts("2026-10-20")]


def _rows(piece, t_decs, t_ins):
    import plan1 as L

    return L.piece_rows(piece, [dict(t_dec=a, t_in=b, t_out=b + MN, side=1, entry=100.0, stop=99.0, risk=1.0,
                                     pnl=0.5, R=0.5, exit="time") for a, b in zip(t_decs, t_ins, strict=True)])


def test_pieces_locate_b2_from_three_days_back_and_keep_decisions_from_the_start(monkeypatch):
    import plan1 as L

    start, end = ts("2026-10-18"), ts("2026-10-21")
    calls = {}

    def asia(m, a, b, ticks, slip):
        calls["asia"] = (a, b, slip)
        return _rows("Asia B2", [ts("2026-10-17 23:59").value, ts("2026-10-19 00:30").value],
                     [ts("2026-10-19 00:31").value, ts("2026-10-19 00:31").value])

    def london(mk, days, ticks, slip):
        calls["days"] = list(days)
        return _rows("London ORB", [ts("2026-10-20 06:16").value], [ts("2026-10-20 06:16").value])

    monkeypatch.setattr(L, "asia_b2", asia)
    monkeypatch.setattr(L, "london_orb", london)
    monkeypatch.setattr(L, "ny_straddle", lambda days, ticks, slip, extra: _rows("NY straddle", [], []))
    monkeypatch.setattr(F.D1, "Market", lambda m: None)
    E = F.pieces(None, start, end, None)
    assert calls["asia"] == (ts("2026-10-15"), end, 0.0)
    assert calls["days"] == [ts("2026-10-19"), ts("2026-10-20")]  # the weekdays from the start, end excluded
    assert E.piece.tolist() == ["Asia B2", "London ORB"]  # the decision before the start dropped
    monkeypatch.setattr(L, "london_orb", lambda mk, days, ticks, slip: _rows("London ORB", [end.value], [end.value]))
    with pytest.raises(ExamPeriodError):
        F.pieces(None, start, end, None)


# ---------------------------------------------------------------- the report
def test_summary_and_weeks_by_hand():
    T = _trades([("Asia B2", ts("2026-10-25 16:59").value, ts("2026-10-25 17:00").value, 13.0),   # Sun 23:59 Thai
                 ("NY straddle", ts("2026-10-25 17:01").value, ts("2026-10-25 17:02").value, 20.0)])  # Mon 00:01 Thai
    T["R"], T["pnl"] = [1.0, -0.5], [10.0, -4.0]
    W = F.weekly(T)
    assert [str(d) for d in W.index] == ["2026-10-19", "2026-10-26"]
    assert W[("unfiltered", "n")].tolist() == [1, 1] and W[("unfiltered", "run")].tolist() == [10.0, 6.0]
    assert W[("VOL-16", "n")].tolist() == [1, 0] and W[("VOL-16", "run")].tolist() == [10.0, 10.0]
    assert W[("VOL-16b", "win")].tolist() == [1.0, 0.0]
    s = F.summary(F.variant(T, "unfiltered"), 5)
    assert (s["n"], s["per_day"], s["R"], s["usd"], s["worst"], s["dd"], s["win"]) == (2, 0.4, 0.25, 6.0, -4.0, 4.0, 0.5)
    assert F.weekdays(ts("2026-10-18"), ts("2026-10-24")) == 5


def test_trade_table():
    T = _trades([("NY straddle", ts("2026-10-20 12:30").value, ts("2026-10-20 13:00").value, 20.0),
                 ("London ORB", ts("2026-10-21 00:05").value, ts("2026-10-21 00:50").value, 17.0),
                 ("Asia B2", ts("2026-10-21 00:10").value, ts("2026-10-21 00:40").value, 14.0),
                 ("Asia B2", ts("2026-10-21 00:20").value, ts("2026-10-21 00:30").value, 18.0)])
    T["side"], T["entry"] = [-1, 1, 1, 1], [4100.0, 4000.0, 4000.0, 4000.0]
    T["pnl"], T["R"], T["exit"] = [2.0, 1.0, -1.5, 0.1], [0.25, 0.1, -0.5, 0.01], ["time", "time", "stop", "time"]
    X = F.trade_table(T)  # the last trade: no variant takes it (outside the band, held by the London trade)
    assert X.piece.tolist() == ["NY straddle", "London ORB", "Asia B2"]
    assert X.exit_px.tolist() == [4098.0, 4001.0, 3998.5]  # a sell's exit = entry - pnl
    assert X.side.tolist() == ["sell", "buy", "buy"]
    assert X.in_thai.tolist() == ["10-20 19:30:00", "10-21 07:05:00", "10-21 07:10:00"]
    assert X.variants.tolist() == ["unfiltered,VOL-16b", "unfiltered", "VOL-16,VOL-16b"]


def test_same_trades():
    a = _rows("Asia B2", [1, 2, 3], [1, 2, 3])
    b = a.copy()
    b.loc[1, "pnl"] = 0.4
    b = b.drop(index=2)
    assert F.same_trades(a, b) == (1, 1, 1, 0)


def test_the_switches(monkeypatch):
    a = F.parse([])
    assert (a.forward, a.end, a.warm_days) == (False, None, 14)
    monkeypatch.setattr(F, "forward", _never)
    monkeypatch.setattr(F, "self_test", _never)
    with pytest.raises(SystemExit):
        F.main(["--end", "2026-10-21"])  # --end only with --forward
    with pytest.raises(SystemExit):
        F.main(["--forward", "--warm-days", "7"])  # the forward warm-up is fixed
    got = {}
    monkeypatch.setattr(F, "forward", lambda end: got.update(end=end))
    F.main(["--forward", "--end", "2026-10-21"])
    assert got["end"] == ts("2026-10-21")


def test_forward_with_fake_readers(monkeypatch, tmp_path):
    """forward() end to end on fakes: the end from the tick names and today, the M1 read from 2026-10-04, the tick
    cache's bounds, the warm-up check on 11 days, the files."""
    seen = {"pieces": []}

    def reader(path, columns, filters):
        seen["filters"] = filters
        hrs = pd.date_range("2026-10-04 00:00", "2026-10-20 23:00", freq="1h", tz="UTC")
        return _table([str(t) for t in hrs])

    def pieces(m, start, end, ticks, *a, **k):
        seen["pieces"].append((m.index.min(), start, end, ticks.start, ticks.end))
        return _every([("Asia B2", ts("2026-10-19 00:30").value, ts("2026-10-19 00:31").value),
                       ("NY straddle", ts("2026-10-20 12:30").value, ts("2026-10-20 12:30:10").value)])

    monkeypatch.setattr(F, "pieces", pieces)
    monkeypatch.setattr(F, "tick_days", lambda folder: [ts("2026-10-19"), ts("2026-10-20"), ts("2026-10-21")])
    T = F.forward(today=ts("2026-10-21 05:07"), out_dir=tmp_path, reader=reader)
    assert seen["filters"] == [("open_time", ">=", ts("2026-10-04")), ("open_time", "<", ts("2026-10-21"))]
    full, short = seen["pieces"]
    assert full == (ts("2026-10-04"), F.FWD_START, ts("2026-10-21"), F.FWD_START, ts("2026-10-21"))
    assert short[0] == ts("2026-10-07")  # the warm-up check: 3 days less
    assert len(T) == 2 and set(T.part) == {"plan1_forward"}
    txt = (tmp_path / "out_plan1_forward.txt").read_text(encoding="utf-8")
    assert "2026-10-18 .. 2026-10-20 (2 weekdays)" in txt and "2 trades equal, 0 differ" in txt
    assert "tick files for 2 of 2 weekdays" in txt
    assert (tmp_path / "plan1_forward_trades.parquet").exists()
    with pytest.raises(ValueError):  # a dry run (another start) needs its end
        F.forward(start=ts("2026-03-07"), out_dir=tmp_path, reader=_never)
    with pytest.raises(ExamPeriodError):  # a dry run reaching the exam is refused before reading
        F.forward(ts("2026-04-25"), ts("2026-04-11"), out_dir=tmp_path, reader=_never)


def test_a_zero_trade_is_not_a_win():
    T = _trades([("Asia B2", ts("2026-10-20 00:30").value, ts("2026-10-20 00:40").value, 13.0)])
    T["R"], T["pnl"] = [0.0], [0.0]
    W = F.weekly(T)
    assert W[("VOL-16", "win")].tolist() == [0.0] and W[("unfiltered", "R")].tolist() == [0.0]
