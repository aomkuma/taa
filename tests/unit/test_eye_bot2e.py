"""Tests for eye/bot2e.py: mode 2e (eye/BOT_SPEC.md section 10) and the fib path (eye/BOT_RULES.md).

The step logic is tested on constructed pivots (``analyse_view``), where every number is chosen; the
no-look-ahead, mirror, window and ledger tests run on the stored gold bars of 2026-04-06 and skip when the
data is not on the machine.
"""

from __future__ import annotations

import csv
import importlib
import re
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.indicators.price_action import Swing, SwingKind  # noqa: E402

bot = importlib.import_module("eye.bot2e")
money = importlib.import_module("eye.money")
score_mod = importlib.import_module("eye.score")

TH = "Asia/Bangkok"
DATA = ROOT / "data/history/FBS-Demo/XAUUSD"
needs_data = pytest.mark.skipif(not (DATA / "M5.parquet").exists(), reason="stored gold bars not present")
P = bot.Params(mode="2e")
BOTH = bot.Params(mode="2e", min_r=0.0, div_mode="both")  # the earlier rule: divergence on both oscillators
P0 = bot.Params(
    mode="2e", min_r=0.0
)  # tests of the steps drop the 2R floor; test_reward_floor tests the floor itself


def now_at(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz=TH).tz_convert("UTC")


@pytest.fixture(scope="module")
def full() -> dict[str, pd.DataFrame]:
    return bot.load_frames()


# --- constructed pivots -------------------------------------------------------------------------------------

GAP = 10  # bars between pivots


def build(
    lows: list[float],
    *,
    macd_div: bool = True,
    rsi_div: bool = True,
    higher_low: bool = True,
    tail: float = 0.0,
    highs_between: list[float] | None = None,
    x: float = 4685.0,
    l_hl: float = 4625.0,
):
    """A BUY in the view: start high 4700, then ``lows`` (the last is L*, the lowest), a high X above the
    high before L* (the break), and - if ``higher_low`` - the higher low ``l_hl`` the dip to which began at
    X. ``tail`` is added to the last bars (a close above X when large)."""
    highs = highs_between or [4690.0 - 5 * i for i in range(len(lows) - 1)]
    pts: list[tuple[bool, float]] = [(False, 4700.0)]
    for i, lo in enumerate(lows):
        pts.append((True, lo))
        if i < len(lows) - 1:
            pts.append((False, highs[i]))
    pts.append((False, x))
    if higher_low:
        pts.append((True, l_hl))
    pos = [GAP * (i + 1) for i in range(len(pts))]
    n = pos[-1] + 6
    path = np.interp(np.arange(n), pos, [p for _, p in pts])
    path[pos[-1] + 1 :] += np.linspace(0, tail, n - pos[-1] - 1) if tail else 0.0
    # oscillators: only the values at the pivots matter; L* against the low before it
    low_pos = [p for (is_low, _), p in zip(pts, pos, strict=True) if is_low]
    macd = np.full(n, -5.0)
    rsi = np.full(n, 40.0)
    lstar_i = len(lows) - 1
    macd[low_pos[lstar_i]] = -4.0 if macd_div else -9.0
    rsi[low_pos[lstar_i]] = 45.0 if rsi_div else 35.0
    if lstar_i >= 1:
        macd[low_pos[lstar_i - 1]] = -6.0
        rsi[low_pos[lstar_i - 1]] = 40.0
    pv = [bot.VPivot(is_low, price, p) for (is_low, price), p in zip(pts, pos, strict=True)]
    return pv, path + 0.1, path - 0.1, path, macd, rsi


# One support zone holds every low (4590-4665); X = 4685 is the entry; the resistance band starts at 4800.
NARROW = [(4590.0, 4665.0), (4800.0, 4810.0)]


def run(lows: list[float], bands=NARROW, params=P0, **kw):
    pv, hi, lo, close, macd, rsi = build(lows, **kw)
    return bot.analyse_view(pv, hi, lo, close, macd, rsi, bands, "M5", params)


def test_count_and_divergence() -> None:
    """Step 2: 2, 3, 5 and 6 lows, with and without divergence on each oscillator."""
    two = [4650.0, 4600.0]
    mid = [4670.0]
    three = [4640.0, 4620.0, 4600.0]
    five = [4660.0, 4650.0, 4640.0, 4620.0, 4600.0]
    six = [4670.0, *five]
    assert run([4600.0]).reason == "step2: count outside 3-5 and no M"  # one zone low
    assert (
        run(two, macd_div=False, rsi_div=False, highs_between=mid).reason == "order written"
    )  # exactly two: the M
    for lows in (three, five):
        assert run(lows).reason == "order written"
        assert run(lows, macd_div=False).reason == "order written"  # one oscillator is enough (R11)
        assert run(lows, rsi_div=False).reason == "order written"
        assert run(lows, macd_div=False, rsi_div=False).reason == "step2: no divergence"
        assert run(lows, macd_div=False, params=BOTH).reason == "step2: no divergence"
    assert run(six, bands=[(4590.0, 4680.0), (4800.0, 4810.0)]).reason == "step2: count outside 3-5 and no M"


def test_m_needs_no_divergence_and_one_zone() -> None:
    """R10: exactly two zone lows hold without divergence; two lows in different bands count one each."""
    one_band = [(4595.0, 4605.0), (4800.0, 4810.0)]
    two_bands = [(4640.0, 4660.0), (4595.0, 4605.0), (4800.0, 4810.0)]
    ok = run([4601.0, 4600.0], bands=one_band, macd_div=False, rsi_div=False, highs_between=[4670.0])
    assert ok.reason == "order written" and ok.setup is not None and ok.setup.kind == "M"
    assert not (ok.setup.div_macd or ok.setup.div_rsi)
    out = run([4650.0, 4600.0], bands=two_bands, macd_div=False, rsi_div=False, highs_between=[4670.0])
    assert out.reason == "step2: count outside 3-5 and no M" and out.info["count"] == "1"
    assert run([4601.0, 4600.0], bands=[(4700.0, 4710.0)]).reason == "step2: L* not in a support band"


def test_three_zone_lows_need_divergence() -> None:
    """R3: three zone lows without divergence are not an M, whatever band they share."""
    out = run([4640.0, 4620.0, 4600.0], macd_div=False, rsi_div=False)
    assert out.reason == "step2: no divergence" and out.setup is None


def test_zone_resets_on_a_close_below() -> None:
    """R10: a close under the band's lower edge ends the zone; lows before it do not count."""
    pv, hi, lo, close, macd, rsi = build([4640.0, 4620.0, 4600.0])
    close[pv[1].pos + 2] = 4580.0  # after the first low (4640), under the band edge 4590
    out = bot.analyse_view(pv, hi, lo, close, macd, rsi, NARROW, "M5", P0)
    assert out.info["count"] == "2"  # 4620 and 4600 only


def test_nearest_centre_band_is_used() -> None:
    """R1: of several bands holding L*, the one whose centre is nearest is the support."""
    bands = [(4590.0, 4606.0), (4597.0, 4603.0), (4800.0, 4810.0)]
    out = run([4602.0, 4601.0, 4600.0], bands=bands)
    assert out.setup is not None and out.setup.band == (4597.0, 4603.0)
    assert out.setup.stop_v == 4597.0 - P.stop_buffer


def test_reward_floor() -> None:
    """R9: R under min_r (2.0) writes nothing; with min_r 0 the same setup is written."""
    near = [(4590.0, 4665.0), (4700.0, 4710.0)]  # target 4699.5, entry 4685, stop 4589.5
    out = run([4640.0, 4620.0, 4600.0], bands=near, params=P)
    assert out.reason == "reward under 2R" and out.setup is None
    assert out.info["step5"].endswith("R 0.15")
    assert run([4640.0, 4620.0, 4600.0], bands=near).setup is not None
    assert bot.Params().min_r == 2.0
    wide = [(4590.0, 4665.0), (5000.0, 5010.0)]  # R about 3
    assert run([4640.0, 4620.0, 4600.0], bands=wide, params=P).setup is not None


def test_steps_3_to_7_formulas() -> None:
    """The order exists only once the higher low is fixed; trigger / limit / stop / target follow section 5."""
    lows = [4640.0, 4620.0, 4600.0]
    before = run(lows, higher_low=False)
    assert before.setup is None and before.reason == "step3: no higher low yet"

    out = run(lows)
    s = out.setup
    assert s is not None
    assert s.entry_v == 4685.0  # H_d
    assert s.trigger_v == 4685.0 + P.trigger_offset  # the stop limit's trigger, a little over
    assert s.stop_v == 4590.0 - P.stop_buffer  # the band's lower edge, below L*
    assert s.target_v == 4800.0 - P.target_buffer  # before the resistance band's lower edge
    assert s.r == pytest.approx((s.target_v - s.entry_v - P.spread) / (s.entry_v - s.stop_v))
    assert s.lhl.price == 4625.0 and s.hd.price == 4685.0

    # a bar has already closed above H_d and price is still above it: a plain limit, no trigger
    plain = run(lows, tail=70.0)
    assert plain.setup is not None and plain.setup.trigger_v is None
    # closed above earlier but back under H_d now: a plain limit would be a stop on the break, so a stop limit
    pv, hi, lo, close, macd, rsi = build(lows)
    close[-4] = 4700.0
    back = bot.analyse_view(pv, hi, lo, close, macd, rsi, NARROW, "M5", P0)
    assert back.setup is not None and back.setup.trigger_v == 4685.0 + P.trigger_offset
    # price below the higher low: void
    assert run(lows, l_hl=4625.0, tail=-30.0).reason == "step5: price below the higher low"
    # no resistance band above the entry: no trade
    assert run(lows, bands=[(4590.0, 4665.0)]).reason == "step7: no target level"


def test_mirror_of_pivots_is_a_sell() -> None:
    """to_view turns a SELL's highs into lows with negated prices."""
    sw = [
        Swing(SwingKind.HIGH, 100.0, 5, 8, 5, 8),
        Swing(SwingKind.LOW, 90.0, 12, 15, 12, 15),
    ]
    assert bot.to_view(sw, 1) == [bot.VPivot(False, 100.0, 5), bot.VPivot(True, 90.0, 12)]
    assert bot.to_view(sw, -1) == [bot.VPivot(True, -100.0, 5), bot.VPivot(False, -90.0, 12)]


# --- H1 modes ------------------------------------------------------------------------------------------------


def swings(highs: tuple[float, float], lows: tuple[float, float]) -> list[Swing]:
    seq = [
        (SwingKind.LOW, lows[0]),
        (SwingKind.HIGH, highs[0]),
        (SwingKind.LOW, lows[1]),
        (SwingKind.HIGH, highs[1]),
    ]
    return [Swing(k, v, i * 10, i * 10 + 3, i * 10, i * 10 + 3) for i, (k, v) in enumerate(seq)]


def test_h1_modes() -> None:
    up = swings((110, 120), (90, 100))
    down = swings((120, 110), (100, 90))
    mixed = swings((120, 110), (90, 100))  # lower high, higher low
    for mode in ("strict", "lows"):
        assert bot.h1_side(up, 105.0, mode) == "BUY"
        assert bot.h1_side(down, 95.0, mode) == "SELL"
    assert bot.h1_side(mixed, 105.0, "strict") is None
    # lows mode: a higher last low with price above it is up ... unless the highs also say down (both = none)
    higher_low_only = swings((110, 120), (100, 100.0001))
    assert bot.h1_side(higher_low_only, 130.0, "lows") == "BUY"
    assert bot.h1_side(higher_low_only, 99.0, "lows") is None  # price under the last low
    lower_high_only = swings((120, 110), (100, 100.0))
    assert bot.h1_side(lower_high_only, 105.0, "lows") == "SELL"
    assert bot.h1_side(lower_high_only, 115.0, "lows") is None  # price over the last high
    # last low higher AND last high lower, price between them: up and down both hold, so none
    assert bot.h1_side(mixed, 105.0, "lows") is None
    assert bot.h1_side([], 100.0, "strict") is None
    with pytest.raises(ValueError):
        bot.h1_side(up, 100.0, "other")


def test_level_bands_stay_separate() -> None:
    """Revision 1, R1: bands are never merged - each price keeps its own band, centre the price."""
    assert bot.level_bands([110.0, 100.0, 101.0], 1.0) == [(99.0, 101.0), (100.0, 102.0), (109.0, 111.0)]


# --- windows, pending, look-ahead ----------------------------------------------------------------------------


def test_window_edges() -> None:
    """R7: a window opens at its start and includes its end close."""
    for day, name, first, last in (
        ("2026-04-06", "Asia", "07:00", "09:00"),
        ("2026-04-06", "London", "13:00", "15:00"),
        ("2026-04-06", "New York", "19:30", "23:00"),
    ):
        before = pd.Timestamp(f"{day} {first}", tz=TH) - pd.Timedelta(minutes=5)
        after = pd.Timestamp(f"{day} {last}", tz=TH) + pd.Timedelta(minutes=5)
        assert bot.window_of(before.tz_convert("UTC")) == ""
        assert bot.window_of(now_at(f"{day} {first}")) == name
        assert bot.window_of(now_at(f"{day} {last}")) == name
        assert bot.window_of(after.tz_convert("UTC")) == ""


def test_played_out_setup_is_not_written() -> None:
    """R8: a touch of the target, or of the stop, after the higher low writes nothing."""
    lows = [4640.0, 4620.0, 4600.0]
    assert run(lows).reason == "order written"
    for col, at in ((0, 4800.0), (1, 4585.0)):
        pv, hi, lo, close, macd, rsi = build(lows)
        (hi, lo)[col][-2] = at
        out = bot.analyse_view(pv, hi, lo, close, macd, rsi, NARROW, "M5", P0)
        assert out.setup is None and out.reason == "setup already played out"


@needs_data
def test_outside_window_and_pending(full) -> None:
    outside = now_at("2026-04-06 11:00")
    res = bot.decide(bot.cut(full, outside), outside, P0)
    assert res.decision is None and res.log["reason"] == "outside window"
    inside = now_at("2026-04-06 21:20")  # the 04-06 New York decision
    free = bot.decide(bot.cut(full, inside), inside, P0)
    assert free.decision is not None  # the bar the walk writes its order at
    held = bot.decide(bot.cut(full, inside), inside, P0, pending=True)
    assert held.decision is None and held.log["reason"] == "order pending"
    again = bot.decide(bot.cut(full, inside), inside, P0, used=frozenset({free.key}))
    assert again.decision is None and again.log["reason"] == "setup already used"


@needs_data
def test_one_order_at_a_time_in_the_walk(full) -> None:
    """A live earlier order (filled, never resolved) stops every new decision, in every window."""
    seen = float(full["M5"].open[now_at("2026-04-02 13:05")])  # a limit at the market fills on the next bar
    live = {c: "" for c in bot.LEDGER_COLUMNS}
    live.update(
        id="B-20260402-1", cutoff_thai="2026-04-02 07:00", decided_at="02/04 13:00", side="BUY",
        entry=f"{seen:.2f}", stop="1", target="99998",
    )  # fmt: skip
    mine, logs = bot.walk_days(["2026-04-06"], P, full, [live])
    assert mine == []
    in_window = [r for r in logs if r["window"] and r["reason"] != "market closed"]
    assert in_window and {r["reason"] for r in in_window} == {"order pending"}


@needs_data
def test_no_lookahead(full) -> None:
    """Decisions with every bar after ``now`` replaced by noise equal those on the real data."""
    rng = np.random.default_rng(7)
    for text in ("2026-04-06 07:05", "2026-04-06 13:05", "2026-04-06 21:20", "2026-04-06 20:00"):
        now = now_at(text)
        noisy = {}
        for tf, df in full.items():
            df = df.copy()
            late = np.asarray(df.index + bot.STEP[tf] > now)
            n = int(late.sum())
            base = rng.normal(4600, 80, n)
            df.loc[late, "open"] = base
            df.loc[late, "close"] = base + rng.normal(0, 5, n)
            df.loc[late, "high"] = base + 60
            df.loc[late, "low"] = base - 60
            noisy[tf] = df
        a = bot.decide(bot.cut(full, now), now, P0)
        b = bot.decide(bot.cut(noisy, now), now, P0)
        assert a.log == b.log and a.decision == b.decision and a.key == b.key
    # an uncut frame is refused
    now = now_at("2026-04-06 13:05")
    with pytest.raises(ValueError):
        bot.decide({tf: df.loc[: now + pd.Timedelta(hours=1)] for tf, df in full.items()}, now, P)


@needs_data
def test_cut_guard_checks_every_bar(full) -> None:
    """Revision 1, R4: a future bar anywhere in a frame is refused, not only a last one."""
    now = now_at("2026-04-06 13:05")
    ok = bot.cut(full, now)
    bot.decide(ok, now, P)  # a clean cut passes
    m5 = ok["M5"]
    future = full["M5"].loc[[now + pd.Timedelta(hours=1)]]
    inside = pd.concat([m5.iloc[:-1], future, m5.iloc[-1:]])
    with pytest.raises(ValueError, match="not sorted"):
        bot.decide({**ok, "M5": inside}, now, P)
    # sorted, but a future bar in the middle: give the middle bar a future time and re-sort positions
    odd = m5.copy()
    odd.index = odd.index.to_series().where(
        odd.index != odd.index[-3], odd.index[-1] + pd.Timedelta(minutes=1)
    )
    odd = odd.sort_index()
    odd.index = odd.index[:-1].append(pd.DatetimeIndex([odd.index[-1] + pd.Timedelta(hours=1)]))
    with pytest.raises(ValueError, match="had not closed"):
        bot.decide({**ok, "M5": odd}, now, P)


@needs_data
def test_cut_keeps_closed_bars_only(full) -> None:
    now = now_at("2026-04-06 13:05")
    for tf, df in bot.cut(full, now).items():
        assert df.index[-1] + bot.STEP[tf] <= now
        nxt = full[tf].index[full[tf].index.get_loc(df.index[-1]) + 1]
        assert nxt + bot.STEP[tf] > now


@needs_data
def test_mirror(full) -> None:
    """The price-negated series gives the mirrored answer at every bar of a window, and mirrored prices."""
    k = 10000.0

    def mirror(df: pd.DataFrame) -> pd.DataFrame:
        m = df.copy()
        m["open"], m["close"] = (k - df.open).round(2), (k - df.close).round(2)
        m["high"], m["low"] = (k - df.low).round(2), (k - df.high).round(2)
        return m

    mirrored = {tf: mirror(df) for tf, df in full.items()}
    flip = {"BUY": "SELL", "SELL": "BUY", "": ""}
    start = now_at("2026-04-06 21:00")
    seen_decision = False
    for i in range(1, 26):
        now = start + pd.Timedelta(minutes=5 * i)
        a = bot.decide(bot.cut(full, now), now, P0)
        b = bot.decide(bot.cut(mirrored, now), now, P0)
        assert a.log["reason"] == b.log["reason"], now
        assert flip[a.log["side"]] == b.log["side"]
        if a.decision is not None:
            seen_decision = True
            assert b.decision is not None
            assert flip[a.decision["side"]] == b.decision["side"]
            for col in ("entry", "stop", "target", "trigger"):
                if a.decision[col]:
                    assert float(b.decision[col]) == pytest.approx(k - float(a.decision[col]), abs=0.011)
    assert seen_decision


# --- the ledger -------------------------------------------------------------------------------------------------


@needs_data
def test_ledger_rows_score_and_money_reads_them(full, tmp_path, monkeypatch) -> None:
    ledger, log = tmp_path / "bot_ledger.csv", tmp_path / "bot_log.csv"
    header = next(csv.reader((ROOT / "eye/ledger.csv").open(encoding="utf-8")))
    assert header == bot.LEDGER_COLUMNS

    # another day's row is kept when a range is re-run
    other = {c: "" for c in bot.LEDGER_COLUMNS}
    other.update(id="B-20260401-1", cutoff_thai="2026-04-01 07:00", reader="bot2e", side="WAIT")
    bot._write(ledger, bot.LEDGER_COLUMNS, [other])
    bot.run("2026-04-06", "2026-04-06", P0, ledger, log)
    rows = bot._read(ledger, bot.LEDGER_COLUMNS)
    assert [r["id"] for r in rows] == ["B-20260401-1", "B-20260406-1"]
    mine = rows[1]
    assert mine["reader"] == "bot2e" and mine["rules"] == "?????????" and mine["setup"] == "+++++++"
    assert mine["why"] == "" and mine["trigger"]  # a stop limit, unscored
    for name in ("min_r=", "trigger_offset=", "stop_buffer=", "target_buffer=", "band_frac=", "h1_mode="):
        assert name in mine["structure"]
    bot.run("2026-04-06", "2026-04-06", P0, ledger, log)  # re-running replaces, never duplicates
    assert [r["id"] for r in bot._read(ledger, bot.LEDGER_COLUMNS)] == ["B-20260401-1", "B-20260406-1"]
    dates = [r["date"] for r in bot._read(log, bot.LOG_COLUMNS)]
    assert len(dates) == 93 and set(dates) == {"2026-04-06"}

    scored = score_mod.score(mine, score_mod.bars(), score_mod.start_of(mine, {}))
    assert scored["why"] and "r_net" in scored
    mine.update(scored)
    bot._write(ledger, bot.LEDGER_COLUMNS, [mine])

    monkeypatch.setattr(money, "HERE", tmp_path)
    monkeypatch.setattr(sys, "argv", ["money.py", "--ledger", "bot_ledger.csv"])
    money.main()


@needs_data
def test_w_zone_4141_on_22_oct(full) -> None:
    """R10's case: at 22/10 07:00 Thai the 4141-4142 resistance zone is one zone on M5, holding both 4141.87
    and 4142.23 (the dip to 4104.92 between them no longer splits it). It holds five fixed highs on M5, not
    two, and on M15 the 4142.23 top is not yet a fixed pivot - see the report."""
    now = now_at("2026-10-22 07:00")
    frames = bot.cut(full, now)
    h1 = bot._zigzag(frames["H1"])
    bands = bot.h1_bands(h1, len(frames["H1"]), now, P)
    bands_v = sorted((-b, -a) for a, b in bands)
    seen = {}
    for tf in ("M15", "M5"):
        df = frames[tf]
        piv = bot.to_view(bot._zigzag(df), -1)
        macd = -bot.macd_mt5(df.close)["main"].to_numpy()
        rsi_v = -bot.rsi(df.close, 14).to_numpy() + 100.0
        seen[tf] = bot.analyse_view(
            piv, -df.low.to_numpy(), -df.high.to_numpy(), -df.close.to_numpy(), macd, rsi_v, bands_v, tf, P
        )
    assert "4141.87" in seen["M5"].info["pivots"] and "4142.23" in seen["M5"].info["pivots"]
    assert seen["M5"].info["count"] == "5" and seen["M15"].info["count"] == "1"


# --- research options (eye/BOT_RESEARCH.md) --------------------------------------------------------------------


def test_h1_swings_three() -> None:
    """h1_swings=3: strict needs the last three highs and lows each rising (two consecutive rises)."""

    def zig(highs: list[float], lows: list[float]) -> list[Swing]:
        out: list[Swing] = []
        for i, (lo, hi) in enumerate(zip(lows, highs, strict=True)):
            out += [
                Swing(SwingKind.LOW, lo, i * 20, i * 20 + 3, i * 20, i * 20 + 3),
                Swing(SwingKind.HIGH, hi, i * 20 + 10, i * 20 + 13, i * 20 + 10, i * 20 + 13),
            ]
        return out

    two_rises = zig([100, 110, 120], [90, 95, 100])
    one_rise = zig([120, 110, 120], [100, 95, 100])  # the last pair rises, the one before it fell
    assert bot.h1_side(two_rises, 105.0, "strict", 3) == "BUY"
    assert bot.h1_side(one_rise, 105.0, "strict", 2) == "BUY"
    assert bot.h1_side(one_rise, 105.0, "strict", 3) is None
    assert bot.h1_side(zig([100, 110], [90, 95]), 105.0, "strict", 3) is None  # too few pivots
    with pytest.raises(ValueError):
        bot.h1_side(two_rises, 105.0, "strict", 4)


@needs_data
def test_h1_tf_h4_gives_the_side_from_h4_pivots(full) -> None:
    sides = set()
    for text in tuple(f"2026-10-{d:02d} 13:05" for d in range(12, 24)):
        now = now_at(text)
        frames = bot.cut(full, now)
        want = bot.h1_side(bot._zigzag(frames["H4"]), float(frames["M5"].close.iloc[-1]), "strict")
        got = bot.decide(frames, now, bot.Params(mode="2e", h1_tf="H4")).log["side"]
        assert got == (want or "")
        sides.add(got)
    assert sides - {""}  # at least one of them had a side


@needs_data
def test_entry_tfs_selects_the_timeframes(full) -> None:
    now = now_at("2026-04-06 21:20")
    frames = bot.cut(full, now)
    assert bot.decide(frames, now, P0).log["tf"] == "M5"
    assert bot.decide(frames, now, bot.Params(mode="2e", min_r=0.0, entry_tfs="M5")).log["tf"] == "M5"
    only15 = bot.decide(frames, now, bot.Params(mode="2e", min_r=0.0, entry_tfs="M15"))
    assert only15.log["tf"] == "M15" and only15.decision is None  # M5 wrote it; M15 alone does not


def test_div_mode_one_versus_both() -> None:
    """R11: one oscillator is enough by default; div_mode=both is the earlier, stricter rule."""
    lows = [4640.0, 4620.0, 4600.0]
    assert P0.div_mode == "one" and bot.Params().div_mode == "one"
    for kw in ({"rsi_div": False}, {"macd_div": False}):
        assert run(lows, **kw).reason == "order written"
        assert run(lows, params=BOTH, **kw).reason == "step2: no divergence"
    assert run(lows, macd_div=False, rsi_div=False).reason == "step2: no divergence"
    out = run(lows, rsi_div=False)
    assert out.setup is not None and out.setup.div_macd and not out.setup.div_rsi
    assert "NOT" not in P0.text() and "div_mode=one" in P0.text()
    assert "h1_tf=H1" in P0.text() and "entry_tfs=M5,M15" in P0.text()


@needs_data
def test_runner_writes_only_its_own_files(full, tmp_path) -> None:
    research = importlib.import_module("eye.bot_research")
    watched = [
        ROOT / "eye" / n for n in ("ledger.csv", "ledger_control.csv", "bot_ledger.csv", "bot_log.csv")
    ]
    before = [(p.read_bytes() if p.exists() else None) for p in watched]
    m5 = score_mod.bars()
    result = research.run_variant(
        "t", {"mode": "2e", "min_r": 0.0}, "2026-04-06", "2026-04-06", full, m5, root=tmp_path
    )
    research.append_summary([result], "2026-04-06", "2026-04-06", root=tmp_path)
    after = [(p.read_bytes() if p.exists() else None) for p in watched]
    assert before == after
    assert (tmp_path / "t" / "ledger.csv").exists() and (tmp_path / "t" / "log.csv").exists()
    assert (tmp_path / "summary.csv").exists() and result["decisions"] == 1
    assert result["filled"] + result["open"] <= 1
    with pytest.raises(SystemExit):
        research.make_params({"nonsense": 1})


T_START = pd.Timestamp("2026-10-05 00:00", tz="UTC")


@needs_data
def test_2e_path_reproduces_round_one(full) -> None:
    """The 2e path (steps 3-6 on the setup timeframe, the only one since R12 was removed) is revision 3 bit
    for bit: the 04-06 21:20 decision measured before R12 was written
    (entry 4699.44, trigger 4699.94, stop 4579.49, target 4712.76, key with the setup-timeframe higher low)."""
    now = now_at("2026-04-06 21:20")
    res = bot.decide(bot.cut(full, now), now, P0)
    d = res.decision
    assert d is not None
    got = (d["side"], d["entry"], d["trigger"], d["stop"], d["target"], d["decided_at"])
    assert got == ("BUY", "4699.44", "4699.94", "4579.49", "4712.76", "06/04 21:15")
    assert res.key == "BUY|M5|2026-04-02 13:20:00+00:00|2026-04-02 16:20:00+00:00"
    assert res.log["tf"] == "M5" and "entry_mode" not in d["structure"]


@needs_data
def test_2e_mode_default_is_unchanged(full) -> None:
    """mode "2e" (chosen explicitly; the default is fib) after the Revision 5 refactor: the stored-data decision of 2026-04-06 21:20 in
    entry_mode setup is the pre-Revision-5 one, bit for bit, and the default Params still read mode 2e."""
    now = now_at("2026-04-06 21:20")
    res = bot.decide(bot.cut(full, now), now, P0)
    d = res.decision
    assert d is not None and bot.Params().mode == "fib" and P0.mode == "2e"
    assert (d["entry"], d["trigger"], d["stop"], d["target"]) == ("4699.44", "4699.94", "4579.49", "4712.76")
    assert "mode=2e" in d["structure"]


@needs_data
def test_max_orders_allows_several_live_orders(full, monkeypatch) -> None:
    """max_orders N: a new decision is asked for only while fewer than N earlier orders are live (pending or
    open). A stand-in decide writes one never-resolving filled order per call it is allowed to; N=1 gives one,
    N=3 gives three, and PEAK records the most live at once."""
    seen = float(full["M5"].open[now_at("2026-04-06 07:05")])
    calls: list[bool] = []

    def fake(frames, now, p, used=frozenset(), pending=False):
        calls.append(pending)
        log = dict.fromkeys(bot.LOG_COLUMNS, "")
        log["reason"] = "order pending" if pending else "order written"
        if pending:
            return bot.Result(log)
        row = {c: "" for c in bot.LEDGER_COLUMNS}
        row.update(
            cutoff_thai="2026-04-06 07:00", decided_at="06/04 07:00", side="BUY",
            entry=f"{seen:.2f}", stop="1", target="99998", reader="bot2e",
        )  # fmt: skip
        return bot.Result(log, row, key=f"k{len(used)}")

    monkeypatch.setattr(bot, "decide", fake)
    for n in (1, 3):
        calls.clear()
        mine, _ = bot.walk_days(["2026-04-06"], bot.Params(mode="2e", max_orders=n), full)
        assert len(mine) == n, n
        assert bot.PEAK["live"] == n and bot.PEAK["filled"] == n
    assert "max_orders=3" in bot.Params(max_orders=3).text() and bot.Params().max_orders == 1
    with pytest.raises(ValueError):
        bot.Params(mode="2e", max_orders=0)


def test_money_stops_counting_when_the_account_is_gone(tmp_path, monkeypatch, capsys) -> None:
    """bot_research.money and money.py stop adding USD once the balance reaches 0 or below and say when; the R
    total still counts every trade."""
    research = importlib.import_module("eye.bot_research")

    # a 200 USD account, 0.01 lot: a loss of 1.0 R with a 120-point stop is -120 USD; two of them end it.
    def trade(day: str, r: str) -> dict[str, str]:
        return {"why": "stop" if float(r) < 0 else "target", "r_net": r, "entry": "4120.00", "stop": "4000.00",
                "decided_at": f"{day} 10:00"}  # fmt: skip

    rows = [trade("01/10", "-1.0"), trade("02/10", "-1.0"), trade("03/10", "3.0"), trade("04/10", "-1.0")]
    m = research.money(rows)
    assert m["account_gone"] == "02/10" and m["usd_from_200"] == pytest.approx(-40.0)
    assert m["r_total"] == pytest.approx(0.0) and m["filled"] == 4  # R and counts keep every trade
    assert research.money(rows[:1])["account_gone"] == ""
    # money.py: the same rule on a ledger file
    ledger = tmp_path / "l.csv"
    cols = bot.LEDGER_COLUMNS
    out_rows = []
    for i, (day, r) in enumerate((("2026-10-01", "-1.0"), ("2026-10-02", "-1.0"), ("2026-10-03", "3.0")), 1):
        row = dict.fromkeys(cols, "")
        row.update(
            id=f"B{i}", cutoff_thai=f"{day} 07:00", side="BUY", entry="4120", stop="4000", why="stop", r_net=r
        )
        out_rows.append(row)
    bot._write(ledger, cols, out_rows)
    monkeypatch.setattr(money, "HERE", tmp_path)
    monkeypatch.setattr(sys, "argv", ["money.py", "--ledger", "l.csv"])
    money.main()
    text = capsys.readouterr().out
    assert "account gone at 2026-10-02" in text and "after the account was gone" in text


def _marker_row(entry: float, stop: float, target: float, side: str, h100: float | None) -> dict[str, str]:
    return {
        "id": "T-1", "cutoff_thai": "2026-10-07 07:00", "decided_at": "07/10 07:25", "side": side,
        "entry": f"{entry:.2f}", "stop": f"{stop:.2f}", "target": f"{target:.2f}", "trigger": "",
        "structure": "bot2e fib x" + ("" if h100 is None else f" (withdraw beyond {h100:.2f})"),
    }  # fmt: skip


def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range("2026-10-07 00:30", periods=len(rows), freq="5min", tz="UTC")  # 07:30 Thai
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def test_scorer_withdraws_a_fib_order_when_h100_trades_before_the_fill() -> None:
    """R19 in score.py: with the marker, a bar beyond H100 before the fill bar withdraws the order (BUY and
    SELL); without the marker the same bars score as before (fill and a result); a fill before H100 trades
    is not withdrawn afterwards."""
    cut = pd.Timestamp("2026-10-07 07:30", tz=TH).tz_convert("UTC")
    run_first = _bars(
        [
            (4050, 4055, 4048, 4052),
            (4052, 4101, 4051, 4100),
            (4100, 4100, 4039, 4045),
            (4045, 4165, 4044, 4160),
        ]
    )
    gone = score_mod.score(_marker_row(4040, 4020, 4160, "BUY", 4100.0), run_first, cut)
    assert gone["why"] == "no fill (stop or target first)" and gone["r_net"] == "0.0"
    plain = score_mod.score(_marker_row(4040, 4020, 4160, "BUY", None), run_first, cut)
    assert plain["fill"] and plain["why"] == "target"
    fill_first = _bars([(4050, 4055, 4048, 4052), (4052, 4060, 4039, 4045), (4045, 4165, 4044, 4160)])
    ok = score_mod.score(_marker_row(4040, 4020, 4160, "BUY", 4100.0), fill_first, cut)
    assert ok["fill"] and ok["why"] == "target"
    sell_bars = _bars(
        [
            (4150, 4152, 4148, 4150),
            (4150, 4151, 4099, 4101),
            (4101, 4161, 4100, 4120),
            (4120, 4125, 4040, 4050),
        ]
    )
    marked = score_mod.score(_marker_row(4160, 4180, 4040, "SELL", 4100.0), sell_bars, cut)
    assert marked["why"] == "no fill (stop or target first)"
    assert score_mod.score(_marker_row(4160, 4180, 4040, "SELL", None), sell_bars, cut)["why"] == "target"


def test_scorer_keeps_the_fill_on_a_bar_that_also_crosses_h100() -> None:
    """A bar that both fills the order and crosses H100 keeps the fill (order inside a bar is unknown), for BUY
    and SELL; the trade is scored from that bar on."""
    cut = pd.Timestamp("2026-10-07 07:30", tz=TH).tz_convert("UTC")
    buy_bars = _bars(
        [(4050, 4101, 4039, 4045), (4045, 4165, 4044, 4160)]
    )  # first bar: low 4039 fills, high 4101 > H100
    buy = score_mod.score(_marker_row(4040, 4020, 4160, "BUY", 4100.0), buy_bars, cut)
    assert buy["fill"] == "07/10 07:30" and buy["why"] == "target"
    sell_bars = _bars(
        [(4150, 4161, 4099, 4120), (4120, 4125, 4040, 4050)]
    )  # high 4161 fills, low 4099 < H100
    sell = score_mod.score(_marker_row(4160, 4180, 4040, "SELL", 4100.0), sell_bars, cut)
    assert sell["fill"] == "07/10 07:30" and sell["why"] == "target"


# --- the fib path (eye/BOT_RULES.md) ---------------------------------------------------------------------------
#
# Constructed bars: every number is chosen. A BUY is tested in the view; the SELL is the same data seen as a SELL
# (side "SELL", sign -1), so its outputs are the negated view prices - or the stored bars negated (test_fib_mirror).

PB = bot.Params(mode="fib", fib_entry=0.382)  # the base case's level; the defaults are tested on their own
LEG_BANDS: list[tuple[float, float]] = []  # the ladder's 1.618 step needs no band


def counter_case(
    *,
    lows=(4060.0, 4040.0, 4000.0),
    div: bool = True,
    bounce: float = 4040.0,
    last: float = 4041.0,
    later: float = 4015.0,
):
    """A BUY in the view: a descending run H 4100 (pos 10), lows ``lows`` (the last is L0 = 4000), highs between
    them, the bounce high ``bounce`` (the pivot after L0), a later higher low ``later``, then a close at ``last``.
    MACD / RSI are higher at L0 than at the low before it when ``div``."""
    highs = [4100.0, 4090.0, 4075.0][: len(lows)]
    if len(lows) > 3:  # a longer run: each high 10 above the low it falls from
        highs = [4100.0, *[lo_ + 10 for lo_ in lows[:-1]]]
    pts = [(False, highs[0])]
    for i, lo_ in enumerate(lows):
        pts.append((True, lo_))
        if i < len(lows) - 1:
            pts.append((False, highs[i + 1]))
    pts += [(False, bounce), (True, later)]
    pos = [10 * (i + 1) for i in range(len(pts))]
    n = pos[-1] + 10
    path = np.interp(np.arange(n), [*pos, n - 1], [q for _, q in pts] + [last])
    macd = np.full(n, -5.0)
    rsi = np.full(n, 40.0)
    l0 = pos[len(pts) - 3]  # L0 is the third pivot from the end (L0, bounce high, later low)
    macd[l0], rsi[l0] = (-4.0, 45.0) if div else (-9.0, 35.0)
    if len(lows) >= 2:
        prev = pos[len(pts) - 3 - 2]
        macd[prev], rsi[prev] = -6.0, 40.0
    pv = [bot.VPivot(is_low, price, x) for (is_low, price), x in zip(pts, pos, strict=True)]
    return pv, path + 0.1, path - 0.1, path, macd, rsi


def leg_data(
    *,
    lows=(4060.0, 4040.0, 4000.0),
    div: bool = True,
    bounce: float = 4040.0,
    last: float = 4041.0,
    later: float = 4015.0,
    m5_highs=(4090.0,),
    bands=LEG_BANDS,
    lean: str | None = None,
    edit=None,
) -> bot.LegData:
    """A BUY ``LegData`` over ``counter_case``. The M5 frame is the setup frame (``fib_tf`` M5); ``m5_highs`` are
    fixed M5 highs before H100 (oldest first, positions 1, 3, 5 ...); ``edit(hi, lo, close, macd, rsi)`` may
    change the arrays."""
    pv, hi, lo, close, macd, rsi = counter_case(lows=lows, div=div, bounce=bounce, last=last, later=later)
    if edit is not None:
        edit(hi, lo, close, macd, rsi)
    times = pd.date_range(T_START, periods=len(close), freq="5min")
    m5_pv = [bot.VPivot(False, h, 1 + 2 * i) for i, h in enumerate(m5_highs)] + pv
    return bot.LegData(
        side="BUY", sign=1, tf="M5", pv=pv, times=times, close_v=close, macd_v=macd, rsi_v=rsi,
        m5_times=times, m5_hi_v=hi, m5_lo_v=lo, price_v=float(close[-1]), m5_pv=m5_pv, m5_ptimes=times,
        bands_v=list(bands), lean=lean, lean_text=lean or "none",
    )  # fmt: skip


def as_sell(d: bot.LegData, lean: str | None = None) -> bot.LegData:
    """The same view data read as a SELL (a mirror: the real prices are the negated view prices)."""
    return replace(d, side="SELL", sign=-1, lean=lean, lean_text=lean or "none")


def swings_of(pv: list[bot.VPivot], sign: int) -> list[Swing]:
    """Real fixed pivots whose view (``to_view`` with ``sign``) is ``pv``."""
    out = []
    for q in pv:
        kind = (
            (SwingKind.LOW if q.low else SwingKind.HIGH)
            if sign > 0
            else (SwingKind.HIGH if q.low else SwingKind.LOW)
        )
        out.append(Swing(kind, sign * q.price, q.pos, q.pos + 3, q.pos, q.pos + 3))
    return out


# --- parameters (the table) ---------------------------------------------------------------------------------


def test_fib_parameter_defaults_are_the_tables() -> None:
    d = bot.Params()
    assert (d.fib_tf, d.fib_entry, d.fib_early, d.fib_stop, d.fib_count) == ("M5", 0.618, 0, "line", "off")
    assert (d.max_trend_legs, d.major_tf, d.level_bars, d.level_min_age_h) == (5, "H4", 500, 24.0)
    assert (d.band_frac, d.band_legs, d.max_entry_frac, d.fib_range) == (0.10, 20, 0.25, "on")
    assert (d.stop_buffer, d.target_buffer, d.spread, d.max_orders) == (0.5, 0.5, 0.3, 1)
    assert (d.order_life_bars, d.min_r, d.mode) == (24, 2.0, "fib")  # fib is the default; 2e is a record
    for gone in ("max_entry_distance", "fib_target", "fib_leg", "fib_side", "fib_high", "fib_level"):
        assert not hasattr(d, gone), gone  # the withdrawn options are not parameters any more
    src = Path(bot.__file__).read_text(encoding="utf-8")
    assert (
        "the owner's rule 7" not in src and "max_entry_distance" not in src
    )  # no fixed USD, no stale comment


def test_meaningless_combinations_are_refused_at_start() -> None:
    for bad in (
        {"fib_early": 0.10},  # early without line_tight
        {"fib_early": 0.10, "fib_stop": "line_tight"},  # the default entry 0.618
        {"fib_early": 0.10, "fib_stop": "line", "fib_entry": 0.382},
        {"fib_early": 0.10, "fib_stop": "line_tight", "fib_entry": 0.236},
        {"fib_stop": "swing", "fib_entry": 0.382},
        {"fib_stop": "swing", "fib_entry": 0.236},
        {"fib_stop": "line_tight", "fib_entry": 0.382},  # line_tight without fib_early
        {"fib_stop": "line_tight"},
        {"fib_entry": 0.5},
        {"fib_early": 0.2, "fib_stop": "line_tight", "fib_entry": 0.382},
        {"fib_tf": "H1"},
        {"fib_count": "x"},
        {"max_trend_legs": 4},
        {"major_tf": "D1"},
        {"fib_range": "x"},
        {"mode": "x"},
        {"max_entry_frac": 0.0},
        {"max_entry_frac": 0.5},  # only the table's 0.15 / 0.25 / 0.35
        {"max_entry_frac": 0.2},
        {"order_life_bars": 0},
        {"max_orders": 0},
    ):
        with pytest.raises(ValueError):
            bot.Params(**{"mode": "fib", **bad})
    ok = (
        {},
        {"fib_stop": "swing"},
        {"fib_entry": 0.382, "fib_early": 0.10, "fib_stop": "line_tight"},
        {"fib_entry": 0.382},
        {"fib_entry": 0.236, "fib_stop": "line"},
        {"fib_tf": "M15", "major_tf": "H1", "max_trend_legs": 3, "max_entry_frac": 0.35, "fib_count": "on"},
    )
    for kw in ok:
        bot.Params(mode="fib", **kw)


def test_fib_params_are_written_into_the_text_and_the_command_line() -> None:
    text = bot.Params(mode="fib", fib_entry=0.382, fib_early=0.10, fib_stop="line_tight").text()
    for part in (
        "mode=fib", "fib_tf=M5", "fib_entry=0.382", "fib_early=0.1", "fib_stop=line_tight", "fib_count=off",
        "max_trend_legs=5", "major_tf=H4", "level_bars=500", "level_min_age_h=24", "band_frac=0.1",
        "band_legs=20", "max_entry_frac=0.25", "fib_range=on", "stop_buffer=0.5", "target_buffer=0.5",
        "spread=0.3", "max_orders=1", "order_life_bars=24", "min_r=2",
    ):  # fmt: skip
        assert part in text, part
    assert "order_life_bars" not in bot.Params(mode="2e").text()  # mode 2e's rows stay scored the old way
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main(
            ["--from", "2026-10-01", "--to", "2026-10-02", "--mode", "fib", "--fib-entry", "0.382",
             "--fib-early", "0.1", "--fib-stop", "line_tight", "--max-trend-legs", "3", "--major-tf", "H1",
             "--max-entry-frac", "0.35", "--fib-range", "off", "--order-life-bars", "12", "--fib-count", "on"]
        )  # fmt: skip
    finally:
        bot.run = orig  # type: ignore[assignment]
    q = seen["params"]
    assert (q.mode, q.fib_entry, q.fib_early, q.fib_stop, q.max_trend_legs, q.major_tf) == (
        "fib", 0.382, 0.1, "line_tight", 3, "H1",
    )  # fmt: skip
    assert (q.max_entry_frac, q.fib_range, q.order_life_bars, q.fib_count) == (0.35, "off", 12, "on")
    with pytest.raises(SystemExit):
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--fib-target", "ext161"])  # withdrawn


# --- rule 1: the H1 lean ------------------------------------------------------------------------------------------


def h1_case(pivots: list[tuple[str, float, int]], bars: dict[int, tuple[float, float]], n: int = 40):
    """An H1 frame of ``n`` bars (high 4060 / low 4040 / close 4050) with the given (high, low) overrides, and
    fixed pivots (kind, price, pos)."""
    idx = pd.date_range(T_START, periods=n, freq="1h")
    hi, lo, cl = np.full(n, 4060.0), np.full(n, 4040.0), np.full(n, 4050.0)
    for k, (h, lw) in bars.items():
        hi[k], lo[k] = h, lw
    df = pd.DataFrame({"open": cl, "high": hi, "low": lo, "close": cl}, index=idx)
    piv = [Swing(SwingKind[k], v, p, p + 3, idx[p], idx[p + 3]) for k, v, p in pivots]
    return df, piv


def mirror_h1(df: pd.DataFrame, piv: list[Swing]):
    m = pd.DataFrame(
        {"open": -df.open, "high": -df.low, "low": -df.high, "close": -df.close}, index=df.index
    )  # fmt: skip
    flip = {SwingKind.HIGH: SwingKind.LOW, SwingKind.LOW: SwingKind.HIGH}
    return m, [
        Swing(flip[s.kind], -s.price, s.pivot_pos, s.confirm_pos, s.pivot_at, s.confirm_at) for s in piv
    ]


def test_rule1_buy_lean_and_its_failures_with_the_sell_mirror() -> None:
    base = [("HIGH", 4100.0, 10), ("LOW", 4050.0, 20)]  # Hp 4100, then Lf 4050
    up = {30: (4101.0, 4045.0)}  # a bar after Lf's pivot bar with a high strictly above Hp
    cases = (
        (base, up, 4052.0, "BUY"),
        (base, up, 4050.0, None),  # the last close must be strictly above Lf
        (base, {30: (4100.0, 4045.0)}, 4052.0, None),  # a touch of Hp is not above it
        (base, {15: (4101.0, 4045.0)}, 4052.0, None),  # the bar is before Lf's pivot bar
        ([("LOW", 4050.0, 20)], up, 4052.0, None),  # no Hp
        # the high is after the latest low: no BUY lean (Lf 4050@5 has no earlier high), but a SELL lean
        ([("LOW", 4050.0, 5), ("HIGH", 4100.0, 10)], up, 4052.0, "SELL"),
        ([("HIGH", 4100.0, 10)], up, 4052.0, None),  # no low at all
    )
    for pivots, bars, last, want in cases:
        df, piv = h1_case(pivots, bars)
        df.loc[df.index[-1], "close"] = last
        got, _ = bot.h1_lean(df, piv)
        mdf, mpiv = mirror_h1(df, piv)
        sell, _ = bot.h1_lean(mdf, mpiv)
        assert got == want, (pivots, bars, last)
        assert (
            sell == {"BUY": "SELL", "SELL": "BUY", None: None}[want]
        )  # the SELL lean is the mirror: lower highs, below Hf


def test_rule1_both_hold_the_later_pivot_wins_and_neither_is_no_lean() -> None:
    # L1 4000@5, H1 4100@10, L2 4020@20, H2 4090@30: BUY lean (Lf = L2@20, Hp = H1) needs a high above 4100
    # after pos 20; SELL lean (Hf = H2@30, Lp = L2) needs a low below 4020 after pos 30
    pivots = [("LOW", 4000.0, 5), ("HIGH", 4100.0, 10), ("LOW", 4020.0, 20), ("HIGH", 4090.0, 30)]
    both = {25: (4101.0, 4045.0), 35: (4060.0, 4010.0)}
    df, piv = h1_case(pivots, both)
    assert bot.h1_lean(df, piv)[0] == "SELL"  # Hf at 30 is later than Lf at 20
    only_buy, _ = h1_case(pivots, {25: (4101.0, 4045.0)})
    assert bot.h1_lean(only_buy, piv)[0] == "BUY"
    only_sell, _ = h1_case(pivots, {35: (4060.0, 4010.0)})
    assert bot.h1_lean(only_sell, piv)[0] == "SELL"
    # the last close at or above Hf kills the SELL lean; with no break above Hp the BUY lean is gone too
    high_close, _ = h1_case(pivots, {35: (4060.0, 4010.0)})
    high_close.loc[high_close.index[-1], "close"] = 4091.0
    assert bot.h1_lean(high_close, piv)[0] is None
    none, _ = h1_case(pivots, {})
    assert bot.h1_lean(none, piv)[0] is None
    assert bot.h1_lean(none, [])[0] is None
    # the text names the pivot
    assert "Hf 4090.00" in bot.h1_lean(df, piv)[1] and "SELL" in bot.h1_lean(df, piv)[1]
    # both holding, mirrored: the sides swap
    mdf, mpiv = mirror_h1(df, piv)
    assert bot.h1_lean(mdf, mpiv)[0] == "BUY"


# --- rule 2: the counter-leg ------------------------------------------------------------------------------------------


def pv_of(spec: list[tuple[str, float, int]]) -> list[bot.VPivot]:
    return [bot.VPivot(k == "L", v, p) for k, v, p in spec]


def test_rule2_leg_l0_run_and_h100_buy_and_sell() -> None:
    spec = [("H", 4100.0, 10), ("L", 4060.0, 20), ("H", 4090.0, 30), ("L", 4040.0, 40), ("H", 4075.0, 50),
            ("L", 4000.0, 60), ("H", 4040.0, 70), ("L", 4015.0, 80)]  # fmt: skip
    close = np.full(90, 4041.0)
    for sign in (1, -1):  # the SELL: the same shape negated, read through to_view
        pv = bot.to_view(swings_of(pv_of(spec), sign), sign)
        assert pv == pv_of(spec)
        got = bot.fib_leg(pv, close)
        assert got is not None
        l0, h100, run = got
        assert (l0.price, h100.price) == (4000.0, 4100.0) and [q.price for q in run] == [
            4060.0,
            4040.0,
            4000.0,
        ]
    pv = pv_of(spec)
    # a close under L0 after its pivot bar: no leg (4040 is not lower than 4000, nothing else qualifies)
    c = close.copy()
    c[65] = 3999.9
    assert bot.fib_leg(pv, c) is None
    c[65] = 4000.0  # a close AT L0 is not below it
    assert bot.fib_leg(pv, c) is not None
    # no fixed low after L0: the newest low is not a bottom yet
    assert bot.fib_leg(pv[:-1], close) is None
    # equal lows are not strictly lower
    eq = pv_of([*spec[:5], ("L", 4000.0, 60), ("H", 4040.0, 70), ("L", 4000.0, 80)])
    assert bot.fib_leg(eq, close) is None
    # the latest candidate that fails the close test gives way to an earlier eligible low
    spec2 = [("H", 4100.0, 10), ("L", 4000.0, 20), ("H", 4050.0, 30), ("L", 4015.0, 40), ("H", 4040.0, 50),
             ("L", 4030.0, 60)]  # fmt: skip
    c2 = close.copy()
    c2[45] = 4010.0  # a close under 4015 (the latest bottom) but not under 4000
    leg2 = bot.fib_leg(pv_of(spec2), c2)
    assert leg2 is not None and leg2[0].price == 4000.0
    assert bot.fib_leg(pv_of(spec2), close)[0].price == 4015.0  # type: ignore[index]
    # the run walks back only while each earlier low is strictly higher; H100 starts at the high before the
    # run's first low, so the 4200 before 4010 does not count
    spec3 = [("H", 4200.0, 5), ("L", 4010.0, 8), ("H", 4120.0, 10), ("L", 4070.0, 20), ("H", 4100.0, 30),
             ("L", 4060.0, 40), ("H", 4090.0, 50), ("L", 4000.0, 60), ("H", 4040.0, 70), ("L", 4015.0, 80)]  # fmt: skip
    l0, h100, run = bot.fib_leg(pv_of(spec3), close)  # type: ignore[misc]
    assert [q.price for q in run] == [4070.0, 4060.0, 4000.0] and h100.price == 4120.0
    # the highest high, not the latest, is H100
    spec4 = [("H", 4080.0, 10), ("L", 4060.0, 20), ("H", 4110.0, 30), ("L", 4040.0, 40), ("H", 4090.0, 50),
             ("L", 4000.0, 60), ("H", 4040.0, 70), ("L", 4015.0, 80)]  # fmt: skip
    assert bot.fib_leg(pv_of(spec4), close)[1].price == 4110.0  # type: ignore[index]


def test_rule2_used_leg_is_not_a_candidate_and_the_key_names_the_leg() -> None:
    d = leg_data()
    out = bot.analyse_leg(d, PB)
    assert out.setup is not None
    t0, t100 = d.times[60], d.times[10]
    assert out.setup.key == f"BUY|M5|{t0}|{t100}"
    again = bot.analyse_leg(d, PB, frozenset({out.setup.key}))
    assert again.setup is None and again.reason == "fib: leg or range already used"
    assert bot.analyse_leg(as_sell(d), PB, frozenset({out.setup.key})).setup is not None  # another side's key


# --- the base order: rules 6-9 numbers ---------------------------------------------------------------------------------


def test_base_order_numbers_buy_and_sell() -> None:
    """The 38.2 % level of 4000 -> 4100 is 4038.2; stop L0 - 0.5; the 1.618 step (no band): 4161.8 - 0.5; R by
    the formula. The SELL is the same view data: real prices negated."""
    d = leg_data()
    s = bot.analyse_leg(d, PB).setup
    assert s is not None
    assert (s.order, s.stop) == (pytest.approx(4038.2), pytest.approx(3999.5))
    assert s.target == pytest.approx(4161.3) and s.step == "1.618"
    assert s.r == pytest.approx((4161.3 - 4038.2 - 0.3) / (4038.2 - 3999.5))
    assert s.marker == "withdraw beyond 4100.00" and s.kind == "leg" and s.side == "BUY"
    assert s.gap == pytest.approx(4041.0 - 4038.2)
    t = bot.analyse_leg(as_sell(d), PB).setup
    assert t is not None and t.side == "SELL" and t.marker == "withdraw beyond -4100.00"
    assert (t.order, t.stop, t.target) == (
        pytest.approx(-4038.2),
        pytest.approx(-3999.5),
        pytest.approx(-4161.3),
    )
    assert t.r == pytest.approx(s.r) and t.gap == pytest.approx(s.gap)
    for part in (
        "L0 4000.00",
        "H100 4100.00",
        "23.6 % 4023.60",
        "38.2 % 4038.20",
        "61.8 % 4061.80",
        "step 1.618",
    ):
        assert part.replace("step", "ladder step") in s.detail or part in s.detail, part


# --- rule 10: a leg that has run ------------------------------------------------------------------------------


def test_rule10_a_high_strictly_above_h100_after_l0_ends_the_leg() -> None:
    why = "fib: leg has run (100 % traded)"
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        base = leg_data()
        assert bot.analyse_leg(wrap(base), PB).reason == "order written"
        # touching H100 is not above it
        touch = leg_data(edit=lambda hi, lo, cl, m, r: hi.__setitem__(75, 4100.0))
        assert bot.analyse_leg(wrap(touch), PB).reason == "order written"
        above = leg_data(edit=lambda hi, lo, cl, m, r: hi.__setitem__(75, 4100.05))
        out = bot.analyse_leg(wrap(above), PB)
        assert out.reason == why and out.setup is None
        # the L0 pivot bar itself (pos 60, its open before its own close) does not count; the next bar does
        on_pivot = leg_data(edit=lambda hi, lo, cl, m, r: hi.__setitem__(60, 4200.0))
        assert bot.analyse_leg(wrap(on_pivot), PB).reason == "order written"
        next_bar = leg_data(edit=lambda hi, lo, cl, m, r: hi.__setitem__(61, 4200.0))
        assert bot.analyse_leg(wrap(next_bar), PB).reason == why
        # a high before L0 does not count
        before = leg_data(edit=lambda hi, lo, cl, m, r: hi.__setitem__(55, 4200.0))
        assert bot.analyse_leg(wrap(before), PB).reason == "order written"


def test_rule10_uses_the_m5_bars_after_an_m15_leg_pivot_bar_closes() -> None:
    """fib_tf M15: the M5 bars whose open is at or after the L0 bar's close (open + 15 min) count."""
    d = leg_data()
    n = len(d.times)
    m15 = pd.date_range(T_START, periods=n, freq="15min")  # the setup frame's own bars
    hi = d.m5_hi_v.copy()
    d15 = replace(d, tf="M15", times=m15, m5_times=pd.date_range(T_START, periods=3 * n, freq="5min"),
                  m5_hi_v=np.repeat(hi, 3), m5_lo_v=np.repeat(d.m5_lo_v, 3), m5_ptimes=pd.date_range(T_START, periods=3 * n, freq="5min"),
                  m5_pv=[bot.VPivot(q.low, q.price, q.pos * 3) for q in d.m5_pv])  # fmt: skip
    t0 = m15[60]
    j = int(d15.m5_times.searchsorted(t0 + pd.Timedelta(minutes=15)))
    assert d15.m5_times[j] == t0 + pd.Timedelta(minutes=15)
    for k, want in ((j - 1, "order written"), (j, "fib: leg has run (100 % traded)")):
        e = d15.m5_hi_v.copy()
        e[k] = 4200.0
        assert bot.analyse_leg(replace(d15, m5_hi_v=e), PB).reason == want, k


# --- rule 3: the M5 trend, and the lean -------------------------------------------------------------------------------


def test_rule3_h100_must_be_above_the_latest_m5_high_before_it() -> None:
    why = "fib: M5 trend (H100 not above the M5 high)"
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        assert bot.analyse_leg(wrap(leg_data(m5_highs=(4090.0,))), PB).reason == "order written"
        assert bot.analyse_leg(wrap(leg_data(m5_highs=(4100.0,))), PB).reason == why  # equal is not above
        assert bot.analyse_leg(wrap(leg_data(m5_highs=(4120.0,))), PB).reason == why
        assert bot.analyse_leg(wrap(leg_data(m5_highs=())), PB).reason == why  # none before H100's time
        # only the LATEST high before H100 is compared: an older, higher one does not matter
        assert bot.analyse_leg(wrap(leg_data(m5_highs=(4150.0, 4090.0))), PB).reason == "order written"
        assert bot.analyse_leg(wrap(leg_data(m5_highs=(4050.0, 4120.0))), PB).reason == why
    # a fixed M5 high AT H100's time is not "strictly before"
    d = leg_data(m5_highs=())
    same_time = replace(d, m5_pv=[bot.VPivot(False, 4000.0, 10), *d.m5_pv])
    assert bot.analyse_leg(same_time, PB).reason == why
    out = bot.analyse_leg(leg_data(m5_highs=(4090.0,)), PB)
    assert out.setup is not None and "H100 4100.00 beyond the M5 high 4090.00" in out.setup.detail
    sell = bot.analyse_leg(as_sell(leg_data()), PB)
    assert sell.setup is not None and "beyond the M5 low -4090.00" in sell.setup.detail


def test_rule1_lean_refuses_the_opposite_leg_and_allows_none() -> None:
    why = "fib: against the H1 lean"
    d = leg_data()
    assert bot.analyse_leg(replace(d, lean="SELL"), PB).reason == why
    assert bot.analyse_leg(replace(d, lean="BUY", lean_text="BUY"), PB).reason == "order written"
    assert (
        bot.analyse_leg(replace(d, lean=None), PB).reason == "order written"
    )  # no lean: M5 trend decides alone
    assert bot.analyse_leg(as_sell(d, "BUY"), PB).reason == why
    assert bot.analyse_leg(as_sell(d, "SELL"), PB).reason == "order written"
    assert bot.analyse_leg(as_sell(d, None), PB).reason == "order written"
    # the order of evaluation: rule 3 is reported before the lean when both refuse
    bad3 = leg_data(m5_highs=(4120.0,), lean="SELL")
    assert bot.analyse_leg(bad3, PB).reason == "fib: M5 trend (H100 not above the M5 high)"


# --- rule 4: the count ------------------------------------------------------------------------------------------------


def test_rule4_count_table_buy_and_sell() -> None:
    assert [bot.count_reason(n, False, False) for n in (1, 2, 3, 5, 6)] == [
        "fib: count outside 3-5 and no M", "", "fib: no divergence", "fib: no divergence",
        "fib: count outside 3-5 and no M",
    ]  # fmt: skip
    for n in (3, 4, 5):
        assert bot.count_reason(n, True, False) == "" and bot.count_reason(n, False, True) == ""
        assert bot.count_reason(n, True, True) == ""
    assert bot.count_reason(2, True, True) == "" and bot.count_reason(6, True, True) != ""
    assert bot.count_reason(1, True, True) != ""
    on = bot.Params(mode="fib", fib_entry=0.382, fib_count="on")
    runs = {
        1: (4000.0,),
        2: (4040.0, 4000.0),
        3: (4060.0, 4040.0, 4000.0),
        4: (4070.0, 4060.0, 4040.0, 4000.0),
        5: (4075.0, 4070.0, 4060.0, 4040.0, 4000.0),
        6: (4078.0, 4075.0, 4070.0, 4060.0, 4040.0, 4000.0),
    }
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        for n, lows in runs.items():
            for div, want in ((True, n in (2, 3, 4, 5)), (False, n == 2)):
                out = bot.analyse_leg(wrap(leg_data(lows=lows, div=div)), on)
                assert (out.setup is not None) == want, (n, div, sell, out.reason)
                assert out.info["count"] == str(n)
            # count off: any run passes, with or without divergence
            assert bot.analyse_leg(wrap(leg_data(lows=lows, div=False)), PB).setup is not None, n
    # the reasons
    assert bot.analyse_leg(leg_data(lows=runs[3], div=False), on).reason == "fib: no divergence"
    assert bot.analyse_leg(leg_data(lows=runs[6]), on).reason == "fib: count outside 3-5 and no M"
    assert bot.analyse_leg(leg_data(lows=runs[1]), on).reason == "fib: count outside 3-5 and no M"


def test_rule4_divergence_flags_and_the_record_say_which_oscillator() -> None:
    """MACD only / RSI only / both / none; the flags are in the row whether or not the count is on."""

    def edit(macd_up: bool, rsi_up: bool):
        def f(hi, lo, cl, macd, rsi):
            macd[60], rsi[60] = (-4.0, 45.0)
            if not macd_up:
                macd[60] = -7.0  # lower than the previous low's -6
            if not rsi_up:
                rsi[60] = 39.0  # lower than the previous low's 40

        return f

    for m_up, r_up in ((True, False), (False, True), (True, True), (False, False)):
        s = bot.analyse_leg(leg_data(edit=edit(m_up, r_up)), PB).setup
        assert s is not None
        assert f"divergence on MACD {m_up}, on RSI {r_up}" in s.detail
    out = bot.analyse_leg(leg_data(edit=edit(True, False)), PB)
    assert (out.info["div_macd"], out.info["div_rsi"]) == ("True", "False")

    # equal oscillator values are not higher
    def flat(hi, lo, cl, macd, rsi):
        macd[60], rsi[60] = -6.0, 40.0

    eq = bot.Params(mode="fib", fib_entry=0.382, fib_count="on")
    assert bot.analyse_leg(leg_data(edit=flat), eq).reason == "fib: no divergence"

    # a non-finite oscillator value is not a divergence
    def nan(hi, lo, cl, macd, rsi):
        macd[60], rsi[60] = np.nan, np.nan

    assert bot.analyse_leg(leg_data(edit=nan), eq).reason == "fib: no divergence"


# --- rule 5: the trend run ------------------------------------------------------------------------------------------


def test_rule5_no_chasing_buy_and_sell() -> None:
    why = "fib: trend run at the limit"
    three = bot.Params(mode="fib", fib_entry=0.382, max_trend_legs=3)
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        # latest first: 4090 < 4100 (leg 2), 4070 < 4090 (3), 4060 < 4070 (4), 4050 < 4060 (5)
        for highs, legs in (((4090.0,), 2), ((4070.0, 4090.0), 3), ((4060.0, 4070.0, 4090.0), 4),
                            ((4050.0, 4060.0, 4070.0, 4090.0), 5)):  # fmt: skip
            d = wrap(leg_data(m5_highs=highs))
            out5 = bot.analyse_leg(d, PB)
            out3 = bot.analyse_leg(d, three)
            assert (out5.setup is None) == (legs >= 5), legs
            assert (out3.setup is None) == (legs >= 3), legs
            if legs >= 5:
                assert out5.reason == why
            assert out5.info["trend_legs"] == str(legs)
        # the chain stops at a high that is not lower: 4095 is not below 4070's successor... 4070, then 4080 breaks it
        d = wrap(
            leg_data(m5_highs=(4085.0, 4070.0, 4090.0))
        )  # latest 4090 (2), then 4070 (3), then 4085 is higher
        assert bot.analyse_leg(d, PB).info["trend_legs"] == "3"


# --- rule 6: the level, the order price, the bounce, played out --------------------------------------------------


def test_rule6_needs_a_bounce_above_the_order_price_and_the_price_above_it() -> None:
    # no M5 bar after L0 has a high strictly above the order price 4038.2 (the bounce high 4040 is lowered)
    low_bounce = leg_data(bounce=4038.0, last=4037.0, later=4020.0)
    assert bot.analyse_leg(low_bounce, PB).reason == "fib: no bounce above the order price"
    # the price at or below the order price: no order (a plain buy limit needs the price above it)
    for last in (4038.2, 4030.0):
        out = bot.analyse_leg(leg_data(last=last), PB)
        assert out.reason == "fib: price not above the order price" and out.setup is None

    # a touch of the order price after the bounce and before now does not stop the order
    def retest(hi, lo, cl, macd, rsi):
        lo[84] = 4038.0
        hi[84] = 4044.0

    assert bot.analyse_leg(leg_data(edit=retest), PB).reason == "order written"
    # the SELL mirror
    assert bot.analyse_leg(as_sell(low_bounce), PB).reason == "fib: no bounce above the order price"
    assert (
        bot.analyse_leg(as_sell(leg_data(last=4038.2)), PB).reason == "fib: price not above the order price"
    )
    # the 0.618 default: order price 4061.8; the base price 4041 is below it
    d618 = bot.Params(mode="fib")
    assert bot.analyse_leg(leg_data(), d618).reason == "fib: no bounce above the order price"
    ok = bot.analyse_leg(leg_data(bounce=4070.0, last=4063.0, later=4030.0), d618).setup
    assert ok is not None and ok.order == pytest.approx(4061.8)
    assert (
        bot.analyse_leg(leg_data(bounce=4070.0, last=4040.0), bot.Params(mode="fib", fib_entry=0.236)).setup
        is not None
    )


def test_rule6_fib_early_moves_the_order_price_above_the_level() -> None:
    tight = bot.Params(mode="fib", fib_entry=0.382, fib_early=0.10, fib_stop="line_tight")
    # the bounce and the price are tested against the order price: the base bounce 4040 is below 4048.2
    assert bot.analyse_leg(leg_data(), tight).reason == "fib: no bounce above the order price"
    case = {"bounce": 4055.0, "last": 4051.0, "later": 4042.0}  # a retest low above the tight stop 4037.7
    s = bot.analyse_leg(leg_data(**case), tight).setup
    assert s is not None and s.order == pytest.approx(4048.2)  # 4038.2 + 0.10 x 100
    assert s.stop == pytest.approx(4037.7)  # line_tight: the 0.382 level - buffer
    t = bot.analyse_leg(as_sell(leg_data(**case)), tight).setup
    assert t is not None and t.order == pytest.approx(-4048.2) and t.stop == pytest.approx(-4037.7)


def test_rule6_played_out_target_from_the_first_bar_stop_from_the_next() -> None:
    why = "setup already played out"
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        # the first bar above the order price 4038.2 is the one with the bounce pivot (pos 70 area); find it
        base = leg_data()
        j = 61 + int(np.flatnonzero(base.m5_hi_v[61:] > 4038.2)[0])

        def set_hi(k, v):
            return lambda hi, lo, cl, m, r: hi.__setitem__(k, v)

        def set_lo(k, v):
            return lambda hi, lo, cl, m, r: lo.__setitem__(k, v)

        # the target 4161.3 - but a high that high is beyond H100: use a ladder step with a nearer target
        # a band before 1.272 gives a target near the order price (the 1.618 target lies beyond H100)
        near = [(4046.0, 4050.0)]  # the target is 4046.0 - 0.5 = 4045.5
        d = wrap(leg_data(bands=near))
        s = bot.analyse_leg(d, bot.Params(mode="fib", fib_entry=0.382, min_r=0.0)).setup
        assert s is not None and s.step == "band"
        assert s.target == pytest.approx(-4045.5 if sell else 4045.5)
        # a high at the target on the first bar above the order price counts; one bar later it counts too
        for k in (j, j + 3):
            e = wrap(leg_data(bands=near, edit=set_hi(k, 4045.5)))
            assert bot.analyse_leg(e, bot.Params(mode="fib", fib_entry=0.382, min_r=0.0)).reason == why, k
        # a high just under the target does not
        e = wrap(leg_data(bands=near, edit=set_hi(j + 3, 4045.4)))
        assert bot.analyse_leg(e, bot.Params(mode="fib", fib_entry=0.382, min_r=0.0)).setup is not None
        # a low at the stop on the first bar above the order price is ignored (the climb out of L0)
        e = wrap(leg_data(edit=set_lo(j, 3999.5)))
        assert bot.analyse_leg(e, PB).reason == "order written"
        # ... but on the next bar it counts, and so does one under it
        for k, v in ((j + 1, 3999.5), (j + 4, 3990.0)):
            e = wrap(leg_data(edit=set_lo(k, v)))
            assert bot.analyse_leg(e, PB).reason == why, (k, v)
        # a low just above the stop does not
        e = wrap(leg_data(edit=set_lo(j + 1, 3999.6)))
        assert bot.analyse_leg(e, PB).reason == "order written"


# --- rule 7: the stop -------------------------------------------------------------------------------------------------


def test_rule7_stop_by_entry_and_fib_stop() -> None:
    d = leg_data(bounce=4070.0, last=4063.0, later=4015.0)  # a later low 4015 under the 23.6 % level 4023.6
    l0 = bot.VPivot(True, 4000.0, 60)
    line = bot.Params(mode="fib")
    assert bot.fib_stop_v(line, d.pv, l0, 100.0) == pytest.approx(4023.6 - 0.5)  # 0.618: beyond 23 %
    swing = bot.Params(mode="fib", fib_stop="swing")
    assert bot.fib_stop_v(swing, d.pv, l0, 100.0) == pytest.approx(4015.0 - 0.5)  # below the lowest later low
    assert bot.fib_stop_v(swing, [q for q in d.pv if q.pos <= 60], l0, 100.0) == pytest.approx(
        4023.1
    )  # none: line
    high_low = leg_data(later=4030.0)  # a later low above the 23.6 % level: the level is the lower one
    assert bot.fib_stop_v(swing, high_low.pv, l0, 100.0) == pytest.approx(4023.1)
    for entry in (0.382, 0.236):
        assert bot.fib_stop_v(bot.Params(mode="fib", fib_entry=entry), d.pv, l0, 100.0) == pytest.approx(
            3999.5
        )
    tight = bot.Params(mode="fib", fib_entry=0.382, fib_early=0.10, fib_stop="line_tight")
    assert bot.fib_stop_v(tight, d.pv, l0, 100.0) == pytest.approx(4038.2 - 0.5)
    # the stop reaches the order: 0.618 line stop, R from it
    d_line = leg_data(bounce=4070.0, last=4063.0, later=4030.0)  # the retest stays above the line stop
    s = bot.analyse_leg(d_line, line).setup
    assert s is not None and s.stop == pytest.approx(4023.1)
    assert s.r == pytest.approx((s.target - s.order - 0.3) / (s.order - 4023.1))
    assert bot.analyse_leg(d, line).reason == "setup already played out"  # 4015 reached the line stop
    t = bot.analyse_leg(as_sell(d), swing).setup
    assert t is not None and t.stop == pytest.approx(-4014.5)
    assert bot.Params(mode="fib", stop_buffer=1.0).stop_buffer == 1.0
    wide = bot.Params(mode="fib", fib_entry=0.382, stop_buffer=2.0)
    assert bot.fib_stop_v(wide, d.pv, l0, 100.0) == pytest.approx(3998.0)


# --- rule 8: the ladder -----------------------------------------------------------------------------------------------


def test_rule8_ladder_steps_and_no_fall_through() -> None:
    p = bot.Params(mode="fib", fib_entry=0.382, min_r=0.0)
    l0, leg, order = 4000.0, 100.0, 4038.2
    raw127, raw161 = l0 + 127.2, l0 + 161.8
    # no band in the way: 1.618
    assert bot.fib_ladder(p, l0, leg, order, []) == (pytest.approx(raw161 - 0.5), "1.618")
    # a band between 1.272 and 1.618 (near edge): 1.272
    assert bot.fib_ladder(p, l0, leg, order, [(raw127 + 5, raw127 + 9)]) == (
        pytest.approx(raw127 - 0.5),
        "1.272",
    )
    # a band before 1.272: its near edge - buffer (the nearest of several)
    got = bot.fib_ladder(p, l0, leg, order, [(4110.0, 4120.0), (4070.0, 4075.0), (raw127 + 5, raw127 + 9)])
    assert got == (pytest.approx(4069.5), "band")
    # a band whose near edge is at or below the order price is ignored, and so is one the price sits inside
    assert bot.fib_ladder(p, l0, leg, order, [(4038.2, 4045.0)])[1] == "1.618"  # edge == order: not above it
    assert bot.fib_ladder(p, l0, leg, order, [(4030.0, 4050.0)])[1] == "1.618"  # the order price is inside
    # edges are strict against the raw extensions: an edge AT the raw 1.618 is not before it
    assert bot.fib_ladder(p, l0, leg, order, [(raw161, raw161 + 4)])[1] == "1.618"
    assert bot.fib_ladder(p, l0, leg, order, [(raw161 - 0.01, raw161 + 4)])[1] == "1.272"
    assert bot.fib_ladder(p, l0, leg, order, [(raw127, raw127 + 4)])[1] == "1.272"  # at 1.272: not before it
    assert bot.fib_ladder(p, l0, leg, order, [(raw127 - 0.01, raw127 + 4)])[1] == "band"
    # target buffer is the parameter
    q = bot.Params(mode="fib", fib_entry=0.382, target_buffer=2.0)
    assert bot.fib_ladder(q, l0, leg, order, [])[0] == pytest.approx(raw161 - 2.0)
    # no fall-through: the nearest band's edge gives R under 2 though the 1.272 step would pay -> no order
    near = [(4046.0, 4050.0)]  # target 4045.5, R tiny
    out = bot.analyse_leg(leg_data(bands=near), bot.Params(mode="fib", fib_entry=0.382))
    assert out.reason == "reward under 2R" and out.setup is None
    # a target not above the order price: no order
    back = [(4038.5, 4040.0)]  # edge 4038.5 > order 4038.2, target 4038.0 <= order
    assert bot.analyse_leg(leg_data(bands=back), p).reason == "fib: no target above the order price"
    # the SELL: a band is the mirror; the nearest edge is the view's lower edge
    sell = bot.analyse_leg(as_sell(leg_data(bands=[(4046.0, 4050.0)])), p).setup
    assert sell is not None and sell.step == "band" and sell.target == pytest.approx(-4045.5)
    # the example of BOT_RULES: leg 3989.14 -> 4025.45, entry 0.382 = 4003.01, stop 3988.64, no band: R 3.07
    leg2 = 4025.45 - 3989.14
    order2 = 3989.14 + 0.382 * leg2
    tgt, step = bot.fib_ladder(p, 3989.14, leg2, order2, [])
    assert (round(order2, 2), step, round(tgt, 2)) == (4003.01, "1.618", 4047.39)
    assert round(bot.planned_r(order2, 3989.14 - 0.5, tgt, 0.3), 2) == 3.07


def test_rule8_min_r_floor_is_the_parameter() -> None:
    d = leg_data()
    s = bot.analyse_leg(d, PB).setup
    assert s is not None
    above = bot.Params(mode="fib", fib_entry=0.382, min_r=s.r + 0.01)
    out = bot.analyse_leg(d, above)
    assert out.reason == "reward under 2R" and out.setup is None
    at = bot.Params(mode="fib", fib_entry=0.382, min_r=s.r)
    assert bot.analyse_leg(d, at).setup is not None  # at the floor passes
    assert bot.planned_r(100.0, 100.0, 110.0, 0.3) == float("-inf")


# --- rule 9: the reach ---------------------------------------------------------------------------------------------


def test_rule9_reach_is_a_share_of_the_leg_both_sides() -> None:
    why = "fib: order price too far from price"
    # the leg is 100: 0.25 x 100 = 25 at the default; the order price 4038.2
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        at = leg_data(last=4038.2 + 25.0, bounce=4070.0)
        assert bot.analyse_leg(wrap(at), PB).reason == "order written"  # exactly the limit is reachable
        over = leg_data(last=4038.2 + 25.05, bounce=4070.0)
        out = bot.analyse_leg(wrap(over), PB)
        assert out.reason == why and out.setup is None and "limit 0.25 x 100.00 = 25.00" in out.info["r9"]
        # the limit scales with the leg and the parameter
        tight = bot.Params(mode="fib", fib_entry=0.382, max_entry_frac=0.15)
        assert bot.analyse_leg(wrap(leg_data(last=4038.2 + 14.9, bounce=4070.0)), tight).setup is not None
        assert bot.analyse_leg(wrap(leg_data(last=4038.2 + 15.1, bounce=4070.0)), tight).reason == why
        wide = bot.Params(mode="fib", fib_entry=0.382, max_entry_frac=0.35)
        assert bot.analyse_leg(wrap(leg_data(last=4038.2 + 34.9, bounce=4070.0)), wide).setup is not None
    # the reach is a share of the leg, not a fixed amount: nothing in the numbers above is 4.0 USD
    big = bot.analyse_leg(leg_data(last=4038.2 + 4.5, bounce=4070.0), PB)
    assert big.setup is not None  # 4.5 away would have been refused by a fixed 4 USD limit


# --- rule 11: the range ----------------------------------------------------------------------------------------------


def rng_p(**kw) -> bot.Params:
    """Fib params for the range tests; a ``max_entry_frac`` outside the table's three values is forced in
    after validation (the range tests need a reach wider than 0.35 of a 100-high range)."""
    frac = kw.pop("max_entry_frac", None)
    p = bot.Params(mode="fib", min_r=kw.pop("min_r", 0.0), **kw)
    if frac is not None:
        object.__setattr__(p, "max_entry_frac", frac)
    return p


def test_rule11_range_orders_levels_stops_targets_and_zone() -> None:
    p = rng_p(max_entry_frac=0.5)
    lo, hi = 4600.0, 4700.0  # height 100
    closes = np.full(10, 4650.0)
    # mid-range: both qualify; the nearer to the price 4650: BUY order 4612 is 38 away, SELL order 4688 is 38 away: tie -> BUY
    out = bot.analyse_range(lo, hi, 4650.0, closes, p, "M5")
    s = out.setup
    assert out.reason == "order written" and s is not None and s.side == "BUY" and s.kind == "range"
    assert s.order == pytest.approx(4612.0) and s.stop == pytest.approx(4573.0 - 0.5)
    assert s.target == pytest.approx(4700.0 - 0.5) and s.step == "range edge"
    assert s.r == pytest.approx((4699.5 - 4612.0 - 0.3) / (4612.0 - 4572.5))
    assert s.marker == "range break M5 close beyond 4573.0000 / 4727.0000"
    # nearer to the top: the SELL at 88 %
    t = bot.analyse_range(lo, hi, 4670.0, closes, p, "M5").setup
    assert t is not None and t.side == "SELL" and t.order == pytest.approx(4688.0)
    assert t.stop == pytest.approx(4727.0 + 0.5) and t.target == pytest.approx(4600.0 + 0.5)
    assert t.r == pytest.approx((4688.0 - 4600.5 - 0.3) / (4727.5 - 4688.0))
    # the zones: BUY needs 0.12 < level < 1, SELL 0 < level < 0.88 (boundaries excluded)
    p = rng_p(max_entry_frac=1.0)  # the reach is tested elsewhere
    only_sell = bot.analyse_range(lo, hi, 4612.0, closes, p, "M5")  # level 0.12: no BUY, SELL qualifies
    assert only_sell.setup is not None and only_sell.setup.side == "SELL"
    only_buy = bot.analyse_range(lo, hi, 4688.0, closes, p, "M5")  # level 0.88: no SELL, BUY qualifies
    assert only_buy.setup is not None and only_buy.setup.side == "BUY"
    for price in (
        4600.0,
        4700.0,
        4590.0,
        4710.0,
    ):  # a level of 0, 1, or outside 0..1 but inside the break levels
        o = bot.analyse_range(lo, hi, price, closes, p, "M5")
        assert o.setup is None and o.reason == "fib: price outside the range zone", price
    # rule 13: the nearer order wins; at equal distance the BUY
    assert bot.choose([t, s]) is t and bot.choose([s, t]) is t
    tie = replace(t, gap=s.gap)
    assert bot.choose([tie, s]).side == "BUY" and bot.choose([s, tie]).side == "BUY"


def test_rule11_floor_reach_and_break() -> None:
    lo, hi = 4600.0, 4700.0
    closes = np.full(10, 4650.0)
    # R floor: the narrow range cannot pay the fixed buffers and the spread
    narrow = bot.analyse_range(4600.0, 4610.0, 4605.0, np.full(10, 4605.0), bot.Params(mode="fib"), "M5")
    assert narrow.reason == "reward under 2R" and narrow.setup is None
    wide = bot.analyse_range(lo, hi, 4650.0, closes, rng_p(max_entry_frac=0.5, min_r=2.0), "M5")
    assert wide.setup is not None and wide.setup.r >= 2.0  # R 2.21 at the 12 % entry
    # reach with the height: 25 at the default; the BUY order 4612 is 38 from 4650
    far = bot.analyse_range(lo, hi, 4650.0, closes, bot.Params(mode="fib", min_r=0.0), "M5")
    assert far.reason == "fib: order price too far from price" and far.setup is None
    near = bot.analyse_range(lo, hi, 4637.0, closes, bot.Params(mode="fib", min_r=0.0), "M5")
    assert near.setup is not None and near.setup.side == "BUY"  # 25 from 4612
    # the break: a closed bar beyond -0.27 or 1.27 (strict) ends the range for both sides
    p = rng_p(max_entry_frac=0.5)
    for bad in (4572.9, 4727.1):
        c = closes.copy()
        c[3] = bad
        o = bot.analyse_range(lo, hi, 4650.0, c, p, "M5")
        assert o.reason == "fib: range broken" and o.setup is None
    for fine in (4573.0, 4727.0):
        c = closes.copy()
        c[3] = fine
        assert bot.analyse_range(lo, hi, 4650.0, c, p, "M5").setup is not None
    assert bot.analyse_range(lo, lo, 4650.0, closes, p, "M5").reason == "fib: no range"
    # the marker names the timeframe
    m15 = bot.analyse_range(lo, hi, 4650.0, closes, p, "M15").setup
    assert m15 is not None and m15.marker.startswith("range break M15 close beyond")


def test_rule11_m5_trend_test() -> None:
    def pv(highs, lows):
        out = [bot.VPivot(False, h, 2 * i) for i, h in enumerate(highs)]
        return out + [bot.VPivot(True, lw, 2 * i + 1) for i, lw in enumerate(lows)]

    assert bot.m5_has_trend(pv([4100, 4110], [4000, 4010])) is True  # higher high and higher low
    assert bot.m5_has_trend(pv([4110, 4100], [4010, 4000])) is True  # lower high and lower low
    assert bot.m5_has_trend(pv([4100, 4110], [4010, 4000])) is False  # broadening
    assert bot.m5_has_trend(pv([4110, 4100], [4000, 4010])) is False  # narrowing
    assert bot.m5_has_trend(pv([4100, 4100], [4000, 4010])) is False  # equal high: neither
    assert bot.m5_has_trend(pv([4100], [4000, 4010])) is None  # fewer than two highs
    assert bot.m5_has_trend(pv([4100, 4110], [4000])) is None
    assert bot.m5_has_trend([]) is None
    # only the latest two of each count
    assert bot.m5_has_trend(pv([4000, 4110, 4100], [3900, 4010, 4000])) is True


def range_inputs(*, lean=None, m5_trend=False, price=4650.0, closes_after=None):
    """FibInputs for the decision layer: a setup frame whose latest fixed pivots are a low 4600 (pos 20) and a
    high 4700 (pos 30); M5 pivots without (or with) a trend."""
    n = 60
    times = pd.date_range(T_START, periods=n, freq="5min")
    close = np.full(n, 4650.0)
    if closes_after:
        for k, v in closes_after.items():
            close[k] = v
    df = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close}, index=times)
    zz = [Swing(SwingKind.LOW, 4600.0, 20, 23, times[20], times[23]),
          Swing(SwingKind.HIGH, 4700.0, 30, 33, times[30], times[33])]  # fmt: skip
    if m5_trend:
        m5 = [Swing(SwingKind.HIGH, 4100.0, 2, 5, times[2], times[5]), Swing(SwingKind.LOW, 4000.0, 4, 7, times[4], times[7]),
              Swing(SwingKind.HIGH, 4110.0, 8, 11, times[8], times[11]), Swing(SwingKind.LOW, 4010.0, 10, 13, times[10], times[13])]  # fmt: skip
    else:
        m5 = [Swing(SwingKind.HIGH, 4100.0, 2, 5, times[2], times[5]), Swing(SwingKind.LOW, 4010.0, 4, 7, times[4], times[7]),
              Swing(SwingKind.HIGH, 4110.0, 8, 11, times[8], times[11]), Swing(SwingKind.LOW, 4000.0, 10, 13, times[10], times[13])]  # fmt: skip
    none = [replace(leg_data(), pv=[]), as_sell(replace(leg_data(), pv=[]))]  # no leg on either side
    return bot.FibInputs(lean, lean or "none", none, df, times, zz, m5, price)


def decide_inputs(fi, p, used=frozenset()):
    log = dict.fromkeys(bot.LOG_COLUMNS, "")

    def done(reason, info=None, tf=""):
        log["reason"], log["tf"] = reason, tf
        log.update(info or {})
        return bot.Result(log)

    return bot.fib_decision(fi, now_at("2026-10-05 10:00"), p, used, log, done)


def test_rule11_gates_lean_trend_switch_and_one_order_per_range() -> None:
    p = rng_p(max_entry_frac=0.5)
    res = decide_inputs(range_inputs(), p)
    assert res.decision is not None and res.decision["side"] == "BUY"
    assert res.key.startswith("range|M5|") and res.key.count("|") == 3
    d = res.decision
    assert d["rules"] == "" and d["setup"] == "" and d["trigger"] == "" and d["conflict"] == ""
    assert (
        "range break M5 close beyond 4573.0000 / 4727.0000" in d["structure"]
        and "withdraw beyond" not in d["structure"]
    )
    # one order per range: the same two pivot times are used
    again = decide_inputs(range_inputs(), p, frozenset({res.key}))
    assert again.decision is None and again.log["reason"] == "fib: leg or range already used"
    # a lean (either side), a trend on M5, fib_range off, or too few M5 pivots: no range
    for fi in (range_inputs(lean="BUY"), range_inputs(lean="SELL"), range_inputs(m5_trend=True)):
        assert decide_inputs(fi, p).decision is None
    assert decide_inputs(range_inputs(), rng_p(max_entry_frac=0.5, fib_range="off")).decision is None
    few = range_inputs()
    few.m5_zz.clear()
    assert decide_inputs(few, p).decision is None
    # a close beyond the break level after the later pivot ends it
    broken = range_inputs(closes_after={40: 4750.0})
    out = decide_inputs(broken, p)
    assert out.decision is None and out.log["reason"] == "fib: range broken"
    # a close beyond it BEFORE the later pivot (pos 30) is not "after"
    old = range_inputs(closes_after={25: 4750.0})
    assert decide_inputs(old, p).decision is not None
    # the pivots in the other order give the same range
    flipped = range_inputs()
    flipped.zz.reverse()
    assert decide_inputs(flipped, p).decision is not None


# --- rule 13: a BUY and a SELL ----------------------------------------------------------------------------------------


def test_rule13_nearer_order_wins_then_the_buy() -> None:
    buy = leg_data(last=4041.0)  # 2.8 from its order price
    sell = as_sell(leg_data(last=4045.0))  # 6.8 from its order price
    fi = bot.FibInputs(None, "none", [buy, sell], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0)
    res = decide_inputs(fi, PB)
    assert res.decision is not None and res.decision["side"] == "BUY"
    fi = bot.FibInputs(None, "none", [leg_data(last=4045.0), as_sell(leg_data(last=4041.0))], pd.DataFrame(),
                       pd.DatetimeIndex([]), [], [], 0.0)  # fmt: skip
    res = decide_inputs(fi, PB)
    assert res.decision is not None and res.decision["side"] == "SELL" and float(res.decision["entry"]) < 0
    fi = bot.FibInputs(
        None, "none", [leg_data(), as_sell(leg_data())], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0
    )
    res = decide_inputs(fi, PB)
    assert res.decision is not None and res.decision["side"] == "BUY"  # equal distance: the BUY
    # a used BUY leg is not a candidate: the SELL is written
    used = frozenset({bot.analyse_leg(buy, PB).setup.key})  # type: ignore[union-attr]
    res = decide_inputs(fi, PB, used)
    assert res.decision is not None and res.decision["side"] == "SELL"


def test_rule13_log_reason_is_the_one_that_got_furthest_and_a_tie_goes_to_the_buy() -> None:
    far = leg_data(lows=(4060.0, 4040.0, 4000.0), last=4038.0)  # price not above the order price (rule 6)
    early = leg_data(m5_highs=(4120.0,))  # refused at rule 3
    fi = bot.FibInputs(None, "none", [early, as_sell(far)], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0)
    res = decide_inputs(fi, PB)
    assert res.decision is None and res.log["reason"] == "fib: price not above the order price"
    fi = bot.FibInputs(
        None, "none", [early, as_sell(early)], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0
    )
    res = decide_inputs(fi, PB)
    assert res.log["reason"] == "fib: M5 trend (H100 not above the M5 high)"
    assert res.log["leg"].startswith("L0 4000.00")  # the BUY's numbers, not the SELL's (negated)


# --- rule 14: the row and the log -----------------------------------------------------------------------------------


def test_rule14_row_fields_structure_and_log_columns() -> None:
    res = decide_inputs(range_inputs(), rng_p(max_entry_frac=0.5))
    d = res.decision
    assert d is not None
    assert list(d) == bot.LEDGER_COLUMNS and d["reader"] == "bot2e"
    assert d["fill"] == d["exit"] == d["why"] == d["r_net"] == d["at_decision_r"] == d["missed_by"] == ""
    fi = bot.FibInputs(None, "none", [leg_data()], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0)
    res = decide_inputs(fi, PB)
    d = res.decision
    assert d is not None
    s = d["structure"]
    for part in (
        "bot2e fib M5 BUY", "Lean none", "L0 4000.00@", "H100 4100.00@", "23.6 % 4023.60", "38.2 % 4038.20",
        "61.8 % 4061.80", "run of 3 lows", "divergence on MACD True, on RSI True", "M5 trend: H100 4100.00 beyond the M5 high",
        "trend legs", "Entry level 38.2 % = 4038.20", "order price 4038.20", "stop 3999.50", "target 4161.30",
        "ladder step 1.618", "planned R", "withdraw beyond 4100.00", "Parameters: mode=fib",
        "order_life_bars=24", "fib_entry=0.382",
    ):  # fmt: skip
        assert part in s, part
    assert (d["entry"], d["stop"], d["target"]) == ("4038.20", "3999.50", "4161.30")
    log = res.log
    assert set(log) == set(bot.LOG_COLUMNS)
    for col in ("r10", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "order", "stop", "target", "ladder", "r"):
        assert log[col], col
    assert log["order"] == "4038.20" and log["ladder"] == "1.618" and log["reason"] == "order written"


def test_every_reason_the_code_can_give_is_ranked() -> None:
    src = Path(bot.__file__).read_text(encoding="utf-8")
    given = set(re.findall(r'(?:done\(|\.reason = |FibOut\(|why = )\s*"([^"]+)"', src))
    given |= set(re.findall(r'\n\s+(?:reason|why)=?"([^"]+)"', src))
    assert "fib: no live leg" in given and "order written" in given and len(given) > 20
    missing = {q for q in given if q not in bot.RANK}
    assert not missing, missing
    assert len(bot.RANK) == len(bot.REASONS)  # no reason twice


# --- rule 12: the order's life (eye/score.py) --------------------------------------------------------------------------


def life_row(
    side: str, entry: float, stop: float, target: float, *, life: int = 24, marker: str = ""
) -> dict:
    return {
        "id": "T-1", "cutoff_thai": "2026-10-07 07:00", "decided_at": "07/10 07:25", "side": side,
        "entry": f"{entry:.2f}", "stop": f"{stop:.2f}", "target": f"{target:.2f}", "trigger": "",
        "structure": f"bot2e fib x. {marker}. Parameters: mode=fib order_life_bars={life} min_r=2",
    }  # fmt: skip


CUT = pd.Timestamp("2026-10-07 07:30", tz=TH).tz_convert("UTC")


def sc(row: dict, rows: list[tuple[float, float, float, float]]) -> dict[str, str]:
    return score_mod.score(row, _bars(rows), CUT)


def test_rule12_fill_price_gap_and_window_buy_and_sell() -> None:
    # BUY limit 4040: opens above and trades down to it - filled AT the price
    r = sc(life_row("BUY", 4040, 4020, 4100), [(4050, 4052, 4039, 4045), (4045, 4101, 4044, 4100)])
    assert r["fill"] == "07/10 07:30" and r["why"] == "target" and r["exit"] == "4100.00"
    assert r["r_net"] == f"{(4100 - 4040 - 0.3) / 20:.2f}"
    # a gap through the limit fills at the open; R = (exit - fill - spread) / the PLANNED risk (order - stop = 20),
    # not the 10 between the gap fill and the stop: (4100 - 4030 - 0.3) / 20
    g = sc(life_row("BUY", 4040, 4020, 4100), [(4030, 4035, 4028, 4032), (4032, 4101, 4031, 4100)])
    assert g["r_net"] == f"{(4100 - 4030 - 0.3) / 20:.2f}" and g["why"] == "target"
    # SELL limit 4160: a gap above fills at the open: gap fill at 4170, exit 4100: (4170 - 4100 - 0.3) / (4180 - 4160)
    s = sc(life_row("SELL", 4160, 4180, 4100), [(4170, 4172, 4165, 4168), (4168, 4169, 4099, 4100)])
    assert s["r_net"] == f"{(4170 - 4100 - 0.3) / 20:.2f}" and s["why"] == "target"
    s2 = sc(life_row("SELL", 4160, 4180, 4100), [(4150, 4161, 4148, 4155), (4155, 4156, 4099, 4100)])
    assert s2["r_net"] == f"{(4160 - 4100 - 0.3) / 20:.2f}"  # opens under the price: filled at the price


def test_rule12_fill_window_expiry_and_open() -> None:
    quiet = (4060.0, 4065.0, 4055.0, 4060.0)
    never = [quiet] * 3
    # three bars of life: touching on the third (last included) fills; on a fourth is too late
    third = [quiet, quiet, (4060, 4062, 4039, 4045), (4045, 4101, 4044, 4100)]
    assert sc(life_row("BUY", 4040, 4020, 4100, life=3), third)["fill"] == "07/10 07:40"
    fourth = [quiet, quiet, quiet, (4060, 4062, 4039, 4045), (4045, 4101, 4044, 4100)]
    late = sc(life_row("BUY", 4040, 4020, 4100, life=3), fourth)
    assert late["why"] == "no fill" and late["fill"] == "" and late["r_net"] == "0.0"
    # not yet touched and the window is not over in the stored bars: open; over: expired
    assert sc(life_row("BUY", 4040, 4020, 4100, life=4), never)["why"] == "open"
    assert sc(life_row("BUY", 4040, 4020, 4100, life=3), never)["why"] == "no fill"
    # the SELL mirror
    sell_q = (4020.0, 4025.0, 4015.0, 4020.0)
    assert sc(life_row("SELL", 4040, 4060, 3980, life=3), [sell_q] * 3)["why"] == "no fill"
    assert sc(life_row("SELL", 4040, 4060, 3980, life=3), [sell_q, sell_q])["why"] == "open"
    # the window length is the row's parameter, not a constant
    many = [quiet] * 30 + [(4060, 4062, 4039, 4045), (4045, 4101, 4044, 4100)]
    assert sc(life_row("BUY", 4040, 4020, 4100, life=40), many)["why"] == "target"
    assert sc(life_row("BUY", 4040, 4020, 4100, life=24), many)["why"] == "no fill"


def test_rule12_withdrawal_only_before_the_fill_bar_with_its_reason() -> None:
    quiet = (4060.0, 4065.0, 4055.0, 4060.0)
    # the target touched before the fill: withdrawn
    t = sc(life_row("BUY", 4040, 4020, 4100), [(4060, 4101, 4055, 4100), (4100, 4100, 4039, 4045)])
    assert t["why"] == "no fill (stop or target first)" and t["fill"] == "" and t["r_net"] == "0.0"
    # a bar that both fills and touches the target keeps the fill (and the target does not count on the fill bar)
    keep = sc(life_row("BUY", 4040, 4020, 4100), [(4060, 4101, 4039, 4045), (4045, 4101, 4044, 4100)])
    assert keep["fill"] == "07/10 07:30" and keep["why"] == "target"
    # H100: strictly above withdraws, a touch does not; the reason names the level
    m = "withdraw beyond 4090.00"
    h = sc(
        life_row("BUY", 4040, 4020, 4200, marker=m), [(4060, 4090.01, 4055, 4060), (4060, 4062, 4039, 4045)]
    )
    assert h["why"] == "no fill (withdrawn: beyond 4090.00)"
    touch = sc(
        life_row("BUY", 4040, 4020, 4200, marker=m), [(4060, 4090.0, 4055, 4060), (4060, 4062, 4039, 4045)]
    )
    assert touch["fill"] == "07/10 07:35"
    on_fill = sc(life_row("BUY", 4040, 4020, 4200, marker=m), [(4060, 4091, 4039, 4045)])
    assert on_fill["fill"] == "07/10 07:30"  # fills and crosses H100 on one bar: the fill stands
    sell = sc(life_row("SELL", 4040, 4060, 3900, marker="withdraw beyond -4000.00".replace("-", "")),
              [(4020, 4025, 3999.9, 4020), (4020, 4041, 4015, 4030)])  # fmt: skip
    assert sell["why"] == "no fill (withdrawn: beyond 4000.00)"
    # where a target and an H100 crossing share a bar, the target's reason is written
    both = sc(
        life_row("BUY", 4040, 4020, 4100, marker=m), [(4060, 4101, 4055, 4100), (4100, 4100, 4039, 4045)]
    )
    assert both["why"] == "no fill (stop or target first)"
    # an earlier H100 crossing beats a later target
    first = sc(
        life_row("BUY", 4040, 4020, 4100, marker=m), [(4060, 4095, 4055, 4060), (4060, 4101, 4055, 4100)]
    )
    assert first["why"] == "no fill (withdrawn: beyond 4090.00)"
    # a bar AFTER the fill bar never withdraws: the trade is held
    held = sc(
        life_row("BUY", 4040, 4020, 4300, marker=m), [(4060, 4062, 4039, 4045), (4045, 4095, 4044, 4090)]
    )
    assert held["fill"] == "07/10 07:30" and held["why"] == "open"
    del quiet


def test_rule12_range_break_by_a_setup_timeframe_close() -> None:
    marker5 = "range break M5 close beyond 4000.0000 / 4100.0000"
    marker15 = "range break M15 close beyond 4000.0000 / 4100.0000"
    # BUY limit 4040 not touched; bar 1 (07:35) closes under 4000
    bars = [(4060, 4065, 4055, 4060), (4060, 4062, 3990, 3999.9), (3999.9, 4000, 3990, 3995)]
    m5 = sc(life_row("BUY", 4040, 3990, 4090, marker=marker5), [bars[0], (4060, 4062, 4055, 3999.9), bars[0]])
    assert m5["why"] == "no fill (withdrawn: range break M5)"
    # a close exactly on the level is not beyond it
    ok = sc(
        life_row("BUY", 4040, 3990, 4090, marker=marker5),
        [(4060, 4062, 4055, 4000.0), (4060, 4062, 4039, 4045)],
    )
    assert ok["fill"] == "07/10 07:35"
    # above the upper level, strictly
    up = sc(
        life_row("SELL", 4040, 4120, 4010, marker=marker5),
        [(4020, 4025, 4015, 4100.1), (4020, 4041, 4015, 4030)],
    )
    assert up["why"] == "no fill (withdrawn: range break M5)"
    # M15: only the M5 bar that closes with an M15 bar counts - 07:40 opens at minute 40 (40 % 15 == 10)
    offbar = [
        (4060, 4065, 4055, 4060),
        (4060, 4062, 4055, 3999.9),
        (4060, 4062, 4055, 4060),
    ]  # 07:35 closes low
    r15 = sc(life_row("BUY", 4040, 3990, 4090, marker=marker15), [*offbar, (4060, 4062, 4039, 4045)])
    assert r15["fill"] == "07/10 07:45"  # the 07:35 close is not an M15 close
    onbar = [
        (4060, 4065, 4055, 4060),
        (4060, 4062, 4055, 4060),
        (4060, 4062, 4055, 3999.9),
    ]  # 07:40 closes low
    w15 = sc(life_row("BUY", 4040, 3990, 4090, marker=marker15), [*onbar, (4060, 4062, 4039, 4045)])
    assert w15["why"] == "no fill (withdrawn: range break M15)"
    # a fill on the same bar as the closing break keeps the fill
    same = sc(life_row("BUY", 4040, 3990, 4090, marker=marker5), [(4060, 4062, 4030, 3999.0)])
    assert same["fill"] == "07/10 07:30"


def test_rule12_hold_fill_bar_stop_only_next_bar_both_is_stop_gap_exit() -> None:
    row = life_row("BUY", 4040, 4020, 4100)
    # the fill bar: only the stop counts - a target on the fill bar is ignored (next bar reaches it)
    a = sc(row, [(4050, 4101, 4039, 4045), (4045, 4101, 4044, 4100)])
    assert a["why"] == "target" and a["exit"] == "4100.00"
    # a stop on the fill bar counts: filled at 4040, stopped at 4020
    b = sc(row, [(4050, 4052, 4019, 4030)])
    assert b["why"] == "stop" and b["exit"] == "4020.00"
    assert b["r_net"] == f"{(4020 - 4040 - 0.3) / 20:.2f}"
    # from the next bar a bar touching both counts as the stop
    c = sc(row, [(4050, 4052, 4039, 4045), (4045, 4101, 4019, 4050)])
    assert c["why"] == "stop"
    # a bar that opens beyond the stop exits at its open
    d = sc(row, [(4050, 4052, 4039, 4045), (4010, 4012, 4005, 4008)])
    assert d["why"] == "stop" and d["exit"] == "4010.00"
    assert d["r_net"] == f"{(4010 - 4040 - 0.3) / 20:.2f}"
    # the fill bar itself opens beyond the stop: filled at its open, exits at its open - a loss of the spread
    e = sc(row, [(4010, 4030, 4005, 4025)])
    assert e["why"] == "stop" and e["exit"] == "4010.00" and e["r_net"] == f"{-0.3 / 20:.2f}"
    # neither: open, with the fill time
    f = sc(row, [(4050, 4052, 4039, 4045), (4045, 4060, 4030, 4050)])
    assert f["why"] == "open" and f["fill"] == "07/10 07:30" and f["r_net"] == ""
    # the SELL mirror: limit 4160, stop 4180, target 4100
    srow = life_row("SELL", 4160, 4180, 4100)
    assert sc(srow, [(4150, 4161, 4099, 4140), (4140, 4141, 4099, 4100)])["why"] == "target"
    assert sc(srow, [(4150, 4181, 4148, 4170)])["exit"] == "4180.00"
    assert sc(srow, [(4150, 4161, 4148, 4155), (4155, 4181, 4099, 4150)])["why"] == "stop"
    g = sc(srow, [(4150, 4161, 4148, 4155), (4190, 4195, 4185, 4190)])
    assert g["why"] == "stop" and g["exit"] == "4190.00"
    assert g["r_net"] == f"{(4160 - 4190 - 0.3) / 20:.2f}"


def test_rule12_legacy_rows_without_the_life_marker_score_as_before() -> None:
    legacy = life_row("BUY", 4040, 4020, 4100)
    legacy["structure"] = "bot2e fib x"  # no order_life_bars: the old scorer
    bars = [(4030, 4035, 4028, 4032), (4032, 4101, 4031, 4100)]
    old = score_mod.score(legacy, _bars(bars), CUT)
    new = sc(life_row("BUY", 4040, 4020, 4100), bars)
    assert old["r_net"] != new["r_net"]  # the old scorer fills at the entry price and divides by entry - stop
    assert old["r_net"] == f"{(4100 - 4040 - 0.3) / 20:.2f}"


@needs_data
def test_rule12_an_expired_order_frees_max_orders_in_the_walk(full, monkeypatch) -> None:
    """Event order: the bar just closed updates the orders already written (an order that has waited its last
    bar is expired) and only then the decision counts max_orders. A stand-in decide writes a limit that can
    never fill, with a 3-bar life: written at once, pending for two decisions, free again at the third."""
    calls: list[bool] = []

    def fake(frames, now, p, used=frozenset(), pending=False, windowed=True):
        calls.append(pending)
        log = dict.fromkeys(bot.LOG_COLUMNS, "")
        log["reason"] = "order pending" if pending else "order written"
        if pending:
            return bot.Result(log)
        row = {c: "" for c in bot.LEDGER_COLUMNS}
        t = now.tz_convert(TH) - pd.Timedelta(minutes=5)
        row.update(
            cutoff_thai=f"{t:%Y-%m-%d} 07:00", decided_at=f"{t:%d/%m %H:%M}", side="BUY", entry="1.00", stop="0.50",
            target="99998", reader="bot2e", structure="bot2e fib x. Parameters: mode=fib order_life_bars=3",
        )  # fmt: skip
        return bot.Result(log, row, key=f"k{len(used)}")

    monkeypatch.setattr(bot, "decide", fake)
    mine, _ = bot.walk_days(["2026-04-06"], bot.Params(mode="fib", order_life_bars=3), full)
    asia = calls[:25]  # the Asia window 07:00..09:00 is 25 decisions
    assert asia[:8] == [False, True, True, False, True, True, False, True]  # written, 2 waiting, free, ...
    assert len(mine) >= 8


# --- the stored bars: acceptance cases (BOT_RULES rule 14) ---------------------------------------------------------


def at(full, text: str, **kw):
    """decide() at a Thai time with the window test off; returns the Result and the per-side outcomes."""
    p = bot.Params(mode="fib", **kw)
    now = now_at(text)
    frames = bot.cut(full, now)
    return bot.decide(frames, now, p, windowed=False), bot.fib_inputs(frames, now, p), p


@needs_data
@pytest.mark.parametrize("text", ["2026-10-22 19:30", "2026-10-22 22:00", "2026-10-23 07:00",
                                  "2026-10-23 13:00", "2026-10-23 19:30", "2026-10-23 22:00"])  # fmt: skip
def test_acceptance_h1_lean_is_sell(full, text) -> None:
    res, fi, _ = at(full, text)
    assert fi.lean == "SELL" and res.log["lean"].startswith("SELL (Hf ")


@needs_data
def test_acceptance_07_oct_0730_lean_buy_sell_candidate_refused_by_the_lean(full) -> None:
    res, fi, p = at(full, "2026-10-07 07:30")
    assert fi.lean == "BUY" and "Lf 4104.21" in fi.lean_text
    buy, sell = (bot.analyse_leg(d, p) for d in fi.datas)
    # the SELL candidate: top 4184.25, the 100 % low 4143.51 - no order, by rule 1
    assert sell.info["leg"].startswith("L0 4184.25@") and "H100 4143.51@" in sell.info["leg"]
    assert sell.reason == "fib: against the H1 lean" and sell.setup is None
    # the BUY candidate (reported): L0 4154.21, H100 4170.48 - it has run (an M5 high of 4184.25 after L0)
    assert buy.info["leg"].startswith("L0 4154.21@") and "H100 4170.48@" in buy.info["leg"]
    assert buy.reason == "fib: leg has run (100 % traded)" and buy.setup is None
    assert res.decision is None


@needs_data
def test_acceptance_27_oct_1830_buy_leg(full) -> None:
    res, fi, p = at(full, "2026-10-27 18:30", fib_entry=0.618)
    assert fi.lean == "SELL"  # reported: Hf 4034.23, so the BUY leg is refused by the lean
    buy = bot.analyse_leg(fi.datas[0], p)
    assert buy.reason == "fib: against the H1 lean" and buy.info["leg"].startswith("L0 3989.14@")
    assert "H100 4025.45@" in buy.info["leg"] and "vs M5 high 4019.18@" in buy.info["r3"]  # rule 3 passes
    free = replace(fi.datas[0], lean=None)  # with the lean set aside, the rules after it
    at618 = bot.analyse_leg(free, p)
    assert (
        at618.info["r6"].startswith("order price 4011.58")
        and at618.reason == "fib: price not above the order price"
    )
    assert float(res.log["price"]) == 4010.95
    q = bot.Params(mode="fib", fib_entry=0.382)
    at382 = bot.analyse_leg(free, q)
    assert at382.info["r6"].startswith("order price 4003.01")
    assert abs(4010.95 - 4003.01) == pytest.approx(7.94, abs=0.005) and pytest.approx(9.0775) == 0.25 * 36.31
    # reported: a band lies in the way, so the ladder step is "band" and R is far under 2 - no order
    assert at382.info["r8"] == "target 4004.47 (step band)" and at382.reason == "reward under 2R"
    assert float(at382.info["r"]) < 2.0


@needs_data
def test_acceptance_19_oct_0700_buy_leg_at_0618(full) -> None:
    _, fi, p = at(full, "2026-10-19 07:00")
    assert fi.lean == "BUY"
    buy = bot.analyse_leg(fi.datas[0], p)
    assert buy.info["leg"].startswith("L0 4155.81@") and "H100 4198.73@" in buy.info["leg"]
    assert buy.info["r6"].startswith("order price 4182.33")
    assert buy.info["r8"] == "target 4188.23 (step band)"  # the target lies above the order price
    assert (
        buy.reason == "reward under 2R" and buy.setup is None and float(buy.info["r"]) == pytest.approx(0.33)
    )


# --- the stored bars: closed bars only, the mirror, the walk -------------------------------------------------------------


@needs_data
def test_fib_path_has_no_lookahead(full) -> None:
    """Frames cut at ``now`` from the real data and from data whose later bars are noise give the same
    decision and log; an uncut frame is refused."""
    rng = np.random.default_rng(5)
    for text in ("2026-10-27 20:00", "2026-10-13 19:35", "2026-10-26 20:00"):
        now = now_at(text)
        noisy = {}
        for tf, df in full.items():
            df = df.copy()
            late = np.asarray(df.index + bot.STEP[tf] > now)
            base = rng.normal(4000, 80, int(late.sum()))
            df.loc[late, "open"] = base
            df.loc[late, "close"] = base + rng.normal(0, 5, int(late.sum()))
            df.loc[late, "high"] = base + 60
            df.loc[late, "low"] = base - 60
            noisy[tf] = df
        for p in (
            bot.Params(mode="fib", fib_entry=0.382, min_r=0.0),
            bot.Params(mode="fib", fib_tf="M15", fib_count="on", major_tf="H1"),
        ):
            a = bot.decide(bot.cut(full, now), now, p)
            b = bot.decide(bot.cut(noisy, now), now, p)
            assert a.log == b.log and a.decision == b.decision and a.key == b.key
    now = now_at("2026-10-27 20:00")
    with pytest.raises(ValueError, match="had not closed"):
        bot.decide(bot.cut(full, now + pd.Timedelta(hours=1)), now, bot.Params(mode="fib"))
    # the warm-up: a frame short of 1,500 closed bars gives no decision
    short = {tf: df.iloc[:1000] for tf, df in bot.cut(full, now).items()}
    short["M5"] = bot.cut(full, now)["M5"]
    res = bot.decide(short, now, bot.Params(mode="fib"), windowed=False)
    assert res.log["reason"] == "warm-up"


@needs_data
def test_fib_mirror_on_stored_bars(full) -> None:
    """The price-negated series (k - price) gives the mirrored answer: the lean flips, the reasons are the same,
    and an order's prices are k - the original's (rule 11 is not mirrored, but the range is symmetric)."""
    k = 10000.0

    def mirror(df: pd.DataFrame) -> pd.DataFrame:
        m = df.copy()
        m["open"], m["close"] = (k - df.open).round(2), (k - df.close).round(2)
        m["high"], m["low"] = (k - df.low).round(2), (k - df.high).round(2)
        return m

    mirrored = {tf: mirror(df) for tf, df in full.items()}
    flip = {"BUY": "SELL", "SELL": "BUY", "none": "none"}
    p = bot.Params(mode="fib", fib_entry=0.382, min_r=0.0, max_entry_frac=0.35)
    for text in ("2026-10-07 07:30", "2026-10-19 07:00", "2026-10-22 19:30", "2026-10-27 18:30", "2026-10-13 19:35",
                 "2026-10-23 13:00"):  # fmt: skip
        now = now_at(text)
        a = bot.decide(bot.cut(full, now), now, p, windowed=False)
        b = bot.decide(bot.cut(mirrored, now), now, p, windowed=False)
        assert a.log["reason"] == b.log["reason"], text
        assert flip[a.log["lean"].split(" ")[0]] == b.log["lean"].split(" ")[0], text
        assert (a.decision is None) == (b.decision is None), text
        if a.decision is not None and b.decision is not None:
            assert flip[a.decision["side"]] == b.decision["side"]
            for col in ("entry", "stop", "target"):
                assert float(b.decision[col]) == pytest.approx(k - float(a.decision[col]), abs=0.011)


@needs_data
def test_fib_walk_one_window_writes_known_reasons_and_scores(full, tmp_path) -> None:
    """The walk over one day's Asia window on stored bars: every log row has a known reason, the row layout is
    the ledger's, a written order is scored by the new rules."""
    p = bot.Params(mode="fib", fib_entry=0.382, min_r=0.0, max_entry_frac=0.35)
    mine, logs = bot.walk_days(["2026-10-13"], p, full)
    assert len(logs) == 25 + 25 + 43 and all(r["reason"] in bot.RANK for r in logs)
    assert set(logs[0]) == set(bot.LOG_COLUMNS)
    for r in mine:
        assert list(r) == bot.LEDGER_COLUMNS and "order_life_bars=24" in r["structure"]
        scored = score_mod.score(r, score_mod.bars(), score_mod.start_of(r, {}))
        assert scored["why"]
    ledger, log = tmp_path / "bot_ledger.csv", tmp_path / "bot_log.csv"
    bot._write(ledger, bot.LEDGER_COLUMNS, mine)
    bot._write(log, bot.LOG_COLUMNS, logs)
    assert len(bot._read(log, bot.LOG_COLUMNS)) == len(logs)


@needs_data
@pytest.mark.parametrize(
    ("text", "kw", "row", "scored"),
    [
        (  # rule 6 fib_early, rule 7 line_tight, rule 8 the band step, a BUY leg under a BUY lean
            "2026-10-19 07:00",
            {"fib_entry": 0.382, "fib_early": 0.10, "fib_stop": "line_tight"},
            ("BUY", "4176.50", "4171.71", "4188.23", "band", "2.39"),
            ("19/10 07:20", "4171.71", "stop", "-1.06"),
        ),
        (  # a SELL leg at the 0.236 level under a SELL lean (the mirror of every BUY rule)
            "2026-10-26 07:00",
            {"fib_entry": 0.236},
            ("SELL", "3999.16", "4006.95", "3974.25", "band", "3.16"),
            ("26/10 08:15", "4006.95", "stop", "-1.04"),
        ),
        (  # rule 11: the range, no lean and no M5 trend (the 2R floor and the reach are relaxed here)
            "2026-10-13 19:35",
            {"min_r": 0.0, "fib_entry": 0.382, "max_entry_frac": 0.35},
            ("SELL", "4188.61", "4193.07", "4180.17", "range edge", "1.82"),
            ("13/10 19:40", "4180.17", "target", "1.83"),
        ),
    ],
)  # fmt: skip
def test_stored_bar_orders_are_written_and_scored_by_the_new_rules(full, text, kw, row, scored) -> None:
    """The first stored-bar cases that write an order: the numbers are what the code gives (hand-checked), and the
    scorer's realised result for each (rule 12): the fill bar, the exit, the realised R."""
    p = bot.Params(mode="fib", **kw)
    now = now_at(text)
    res = bot.decide(bot.cut(full, now), now, p)
    d = res.decision
    assert d is not None
    assert (d["side"], d["entry"], d["stop"], d["target"], res.log["ladder"], res.log["r"]) == row
    d["id"] = "X"
    got = score_mod.score(d, score_mod.bars(), score_mod.start_of(d, {}), p.spread)
    assert (got["fill"], got["exit"], got["why"], got["r_net"]) == scored


@needs_data
def test_a_leg_is_used_across_runs_the_keys_of_the_ledger_rows_count(full) -> None:
    """Rule 2: a leg or range is used once an order is written on it, in this run or an earlier one. Two walks
    over overlapping days: the second, given the first's rows as the ledger, writes none of the same keys; the
    row carries its key, and a row without one (any other reader) adds none."""
    p = bot.Params(mode="fib", fib_entry=0.382, min_r=0.0)
    day = "2026-10-13"
    first, _ = bot.walk_days([day], p, full)
    assert first, "the test day writes an order with these parameters"
    keys = {bot.row_key(r) for r in first}
    assert all(k and k.count("|") == 3 for k in keys)
    second, _ = bot.walk_days([day, "2026-10-14"], p, full, first)
    assert not keys & {bot.row_key(r) for r in second}
    # without the ledger rows the same leg is written again (the control)
    again, _ = bot.walk_days([day], p, full)
    assert {bot.row_key(r) for r in again} == keys
    assert bot.row_key({"structure": "bot2e 5m BUY ..."}) == "" and bot.row_key({}) == ""


@needs_data
def test_run_seeds_used_from_every_kept_row_later_days_too(full, tmp_path) -> None:
    """Rule 2 through run(): the rows of the days a run walks are replaced, every other row is kept and its
    key is used - a row on a LATER day too. The same leg is not written on the earlier day again."""
    p = bot.Params(mode="fib", fib_entry=0.382, min_r=0.0)
    ledger, log = tmp_path / "l.csv", tmp_path / "g.csv"
    bot.run("2026-10-13", "2026-10-13", p, ledger, log)
    rows = bot._read(ledger, bot.LEDGER_COLUMNS)
    assert rows and all(bot.row_key(r) for r in rows)
    keys = {bot.row_key(r) for r in rows}
    # move the ledger's rows to a later day (as if written there), then walk the earlier day
    later = [
        {**r, "cutoff_thai": "2026-10-14 07:00", "id": r["id"].replace("20261013", "20261014")} for r in rows
    ]
    bot._write(ledger, bot.LEDGER_COLUMNS, later)
    bot.run("2026-10-13", "2026-10-13", p, ledger, log)
    after = bot._read(ledger, bot.LEDGER_COLUMNS)
    on_13 = [r for r in after if r["cutoff_thai"][:10] == "2026-10-13"]
    assert not keys & {bot.row_key(r) for r in on_13}  # the kept later rows' keys are used
    assert [r for r in after if r["cutoff_thai"][:10] == "2026-10-14"] == later  # and the later rows stay
    # control: with the later rows gone the earlier day writes the same keys again
    bot._write(ledger, bot.LEDGER_COLUMNS, [])
    bot.run("2026-10-13", "2026-10-13", p, ledger, log)
    assert keys <= {bot.row_key(r) for r in bot._read(ledger, bot.LEDGER_COLUMNS)}
