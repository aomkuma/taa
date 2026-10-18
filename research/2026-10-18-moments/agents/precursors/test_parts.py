"""The building blocks under every setup, with hand-worked answers: the bars against the broker's own, fractals, level
merging, the library's support / resistance, the run catalogue and the outcome labels.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_parts.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import foundation as F  # noqa: E402
import library  # noqa: E402
import plib  # noqa: E402

ROOT = HERE.parents[3]


# ---------------------------------------------------------------- bars
@pytest.mark.parametrize("tf,rule", [("M5", "5min"), ("M15", "15min"), ("M30", "30min"), ("H1", "1h"), ("H4", "4h")])
def test_our_bars_are_the_brokers(tf, rule):
    """Every stored FBS bar of 2025-10 .. 2026-10 against the bar we build from M1: the same open times, the same
    OHLC except at most one bar the broker saved while it was still forming."""
    m = plib.load()
    br = pd.read_parquet(ROOT / f"data/history/FBS-Demo/XAUUSD/{tf}.parquet")
    br.index = pd.DatetimeIndex(pd.to_datetime(br["open_time"], utc=True))
    lo_t, hi_t = pd.Timestamp("2025-10-08", tz="UTC"), pd.Timestamp("2026-10-13", tz="UTC")
    br = br[(br.index >= lo_t) & (br.index <= hi_t)]
    mine = plib.tf_bars(m[(m.index >= lo_t - pd.Timedelta(hours=8)) & (m.index <= hi_t + pd.Timedelta(hours=8))], rule)
    if rule == "4h":
        key = pd.DatetimeIndex(mine["last"]).tz_convert("Europe/Athens").tz_localize(None).floor("4h")
        key = key.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    else:
        key = pd.DatetimeIndex(mine["last"]).floor(rule)
    mine.index = key
    j = br[["open", "high", "low", "close", "tick_volume"]].join(mine[["open", "high", "low", "close", "tv"]], rsuffix="_m",
                                                                  how="inner")
    assert len(j) == len(br)  # every broker bar has ours at the same open time (H4 on the server day, DST)
    d = np.abs(j[["open", "high", "low", "close"]].to_numpy() - j[["open_m", "high_m", "low_m", "close_m"]].to_numpy())
    # no M1 minute missing: the broker's tick volume of a bar is the sum of its minutes' (the forming bar excepted)
    bad = (d > 1e-6).any(axis=1) | (j.tick_volume.to_numpy() != j.tv.to_numpy())
    assert bad.sum() <= 1


def test_the_m1_data_is_clean():
    """The learning and exam period's M1 bars: one per minute, in order, OHLC consistent, a spread recorded."""
    m = plib.load()
    m = m[(m.index >= plib.LEARN_START) & (m.index < plib.EXAM_END)]
    assert m.index.is_unique and m.index.is_monotonic_increasing
    assert ((m.index - m.index.floor("1min")) == pd.Timedelta(0)).all()
    assert (m.high >= m[["open", "close"]].max(axis=1)).all() and (m.low <= m[["open", "close"]].min(axis=1)).all()
    assert (m.spread > 0).mean() > 0.999 and (m.spread >= 0).all()


# ---------------------------------------------------------------- swings and levels
H = np.array([101, 102, 103, 104, 105, 110, 105, 104, 103, 102, 101, 102, 110.1, 103, 102, 101, 100, 99, 98, 97.0])
LO = H - 5
LO[9] = 90.0


def test_fractals_need_k_bars_each_side():
    ph, pl = F.fractals(H, LO, 3)
    assert ph.tolist() == [5, 12] and pl.tolist() == [9]
    h = np.array([1.0, 3, 3, 1, 0])
    assert F.fractals(h, h - 1, 1)[0].tolist() == [1, 2]  # equal highs inside one window: both are swings
    assert F.fractals(np.array([1.0, 2, 3]), np.array([0.0, 1, 2]), 3)[0].tolist() == []  # no full window: none


def test_levels_are_no_wider_than_the_tolerance():
    lv, cnt = F.merge_levels(np.array([100.6, 100.0, 100.4, 100.2]), 0.25)
    assert np.round(lv, 3).tolist() == [100.1, 100.5] and cnt.tolist() == [2, 2]
    assert len(F.merge_levels(np.array([]), 1.0)[0]) == 0 and len(F.merge_levels(np.array([1.0]), 0.0)[0]) == 0


def test_library_levels_use_only_confirmed_swings():
    b = pd.DataFrame({"high": H, "low": LO})
    out = library.sr_levels(b, np.ones(len(H)), 100)
    assert len(out[7][0]) == 0  # the 110 peak (bar 5) is known 3 bars later, at bar 8
    assert out[8][0].tolist() == [110.0]
    assert out[12][0].tolist() == [90.0, 110.0]  # the 90 trough (bar 9) known at 12; 110.1 (bar 12) not yet
    lv, cnt = out[15]
    assert np.round(lv, 3).tolist() == [90.0, 110.05] and cnt.tolist() == [1, 2]  # 110 and 110.1 within 0.25
    lv5, _ = library.sr_levels(b, np.ones(len(H)), 5)[15]
    assert lv5.tolist() == [110.1]  # only the swings of the last 5 bars


def test_where_price_sits_against_the_levels():
    levels = [(np.array([90.0, 110.05]), np.array([1, 2]))]
    one = np.array([0])
    loc, imp = library.sr_codes(levels, one, np.array([109.9]), np.array([100.0]), np.array([1.0]))
    assert (loc[0], imp[0]) == (2, 2)  # 0.15 under a 2-swing level: at resistance
    loc, _ = library.sr_codes(levels, one, np.array([110.3]), np.array([100.0]), np.array([1.0]))
    assert loc[0] == 3  # crossed it since the close three bars back: broke up
    loc, imp = library.sr_codes(levels, one, np.array([90.2]), np.array([95.0]), np.array([1.0]))
    assert (loc[0], imp[0]) == (1, 1)  # just above a 1-swing level: at support
    loc, _ = library.sr_codes(levels, one, np.array([95.0]), np.array([100.0]), np.array([1.0]))
    assert loc[0] == 0  # between levels
    loc, _ = library.sr_codes(levels, one, np.array([89.0]), np.array([95.0]), np.array([1.0]))
    assert loc[0] == 4  # crossed 90 downwards: broke down


# ---------------------------------------------------------------- the run catalogue and the labels
def synthetic_m1(path_close: np.ndarray, start="2026-01-05 00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(path_close), freq="1min", tz="UTC")
    c = np.asarray(path_close, float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.1, "low": np.minimum(o, c) - 0.1, "close": c,
                         "tick_volume": 1.0, "spread": 20.0}, index=idx)


def test_the_catalogue_finds_a_clean_ten_unit_run_and_its_start():
    # flat at 4100 (lows 4099.9), then +1.0 a minute for 15 minutes from bar 30, whose low dips to 4099.5: an up-run
    # of 10 U (U = price / 4100 = 1 USD here) starting at the extreme, bar 30 (notes.md: "its start the extreme")
    c = np.r_[np.full(30, 4100.0), 4100.0 + np.arange(1, 16), np.full(30, 4115.0)]
    m = synthetic_m1(c)
    m.iloc[30, m.columns.get_loc("low")] = 4099.5
    C = plib.catalogue(m, 10)
    up = C[C.side == 1]
    assert len(up) == 1 and int(up.i.iloc[0]) == 30  # bars 25 .. 29 would reach 10 U too, but bar 30 breaks them
    assert up.start_px.iloc[0] == pytest.approx(4099.5)
    # 4099.5 + 10.0 is first reached by the high of bar 39 (close 4110 + 0.1 = 4110.1; bar 38 only 4109.1): 10 minutes
    assert int(up.mins_to_x.iloc[0]) == 10
    assert len(C[C.side == -1]) == 0


def test_equal_lows_start_at_the_earliest_bar():
    # the same climb from a flat base with no dip: bars 25 .. 30 share the low 4099.9; the earliest one from which
    # 10 U is reached within 15 minutes (bar 25: its bar 39 is 14 minutes later) is the start
    c = np.r_[np.full(30, 4100.0), 4100.0 + np.arange(1, 16), np.full(30, 4115.0)]
    C = plib.catalogue(synthetic_m1(c), 10)
    assert C[C.side == 1].i.tolist() == [25]


def test_a_broken_start_is_no_run():
    # the same climb, but a dip below the start low at bar 33 before 10 U: the start at bar 30 does not qualify
    c = np.r_[np.full(30, 4100.0), 4101.0, 4102.0, 4103.0, 4099.0, 4100.0 + np.arange(1, 12), np.full(20, 4111.0)]
    m = synthetic_m1(c)
    C = plib.catalogue(m, 10)
    assert not (C.i == 30).any()


def test_the_window_is_minutes_not_bars():
    # the equal-lows climb with minute 35 missing from the data: from minute 24 the bar that reaches 10 U (minute 39)
    # is only 14 bars later but 15 minutes later - outside the window; the start is minute 25
    c = np.r_[np.full(30, 4100.0), 4100.0 + np.arange(1, 16), np.full(30, 4115.0)]
    m = synthetic_m1(c).drop(index=pd.Timestamp("2026-01-05 00:35", tz="UTC"))
    C = plib.catalogue(m, 10)
    assert C[C.side == 1].t.tolist() == [pd.Timestamp("2026-01-05 00:25", tz="UTC")]


def labelled(c: np.ndarray, snap_bar: int = 50, low_at: dict | None = None, high_at: dict | None = None):
    """One snap at the close of `snap_bar` on a synthetic series; its outcome columns (snaps.labels)."""
    import snaps  # noqa: PLC0415

    m = synthetic_m1(c)
    for i, v in (low_at or {}).items():
        m.iloc[i, m.columns.get_loc("low")] = v
    for i, v in (high_at or {}).items():
        m.iloc[i, m.columns.get_loc("high")] = v
    S = pd.DataFrame({"S": [m.index[snap_bar] + pd.Timedelta(minutes=1)], "idx": [snap_bar]})
    cats = {10: plib.catalogue(m, 10), 5: plib.catalogue(m, 5)}
    return snaps.labels(m, S, cats).iloc[0]


BASE = 4100.0


def test_label_ran_up():
    # flat to bar 55 (its low dips to 4099.5), then +1 a minute for 15 bars: a 10 U up-run starting at bar 55,
    # 4 minutes after the snap (the snap second is bar 51's open)
    c = np.r_[np.full(56, BASE), BASE + 1 + np.arange(15), np.full(50, BASE + 15)]
    r = labelled(c, low_at={55: 4099.5})
    assert r.cls == "ran_up"
    assert r.r10_up_lead == 4 and r.r10_up_mae == pytest.approx(0.5)  # 0.5 U against the snap close first
    assert r.r10_up_size == pytest.approx(15.6)  # 4115.1 - 4099.5, followed to the end (no 40 % pullback)
    assert r.mfe_up15 == pytest.approx(10.1)  # bars 51 .. 65: the high of bar 65 is 4110.1
    assert r.first10 == 1 and np.isnan(r.r10_dn_lead)


def test_label_ran_down():
    c = np.r_[np.full(56, BASE), BASE - 1 - np.arange(15), np.full(50, BASE - 15)]
    r = labelled(c, high_at={55: 4100.5})
    assert r.cls == "ran_dn" and r.r10_dn_lead == 4 and r.first10 == -1


def test_label_fake_up():
    # +3.5 in four minutes (3 U out), back below the snap close at bar 60, never 10 U: faked up
    c = np.r_[np.full(51, BASE), BASE + np.array([1.0, 2, 3, 3.5, 3, 2, 1, 0, -1]), np.full(60, BASE - 1)]
    r = labelled(c)
    assert (r.start3, r.cont10) == (1, 0) and r.cls == "fake_up"


def test_label_slow_up():
    # +0.25 a minute: 3 U out at bar 62, 10 U at bar 90 (28 minutes later, within 60), never back: slow up;
    # no 10 U within 15 minutes, so no run
    c = np.r_[np.full(51, BASE), BASE + 0.25 * np.arange(1, 81), np.full(30, BASE + 20)]
    r = labelled(c)
    assert np.isnan(r.r10_up_lead) and (r.start3, r.cont10) == (1, 1) and r.cls == "slow_up"


def test_label_slow_up_after_a_dip_that_stays_above_the_snap():
    # 3 U out at bar 53, back to +0.6 (lows down to +0.5, never the snap close), then +0.5 a minute to 10 U:
    # it continued (not faked), and no 10 U inside 15 minutes: slow up
    c = np.r_[np.full(51, BASE), BASE + np.array([1.0, 2, 3, 3.5, 3, 2, 1, 0.6]), BASE + 0.6 + 0.5 * np.arange(1, 41),
              np.full(30, BASE + 20.6)]
    r = labelled(c)
    assert (r.start3, r.cont10) == (1, 1) and r.cls == "slow_up"


def test_label_flat():
    r = labelled(np.full(200, BASE))
    assert r.start3 == 0 and r.cls == "flat" and r.cls5 == "none"


# ---------------------------------------------------------------- the formation fingerprint and its similarity
def zig_r() -> tuple[dict, int]:
    """Closes through 100 (bar 0) 106 (6) 102 (10) 108 (16) 104 (20) 110 (26) 107 (29), high = low = close, ATR 1:
    with k = 3 the ZigZag confirms every turn 3 points later. Indicators set by hand at bar 29."""
    v = [(0, 100), (6, 106), (10, 102), (16, 108), (20, 104), (26, 110), (29, 107)]
    c = np.interp(np.arange(30), [a for a, _ in v], [b for _, b in v])
    n = len(c)
    R = {k: np.full(n, np.nan) for k in ("rsi", "macd", "sig", "hist", "k", "d", "e20", "e50", "mid", "sd", "width",
                                         "wpct", "pdi", "ndi", "adx")}
    R.update(h=c, lo=c, c=c, atr=np.ones(n))
    R["rsi"][:] = 50.0
    R["rsi"][[16, 26, 29]] = [65.0, 55.0, 60.0]  # peaks 108 -> 110 higher, RSI 65 -> 55 lower: bearish divergence
    R["macd"][26:30] = [0.6, 0.7, 0.7, 0.5]
    R["sig"][26:30] = [0.8, 0.8, 0.6, 0.4]  # MACD minus signal: -, -, +, +  -> crossed up
    R["hist"] = R["macd"]
    R["k"][29], R["d"][29] = 85.0, 80.0
    R["e20"][26], R["e20"][29], R["e50"][29] = 105.0, 106.0, 105.0
    R["mid"][29], R["sd"][29], R["wpct"][29] = 106.0, 0.4, 0.1
    R["adx"][28:30], R["pdi"][29], R["ndi"][29] = [24.0, 25.0], 30.0, 20.0
    return R, 29


def test_zigzag_turns_are_confirmed_three_points_later():
    import fingerprint as fp  # noqa: PLC0415

    R, _ = zig_r()
    pidx, pval, ptyp, pconf = fp.zigzag(R["h"], R["lo"], R["atr"], 3.0)
    assert pidx.tolist() == [0, 6, 10, 16, 20, 26] and pval.tolist() == [100, 106, 102, 108, 104, 110]
    assert ptyp.tolist() == [-1, 1, -1, 1, -1, 1] and pconf.tolist() == [3, 9, 13, 19, 23, 29]


def test_fingerprint_attributes_by_hand():
    import fingerprint as fp  # noqa: PLC0415

    R, b = zig_r()
    f = fp.fingerprint(R, np.array([b])).iloc[0].to_dict()
    want = dict(
        npiv=2,  # six swings visible: 6 is in [6, 10)
        leg=0,  # the last swing is a peak: falling from it
        pk1=2, pk2=2, tr1=2, tr2=2,  # 110 > 108 > 106, 104 > 102 > 100 (beyond 0.25 ATR)
        legr=1,  # the current leg 110 -> 107 = 3 is 0.5 of the last 104 -> 110 = 6 (0.5 .. 1)
        legr2=2,  # 6 against the one before, 108 -> 104 = 4: 1.5 (> 1)
        where=3,  # 107 in the middle third between the trough 104 and the peak 110
        net=4,  # +7 ATR since bar 0 (> 6)
        rsi=3, rsi_up=1,  # 60 is in [55, 70); above its value three bars back (55)
        div=1,  # bearish divergence
        macd_h=2,  # above 0, lower than the bar before (0.7)
        macd0=1, macd_x=1,  # above 0; crossed above the signal inside the last four bars
        stoch=5,  # 85 above 80 (2 x 2) and above %D (+1)
        ema=1,  # close > EMA20 > EMA50 (stack 0), EMA20 rising over three bars (+1)
        bb=9,  # above the upper band (3 x 3), width in its lowest fifth (0)
        adx=1,  # ADX 25 >= 20, +DI leads, rising
    )
    assert f == want
    # one bar earlier the 110 peak is not confirmed yet: the last peak is 108 (bar 16), the last trough 104 (bar 20),
    # and the close 108 sits in the upper third
    assert int(fp.fingerprint(R, np.array([28])).iloc[0]["where"]) == 2


def test_similarity_is_the_share_of_equal_attributes():
    import cluster_fp  # noqa: PLC0415

    rows = np.array([[0, 1, 3, 0],
                     [1, 1, 3, 0],  # equal to row 0 in attributes 2, 3, 4: 0.75
                     [2, 0, 3, 1],  # equal to rows 0 and 1 only in attribute 3: 0.25
                     [0, 1, 0, 1]])  # equal to row 0 in attributes 1, 2: 0.5; to row 2 in attribute 4: 0.25
    V = cluster_fp.onehot([rows[:, j] for j in range(4)])
    assert V[0] @ V[0] == pytest.approx(1.0)
    assert V[0] @ V[1] == pytest.approx(0.75) and V[0] @ V[3] == pytest.approx(0.5)
    assert V[0] @ V[2] == pytest.approx(0.25) and V[1] @ V[2] == pytest.approx(0.25) and V[2] @ V[3] == pytest.approx(0.25)
    assert cluster_fp.leaders(V, 0.75).tolist() == [0, 0, 1, 2]  # row 1 joins row 0's set at 0.75; rows 2, 3 start sets
    assert cluster_fp.leaders(V, 0.8).tolist() == [0, 1, 2, 3]  # at 0.8 nothing joins


# ---------------------------------------------------------------- the wiring between the parts
def test_snap_times_follow_each_zone_through_dst():
    import snaps  # noqa: PLC0415

    m = plib.load()
    m = m[(m.index >= "2026-01-14") & (m.index < "2026-07-17")]
    S = snaps.snap_times(m)
    names = dict(zip(S.S, S.name))

    def at(x: str) -> str:
        return names.get(pd.Timestamp(x, tz="UTC"), "")

    # New York 09:30: 14:30 UTC in winter (EST), 13:30 UTC in summer (EDT) = 21:30 / 20:30 Thai
    assert "NY0930" in at("2026-01-15 14:30") and "NY0930" in at("2026-07-15 13:30")
    # Frankfurt 08:00: 07:00 UTC in winter, 06:00 in summer; London 08:00: 08:00 / 07:00 UTC; Thai 07:00 = 00:00 UTC
    assert "FR0800" in at("2026-01-15 07:00") and "FR0800" in at("2026-07-15 06:00")
    assert "LO0800" in at("2026-01-15 08:00") and "LO0800" in at("2026-07-15 07:00")
    assert "TH0700" in at("2026-07-15 00:00")
    # one second, two names: 2026-03-08 .. 03-28 New York is already on summer time, London not yet - London 12:00 and
    # New York 08:00 are both 12:00 UTC; the snap carries both
    assert set(at("2026-03-10 12:00").split("+")) == {"LO1200", "NY0800"}
    # the snap's bar is the last M1 bar before the snap second
    r = S[S.S == pd.Timestamp("2026-07-15 13:30", tz="UTC")].iloc[0]
    assert m.index[r.idx] == pd.Timestamp("2026-07-15 13:29", tz="UTC")
    # weekdays of the zone only: no snap on a Saturday or Sunday in its own zone
    assert not any(pd.Timestamp(t).tz_convert("America/New_York").dayofweek >= 5 for t, n in zip(S.S, S.name)
                   if n.startswith("NY"))


def test_raw_feeds_each_column_its_indicator():
    import fingerprint as fp  # noqa: PLC0415

    m = plib.load()
    b = plib.tf_bars(m[(m.index >= "2026-03-02") & (m.index < "2026-03-20")], "15min")
    h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
    R = fp.raw(b)
    line, sig = F.macd(c)
    k, d = F.stochastic(h, lo, c, 14, 3, 3)
    pdi, ndi, adx = F.adx(h, lo, c, 14)
    mid, up, _ = F.bands(c, 20, 2.0)
    want = dict(h=h, lo=lo, c=c, atr=F.atr(h, lo, c, 14), rsi=F.rsi(c, 14), macd=line, hist=line, sig=sig, k=k, d=d,
                e20=F.ema(c, 20), e50=F.ema(c, 50), mid=mid, sd=(up - mid) / 2, pdi=pdi, ndi=ndi, adx=adx)
    for key, v in want.items():
        np.testing.assert_array_equal(R[key], v, err_msg=key)


def test_core_attributes_of_a_timeframe():
    import cluster_fp  # noqa: PLC0415

    cols = ["npiv", "leg", "pk1", "tr1", "where", "rsi_up", "macd_h", "ema"]
    vals = ([1] * 6, [0] * 6, [2] * 6, [0] * 6, [0, 1, 2, 3, 4, 5], [1] * 6, [3] * 6, [0, 1, 2, 3, 4, 5])
    Fx = pd.DataFrame({f"M5_fp_{c}": v for c, v in zip(cols, vals)})
    got = cluster_fp.core_cols(Fx, "M5")
    assert [g.tolist() for g in got] == [[1] * 6, [0] * 6, [2] * 6, [0] * 6,
                                         [0, 1, 2, 2, 3, 4],  # above the peak, below the trough, upper half x2, lower, none
                                         [1] * 6, [3] * 6,
                                         [0, 0, 1, 1, 2, 2]]  # the EMA stack without its slope


def test_the_evidence_word():
    from evidence_journal import evidence_label  # noqa: PLC0415

    def row(**kw):
        base = {f"{L}_{k}": v for L in ("ctx", "set", "trg") for k, v in (("days", 0), ("with", np.nan), ("against", np.nan))}
        base.update(kw)
        return base

    out = pd.DataFrame([
        row(),  # no layer seen on 5 days
        row(trg_days=5, trg_with=0.3, trg_against=0.2),  # +0.1: supports (the boundary)
        row(trg_days=5, trg_with=0.2, trg_against=0.3, set_days=4, set_with=0.9, set_against=0.0),  # set ignored: against
        row(trg_days=9, trg_with=0.30, trg_against=0.25, ctx_days=7, ctx_with=0.2, ctx_against=0.2),  # +0.05: mixed
        row(trg_days=9, trg_with=0.5, trg_against=0.1, ctx_days=7, ctx_with=0.1, ctx_against=0.6),  # +0.4 -0.5: against
    ])
    assert evidence_label(out, "days").tolist() == ["none", "supports", "against", "mixed", "against"]


def test_ny_trades_are_the_new_york_windows():
    t = pd.DatetimeIndex(["2026-07-15 13:30", "2026-01-15 14:30", "2026-07-15 17:59", "2026-07-15 18:05",
                          "2026-07-15 08:00", "2026-07-18 13:30"], tz="UTC")
    # 09:30 EDT, 09:30 EST, 13:59 EDT (the last minute of 11:00-14:00), 14:05 EDT (after), London 09:00, a Saturday
    assert plib.ny_mask(t).tolist() == [True, True, True, False, False, False]


def test_a_trade_is_known_at_the_end_of_its_exit_bar():
    import wf  # noqa: PLC0415

    ot = pd.date_range("2026-05-31 23:57", periods=4, freq="1min", tz="UTC")
    # a stop hit inside the 23:59 bar is known at 00:00 on June 1 - in time for June's choice, not earlier
    assert wf.exit_time(ot, np.array([2])).tolist() == [pd.Timestamp("2026-06-01 00:00", tz="UTC")]


def test_the_picture_shows_the_bars_the_bot_had():
    import lvl_losers  # noqa: PLC0415

    m = plib.load()
    t_dec = pd.Timestamp("2026-03-09 02:30", tz="UTC")  # 09:30 Thai, the owner's March 9 case
    sl_ = m[(m.index >= t_dec - pd.Timedelta(days=14)) & (m.index <= t_dec + pd.Timedelta(hours=3))]
    b, start_t, done, future = lvl_losers.picture_bars(sl_, t_dec, "1h", None, pd.Timedelta(0))
    full = plib.tf_bars(m[(m.index >= "2026-02-01") & (m.index < "2026-03-12")], "1h")
    full = full[full["avail"] <= t_dec].tail(120).reset_index(drop=True)
    assert len(b) == 120 and (done <= t_dec).all() and not future.any()
    np.testing.assert_array_equal(b[["open", "high", "low", "close"]].to_numpy(),
                                  full[["open", "high", "low", "close"]].to_numpy())
    assert start_t.iloc[-1] == pd.Timestamp("2026-03-09 08:00", tz="Asia/Bangkok")  # the 01:00 UTC bar, closed at 02:00
    b5, _, done5, future5 = lvl_losers.picture_bars(sl_, t_dec, "5min", pd.Timedelta(hours=9), pd.Timedelta(hours=2))
    seen = ~future5
    assert (seen == np.asarray(done5 <= t_dec)).all()
    assert pd.DatetimeIndex(b5["last"])[seen].max() == pd.Timestamp("2026-03-09 02:29", tz="UTC")  # nothing after
    assert pd.DatetimeIndex(b5["last"])[~seen].min() > t_dec  # the rest is drawn grey (the future)
    # two minutes into an M5 bar: that bar is still forming - grey, though it completes three minutes later
    t2 = t_dec + pd.Timedelta(minutes=2)
    b5, _, _, future5 = lvl_losers.picture_bars(sl_, t2, "5min", pd.Timedelta(hours=9), pd.Timedelta(hours=2))
    assert pd.DatetimeIndex(b5["last"])[~future5].max() == pd.Timestamp("2026-03-09 02:29", tz="UTC")
