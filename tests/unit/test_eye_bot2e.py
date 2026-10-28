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
        assert run(lows, macd_div=False).reason == "step2: no divergence on both"
        assert run(lows, rsi_div=False).reason == "step2: no divergence on both"
        assert run(lows, macd_div=False, rsi_div=False).reason == "step2: no divergence on both"
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
    assert out.reason == "step2: no divergence on both" and out.setup is None


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
