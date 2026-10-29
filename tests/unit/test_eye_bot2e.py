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
# The round-1 tests pin the setup-timeframe geometry, so they run in entry_mode="setup" (R12 made "m1" the default).
P = bot.Params(entry_mode="setup")
BOTH = bot.Params(
    min_r=0.0, div_mode="both", entry_mode="setup"
)  # the earlier rule: divergence on both oscillators
P0 = bot.Params(
    min_r=0.0, entry_mode="setup"
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
    assert bot.Params().min_r == 2.0 and bot.Params().entry_mode == "m1"
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
        got = bot.decide(frames, now, bot.Params(h1_tf="H4", entry_mode="setup")).log["side"]
        assert got == (want or "")
        sides.add(got)
    assert sides - {""}  # at least one of them had a side


@needs_data
def test_entry_tfs_selects_the_timeframes(full) -> None:
    now = now_at("2026-04-06 21:20")
    frames = bot.cut(full, now)
    assert bot.decide(frames, now, P0).log["tf"] == "M5"
    assert (
        bot.decide(frames, now, bot.Params(min_r=0.0, entry_tfs="M5", entry_mode="setup")).log["tf"] == "M5"
    )
    only15 = bot.decide(frames, now, bot.Params(min_r=0.0, entry_tfs="M15", entry_mode="setup"))
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
        "t", {"min_r": 0.0, "entry_mode": "setup"}, "2026-04-06", "2026-04-06", full, m5, root=tmp_path
    )
    research.append_summary([result], "2026-04-06", "2026-04-06", root=tmp_path)
    after = [(p.read_bytes() if p.exists() else None) for p in watched]
    assert before == after
    assert (tmp_path / "t" / "ledger.csv").exists() and (tmp_path / "t" / "log.csv").exists()
    assert (tmp_path / "summary.csv").exists() and result["decisions"] == 1
    assert result["filled"] + result["open"] <= 1
    with pytest.raises(SystemExit):
        research.make_params({"nonsense": 1})


# --- revision 4 (R12): steps 3-6 on M1 -----------------------------------------------------------------------

PM1 = bot.Params(min_r=0.0)  # entry_mode "m1" (the default), the 2R floor dropped for the geometry tests
T_START = pd.Timestamp("2026-10-05 00:00", tz="UTC")


def m1_case(*, far: float = 5000.0):
    """A BUY in the view. Setup timeframe (15 min bars): zone lows 4640, 4620, 4600 (L*, a count of 3 with
    divergence) in the band 4590-4665, no higher low there. M1: a low 4580 BEFORE L*'s bar (must be ignored),
    then L1 = 4598 (a little under L*), a break to 4720, a higher low 4625, H_d = 4720."""
    pv, hi, lo, close, macd, rsi = build([4640.0, 4620.0, 4600.0], higher_low=False)
    setup_times = pd.date_range(T_START, periods=len(close), freq="15min")
    assert pv[-2].low and pv[-2].price == 4600.0  # L* is the last low; pv[-1] is X
    t0 = setup_times[pv[-2].pos]
    m1pv, mhi, mlo, mclose, _, _ = build([4580.0, 4598.0], x=4720.0, l_hl=4625.0)
    m1_times = pd.date_range(t0 - pd.Timedelta(minutes=35), periods=len(mclose), freq="1min")
    ctx = bot.M1Ctx(setup_times, m1_times, m1pv, mhi, mlo, mclose)
    bands = [(4590.0, 4665.0), (far, far + 10.0)]
    return (pv, hi, lo, close, macd, rsi), ctx, bands


def run_m1(case, params=PM1):
    (pv, hi, lo, close, macd, rsi), ctx, bands = case
    return bot.analyse_view(pv, hi, lo, close, macd, rsi, bands, "M15", params, lambda: ctx, ctx.setup_times)


def with_m1(ctx, *, hi=None, lo=None, close=None, times=None):
    return bot.M1Ctx(
        ctx.setup_times,
        ctx.m1_times if times is None else times,
        ctx.pv,
        ctx.hi_v if hi is None else hi,
        ctx.lo_v if lo is None else lo,
        ctx.close_v if close is None else close,
    )


def test_m1_mode_formulas_and_no_band_edge() -> None:
    """R12 on a constructed BUY: L1 is the lowest M1 low from L*'s bar on (the earlier 4580 is ignored), the
    break is the M1 high before L1 (4690), the M1 higher low is 4625, H_d = 4720; stop = min(L*, L1) - buffer
    with NO band edge (the band's lower edge 4590 is above it), target before the next band, R net of spread."""
    out = run_m1(m1_case())
    s = out.setup
    assert out.reason == "order written" and s is not None
    assert s.l1 is not None and s.l1.price == 4598.0 and s.m1_break_v == 4690.0
    assert s.lhl.price == 4625.0 and s.hd.price == 4720.0
    assert s.entry_v == 4720.0
    assert s.trigger_v == 4720.0 + PM1.trigger_offset  # the last M1 close (4625) is under H_d: stop limit
    assert s.stop_v == 4598.0 - PM1.stop_buffer  # min(L*=4600, L1=4598) - buffer; not the band edge 4590
    assert s.target_v == 5000.0 - PM1.target_buffer
    assert s.r == pytest.approx((s.target_v - s.entry_v - PM1.spread) / (s.entry_v - s.stop_v))
    # L* lower than L1: the stop follows the lower of the two
    sa, ctx, bands = m1_case()
    pv = list(sa[0])
    pv[-2] = bot.VPivot(True, 4595.0, pv[-2].pos)  # L* = 4595 < L1 = 4598 (still in the band)
    out2 = run_m1(((pv, *sa[1:]), ctx, bands))
    assert out2.setup is not None and out2.setup.stop_v == 4595.0 - PM1.stop_buffer
    # the 2R floor applies on the M1 geometry too: a near target gives "reward under 2R"
    near = run_m1(m1_case(far=4800.0), bot.Params())
    assert near.reason == "reward under 2R" and near.setup is None
    # plain limit while the last M1 close is above H_d; void while it is below the M1 higher low
    sa, ctx, bands = m1_case()
    up = np.array(ctx.close_v)
    up[-1] = 4730.0
    plain = run_m1((sa, with_m1(ctx, close=up), bands))
    assert plain.setup is not None and plain.setup.trigger_v is None
    down = np.array(ctx.close_v)
    down[-1] = 4620.0
    assert run_m1((sa, with_m1(ctx, close=down), bands)).reason == "step5: price below the higher low"
    # a frame that does not reach back to L*'s bar
    late = with_m1(ctx, times=ctx.m1_times + pd.Timedelta(days=1))
    assert run_m1((sa, late, bands)).reason == "m1: L* older than the M1 frame"


def test_m1_mode_sell_is_the_mirror() -> None:
    """A SELL built as the real-price mirror of the BUY case (prices negated, highs and lows swapped), pushed
    through ``to_view`` / ``m1_context`` as ``decide`` does, gives the BUY's numbers negated in the row."""
    (pv, hi, lo, close, macd, rsi), ctx, bands = m1_case()
    buy = run_m1(m1_case())

    def swings(vp):  # the view's pivots as a SELL's real fixed pivots: kinds swapped, prices negated
        return [
            Swing(SwingKind.HIGH if q.low else SwingKind.LOW, -q.price, q.pos, q.pos, q.pos, q.pos)
            for q in vp
        ]

    def frame_of(h_v, l_v, c_v, times):
        return pd.DataFrame({"open": -c_v, "high": -l_v, "low": -h_v, "close": -c_v}, index=times)

    setup_df = frame_of(hi, lo, close, ctx.setup_times)
    m1_df = frame_of(ctx.hi_v, ctx.lo_v, ctx.close_v, ctx.m1_times)
    sctx = bot.m1_context(m1_df, -1, swings(ctx.pv), ctx.setup_times)
    spv = bot.to_view(swings(pv), -1)
    bands_v = sorted((min(-b[0], -b[1]), max(-b[0], -b[1])) for b in [(-b[1], -b[0]) for b in bands])
    out = bot.analyse_view(
        spv, -setup_df.low.to_numpy(), -setup_df.high.to_numpy(), -setup_df.close.to_numpy(),
        macd, rsi, bands_v, "M15", PM1, lambda: sctx, ctx.setup_times,
    )  # fmt: skip
    s = out.setup
    assert s is not None and buy.setup is not None
    for name in ("entry_v", "stop_v", "target_v", "r", "trigger_v"):
        assert getattr(s, name) == pytest.approx(getattr(buy.setup, name))
    assert s.l1 is not None and s.l1.price == 4598.0  # the view's price; the real SELL price is -4598
    row = bot._row(s, "SELL", -1, T_START + pd.Timedelta(days=1), setup_df, PM1, m1_df)
    assert row["side"] == "SELL" and float(row["entry"]) == -4720.0
    assert float(row["stop"]) == -(4598.0 - PM1.stop_buffer) and float(row["target"]) == -(5000.0 - 0.5)
    assert row["structure"].startswith("bot2e M15>M1 SELL") and "L1=-4598.00" in row["structure"]
    assert "M1 higher low -4625.00" in row["structure"] and "H_d=-4720.00" in row["structure"]


def test_m1_played_out_is_read_on_m1_bars() -> None:
    """R8 on M1: the target or the stop traded on an M1 bar after the M1 higher low writes nothing; a touch
    on the setup timeframe's own bars does not count in m1 mode."""
    assert run_m1(m1_case()).reason == "order written"
    for col, at in ((0, 5000.0), (1, 4590.0)):
        sa, ctx, bands = m1_case()
        hi, lo = np.array(ctx.hi_v), np.array(ctx.lo_v)
        (hi, lo)[col][-2] = at
        out = run_m1((sa, with_m1(ctx, hi=hi, lo=lo), bands))
        assert out.setup is None and out.reason == "setup already played out"
    sa, ctx, bands = m1_case()
    setup_hi = np.array(sa[1])
    setup_hi[-2] = 6000.0
    assert run_m1(((sa[0], setup_hi, *sa[2:]), ctx, bands)).reason == "order written"


def test_m1_cut_guard_refuses_a_later_bar() -> None:
    """No look-ahead: an M1 bar that had not closed at ``now`` is refused, and an unsorted M1 frame too."""
    now = pd.Timestamp("2026-10-05 10:00", tz="UTC")
    idx = pd.date_range(now - pd.Timedelta(minutes=10), periods=10, freq="1min")  # the last bar closes at now
    cols = {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}
    ok = pd.DataFrame(cols, index=idx)
    bot._check_cut({"M1": ok}, now)
    late = pd.DataFrame(cols, index=idx.append(idx[-1:] + pd.Timedelta(minutes=1)))
    with pytest.raises(ValueError, match="had not closed"):
        bot._check_cut({"M1": late}, now)
    with pytest.raises(ValueError, match="not sorted"):
        bot._check_cut({"M1": ok.iloc[::-1]}, now)


@needs_data
def test_m1_cut_and_noise_after_now_changes_nothing(full) -> None:
    """On the stored bars: the M1 cut keeps closed bars only, and M1 bars after ``now`` replaced by noise
    give the same decision in m1 mode."""
    now = now_at("2026-04-06 21:20")
    cutm1 = bot.cut(full, now)["M1"]
    assert 0 < len(cutm1) <= bot.FRAME_BARS["M1"] and cutm1.index[-1] + bot.STEP["M1"] <= now
    rng = np.random.default_rng(11)
    noisy = {tf: df.copy() for tf, df in full.items()}
    df = noisy["M1"]
    late = np.asarray(df.index + bot.STEP["M1"] > now)
    base = rng.normal(4600, 80, int(late.sum()))
    df.loc[late, "open"] = base
    df.loc[late, "close"] = base
    df.loc[late, "high"] = base + 60
    df.loc[late, "low"] = base - 60
    a = bot.decide(bot.cut(full, now), now, PM1)
    b = bot.decide(bot.cut(noisy, now), now, PM1)
    assert a.log == b.log and a.decision == b.decision and a.key == b.key
    assert a.log["tf"].endswith(">M1")


@needs_data
def test_setup_mode_reproduces_round_one(full) -> None:
    """entry_mode="setup" is revision 3 bit for bit: the 04-06 21:20 decision measured before R12 was written
    (entry 4699.44, trigger 4699.94, stop 4579.49, target 4712.76, key with the setup-timeframe higher low)."""
    now = now_at("2026-04-06 21:20")
    res = bot.decide(bot.cut(full, now), now, P0)
    d = res.decision
    assert d is not None
    got = (d["side"], d["entry"], d["trigger"], d["stop"], d["target"], d["decided_at"])
    assert got == ("BUY", "4699.44", "4699.94", "4579.49", "4712.76", "06/04 21:15")
    assert res.key == "BUY|M5|2026-04-02 13:20:00+00:00|2026-04-02 16:20:00+00:00"
    assert res.log["tf"] == "M5" and "entry_mode=setup" in d["structure"]
    assert "entry_mode=m1" in bot.Params().text()
