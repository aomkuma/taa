"""Tests for eye/bot2e.py (eye/BOT_SPEC.md section 10).

The step logic is tested on constructed pivots (``analyse_view``), where every number is chosen; the
no-look-ahead, mirror, window and ledger tests run on the stored gold bars of 2026-04-06 and skip when the
data is not on the machine.
"""

from __future__ import annotations

import csv
import importlib
import sys
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
P = bot.Params()
BOTH = bot.Params(min_r=0.0, div_mode="both")  # the earlier rule: divergence on both oscillators
P0 = bot.Params(min_r=0.0)  # tests of the steps drop the 2R floor; test_reward_floor tests the floor itself


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
        got = bot.decide(frames, now, bot.Params(h1_tf="H4")).log["side"]
        assert got == (want or "")
        sides.add(got)
    assert sides - {""}  # at least one of them had a side


@needs_data
def test_entry_tfs_selects_the_timeframes(full) -> None:
    now = now_at("2026-04-06 21:20")
    frames = bot.cut(full, now)
    assert bot.decide(frames, now, P0).log["tf"] == "M5"
    assert bot.decide(frames, now, bot.Params(min_r=0.0, entry_tfs="M5")).log["tf"] == "M5"
    only15 = bot.decide(frames, now, bot.Params(min_r=0.0, entry_tfs="M15"))
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
    result = research.run_variant("t", {"min_r": 0.0}, "2026-04-06", "2026-04-06", full, m5, root=tmp_path)
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


# --- revision 5 (R13-R17): the owner's Fibonacci -------------------------------------------------------------

PF = bot.Params(mode="fib", min_r=0.0, fib_target="level")  # the geometry tests drop the 2R floor
FIB_BANDS = [(4790.0, 4800.0)]  # an H1 band above the leg (the ext targets need none)


def fib_sell_inputs(pv, hi, lo, close):
    """The same leg as a SELL's real data: prices negated, kinds swapped; read back through the view."""
    sw = [Swing(SwingKind.HIGH if q.low else SwingKind.LOW, -q.price, q.pos, q.pos, q.pos, q.pos) for q in pv]
    idx = pd.date_range(T_START, periods=len(close), freq="15min")
    df = pd.DataFrame({"open": -close, "high": -lo, "low": -hi, "close": -close}, index=idx)
    v = bot._view_arrays(df, -1)
    return bot.to_view(sw, -1), v[0], v[1], v[2], df


def test_fib_range_formulas_buy_and_sell() -> None:
    """R17: a range 4600-4700. Buy: limit 12 % (4612), stop under -27 % (4573) - buffer, target the range high
    (the owner: sideways, around 100 %) - buffer. Sell (the mirror): limit 88 % (4688), stop over 127 % (4727)
    + buffer, target the range low + buffer. R = 87.2 / 39.5 = 2.21, so the 2R floor passes it."""
    n = 30
    close = np.full(n, 4650.0)
    hi, lo = close + 1.0, close - 1.0
    out = bot.analyse_range(4600.0, 100.0, hi, lo, close, PF)
    s = out.setup
    assert out.reason == "order written" and s is not None
    assert s.entry_v == pytest.approx(4612.0) and s.stop_v == pytest.approx(4573.0 - PF.stop_buffer)
    assert s.target_v == pytest.approx(4700.0 - PF.target_buffer)
    assert s.r == pytest.approx((s.target_v - s.entry_v - PF.spread) / (s.entry_v - s.stop_v))
    assert s.r == pytest.approx(2.21, abs=0.01)
    assert bot.analyse_range(4600.0, 100.0, hi, lo, close, bot.Params(mode="fib")).setup is not None
    # a narrow range cannot pay for the fixed buffers and spread: under 2R
    mid = np.full(n, 4605.0)
    narrow = bot.analyse_range(4600.0, 10.0, mid + 1, mid - 1, mid, bot.Params(mode="fib"))
    assert narrow.reason == "reward under 2R" and narrow.setup is None
    # the sell: the same range seen in the mirror (prices negated, highs and lows swapped)
    sell = bot.analyse_range(-4700.0, 100.0, -lo, -hi, -close, PF)
    t = sell.setup
    assert t is not None and -t.entry_v == pytest.approx(4688.0)
    assert -t.stop_v == pytest.approx(4727.0 + PF.stop_buffer) and -t.target_v == pytest.approx(4600.0 + 0.5)
    assert t.r == pytest.approx(s.r)
    # the price must be on the far side of the limit; a close beyond the stop level voids the range
    under = np.full(n, 4610.0)
    res = bot.analyse_range(4600.0, 100.0, under + 1, under - 1, under, PF)
    assert res.reason == "fib: price past the range edge"
    broke = close.copy()
    broke[5] = 4570.0
    assert bot.analyse_range(4600.0, 100.0, hi, lo, broke, PF).reason == "fib: range broken"
    # R8: the target traded since the pivot
    h2 = hi.copy()
    h2[7] = 4699.5
    assert bot.analyse_range(4600.0, 100.0, h2, lo, close, PF).reason == "setup already played out"


def test_fib_params_validated_and_in_text() -> None:
    """Every Revision 5 parameter is in Params.text(); a wrong value is refused; the defaults are 2e mode."""
    d = bot.Params()
    assert (d.mode, d.fib_tf, d.fib_entry, d.fib_target, d.fib_count, d.fib_range) == (
        "2e", "M15", 0.382, "ext161", "off", "off",
    )  # fmt: skip
    text = bot.Params(
        mode="fib",
        fib_tf="M5",
        fib_entry=0.236,
        fib_target="high",
        fib_count="on",
        fib_range="on",
    ).text()
    for part in (
        "mode=fib",
        "fib_tf=M5",
        "fib_entry=0.236",
        "fib_target=high",
        "fib_count=on",
        "fib_range=on",
    ):
        assert part in text
    for bad in (
        {"mode": "x"},
        {"fib_tf": "H1"},
        {"fib_target": "x"},
        {"fib_target": "ext200"},
        {"fib_count": "x"},
        {"fib_range": "x"},
        {"fib_side": "any"},  # removed: the H1 side is never ignored
        {"fib_side": "entry"},
        {"fib_leg": "trend"},  # removed: the counter leg is the only leg
        {"fib_high": "auto"},
    ):
        with pytest.raises(ValueError):
            bot.Params(**bad)


@needs_data
def test_2e_mode_default_is_unchanged(full) -> None:
    """mode "2e" (the default) after the Revision 5 refactor: the stored-data decision of 2026-04-06 21:20 in
    entry_mode setup is the pre-Revision-5 one, bit for bit, and the default Params still read mode 2e."""
    now = now_at("2026-04-06 21:20")
    res = bot.decide(bot.cut(full, now), now, P0)
    d = res.decision
    assert d is not None and bot.Params().mode == "2e"
    assert (d["entry"], d["trigger"], d["stop"], d["target"]) == ("4699.44", "4699.94", "4579.49", "4712.76")
    assert "mode=2e" in d["structure"]


@needs_data
def test_fib_decide_on_stored_bars_one_order_per_leg(full) -> None:
    """A fib-mode decision on stored bars is a plain limit with the leg in its text, closed bars only; the
    same leg is not written twice (key side|fib_tf|low time|high time)."""
    p = bot.Params(mode="fib", h1_mode="lows", min_r=0.0)
    hit = None
    for day in ("2026-04-06", "2026-04-07"):
        mine, _ = bot.walk_days([day], p, full)
        if mine:
            hit = mine[0]
            break
    assert hit is not None, "no fib decision on the two test days"
    assert hit["trigger"] == "" and "Leg low" in hit["structure"] and "mode=fib" in hit["structure"]
    day, hhmm = (
        hit["cutoff_thai"][:4] + "-" + hit["decided_at"][3:5] + "-" + hit["decided_at"][:2],
        hit["decided_at"][6:],
    )
    now = (pd.Timestamp(f"{day} {hhmm}", tz=TH) + pd.Timedelta(minutes=5)).tz_convert("UTC")
    first = bot.decide(bot.cut(full, now), now, p)
    assert first.decision is not None and first.key.count("|") == 3
    again = bot.decide(bot.cut(full, now), now, p, used=frozenset({first.key}))
    assert again.decision is None and again.log["reason"] == "setup already used"
    # the cut guard still holds in fib mode
    with pytest.raises(ValueError, match="had not closed"):
        bot.decide(bot.cut(full, now + pd.Timedelta(hours=1)), now, p)


# --- revision 6 (R18): the counter-move leg ------------------------------------------------------------------

# fib_leg "counter" is the default; counter_case's last close (4041) is 2.8 from the 38.2 % entry, inside R20
PC = bot.Params(mode="fib", min_r=0.0, fib_target="ext161")
R18_BANDS: list[tuple[float, float]] = []  # the ext targets need no H1 band


def counter_case(
    *,
    lows=(4060.0, 4040.0, 4000.0),
    div: bool = True,
    bounce: float = 4040.0,
    last: float = 4041.0,
    later: float = 4015.0,
):
    """A BUY in the view: a descending run H 4100 (pos 10), lows ``lows`` (the last is L0 = 4000), highs between
    them, the bounce high ``bounce`` (the pivot after L0), a later higher low 4015, then a close at ``last``.
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


def test_counter_leg_and_formulas() -> None:
    """R18: L0 = the latest fixed low lower than every later one; H100 = the highest high of the descending run
    into it; entry = L0 + x (H100 - L0) with a plain limit; stop L0 - buffer (0.236 level - buffer at 0.618);
    target ext127 / ext161; R by the formula."""
    pv, hi, lo, close, *_ = counter_case()
    leg = bot.fib_leg_counter(pv, close)
    assert leg is not None and (leg[0].price, leg[1].price) == (4000.0, 4100.0)
    assert [q.price for q in leg[2]] == [4060.0, 4040.0, 4000.0]
    for target, ext in (("ext127", 1.272), ("ext161", 1.618)):
        p = bot.Params(mode="fib", min_r=0.0, fib_target=target)
        s = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, p).setup
        assert s is not None and (s.lo_v, s.hi_v) == (4000.0, 4100.0)
        assert s.entry_v == pytest.approx(4038.2) and s.stop_v == 3999.5
        assert s.target_v == pytest.approx(4000.0 + ext * 100.0 - 0.5)
        assert s.r == pytest.approx((s.target_v - s.entry_v - p.spread) / (s.entry_v - s.stop_v))
        assert s.lo_pos == pv[-3].pos and s.hi_pos == pv[0].pos  # the key is made of L0's and H100's bars
    p618 = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_entry=0.618)
    pv2, hi2, lo2, close2, *_ = counter_case(bounce=4070.0, last=4063.0, later=4030.0)
    s618 = bot.analyse_fib(pv2, hi2, lo2, close2, R18_BANDS, p618).setup
    assert s618 is not None and s618.entry_v == pytest.approx(4061.8) and s618.stop_v == pytest.approx(4023.1)
    # the 2R floor (default min_r 2.0): R is about 3.2 for ext161 and about 2.2 for ext127 here
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, bot.Params(mode="fib", fib_target="ext161")).setup
    shallow = bot.Params(mode="fib", fib_target="level")  # no H1 band above: no target at all
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, shallow).reason == "fib: no target level"
    near = [(4050.0, 4060.0)]  # a level target just before 4050 gives R under 2
    assert bot.analyse_fib(pv, hi, lo, close, near, shallow).reason == "reward under 2R"


def test_counter_entry_conditions_and_invalidation() -> None:
    """The bounce must have traded above the entry level and the last close be above it; a close under L0 kills
    the leg; the newest low is not a bottom until a higher low follows it; R8 reads the bars after L0."""
    pv, hi, lo, close, *_ = counter_case(bounce=4030.0, last=4020.0)
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, PC).reason == "fib: no bounce above the entry level"
    pv, hi, lo, close, *_ = counter_case(last=4030.0)  # bounced to 4040 > 4038.2, now back under the level
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, PC).reason == "fib: price below the entry level"
    pv, hi, lo, close, *_ = counter_case()
    dead = close.copy()
    dead[-3] = 3999.0
    assert bot.analyse_fib(pv, hi, lo, dead, R18_BANDS, PC).reason == "fib: no live leg"
    assert bot.fib_leg_counter(pv[:-1], close) is None  # no later low after L0: L0 is not yet a bottom
    lw = lo.copy()
    lw[-3] = 3999.0  # the stop traded (the close stays up)
    assert bot.analyse_fib(pv, hi, lw, close, R18_BANDS, PC).reason == "setup already played out"
    hw = hi.copy()
    hw[-3] = 4170.0  # the 161.8 % target 4161.3 traded - above H100, so R19 (not R8) refuses it now
    assert bot.analyse_fib(pv, hw, lo, close, R18_BANDS, PC).reason == "fib: leg has run (100 % traded)"


def test_counter_sell_is_the_mirror() -> None:
    """The SELL view of the counter leg gives the BUY's numbers; the row has real (negated) prices."""
    pv, hi, lo, close, *_ = counter_case()
    buy = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, PC)
    spv, shi, slo, sclose, df = fib_sell_inputs(pv, hi, lo, close)
    sell = bot.analyse_fib(spv, shi, slo, sclose, R18_BANDS, PC)
    assert buy.setup is not None and sell.setup is not None
    for name in ("lo_v", "hi_v", "entry_v", "stop_v", "target_v", "r", "lo_pos", "hi_pos"):
        assert getattr(sell.setup, name) == pytest.approx(getattr(buy.setup, name)), name
    times = pd.DatetimeIndex(df.index)
    row = bot._fib_row(sell.setup, "SELL", -1, T_START + pd.Timedelta(days=1), times, "M15", PC)
    assert row["side"] == "SELL" and float(row["entry"]) == pytest.approx(-4038.2)
    assert "leg counter" in row["structure"] and "fib_leg=counter" in row["structure"]
    assert "highest fixed high of the descending run into L0" in row["structure"]
    # the SELL count: each fixed HIGH higher than the one before, into the top (the mirror of the BUY's lows)
    on = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_count="on")
    pvc, hic, loc, closec, macdc, rsic = counter_case()
    spvc, shic, sloc, sclosec, _ = fib_sell_inputs(pvc, hic, loc, closec)
    # the oscillators of the SELL view are the BUY view's (the mirror negates price and MACD, flips RSI)
    sc = bot.analyse_fib(spvc, shic, sloc, sclosec, R18_BANDS, on, macdc, rsic).setup
    assert sc is not None and sc.count is not None and len(sc.count.counted) == 3
    real_highs = [-q.price for q in sc.count.counted]  # the SELL's real highs (this test's data is negated)
    assert real_highs == [-4060.0, -4040.0, -4000.0]
    assert real_highs == sorted(real_highs)  # each fixed high higher than the one before
    assert sc.count.div_macd and sc.count.div_rsi


def test_counter_count_on_run_of_lower_lows_with_divergence() -> None:
    """R18 count on: 3-5 lower lows into L0 with divergence at L0 against the low before it; the entry stays the
    plain limit at the level (not the last close)."""
    on = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_count="on")
    pv, hi, lo, close, macd, rsi = counter_case()
    s = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, on, macd, rsi).setup
    assert s is not None and s.entry_v == pytest.approx(4038.2) and s.entry_v != close[-1]
    assert s.count is not None and len(s.count.counted) == 3 and s.count.div_macd and s.count.div_rsi
    pv, hi, lo, close, macd, rsi = counter_case(div=False)
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, on, macd, rsi).reason == "step2: no divergence"
    both = bot.Params(mode="fib", min_r=0.0, fib_count="on", div_mode="both")
    pv, hi, lo, close, macd, rsi = counter_case()
    macd2 = macd.copy()
    macd2[pv[-3].pos] = -9.0  # MACD no longer diverges, RSI does: "one" holds, "both" does not
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, on, macd2, rsi).setup is not None
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, both, macd2, rsi).reason == "step2: no divergence"
    pv, hi, lo, close, macd, rsi = counter_case(lows=(4040.0, 4000.0))
    two = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, on, macd, rsi)
    assert two.reason == "fib: count outside 3-5" and two.setup is None
    with pytest.raises(ValueError):
        bot.analyse_fib(pv, hi, lo, close, R18_BANDS, on)


def test_counter_row_text_names_everything() -> None:
    """The decision text names the mode, the counter leg, L0 / H100 with Thai times, levels, entry, stop, R."""
    pv, hi, lo, close, *_ = counter_case()
    s = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, PC).setup
    assert s is not None
    times = pd.date_range(T_START, periods=len(close), freq="15min")
    row = bot._fib_row(s, "BUY", 1, T_START + pd.Timedelta(days=1), times, "M15", PC)
    text = row["structure"]
    lo_t = f"{times[s.lo_pos].tz_convert(TH):%d/%m %H:%M}"
    hi_t = f"{times[s.hi_pos].tz_convert(TH):%d/%m %H:%M}"
    for part in (
        "bot2e fib M15 BUY", "mode fib", f"Leg low 4000.00@{lo_t}", f"high 4100.00@{hi_t}",
        "23.6 % 4023.60", "38.2 % 4038.20", "61.8 % 4061.80", "entry level 38.2 % = 4038.20",
        "stop 3999.50", "fib_entry=0.382", "mode=fib", "fib_count=off", "side h1", "fib_side=h1",
    ):  # fmt: skip
        assert part in text, part
    assert (row["entry"], row["stop"], row["trigger"]) == ("4038.20", "3999.50", "")
    assert row["target"] == f"{s.target_v:.2f}"


def test_fixed_targets_and_stops_follow_the_leg() -> None:
    """ext127 = low + 1.272 x leg - buffer, ext161 = low + 1.618 x leg - buffer, high = the 100 % - buffer,
    level has no fixed price; the stop is under the 0 % (under the 23.6 % level at a 61.8 % entry)."""
    cases = (("ext127", 4727.2 - 0.5), ("ext161", 4761.8 - 0.5), ("high", 4700.0 - 0.5), ("level", None))
    for name, want in cases:
        got = bot.fib_fixed_target_v(bot.Params(mode="fib", fib_target=name), 4600.0, 4700.0)
        assert got == (pytest.approx(want) if want is not None else None), name
    assert bot.fib_stop_v(bot.Params(mode="fib"), 4600.0, 4700.0) == pytest.approx(4599.5)
    assert bot.fib_stop_v(bot.Params(mode="fib", fib_entry=0.236), 4600.0, 4700.0) == pytest.approx(4599.5)
    assert bot.fib_stop_v(bot.Params(mode="fib", fib_entry=0.618), 4600.0, 4700.0) == pytest.approx(4623.1)


def test_removed_options_are_refused() -> None:
    """fib_side "any" / "entry" and fib_leg "trend" are gone: Params and the command line refuse them, and the
    only values left are the H1 side and the counter leg."""
    for bad in ({"fib_side": "any"}, {"fib_side": "entry"}, {"fib_leg": "trend"}):
        with pytest.raises(ValueError):
            bot.Params(**bad)
    base = ["--from", "2026-10-01", "--to", "2026-10-02", "--mode", "fib"]
    for flag, value in (("--fib-side", "entry"), ("--fib-side", "any"), ("--fib-leg", "trend")):
        with pytest.raises(SystemExit):
            bot.main([*base, flag, value])
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main([*base, "--fib-side", "h1", "--fib-leg", "counter"])
    finally:
        bot.run = orig  # type: ignore[assignment]
    assert seen["params"].fib_side == "h1" and seen["params"].fib_leg == "counter"
    assert "fib_side=h1" in bot.Params().text() and "fib_leg=counter" in bot.Params().text()


@needs_data
def test_fib_refuses_the_view_against_the_h1_side(full, monkeypatch) -> None:
    """The H1 side is never ignored: a BUY view that qualifies is refused while H1 says SELL, and a SELL view
    that qualifies is refused while H1 says BUY. 27/10 20:00 on stored bars; analyse_fib is stood in so that
    only the BUY view (positive prices) or only the SELL view (negated prices) qualifies. The control runs
    write the order when the qualifying view is the H1 side."""
    now = now_at("2026-10-27 20:00")
    frames = bot.cut(full, now)
    p = bot.Params(mode="fib", fib_tf="M5", h1_mode="lows")
    views: list[int] = []

    def only(sign_ok: int):
        def fake(pv, hi_v, lo_v, close_v, bands_v, p, macd_v=None, rsi_v=None, price_v=None):
            sign = 1 if float(close_v[-1]) > 0 else -1
            views.append(sign)
            if sign != sign_ok:
                return bot.FibOut("fib: no live leg")
            setup = bot.FibSetup("leg", 4000.0, 4100.0, 200, 195, 4038.2, 3999.5, 4161.3, 3.0)
            return bot.FibOut("order written", {}, setup)

        return fake

    cases = (("SELL", 1, True), ("BUY", -1, True), ("BUY", 1, False), ("SELL", -1, False))
    for h1_says, qualifying, refused in cases:
        monkeypatch.setattr(bot, "h1_side", lambda *a, h1_says=h1_says, **k: h1_says)
        monkeypatch.setattr(bot, "analyse_fib", only(qualifying))
        views.clear()
        res = bot.decide(frames, now, p)
        assert len(set(views)) == 1  # only the H1 side's view is ever evaluated
        if refused:
            assert res.decision is None
        else:
            assert res.decision is not None and res.decision["side"] == h1_says
    # no H1 side and range mode off: no fib order at all
    monkeypatch.setattr(bot, "h1_side", lambda *a, **k: None)
    monkeypatch.setattr(bot, "analyse_fib", only(1))
    none = bot.decide(frames, now, p)
    assert none.decision is None and none.log["reason"] == "step1: no side"


@needs_data
def test_27_oct_counter_leg_on_stored_bars(full) -> None:
    """Stored bars, 27/10/2026 (Thai). M5 at 18:30: the descending run into L0 = 3989.14 (15:50) is 4005.56,
    4000.00, 3997.23, 3989.14 - the owner's three legs 4000.00, 3997.23, 3989.14 plus the 4005.56 before them -
    with MACD and RSI both higher at L0; H100 = 4025.45 (11:20). Count on writes the BUY plain limit at the
    38.2 % level 4003.01, stop 3988.64, target (161.8 %) 4047.39, R 3.07. On M15 at 18:30 the 3989.14 low is
    not yet a fixed pivot (the run is 4010.37, 3988.74 of 26/10 under H100 4025.47): count on refuses, 2 lows."""
    now = now_at("2026-10-27 18:30")
    frames = bot.cut(full, now)
    p = bot.Params(
        mode="fib", fib_count="on", fib_target="ext161", h1_mode="lows", fib_tf="M5", max_entry_distance=100.0
    )
    bands = sorted(bot.h1_bands(bot._zigzag(frames["H1"]), len(frames["H1"]), now, p))
    zz = bot._zigzag(frames["M5"])
    hi, lo, close, macd, rsi = bot._view_arrays(frames["M5"], 1)
    out = bot.analyse_fib(bot.to_view(zz, 1), hi, lo, close, bands, p, macd, rsi)
    s = out.setup
    assert out.reason == "order written" and s is not None and s.count is not None
    assert [q.price for q in s.count.counted] == [4005.56, 4000.0, 3997.23, 3989.14]
    assert s.count.div_macd and s.count.div_rsi and (s.lo_v, s.hi_v) == (3989.14, 4025.45)
    got = (round(s.entry_v, 2), round(s.stop_v, 2), round(s.target_v, 2), round(s.r, 2))
    assert got == (4003.01, 3988.64, 4047.39, 3.07)
    # R20: the last M5 close was 4010.95, 7.94 USD from the entry - the default 4.0 refuses the order (the pin
    # is now this refusal; the order never filled, the low after was 4007.53). The numbers above are the
    # leg's, read with the distance opened wide.
    strict = bot.Params(mode="fib", fib_count="on", fib_target="ext161", h1_mode="lows", fib_tf="M5")
    refused = bot.analyse_fib(bot.to_view(zz, 1), hi, lo, close, bands, strict, macd, rsi)
    assert refused.reason == "fib: entry too far from price" and refused.setup is None
    assert float(frames["M5"].close.iloc[-1]) == pytest.approx(4010.95)
    # the SELL view sees no such order
    shi, slo, sclose, smacd, srsi = bot._view_arrays(frames["M5"], -1)
    sell = bot.analyse_fib(bot.to_view(zz, -1), shi, slo, sclose, [], p, smacd, srsi)
    assert sell.setup is None
    # M15
    p15 = bot.Params(mode="fib", fib_count="on", fib_target="ext161", fib_tf="M15")
    z15 = bot._zigzag(frames["M15"])
    h15, l15, c15, m15, r15 = bot._view_arrays(frames["M15"], 1)
    leg = bot.fib_leg_counter(bot.to_view(z15, 1), c15)
    assert leg is not None and (leg[0].price, leg[1].price) == (3988.74, 4025.47)
    out15 = bot.analyse_fib(bot.to_view(z15, 1), h15, l15, c15, bands, p15, m15, r15)
    # (with R19 the M15 leg is refused earlier than its count: bars after 3988.74 traded above H100 4025.47)
    assert out15.reason == "fib: leg has run (100 % traded)" and out15.setup is None


def test_counter_high_choice_start_or_latest() -> None:
    """fib_high: "start" = the highest fixed high of the descending run (4100), "latest" = the fixed high just
    before L0 (4075); the default is start at every entry (the depth-based auto was withdrawn). The decision
    text names the choice."""
    pv, hi, lo, close, *_ = counter_case()
    start = bot.fib_leg_counter(pv, close, "start")
    latest = bot.fib_leg_counter(pv, close, "latest")
    assert start is not None and latest is not None
    assert (start[1].price, latest[1].price) == (4100.0, 4075.0) and start[0] == latest[0]
    assert bot.Params().fib_high == "start" and bot.Params().fib_target == "ext161"
    assert bot.fib_high_choice(bot.Params(fib_entry=0.236)) == "start"
    assert bot.fib_high_choice(bot.Params(fib_entry=0.382)) == "start"
    assert bot.fib_high_choice(bot.Params(fib_entry=0.618)) == "start"
    assert bot.fib_high_choice(bot.Params(fib_entry=0.236, fib_high="start")) == "start"
    assert bot.fib_high_choice(bot.Params(fib_entry=0.618, fib_high="latest")) == "latest"
    times = pd.date_range(T_START, periods=len(close), freq="15min")
    for choice, top in (("start", 4100.0), ("latest", 4075.0)):
        # the "latest" entry (4028.6) is 12.4 from the last close: R20 is opened wide, this test is about H100
        p = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_high=choice, max_entry_distance=100.0)
        s = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, p).setup
        assert s is not None and s.hi_v == top and s.entry_v == pytest.approx(4000.0 + 0.382 * (top - 4000.0))
        assert s.target_v == pytest.approx(4000.0 + 1.618 * (top - 4000.0) - p.target_buffer)
        text = bot._fib_row(s, "BUY", 1, T_START + pd.Timedelta(days=1), times, "M15", p)["structure"]
        assert f"fib_high {choice} -> {choice}" in text and f"fib_high={choice}" in text
    assert "fixed high immediately before L0" in text
    for bad in ("x", "auto"):
        with pytest.raises(ValueError):
            bot.Params(fib_high=bad)


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
        mine, _ = bot.walk_days(["2026-04-06"], bot.Params(max_orders=n), full)
        assert len(mine) == n, n
        assert bot.PEAK["live"] == n and bot.PEAK["filled"] == n
    assert "max_orders=3" in bot.Params(max_orders=3).text() and bot.Params().max_orders == 1
    with pytest.raises(ValueError):
        bot.Params(max_orders=0)


def test_counter_count_accepts_4_and_5_rejects_6_both_sides() -> None:
    """R18 count on: 4 and 5 lower lows into L0 are accepted, 6 is not, and the SELL (higher highs into the top,
    via the mirror) is counted the same way."""
    on = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_count="on")
    runs = {
        4: (4070.0, 4060.0, 4040.0, 4000.0),
        5: (4075.0, 4070.0, 4060.0, 4040.0, 4000.0),
        6: (4078.0, 4075.0, 4070.0, 4060.0, 4040.0, 4000.0),
    }
    for n, lows in runs.items():
        pv, hi, lo, close, macd, rsi = counter_case(lows=lows)
        buy = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, on, macd, rsi)
        spv, shi, slo, sclose, _ = fib_sell_inputs(pv, hi, lo, close)
        sell = bot.analyse_fib(spv, shi, slo, sclose, R18_BANDS, on, macd, rsi)
        for out in (buy, sell):
            if n < 6:
                assert out.setup is not None and out.setup.count is not None, n
                assert len(out.setup.count.counted) == n
            else:
                assert out.setup is None and out.reason == "fib: count outside 3-5"


@needs_data
def test_counter_key_and_one_order_per_leg(full, monkeypatch) -> None:
    """the key is side|fib_tf|L0 time|H100 time; the same leg is not written twice."""
    # 26/10 13:05 Thai (London window): the leg L0 23/10 21:30 Thai / top 20:20 Thai has not run (R19). The
    # distance is opened wide - this test is about the key, not R20 - and the BUY side is stood in.
    now = now_at("2026-10-26 13:05")
    p = bot.Params(mode="fib", fib_tf="M5", h1_mode="lows", max_entry_distance=1000.0)
    monkeypatch.setattr(bot, "h1_side", lambda *a, **k: "BUY")
    res = bot.decide(bot.cut(full, now), now, p)
    assert res.decision is not None
    assert res.key == "BUY|M5|2026-10-23 14:30:00+00:00|2026-10-23 13:20:00+00:00"
    again = bot.decide(bot.cut(full, now), now, p, used=frozenset({res.key}))
    assert again.decision is None and again.log["reason"] == "setup already used"


@needs_data
def test_fib_path_has_no_lookahead(full) -> None:
    """The fib path: frames cut at ``now`` from the real data and from data whose later bars are noise give the
    same decision; an uncut frame is refused."""
    rng = np.random.default_rng(5)
    for text in ("2026-10-27 20:00", "2026-10-22 20:00", "2026-10-26 20:00"):
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
            bot.Params(mode="fib", fib_tf="M5", h1_mode="lows"),
            bot.Params(mode="fib", fib_tf="M5", fib_count="on", h1_mode="lows"),
            bot.Params(mode="fib", fib_tf="M15", fib_side="h1", h1_mode="lows", fib_entry=0.618),
        ):
            a = bot.decide(bot.cut(full, now), now, p)
            b = bot.decide(bot.cut(noisy, now), now, p)
            assert a.log == b.log and a.decision == b.decision and a.key == b.key
    now = now_at("2026-10-27 20:00")
    with pytest.raises(ValueError, match="had not closed"):
        bot.decide(bot.cut(full, now + pd.Timedelta(hours=1)), now, bot.Params(mode="fib"))


def test_counter_r8_crossing_bar_target_counts_low_does_not() -> None:
    """R8 on the counter leg: on the first bar that traded above the entry level the TARGET counts (played out)
    but its LOW does not; from the next bar on the stop counts too."""
    pv, hi, lo, close, *_ = counter_case()
    base = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, PC)
    assert base.setup is not None
    cross = int(np.flatnonzero(hi[pv[-3].pos + 1 :] > base.setup.entry_v)[0]) + pv[-3].pos + 1
    h = hi.copy()
    h[cross] = 4161.3  # the 161.8 % target on the crossing bar itself: beyond H100, so R19 refuses it now
    assert bot.analyse_fib(pv, h, lo, close, R18_BANDS, PC).reason == "fib: leg has run (100 % traded)"
    lw = lo.copy()
    lw[cross] = 3990.0  # a low under the stop 3999.5 on the crossing bar: ignored
    assert bot.analyse_fib(pv, hi, lw, close, R18_BANDS, PC).reason == "order written"
    lw2 = lo.copy()
    lw2[cross + 1] = 3990.0  # the same low on the next bar: the stop counts
    assert bot.analyse_fib(pv, hi, lw2, close, R18_BANDS, PC).reason == "setup already played out"


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


# --- revision 7 (R19, R20, fib_stop, fib_level) ---------------------------------------------------------------

P618 = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_entry=0.618)
SWING618 = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_entry=0.618, fib_stop="swing")
R7_TIMES = pd.date_range(T_START, periods=200, freq="15min")


def test_r19_leg_that_has_run_gets_no_order_buy_and_sell() -> None:
    """R19: any bar after L0 that traded beyond H100 (4100) ends the leg; touching 4100.0 exactly does not; a
    high before L0 does not count. The SELL view (the same data negated) gives the same answers."""
    pv, hi, lo, close, *_ = counter_case()
    after = pv[-3].pos + 5  # a bar after L0
    for h100_bar, reason in ((4100.0, "order written"), (4100.05, "fib: leg has run (100 % traded)")):
        h = hi.copy()
        h[after] = h100_bar
        assert bot.analyse_fib(pv, h, lo, close, R18_BANDS, PC).reason == reason
        spv, shi, slo, sclose, _ = fib_sell_inputs(pv, h, lo, close)
        assert bot.analyse_fib(spv, shi, slo, sclose, R18_BANDS, PC).reason == reason
    h = hi.copy()
    h[pv[-3].pos - 5] = 4200.0
    assert bot.analyse_fib(pv, h, lo, close, R18_BANDS, PC).reason == "order written"


def test_r20_entry_must_be_within_the_distance_of_the_last_close() -> None:
    """R20: entry 4038.2, last close 4045 = 6.8 away: refused at the default 4.0, written at 6.9; a close 3.3
    away is written at the default. Mirrored for a SELL; a non-positive distance is refused."""
    assert bot.Params().max_entry_distance == 4.0
    pv, hi, lo, close, *_ = counter_case(last=4045.0)
    near = bot.Params(mode="fib", min_r=0.0, fib_target="ext161")
    why = "fib: entry too far from price"
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, near).reason == why
    ok = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", max_entry_distance=6.9)
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, ok).reason == "order written"
    pv2, hi2, lo2, close2, *_ = counter_case(last=4041.5)
    assert bot.analyse_fib(pv2, hi2, lo2, close2, R18_BANDS, near).reason == "order written"
    # the price is the last closed M5 close, not the fib timeframe's: a fib-timeframe close 6.8 away is passed
    # when the M5 close is 3.3 away, and a near one is refused when the M5 close is 6.8 away
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, near, price_v=4041.5).reason == "order written"
    assert bot.analyse_fib(pv2, hi2, lo2, close2, R18_BANDS, near, price_v=4045.0).reason == why
    spv, shi, slo, sclose, _ = fib_sell_inputs(pv, hi, lo, close)
    assert bot.analyse_fib(spv, shi, slo, sclose, R18_BANDS, near).reason == why
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            bot.Params(max_entry_distance=bad)


def test_r20_boundary_exactly_the_distance_is_written_and_a_little_more_is_refused() -> None:
    """R20 at the limit: an M5 price exactly 4.0 from the entry (above it) is written, 4.01 is refused, and the
    refusal names the actual limit in the log text (step5) even when max_entry_distance is changed."""
    pv, hi, lo, close, *_ = counter_case()
    entry = 4038.2
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, PC, price_v=entry + 4.0).reason == "order written"
    cut = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, PC, price_v=entry + 4.01)
    assert cut.reason == "fib: entry too far from price" and cut.setup is None
    assert "limit 4" in cut.info["step5"] and "4.01 USD" in cut.info["step5"]
    wide = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", max_entry_distance=2.5)
    out = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, wide, price_v=entry + 2.6)
    assert out.reason == "fib: entry too far from price" and "limit 2.5" in out.info["step5"]
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, wide, price_v=entry + 2.5).reason == "order written"


def test_fib_stop_swing_is_beyond_the_latest_low_buy_and_sell() -> None:
    """fib_stop swing, 61.8 % entry 4061.8: the line stop is 4000 + 23.6 - 0.5 = 4023.1; the higher low after L0
    (4015) is lower, so the swing stop is 4014.5 and R is recomputed from it. A 0 % stop is unchanged (every
    later low is above L0). A swing R under min_r gives no order."""
    # the higher low 4015 comes before price first trades above the 61.8 % entry, so R8 does not void the line
    pv, hi, lo, close, *_ = counter_case(last=4063.0)
    line = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, P618).setup
    swing = bot.analyse_fib(pv, hi, lo, close, R18_BANDS, SWING618).setup
    assert line is not None and swing is not None
    assert line.stop_v == pytest.approx(4023.1) and swing.stop_v == pytest.approx(4014.5)
    assert swing.r == pytest.approx(
        (swing.target_v - swing.entry_v - SWING618.spread) / (swing.entry_v - 4014.5)
    )
    assert swing.r < line.r
    spv, shi, slo, sclose, _ = fib_sell_inputs(pv, hi, lo, close)
    sell = bot.analyse_fib(spv, shi, slo, sclose, R18_BANDS, SWING618).setup
    assert sell is not None and sell.stop_v == pytest.approx(4014.5) and sell.r == pytest.approx(swing.r)
    zero = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_stop="swing")
    pv0, hi0, lo0, close0, *_ = counter_case()  # the 38.2 % entry 4038.2, last close 4041
    z = bot.analyse_fib(pv0, hi0, lo0, close0, R18_BANDS, zero).setup
    assert z is not None and z.stop_v == pytest.approx(3999.5)
    strict = bot.Params(
        mode="fib", min_r=swing.r + 0.01, fib_target="ext161", fib_entry=0.618,
        fib_stop="swing",
    )  # fmt: skip
    assert bot.analyse_fib(pv, hi, lo, close, R18_BANDS, strict).reason == "reward under 2R"


def test_fib_level_needs_l0_in_a_support_band_buy_and_sell() -> None:
    """fib_level on: L0 (4000) must lie in an H1 support band; off ignores the bands. A SELL's bands are the
    mirror (resistance). The row text names the R19 withdrawal level, R20, the stop mode and the level mode."""
    pv, hi, lo, close, *_ = counter_case()
    on = bot.Params(mode="fib", min_r=0.0, fib_target="ext161", fib_level="on")
    why = "fib: L0 not in a support band"
    assert bot.analyse_fib(pv, hi, lo, close, [(3995.0, 4005.0)], on).reason == "order written"
    assert bot.analyse_fib(pv, hi, lo, close, [(4010.0, 4020.0)], on).reason == why
    assert bot.analyse_fib(pv, hi, lo, close, [], on).reason == why
    assert bot.analyse_fib(pv, hi, lo, close, [(4010.0, 4020.0)], PC).reason == "order written"
    spv, shi, slo, sclose, _ = fib_sell_inputs(pv, hi, lo, close)
    # the fixture's SELL data is the BUY data negated, so its view (and the view's bands) equal the BUY's;
    # the band edges are inclusive
    assert bot.analyse_fib(spv, shi, slo, sclose, [(3995.0, 4005.0)], on).reason == "order written"
    assert bot.analyse_fib(spv, shi, slo, sclose, [(4010.0, 4020.0)], on).reason == why
    assert bot.analyse_fib(pv, hi, lo, close, [(4000.0, 4010.0)], on).reason == "order written"
    assert bot.analyse_fib(pv, hi, lo, close, [(3990.0, 4000.0)], on).reason == "order written"
    s = bot.analyse_fib(pv, hi, lo, close, [(3995.0, 4005.0)], on).setup
    assert s is not None
    text = bot._fib_row(s, "BUY", 1, T_START + pd.Timedelta(days=1), R7_TIMES, "M15", on)["structure"]
    for part in (
        "R19 leg not run (withdraw beyond 4100.00)", "R20 entry within 4 USD", "level band on",
        "fib_stop line", "fib_level=on",
    ):  # fmt: skip
        assert part in text


def test_revision7_params_validated_and_in_text() -> None:
    d = bot.Params()
    assert (d.max_entry_distance, d.fib_stop, d.fib_level) == (4.0, "line", "off")
    text = bot.Params(max_entry_distance=3.5, fib_stop="swing", fib_level="on").text()
    for part in ("max_entry_distance=3.5", "fib_stop=swing", "fib_level=on"):
        assert part in text
    for bad in ({"fib_stop": "x"}, {"fib_level": "x"}):
        with pytest.raises(ValueError):
            bot.Params(**bad)
    for flag in ("--fib-stop", "--fib-level", "--max-entry-distance"):
        assert flag in Path(bot.__file__).read_text(encoding="utf-8")


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


@needs_data
@pytest.mark.parametrize(
    ("day", "label", "reason"),
    [
        ("07", "07:30", "order written"),
        ("01", "06:55", "fib: leg has run (100 % traded)"),
        ("12", "06:55", "fib: leg has run (100 % traded)"),
        ("16", "13:15", "fib: leg has run (100 % traded)"),
        ("21", "21:00", "fib: leg has run (100 % traded)"),
        ("27", "14:00", "fib: leg has run (100 % traded)"),
        ("09", "06:55", "fib: entry too far from price"),
    ],
)  # fmt: skip
def test_revision7_acceptance_cases_on_stored_bars(full, day, label, reason) -> None:
    """BOT_SPEC revision 7, October 2026: the h1-side lows / M5 / 0.618 / ext161 variant, decided_at label
    (the last bar's open, Thai) -> decide() at label + 5 minutes."""
    p = bot.Params(
        mode="fib", h1_mode="lows", fib_side="h1", fib_entry=0.618, fib_tf="M5", fib_target="ext161",
        fib_high="start",
    )  # fmt: skip
    now = (pd.Timestamp(f"2026-10-{day} {label}", tz=TH) + pd.Timedelta(minutes=5)).tz_convert("UTC")
    res = bot.decide(bot.cut(full, now), now, p)
    assert res.log["reason"] == reason
    if reason == "order written":
        d = res.decision
        assert d is not None and d["side"] == "SELL" and d["entry"] == "4159.07"
        assert "withdraw beyond" in d["structure"]
    else:
        assert res.decision is None
