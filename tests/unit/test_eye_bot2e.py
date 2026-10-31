"""Tests for eye/bot2e.py: the fib path (eye/BOT_RULES.md), reading M15 and M5 only.

The rules are tested on constructed pivots and bars, where every number is chosen; the no-look-ahead, mirror,
window and ledger tests run on the stored gold bars and skip when the data is not on the machine.
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
P = bot.Params()
P0 = bot.Params(min_r=0.0)  # tests that are not about the 2R floor drop it


def now_at(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz=TH).tz_convert("UTC")


@pytest.fixture(scope="module")
def full() -> dict[str, pd.DataFrame]:
    return bot.load_frames()


def test_mirror_of_pivots_is_a_sell() -> None:
    """to_view turns a SELL's highs into lows with negated prices."""
    sw = [
        Swing(SwingKind.HIGH, 100.0, 5, 8, 5, 8),
        Swing(SwingKind.LOW, 90.0, 12, 15, 12, 15),
    ]
    assert bot.to_view(sw, 1) == [bot.VPivot(False, 100.0, 5, 8), bot.VPivot(True, 90.0, 12, 15)]
    assert bot.to_view(sw, -1) == [
        bot.VPivot(True, -100.0, 5, 8),
        bot.VPivot(False, -90.0, 12, 15),
    ]  # confirm bars kept


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


@needs_data
def test_outside_window_and_pending(full) -> None:
    outside = now_at("2026-04-06 11:00")
    res = bot.decide(bot.cut(full, outside), outside, replace(P0, windows="on"))
    assert res.decision is None and res.log["reason"] == "outside window"
    inside = now_at("2026-04-06 21:20")
    held = bot.decide(bot.cut(full, inside), inside, P0, pending=True)
    assert held.decision is None and held.log["reason"] == "order pending"


@needs_data
def test_windows_parameter_off_runs_all_day_on_keeps_the_three_windows(full) -> None:
    """Rule 0: 03:00 Thai on a weekday (market open) is looked at with ``windows`` off (the default) and is
    "outside window" with it on; an explicit ``windowed`` still wins; the parameter is validated and written."""
    three = now_at("2026-10-13 03:00")
    frames = bot.cut(full, three)
    assert bot.window_of(three) == ""
    assert bot.Params().windows == "off"
    off = bot.decide(frames, three, P0)
    on = bot.decide(frames, three, replace(P0, windows="on"))
    assert off.log["reason"] not in ("outside window", "market closed")
    assert on.log["reason"] == "outside window"
    assert bot.decide(frames, three, P0, windowed=True).log["reason"] == "outside window"
    assert (
        bot.decide(frames, three, replace(P0, windows="on"), windowed=False).log["reason"] != "outside window"
    )
    assert "windows=off" in bot.Params().text() and "windows=on" in bot.Params(windows="on").text()
    with pytest.raises(ValueError):
        bot.Params(windows="maybe")


def _quiet_decide(monkeypatch, nows: list[pd.Timestamp], row_at: str = "") -> None:
    """A stand-in decide that records every ``now`` and writes one order at the Thai time ``row_at``."""

    def fake(frames, now, p, used=frozenset(), pending=False, windowed=None):
        nows.append(now)
        t = now.tz_convert(TH)
        log = dict.fromkeys(bot.LOG_COLUMNS, "")
        log.update(date=f"{t:%Y-%m-%d}", time_thai=f"{t:%H:%M}", reason="outside window")
        if f"{t:%H:%M}" != row_at:
            return bot.Result(log)
        log["reason"] = "order written"
        row = {c: "" for c in bot.LEDGER_COLUMNS}
        row.update(
            cutoff_thai=f"{t:%Y-%m-%d} 07:00", decided_at=f"{t - pd.Timedelta(minutes=5):%d/%m %H:%M}",
            side="BUY", entry="1.00", stop="0.50", target="99998", reader="bot2e",
        )  # fmt: skip
        return bot.Result(log, row, key="k")

    monkeypatch.setattr(bot, "decide", fake)


@needs_data
def test_walk_days_schedule_is_288_times_off_and_93_on(full, monkeypatch) -> None:
    """Rule 0: one day's walk has the 288 times 00:00 .. 23:55 with ``windows`` off, the three windows (25 + 25
    + 43 = 93, start and end included) with it on; the log's date is the calendar day of ``now``."""
    nows: list[pd.Timestamp] = []
    _quiet_decide(monkeypatch, nows)
    _, logs = bot.walk_days(["2026-04-07"], bot.Params(), full)
    assert len(logs) == len(nows) == 288 and len(set(nows)) == 288
    thai = [n.tz_convert(TH) for n in nows]
    assert f"{thai[0]:%Y-%m-%d %H:%M}" == "2026-04-07 00:00" and f"{thai[-1]:%H:%M}" == "23:55"
    assert {r["date"] for r in logs} == {"2026-04-07"}
    nows.clear()
    _, logs = bot.walk_days(["2026-04-07"], bot.Params(windows="on"), full)
    assert len(logs) == len(nows) == 25 + 25 + 43
    assert all(bot.window_of(n) for n in nows)


@needs_data
def test_an_order_at_midnight_carries_that_days_date(full, monkeypatch) -> None:
    """Rule 0: 00:00 belongs to the day it falls on - the order id, the row's date and the log's date."""
    _quiet_decide(monkeypatch, [], row_at="00:00")
    mine, logs = bot.walk_days(["2026-04-07"], bot.Params(), full)
    assert [r["id"] for r in mine] == ["B-20260407-1"] and mine[0]["cutoff_thai"][:10] == "2026-04-07"
    assert logs[0]["date"] == "2026-04-07" and logs[0]["time_thai"] == "00:00"


@needs_data
def test_one_order_at_a_time_in_the_walk(full) -> None:
    """A live earlier order (filled, never resolved) stops every new decision, in every window."""
    seen = float(full["M5"].open[now_at("2026-04-02 13:05")])  # a limit at the market fills on the next bar
    live = {c: "" for c in bot.LEDGER_COLUMNS}
    live.update(
        id="B-20260402-1", cutoff_thai="2026-04-02 07:00", decided_at="02/04 13:00", side="BUY",
        entry=f"{seen:.2f}", stop="1", target="99998",
    )  # fmt: skip
    mine, logs = bot.walk_days(["2026-04-06"], replace(P, windows="on"), full, [live])
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


# --- the ledger -------------------------------------------------------------------------------------------------


@needs_data
def test_ledger_rows_score_and_money_reads_them(full, tmp_path, monkeypatch) -> None:
    ledger, log = tmp_path / "bot_ledger.csv", tmp_path / "bot_log.csv"
    header = next(csv.reader((ROOT / "eye/ledger.csv").open(encoding="utf-8")))
    assert header == bot.LEDGER_COLUMNS

    # another day's row is kept when a range is re-run
    other = {c: "" for c in bot.LEDGER_COLUMNS}
    other.update(id="B-20261018-1", cutoff_thai="2026-10-18 07:00", reader="bot2e", side="WAIT")
    bot._write(ledger, bot.LEDGER_COLUMNS, [other])
    p = bot.Params(
        fib_entry=0.382, fib_early=0.10, fib_stop="line_tight", windows="on"
    )  # an order at 10-19 07:00
    bot.run("2026-10-19", "2026-10-19", p, ledger, log)
    rows = bot._read(ledger, bot.LEDGER_COLUMNS)
    ids = [r["id"] for r in rows]
    assert ids[0] == "B-20261018-1" and len(ids) >= 2 and all(i.startswith("B-20261019-") for i in ids[1:])
    mine = rows[1]
    assert mine["reader"] == "bot2e" and mine["rules"] == "" and mine["setup"] == "" and mine["trigger"] == ""
    assert mine["why"] == ""  # unscored
    for name in (
        "min_r=",
        "stop_buffer=",
        "target_buffer=",
        "order_life_bars=",
        "windows=on",
        "H4 ",
        "trade: ",
    ):
        assert name in mine["structure"], name
    bot.run("2026-10-19", "2026-10-19", p, ledger, log)  # re-running replaces, never duplicates
    assert [r["id"] for r in bot._read(ledger, bot.LEDGER_COLUMNS)] == ids
    dates = [r["date"] for r in bot._read(log, bot.LOG_COLUMNS)]
    assert len(dates) == 93 and set(dates) == {"2026-10-19"}

    scored = score_mod.score(mine, score_mod.bars(), score_mod.start_of(mine, {}))
    assert scored["why"] and "r_net" in scored
    mine.update(scored)
    bot._write(ledger, bot.LEDGER_COLUMNS, [mine])

    monkeypatch.setattr(money, "HERE", tmp_path)
    monkeypatch.setattr(sys, "argv", ["money.py", "--ledger", "bot_ledger.csv"])
    money.main()


# --- research options (eye/BOT_RESEARCH.md) --------------------------------------------------------------------


@needs_data
def test_runner_writes_only_its_own_files(full, tmp_path) -> None:
    research = importlib.import_module("eye.bot_research")
    watched = [
        ROOT / "eye" / n for n in ("ledger.csv", "ledger_control.csv", "bot_ledger.csv", "bot_log.csv")
    ]
    before = [(p.read_bytes() if p.exists() else None) for p in watched]
    m5 = score_mod.bars()
    result = research.run_variant(
        "t", {"min_r": 0.0, "fib_entry": 0.382}, "2026-10-19", "2026-10-19", full, m5, root=tmp_path
    )
    after = [(p.read_bytes() if p.exists() else None) for p in watched]
    assert before == after
    assert (tmp_path / "t" / "ledger.csv").exists() and (tmp_path / "t" / "log.csv").exists()
    assert (tmp_path / "t" / "summary.csv").exists() and result["orders"] >= 1
    with pytest.raises(SystemExit):
        research.make_params({"nonsense": 1})
    with pytest.raises(SystemExit):
        research.make_params({"band_frac": 0.15})  # an H1 band parameter: removed


T_START = pd.Timestamp("2026-10-05 00:00", tz="UTC")


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
        mine, _ = bot.walk_days(["2026-04-06"], bot.Params(max_orders=n, windows="on"), full)
        assert len(mine) == n, n
        assert bot.PEAK["live"] == n and bot.PEAK["filled"] == n
    assert "max_orders=3" in bot.Params(max_orders=3).text() and bot.Params().max_orders == 1
    with pytest.raises(ValueError):
        bot.Params(max_orders=0)


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
    assert m["r_total"] == pytest.approx(0.0) and m["fills"] == 4  # R and counts keep every trade
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

PB = bot.Params(
    mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382
)  # the base case's level; the defaults are tested on their own


def leg_data(
    *,
    last: float = 4041.0,
    m5_highs=(4090.0,),
    edit=None,
    start: float = 4000.0,
    end: float = 4100.0,
    h4: str = "up",
    confirm: int = -1,
) -> bot.LegData:
    """A BUY ``LegData`` for the leg traded with it (rule 2): ``L0`` = ``start`` (a fixed LOW at position 40, 0 %),
    ``H100`` = ``end`` (the latest fixed HIGH at position 60, 100 %), then the pullback falling to ``last`` at the
    final bar (the price). The M5 frame is the setup frame (``fib_tf`` M5); ``m5_highs`` are fixed M5 highs before
    H100 (oldest first, positions 1, 3, 5 ...); ``edit(hi, lo, close, macd, rsi)`` may change the arrays."""
    n = 90
    path = np.interp(np.arange(n), [0, 40, 60, n - 1], [start + 20.0, start, end, last])
    hi, lo, close = path + 0.1, path - 0.1, path.copy()
    if edit is not None:
        edit(hi, lo, close, np.zeros(n), np.zeros(n))  # (macd and rsi are not read any more)
    pv = [bot.VPivot(True, start, 40), bot.VPivot(False, end, 60, confirm)]
    times = pd.date_range(T_START, periods=n, freq="5min")
    m5_pv = [bot.VPivot(False, h, 1 + 2 * i) for i, h in enumerate(m5_highs)] + pv
    return bot.LegData(
        side="BUY", sign=1, tf="M5", pv=pv, times=times, hi_v=hi, lo_v=lo, close_v=close,
        m5_times=times, m5_hi_v=hi, m5_lo_v=lo, price_v=float(close[-1]), m5_pv=m5_pv, m5_ptimes=times,
        h4=h4, h4_text=f"H4 {h4} (test)",
    )  # fmt: skip


def as_sell(d: bot.LegData) -> bot.LegData:
    """The same view data read as a SELL (a mirror: the real prices are the negated view prices); an H4 trend
    is mirrored with it."""
    h4 = {"up": "down", "down": "up"}.get(d.h4, d.h4)
    return replace(d, side="SELL", sign=-1, h4=h4, h4_text=f"H4 {h4} (test)")


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
    assert (d.fib_tf, d.fib_entry, d.fib_early, d.fib_stop, d.fib_count) == ("M5", 0.382, 0, "line", "off")
    assert (d.fib_target, d.fib_early) == (1.618, 0)
    assert d.max_entry_frac == 0.25
    assert d.fib_lean == "on"  # kept as a parameter; rule 16's side is not built yet, nothing to act on
    assert (d.stop_buffer, d.target_buffer, d.spread, d.max_orders) == (0.5, 0.5, 0.3, 1)
    assert (d.order_life_bars, d.min_r, d.mode) == (24, 2.0, "fib")  # fib is the default; 2e is a record
    for gone in (
        "max_entry_distance", "major_tf", "fib_leg", "fib_side", "fib_high", "fib_level",
        # H1 / H4 and the old range, bands and 2e record (removed, 2026-10-30)
        "h1_mode", "h1_tf", "h1_swings", "level_min_age_h", "level_bars", "band_frac", "band_legs",
        "counter_pivots", "count_min", "count_max", "trigger_offset", "entry_tfs", "div_mode",
        "fib_range", "range_min_leg", "range_tp", "max_trend_legs",  # rule 5 withdrawn
    ):  # fmt: skip
        assert not hasattr(d, gone), gone  # the withdrawn options are not parameters any more
    src = Path(bot.__file__).read_text(encoding="utf-8")
    assert (
        "the owner's rule 7" not in src and "max_entry_distance" not in src
    )  # no fixed USD, no stale comment


def test_meaningless_combinations_are_refused_at_start() -> None:
    for bad in (
        {"fib_early": 0.10},  # early without line_tight
        {"fib_early": 0.10, "fib_stop": "line_tight", "fib_entry": 0.618},
        {"fib_early": 0.10, "fib_stop": "line", "fib_entry": 0.382},
        {"fib_early": 0.10, "fib_stop": "line_tight", "fib_entry": 0.236},
        {"fib_stop": "swing"},  # withdrawn with rule 2's rewrite
        {"fib_stop": "line_tight", "fib_entry": 0.382},  # line_tight without fib_early
        {"fib_stop": "line_tight"},
        {"fib_entry": 0.5},
        {"fib_early": 0.2, "fib_stop": "line_tight", "fib_entry": 0.382},
        {"fib_tf": "H1"},
        {"fib_count": "x"},
        {"fib_count": "on"},  # fixed off
        {"fib_target": 1.5},
        {"fib_target": 2.0},
        {"mode": "2e"},  # the 2e record is removed
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
        {"fib_entry": 0.382, "fib_early": 0.10, "fib_stop": "line_tight"},
        {"fib_entry": 0.382},
        {"fib_entry": 0.236, "fib_stop": "line"},
        {
            "fib_tf": "M15",
            "fib_target": 1.272,
            "max_entry_frac": 0.35,
        },
    )
    for kw in ok:
        bot.Params(mode="fib", m5_trend="h100", early_leg="off", **kw)


def test_fib_params_are_written_into_the_text_and_the_command_line() -> None:
    text = bot.Params(
        mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, fib_early=0.10, fib_stop="line_tight"
    ).text()
    for part in (
        "mode=fib", "fib_tf=M5", "fib_entry=0.382", "fib_early=0.1", "fib_stop=line_tight", "fib_count=off",
        "fib_target=1.618", "max_entry_frac=0.25", "fib_lean=on", "stop_buffer=0.5", "target_buffer=0.5",
        "spread=0.3", "max_orders=1", "order_life_bars=24", "min_r=2",
    ):  # fmt: skip
        assert part in text, part
    for gone in ("fib_range", "range_min_leg", "range_tp", "h1_mode", "band_frac", "trigger_offset"):
        assert gone not in text, gone  # the removed parameters are not written
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main(
            ["--from", "2026-10-01", "--to", "2026-10-02", "--mode", "fib", "--fib-entry", "0.382",
             "--fib-early", "0.1", "--fib-stop", "line_tight", "--fib-target", "1.272",
             "--max-entry-frac", "0.35", "--order-life-bars", "12", "--fib-count", "off"]
        )  # fmt: skip
    finally:
        bot.run = orig  # type: ignore[assignment]
    q = seen["params"]
    assert (q.mode, q.fib_entry, q.fib_early, q.fib_stop, q.fib_target) == (
        "fib", 0.382, 0.1, "line_tight", 1.272,
    )  # fmt: skip
    assert (q.max_entry_frac, q.order_life_bars, q.fib_count) == (0.35, 12, "off")
    with pytest.raises(SystemExit):
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--fib-target", "ext161"])  # withdrawn
    for flag in ("--fib-range", "--range-min-leg", "--range-tp", "--h1-mode", "--h1-tf", "--h1-swings",
                 "--entry-tfs", "--div-mode", "--band-frac", "--band-legs", "--level-min-age-h",
                 "--level-bars", "--counter-pivots", "--trigger-offset"):  # fmt: skip
        with pytest.raises(SystemExit):
            bot.main(["--from", "2026-10-01", "--to", "2026-10-02", flag, "1"])  # removed with H1 and 2e
    for flag, val in (
        ("--max-trend-legs", "5"),
        ("--mode", "2e"),
        ("--fib-count", "on"),
        ("--fib-stop", "swing"),
    ):
        with pytest.raises(SystemExit):
            bot.main(["--from", "2026-10-01", "--to", "2026-10-02", flag, val])  # withdrawn / fixed


# --- rule 1: the H1 lean ------------------------------------------------------------------------------------------


# --- rule 2: the counter-leg ------------------------------------------------------------------------------------------


def pv_of(spec: list[tuple[str, float, int]]) -> list[bot.VPivot]:
    return [bot.VPivot(k == "L", v, p) for k, v, p in spec]


def test_rule2_used_leg_is_not_a_candidate_and_the_key_names_the_leg() -> None:
    d = leg_data()
    out = bot.analyse_leg(d, PB)
    assert out.setup is not None
    assert out.setup.key == f"BUY|M5|{d.times[40]}"  # side, setup timeframe, L0's time (rule 2)
    again = bot.analyse_leg(d, PB, frozenset({out.setup.key}))
    assert again.setup is None and again.reason == "fib: leg already used"
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
    assert s.marker == "withdraw beyond 4100.00" and s.side == "BUY"
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
        "extension 1.618",
    ):
        assert part in s.detail, part


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
    same_time = replace(d, m5_pv=[bot.VPivot(False, 4000.0, 60), *d.m5_pv])
    assert bot.analyse_leg(same_time, PB).reason == why
    out = bot.analyse_leg(leg_data(m5_highs=(4090.0,)), PB)
    assert out.setup is not None and "H100 4100.00 beyond the M5 high 4090.00" in out.setup.detail
    sell = bot.analyse_leg(as_sell(leg_data()), PB)
    assert sell.setup is not None and "beyond the M5 low -4090.00" in sell.setup.detail


# --- rule 4: the count ------------------------------------------------------------------------------------------------


# --- rule 5: the trend run ------------------------------------------------------------------------------------------


# --- rule 6: the level, the order price, the bounce, played out --------------------------------------------------


def test_rule6_needs_a_bounce_above_the_order_price_and_the_price_above_it() -> None:
    # no M5 bar after H100's bar has a high strictly above the order price 4038.2 (they are lowered)
    def no_bounce(hi, lo, cl, macd, rsi):
        hi[61:] = 4030.0

    nb = leg_data(edit=no_bounce)
    assert bot.analyse_leg(nb, PB).reason == "fib: no bounce above the order price"
    assert bot.analyse_leg(as_sell(nb), PB).reason == "fib: no bounce above the order price"

    # a high on H100's own bar is not after it
    def only_h100_bar(hi, lo, cl, macd, rsi):
        hi[61:] = 4030.0
        hi[60] = 4100.1

    assert bot.analyse_leg(leg_data(edit=only_h100_bar), PB).reason == "fib: no bounce above the order price"
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
    assert (
        bot.analyse_leg(as_sell(leg_data(last=4038.2)), PB).reason == "fib: price not above the order price"
    )
    # the 0.618 level: order price 4061.8; the base price 4041 is below it
    d618 = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.618)
    assert bot.analyse_leg(leg_data(), d618).reason == "fib: price not above the order price"
    ok = bot.analyse_leg(leg_data(last=4063.0), d618).setup
    assert ok is not None and ok.order == pytest.approx(4061.8)
    assert (
        bot.analyse_leg(
            leg_data(last=4040.0),
            bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.236),
        ).setup
        is not None
    )


def test_rule6_fib_early_moves_the_order_price_above_the_level() -> None:
    tight = bot.Params(
        mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, fib_early=0.10, fib_stop="line_tight"
    )
    # the price is tested against the order price 4048.2: the base price 4041 is below it
    assert bot.analyse_leg(leg_data(), tight).reason == "fib: price not above the order price"
    s = bot.analyse_leg(leg_data(last=4051.0), tight).setup
    assert s is not None and s.order == pytest.approx(4048.2)  # 4038.2 + 0.10 x 100
    assert s.stop == pytest.approx(4037.7)  # line_tight: the 0.382 level - buffer
    t = bot.analyse_leg(as_sell(leg_data(last=4051.0)), tight).setup
    assert t is not None and t.order == pytest.approx(-4048.2) and t.stop == pytest.approx(-4037.7)


def test_rule6_played_out_target_from_the_first_bar_stop_from_the_next() -> None:
    why = "setup already played out"
    # the 0.618 entry: order 4061.8, line stop 4023.1 (the 0.382 / 0.236 stops lie beyond L0, which a low kills
    # as no leg first); the target lies beyond H100, so a high at it ends the leg by rule 10 first
    p618 = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.618)
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        base = leg_data(last=4063.0)
        j = 61 + int(np.flatnonzero(base.m5_hi_v[61:] > 4061.8)[0])  # the first bar above the order price

        def set_lo(k, v):
            return lambda hi, lo, cl, m, r: lo.__setitem__(k, v)

        assert bot.analyse_leg(wrap(base), p618).reason == "order written"
        # a low at the stop on the first bar above the order price is ignored
        assert (
            bot.analyse_leg(wrap(leg_data(last=4063.0, edit=set_lo(j, 4023.1))), p618).reason
            == "order written"
        )
        # ... but on the next bar it counts, and so does one under it
        for k, v in ((j + 1, 4023.1), (j + 4, 4010.0)):
            e = wrap(leg_data(last=4063.0, edit=set_lo(k, v)))
            assert bot.analyse_leg(e, p618).reason == why, (k, v)
        # a low just above the stop does not
        e = wrap(leg_data(last=4063.0, edit=set_lo(j + 1, 4023.2)))
        assert bot.analyse_leg(e, p618).reason == "order written"


# --- rule 7: the stop -------------------------------------------------------------------------------------------------


def test_rule7_stop_by_entry_and_fib_stop() -> None:
    l0 = bot.VPivot(True, 4000.0, 40)
    line = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.618)
    assert bot.fib_stop_v(line, l0, 100.0) == pytest.approx(4023.6 - 0.5)  # 0.618: beyond 23 %
    for entry in (0.382, 0.236):  # beyond 0 %
        assert bot.fib_stop_v(
            bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=entry), l0, 100.0
        ) == pytest.approx(3999.5)
    tight = bot.Params(
        mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, fib_early=0.10, fib_stop="line_tight"
    )
    assert bot.fib_stop_v(tight, l0, 100.0) == pytest.approx(4038.2 - 0.5)
    # the stop reaches the order: 0.618 line stop, R from it
    s = bot.analyse_leg(leg_data(last=4063.0), line).setup
    assert s is not None and s.stop == pytest.approx(4023.1)
    assert s.r == pytest.approx((s.target - s.order - 0.3) / (s.order - 4023.1))
    t = bot.analyse_leg(as_sell(leg_data(last=4063.0)), line).setup
    assert t is not None and t.stop == pytest.approx(-4023.1)
    assert bot.Params(mode="fib", m5_trend="h100", early_leg="off", stop_buffer=1.0).stop_buffer == 1.0
    wide = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, stop_buffer=2.0)
    assert bot.fib_stop_v(wide, l0, 100.0) == pytest.approx(3998.0)
    assert not hasattr(bot.Params(), "max_trend_legs")  # rule 5 is gone, and the swing stop with it


# --- rule 8: the target is the extension ---------------------------------------------------------------------------


def test_rule8_target_is_the_extension_both_sides_and_both_values() -> None:
    l0, leg = 4000.0, 100.0
    p = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, min_r=0.0)
    assert bot.fib_target_v(p, l0, leg) == pytest.approx(4161.8 - 0.5)  # 1.618 is the default
    q = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, fib_target=1.272)
    assert bot.fib_target_v(q, l0, leg) == pytest.approx(4127.2 - 0.5)
    assert bot.fib_target_v(
        bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, target_buffer=2.0), l0, leg
    ) == (pytest.approx(4161.8 - 2.0))
    for ext, step in ((1.618, "1.618"), (1.272, "1.272")):
        pe = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, fib_target=ext)
        buy = bot.analyse_leg(leg_data(), pe).setup
        sell = bot.analyse_leg(as_sell(leg_data()), pe).setup
        assert buy is not None and sell is not None
        assert buy.target == pytest.approx(4000.0 + ext * 100.0 - 0.5) and buy.step == step
        assert sell.target == pytest.approx(
            -(4000.0 + ext * 100.0 - 0.5)
        )  # the mirror: L0 - ext x leg + buffer
        assert f"extension {step}" in buy.detail and "ladder" not in buy.detail
    # the example of BOT_RULES: leg 3989.14 -> 4025.45, entry 0.382 = 4003.01, stop 3988.64: TP 4047.39, R 3.07
    leg2 = 4025.45 - 3989.14
    order2 = 3989.14 + 0.382 * leg2
    tgt = bot.fib_target_v(p, 3989.14, leg2)
    assert (round(order2, 2), round(tgt, 2)) == (4003.01, 4047.39)
    assert round(bot.planned_r(order2, 3989.14 - 0.5, tgt, 0.3), 2) == 3.07
    # no band is read: the fib path has neither the function nor the parameters
    assert (
        not hasattr(bot, "fib_ladder")
        and not hasattr(p, "major_tf")
        and "bands_v" not in bot.LegData.__annotations__
    )


def test_rule8_no_order_when_r_is_under_min_r_or_the_target_is_not_beyond_the_order_price() -> None:
    # R under the floor: the 1.272 extension of a leg whose order sits deep pays less than 2R
    d = leg_data(last=4063.0)
    deep = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.618, fib_target=1.272)
    out = bot.analyse_leg(d, deep)
    s = bot.analyse_leg(
        d, bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.618)
    ).setup  # 1.618: R 2.56
    assert s is not None and s.r == pytest.approx((4161.3 - 4061.8 - 0.3) / (4061.8 - 4023.1))
    assert out.setup is None and out.reason == "reward under 2R"  # (4126.7 - 4061.8 - 0.3) / 38.7 = 1.67
    # the TP not beyond the order price: a huge target_buffer pulls it under (BUY) / over (SELL)
    pulled = bot.Params(
        mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, target_buffer=130.0, min_r=0.0
    )
    for wrap in (lambda x: x, as_sell):
        o = bot.analyse_leg(wrap(leg_data()), pulled)
        assert o.reason == "fib: no target above the order price" and o.setup is None


def test_rule8_min_r_floor_is_the_parameter() -> None:
    d = leg_data()
    s = bot.analyse_leg(d, PB).setup
    assert s is not None
    above = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, min_r=s.r + 0.01)
    out = bot.analyse_leg(d, above)
    assert out.reason == "reward under 2R" and out.setup is None
    at = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, min_r=s.r)
    assert bot.analyse_leg(d, at).setup is not None  # at the floor passes
    assert bot.planned_r(100.0, 100.0, 110.0, 0.3) == float("-inf")


# --- rule 9: the reach ---------------------------------------------------------------------------------------------


def test_rule9_reach_is_a_share_of_the_leg_both_sides() -> None:
    why = "fib: order price too far from price"
    # the leg is 100: 0.25 x 100 = 25 at the default; the order price 4038.2
    for sell in (False, True):
        wrap = as_sell if sell else (lambda x: x)
        at = leg_data(last=4038.2 + 25.0)
        assert bot.analyse_leg(wrap(at), PB).reason == "order written"  # exactly the limit is reachable
        over = leg_data(last=4038.2 + 25.05)
        out = bot.analyse_leg(wrap(over), PB)
        assert out.reason == why and out.setup is None and "limit 0.25 x 100.00 = 25.00" in out.info["r9"]
        # the limit scales with the leg and the parameter
        tight = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, max_entry_frac=0.15)
        assert bot.analyse_leg(wrap(leg_data(last=4038.2 + 14.9)), tight).setup is not None
        assert bot.analyse_leg(wrap(leg_data(last=4038.2 + 15.1)), tight).reason == why
        wide = bot.Params(mode="fib", m5_trend="h100", early_leg="off", fib_entry=0.382, max_entry_frac=0.35)
        assert bot.analyse_leg(wrap(leg_data(last=4038.2 + 34.9)), wide).setup is not None
    # the reach is a share of the leg, not a fixed amount: nothing in the numbers above is 4.0 USD
    big = bot.analyse_leg(leg_data(last=4038.2 + 4.5), PB)
    assert big.setup is not None  # 4.5 away would have been refused by a fixed 4 USD limit


def decide_inputs(fi, p, used=frozenset()):
    log = dict.fromkeys(bot.LOG_COLUMNS, "")

    def done(reason, info=None, tf=""):
        log["reason"], log["tf"] = reason, tf
        log.update(info or {})
        return bot.Result(log)

    return bot.fib_decision(fi, now_at("2026-10-05 10:00"), p, used, log, done)


# --- rule 13: a BUY and a SELL ----------------------------------------------------------------------------------------


def test_rule13_nearer_order_wins_then_the_buy() -> None:
    buy = leg_data(last=4041.0)  # 2.8 from its order price
    sell = as_sell(leg_data(last=4045.0))  # 6.8 from its order price
    fi = bot.FibInputs("up", bot.H4_NOT_READ, [buy, sell], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0)
    res = decide_inputs(fi, PB)
    assert res.decision is not None and res.decision["side"] == "BUY"
    fi = bot.FibInputs("up", bot.H4_NOT_READ, [leg_data(last=4045.0), as_sell(leg_data(last=4041.0))], pd.DataFrame(),
                       pd.DatetimeIndex([]), [], [], 0.0)  # fmt: skip
    res = decide_inputs(fi, PB)
    assert res.decision is not None and res.decision["side"] == "SELL" and float(res.decision["entry"]) < 0
    fi = bot.FibInputs(
        "up",
        bot.H4_NOT_READ,
        [leg_data(), as_sell(leg_data())],
        pd.DataFrame(),
        pd.DatetimeIndex([]),
        [],
        [],
        0.0,
    )
    res = decide_inputs(fi, PB)
    assert res.decision is not None and res.decision["side"] == "BUY"  # equal distance: the BUY
    # a used BUY leg is not a candidate: the SELL is written
    used = frozenset({bot.analyse_leg(buy, PB).setup.key})  # type: ignore[union-attr]
    res = decide_inputs(fi, PB, used)
    assert res.decision is not None and res.decision["side"] == "SELL"


def test_rule13_log_reason_is_the_one_that_got_furthest_and_a_tie_goes_to_the_buy() -> None:
    far = leg_data(last=4038.0)  # price not above the order price (rule 6)
    early = leg_data(m5_highs=(4120.0,))  # refused at rule 3
    fi = bot.FibInputs(
        "up", bot.H4_NOT_READ, [early, as_sell(far)], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0
    )
    res = decide_inputs(fi, PB)
    assert res.decision is None and res.log["reason"] == "fib: price not above the order price"
    fi = bot.FibInputs(
        "up", bot.H4_NOT_READ, [early, as_sell(early)], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0
    )
    res = decide_inputs(fi, PB)
    assert res.log["reason"] == "fib: M5 trend (H100 not above the M5 high)"
    assert res.log["leg"].startswith("L0 4000.00")  # the BUY's numbers, not the SELL's (negated)


# --- rule 14: the row and the log -----------------------------------------------------------------------------------


def test_rule14_row_fields_structure_and_log_columns() -> None:
    fi = bot.FibInputs("up", bot.H4_NOT_READ, [leg_data()], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0)
    res = decide_inputs(fi, PB)
    d = res.decision
    assert d is not None
    s = d["structure"]
    for part in (
        "bot2e fib M5 BUY", "H4 up (test). Leg", "L0 4000.00@", "H100 4100.00@", "23.6 % 4023.60", "38.2 % 4038.20",
        "61.8 % 4061.80", "M5 trend: H100 4100.00 beyond the M5 high",
        "Entry level 38.2 % = 4038.20", "order price 4038.20", "stop 3999.50", "target 4161.30",
        "extension 1.618", "planned R", "withdraw beyond 4100.00", "Parameters: mode=fib",
        "order_life_bars=24", "fib_entry=0.382",
    ):  # fmt: skip
        assert part in s, part
    assert (d["entry"], d["stop"], d["target"]) == ("4038.20", "3999.50", "4161.30")
    log = res.log
    assert set(log) == set(bot.LOG_COLUMNS)
    for gone in ("count", "pivots", "div_macd", "div_rsi", "r4", "r5", "trend_legs"):
        assert gone not in bot.LOG_COLUMNS, gone  # rules 4 and 5 are not used
    assert "trend legs" not in s and "run of" not in s and "divergence" not in s
    for col in ("r10", "r3", "r6", "r7", "r8", "r9", "order", "stop", "target", "extension", "r"):
        assert log[col], col
    assert log["order"] == "4038.20" and log["extension"] == "1.618" and log["reason"] == "order written"


def test_every_reason_the_code_can_give_is_ranked() -> None:
    src = Path(bot.__file__).read_text(encoding="utf-8")
    given = set(re.findall(r'(?:done\(|\.reason = |FibOut\(|(?<!\.)why = )\s*"([^"]+)"', src))
    given |= set(re.findall(r'\n\s+(?:reason|why)=?"([^"]+)"', src))
    assert "fib: no live leg" in given and "order written" in given and len(given) > 15
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

    def fake(frames, now, p, used=frozenset(), pending=False, windowed=None):
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
    mine, _ = bot.walk_days(["2026-04-06"], bot.Params(mode="fib", order_life_bars=3, windows="on"), full)
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
def test_acceptance_19_oct_0700_h4_not_clear_and_no_fade_leg(full) -> None:
    """19/10 07:00: H4 reads not clear (highs 4184.25 -> 4217.08, lows 4104.21 -> 4066.42), so a fade leg is
    wanted; the latest M5 run does not pass fade_min, so neither side has a leg and no order is written."""
    res, fi, p = at(full, "2026-10-19 07:00")
    assert fi.h4 == "none" and fi.h4_text.startswith(
        "H4 not clear (highs 4184.25->4217.08, lows 4104.21->4066.42)"
    )
    assert [bot.analyse_leg(d, p).reason for d in fi.datas] == [
        "fib: no live leg"
    ] * 2 and res.decision is None


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
            bot.Params(mode="fib", fib_tf="M15", fib_target=1.272),
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
    """The price-negated series (k - price) gives the mirrored answer: the reasons are the same, and an order's
    prices are k - the original's, and rule 16's H4 reading flips."""
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
        wa, wb = a.log["rule16"].split(" "), b.log["rule16"].split(" ")
        assert wa[0] == wb[0] == "H4", text
        assert {"up": "down", "down": "up", "not": "not"}[wa[1]] == wb[1], (
            text
        )  # H4 trend flips with the mirror
        assert (a.decision is None) == (b.decision is None), text
        if a.decision is not None and b.decision is not None:
            assert flip[a.decision["side"]] == b.decision["side"]
            for col in ("entry", "stop", "target"):
                assert float(b.decision[col]) == pytest.approx(k - float(a.decision[col]), abs=0.011)


@needs_data
def test_fib_walk_one_window_writes_known_reasons_and_scores(full, tmp_path) -> None:
    """The walk over one day's Asia window on stored bars: every log row has a known reason, the row layout is
    the ledger's, a written order is scored by the new rules."""
    p = bot.Params(mode="fib", fib_entry=0.382, min_r=0.0, max_entry_frac=0.35, windows="on")
    mine, logs = bot.walk_days(["2026-10-13"], p, full)  # (writes an order or not: both are checked below)
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
        (  # a trend leg BUY (H4 up): H100 the latest fixed high, L0 the low before it, the 0.382 level
            "2026-10-20 14:35",
            {},
            ("BUY", "4125.40", "4117.96", "4147.38", "1.618", "2.91"),
            ("20/10 14:35", "4117.96", "stop", "-1.04"),
        ),
        (  # a trend leg SELL (H4 down), the mirror of every BUY rule
            "2026-10-06 13:20",
            {},
            ("SELL", "4129.09", "4139.32", "4098.09", "1.618", "3.00"),
            ("06/10 13:20", "4139.32", "stop", "-1.03"),
        ),
        (  # a fade SELL after a run up (H4 not clear): limit at 0.5, stop beyond E, the 1.618 target
            "2026-10-15 14:15",
            {},
            ("SELL", "4148.97", "4162.19", "4121.03", "1.618", "2.09"),
            ("15/10 15:05", "4162.19", "stop", "-1.02"),
        ),
        (  # a fade BUY after a run down (H4 not clear): the limit never fills
            "2026-10-15 20:10",
            {},
            ("BUY", "4144.84", "4129.98", "4176.47", "1.618", "2.11"),
            ("", "", "no fill", "0.0"),
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
    assert (d["side"], d["entry"], d["stop"], d["target"], res.log["extension"], res.log["r"]) == row
    d["id"] = "X"
    got = score_mod.score(d, score_mod.bars(), score_mod.start_of(d, {}), p.spread)
    assert (got["fill"], got["exit"], got["why"], got["r_net"]) == scored


def _keyed_decide(monkeypatch, entry: str = "5000.00"):
    """A stand-in decide: at the first free bar of an Asia window it writes one fib-style row on a fixed leg
    key, unless that key is used (this isolates rule 2's bookkeeping from the market). ``entry`` 5000 is a BUY
    limit far above the market: it fills on the next bar; 1.00 is far below: it never fills and expires."""
    key = "BUY|M5|2026-10-12 05:00:00+00:00"

    def fake(frames, now, p, used=frozenset(), pending=False, windowed=None):
        log = dict.fromkeys(bot.LOG_COLUMNS, "")
        if pending or key in used or bot.window_of(now) != "Asia":
            log["reason"] = "order pending" if pending else "outside window"
            return bot.Result(log)
        log["reason"] = "order written"
        t = now.tz_convert(TH) - pd.Timedelta(minutes=5)
        row = {c: "" for c in bot.LEDGER_COLUMNS}
        row.update(
            cutoff_thai=f"{t:%Y-%m-%d} 07:00", decided_at=f"{t:%d/%m %H:%M}", side="BUY", entry=entry,
            stop="0.50", target="99998", reader="bot2e",
            structure=f"bot2e fib x. Key [{key}]. Parameters: mode=fib order_life_bars=3",
        )  # fmt: skip
        return bot.Result(log, row, key=key)

    monkeypatch.setattr(bot, "decide", fake)
    return key


@needs_data
def test_a_leg_is_used_across_runs_the_keys_of_the_ledger_rows_count(full, monkeypatch) -> None:
    """Rule 2: a leg is used once an order on it FILLS, in this run or an earlier one. Two walks over overlapping
    days: the second, given the first's (filled) rows as the ledger, writes none of the same key; the row
    carries its key, and a row without one (any other reader) adds none."""
    key = _keyed_decide(monkeypatch)
    p = bot.Params(mode="fib", windows="on")
    first, _ = bot.walk_days(["2026-10-13"], p, full)
    assert [bot.row_key(r) for r in first] == [key]
    second, _ = bot.walk_days(["2026-10-13", "2026-10-14"], p, full, first)
    assert second == []
    again, _ = bot.walk_days(
        ["2026-10-13"], p, full
    )  # the control: without the ledger rows it is written again
    assert [bot.row_key(r) for r in again] == [key]
    assert bot.row_key({"structure": "bot2e 5m BUY ..."}) == "" and bot.row_key({}) == ""


@needs_data
def test_run_seeds_used_from_every_kept_row_later_days_too(full, tmp_path, monkeypatch) -> None:
    """Rule 2 through run(): the rows of the days a run walks are replaced, every other row is kept and its
    key is used - a row on a LATER day too. The same leg is not written on the earlier day again."""
    key = _keyed_decide(monkeypatch)
    p = bot.Params(mode="fib", windows="on")
    ledger, log = tmp_path / "l.csv", tmp_path / "g.csv"
    bot.run("2026-10-13", "2026-10-13", p, ledger, log)
    rows = bot._read(ledger, bot.LEDGER_COLUMNS)
    assert [bot.row_key(r) for r in rows] == [key]
    later = [
        {**r, "cutoff_thai": "2026-10-14 07:00", "id": r["id"].replace("20261013", "20261014")} for r in rows
    ]
    bot._write(ledger, bot.LEDGER_COLUMNS, later)
    bot.run("2026-10-13", "2026-10-13", p, ledger, log)
    after = bot._read(ledger, bot.LEDGER_COLUMNS)
    assert [
        r for r in after if r["cutoff_thai"][:10] == "2026-10-13"
    ] == []  # the kept later row's key is used
    assert [r for r in after if r["cutoff_thai"][:10] == "2026-10-14"] == later  # and the later row stays
    bot._write(ledger, bot.LEDGER_COLUMNS, [])  # control: with the later row gone it is written again
    bot.run("2026-10-13", "2026-10-13", p, ledger, log)
    assert [bot.row_key(r) for r in bot._read(ledger, bot.LEDGER_COLUMNS)] == [key]


@needs_data
def test_a_leg_is_used_only_when_its_order_fills_an_expired_order_frees_it(full, monkeypatch) -> None:
    """Rule 2 / 12: an order that waits blocks its leg; one that expires unfilled frees it (the Fibo moves while
    there is no trade) - the leg is written again - and in the ledger of an earlier run only a row that FILLED
    counts. With a filling entry the leg is written once."""
    key = _keyed_decide(monkeypatch, entry="1.00")  # never fills: expires after 3 bars
    p = bot.Params(mode="fib", order_life_bars=3, windows="on")
    rows, _ = bot.walk_days(["2026-10-13"], p, full)
    assert len(rows) >= 3 and {bot.row_key(r) for r in rows} == {key}  # written again after each expiry
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    # the rows of an earlier run that never filled do not use the leg
    again, _ = bot.walk_days(["2026-10-13"], p, full, (), kept=rows)
    assert len(again) >= 3
    # a filling order uses it once, whatever happens to the order afterwards
    _keyed_decide(monkeypatch, entry="5000.00")
    filled, _ = bot.walk_days(["2026-10-13"], p, full)
    assert [bot.row_key(r) for r in filled] == [key]
    again2, _ = bot.walk_days(["2026-10-13"], p, full, (), kept=filled)
    assert again2 == []  # a kept row that filled uses the leg


def test_old_log_ladder_values_are_carried_into_extension(tmp_path) -> None:
    """A bot_log.csv written with the old ``ladder`` header keeps those values under ``extension``."""
    path = tmp_path / "log.csv"
    path.write_text(
        "date,reason,ladder,r\n2026-10-13,order written,1.618,3.07\n2026-10-14,x,,\n", encoding="utf-8"
    )
    rows = bot._read(path, bot.LOG_COLUMNS)
    assert [r["extension"] for r in rows] == ["1.618", ""] and rows[0]["r"] == "3.07"
    bot._write(path, bot.LOG_COLUMNS, rows)
    assert bot._read(path, bot.LOG_COLUMNS)[0]["extension"] == "1.618"


def test_fib_lean_switch_validated_in_text_and_cli() -> None:
    assert bot.Params().fib_lean == "on" and "fib_lean=on" in bot.Params().text()
    assert "fib_lean=off" in bot.Params(fib_lean="off").text()
    with pytest.raises(ValueError):
        bot.Params(fib_lean="maybe")
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--fib-lean", "off"])
    finally:
        bot.run = orig  # type: ignore[assignment]
    assert seen["params"].fib_lean == "off"


# range LOW 4000 / HIGH 4100 (height 100): the HIGH zone is 4088..4127, the LOW zone 3973..4012
BASE = [("LOW", 4000.0), ("HIGH", 4100.0)]


# --- look-ahead: a pivot is used only once its confirm bar has closed ---------------------------------------------


def walk_frame(n: int, freq: str, end: str, seed: int) -> pd.DataFrame:
    """A random-walk OHLC frame of ``n`` bars of ``freq`` whose last bar opens at ``end`` (UTC)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=n, freq=freq)
    close = 4000.0 + np.cumsum(rng.normal(0, 3.0, n))
    spread = np.abs(rng.normal(0, 1.5, n)) + 0.2
    return pd.DataFrame(
        {"open": close, "high": close + spread, "low": close - spread, "close": close}, index=idx
    )


@pytest.mark.parametrize(("freq", "end"), [("15min", "2026-10-05 11:45"), ("5min", "2026-10-05 11:55")])
def test_lookahead_a_pivot_is_absent_until_its_confirm_bar_has_closed(freq, end) -> None:
    """M15 and M5: take a pivot of the full series; the frame cut just before its confirm bar does not
    return it, the frame that includes the confirm bar does; and no returned pivot ever has a confirm bar at or
    beyond the frame's length."""
    df = walk_frame(1700, freq, end, seed=11)
    full = bot._zigzag(df)
    target = next(s for s in reversed(full) if s.confirm_pos < len(df) - 5)
    c = target.confirm_pos
    before, with_it = bot._zigzag(df.iloc[:c]), bot._zigzag(df.iloc[: c + 1])
    assert target.pivot_pos not in [
        s.pivot_pos for s in before if s.kind is target.kind and s.price == target.price
    ]
    assert any(s.pivot_pos == target.pivot_pos and s.price == target.price for s in with_it)
    for cut_at in (c, c + 1, c + 40, len(df)):
        frame = df.iloc[:cut_at]
        assert all(s.confirm_pos < len(frame) for s in bot._zigzag(frame))


def test_lookahead_fib_inputs_reads_only_confirmed_pivots_on_every_timeframe() -> None:
    end = {"H4": "2026-10-05 08:00", "M15": "2026-10-05 11:45", "M5": "2026-10-05 11:55"}
    freq = {"H4": "4h", "M15": "15min", "M5": "5min"}
    frames = {tf: walk_frame(1700, freq[tf], end[tf], seed=3 + i) for i, tf in enumerate(freq)}
    now = pd.Timestamp("2026-10-05 12:00", tz="UTC")
    for tf in ("M5", "M15"):
        fi = bot.fib_inputs(frames, now, bot.Params(mode="fib", fib_tf=tf))
        assert fi.zz and fi.m5_zz
        assert all(s.confirm_pos < len(fi.df) for s in fi.zz)
        assert all(s.confirm_pos < min(len(frames["M5"]), bot.FIB_BARS) for s in fi.m5_zz)
        # the M5 / setup pivots used are exactly those of the closed frame
        assert [s.pivot_pos for s in fi.zz] == [
            s.pivot_pos for s in bot._zigzag(frames[tf].tail(bot.FIB_BARS))
        ]


# --- no H1, and rule 16's H4 ---------------------------------------------------------------------------


def test_the_bot_reads_h4_m15_and_m5_only() -> None:
    """Rule 0: H4 (rule 16), M15 and M5. ``cut`` keeps those three; any other frame handed in is dropped and never
    read; the warm-up counts H4 and M5 (and M15 as the setup timeframe)."""
    assert bot.TIMEFRAMES == ("H4", "M15", "M5")
    end = {"H4": "2026-10-05 08:00", "M15": "2026-10-05 11:45", "M5": "2026-10-05 11:55"}
    freq = {"H4": "4h", "M15": "15min", "M5": "5min"}
    three = {tf: walk_frame(1700, freq[tf], end[tf], seed=3 + i) for i, tf in enumerate(freq)}
    now = pd.Timestamp("2026-10-05 12:00", tz="UTC")
    extra = {**three, "H1": walk_frame(1700, "1h", "2026-10-05 11:00", seed=9)}
    assert set(bot.cut(extra, now)) == {"H4", "M15", "M5"}  # an H1 frame given to ``cut`` is not carried on
    for tf in ("M5", "M15"):
        res = bot.decide(bot.cut(three, now), now, bot.Params(fib_tf=tf), windowed=False)
        assert res.log["reason"] in bot.RANK and res.log["reason"] != "warm-up"
        assert res.log["rule16"].startswith("H4 ")
    short_h4 = {**bot.cut(three, now), "H4": three["H4"].iloc[:1000]}
    assert bot.decide(short_h4, now, bot.Params(), windowed=False).log["reason"] == "warm-up"
    short_m15 = {**bot.cut(three, now), "M15": three["M15"].iloc[:1000]}
    assert bot.decide(short_m15, now, bot.Params(), windowed=False).log["reason"] != "warm-up"  # M5 setup: ok
    assert bot.decide(short_m15, now, bot.Params(fib_tf="M15"), windowed=False).log["reason"] == "warm-up"
    src = Path(bot.__file__).read_text(encoding="utf-8")
    assert '"H1"' not in src and '"M30"' not in src
    for gone in ("h1_lean", "h1_range", "range_gate", "h1_side", "h1_bands", "level_bands", "lean_view",
                 "analyse_view", "step2", "H1Range", "Setup", "Outcome", "_row", "FRAME_BARS_2E", "SideStrip",
                 "side_strip", "rule16_side", "Frames", "written_side"):  # fmt: skip
        assert not hasattr(bot, gone), gone
    assert set(bot.FRAME_BARS) == {"H4", "M15", "M5"} and "signal_study" not in src
    for col in ("lean", "r11", "h1_mode", "band", "kind", "step3", "step4", "step5"):
        assert col not in bot.LOG_COLUMNS, col


@needs_data
def test_load_frames_holds_h4_m15_and_m5(full) -> None:
    assert set(full) == {"H4", "M15", "M5"} and set(bot.load_frames()) == {"H4", "M15", "M5"}


# --- rule 16: H4's clear trend, else a fade ----------------------------------------------------------------------


@needs_data
def test_acceptance_27_oct_1830_h4_not_clear_and_no_fade_leg(full) -> None:
    """27/10 18:30: H4 not clear (highs 4217.08 -> 4198.73, lows 4066.42 -> 4073.41): a fade is wanted but the latest
    run is not long enough (fade_min) - no leg on either side, no order."""
    res, fi, p = at(full, "2026-10-27 18:30")
    assert fi.h4 == "none" and res.decision is None
    assert [bot.analyse_leg(d, p).reason for d in fi.datas] == ["fib: no live leg"] * 2


def test_setup_days_parameter_text_and_refused_values() -> None:
    assert bot.Params().setup_days == 2 and "setup_days=2" in bot.Params().text()
    for bad in (1, 3, 0, 2.5, "2"):
        with pytest.raises(ValueError):
            bot.Params(setup_days=bad)  # type: ignore[arg-type]
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--setup-days", "2"])
    finally:
        bot.run = orig  # type: ignore[assignment]
    assert seen["params"].setup_days == 2
    with pytest.raises(SystemExit):
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--setup-days", "3"])
    assert (bot.state11.BARS_PER_DAY["M5"], bot.state11.BARS_PER_DAY["M15"]) == (274, 92)


def test_setup_look_the_leg_needs_l0_and_h100_inside() -> None:
    """leg_data: L0 at position 40, H100 at 60. A look starting at 40 holds both (the leg is read); one
    starting at 41 leaves L0 outside, and one starting at 61 leaves H100 outside: no leg, either side."""
    for sell in (False, True):
        d = as_sell(leg_data()) if sell else leg_data()
        assert bot.analyse_leg(replace(d, look_lo=40), PB).reason == "order written"
        for lo in (41, 50, 60, 61):
            out = bot.analyse_leg(replace(d, look_lo=lo), PB)
            assert out.reason == "fib: no live leg" and out.setup is None, lo
    assert bot.analyse_leg(leg_data(), PB).reason == "order written"  # the default look starts at the frame


def test_setup_look_bounds_the_m5_pivots_of_rules_3_and_5() -> None:
    """fib_inputs: the M5 pivots rules 3 and 5 read are those of the 1,500-bar M5 frame whose pivot bar lies in
    the last 2 x 274 M5 bars; with fib_tf M15 the leg's look is 2 x 92 M15 bars while rules 3 and 5 still read
    2 days of M5. The frame's own pivots (fi.m5_zz, fi.zz) are all of them: the look only chooses."""
    end = {"H4": "2026-10-05 08:00", "M15": "2026-10-05 11:45", "M5": "2026-10-05 11:55"}
    freq = {"H4": "4h", "M15": "15min", "M5": "5min"}
    frames = {tf: walk_frame(1700, freq[tf], end[tf], seed=3 + i) for i, tf in enumerate(freq)}
    now = pd.Timestamp("2026-10-05 12:00", tz="UTC")
    for tf, leg_days_bars in (("M5", 548), ("M15", 184)):
        fi = bot.fib_inputs(frames, now, bot.Params(fib_tf=tf))
        m5_lo = bot.FIB_BARS - 548  # the M5 look: 2 days x 274 bars, in the 1,500-bar M5 frame
        every = [s.pivot_pos for s in fi.m5_zz]
        assert any(x < m5_lo for x in every) and any(x >= m5_lo for x in every)  # the cut is not vacuous
        for d in fi.datas:
            assert [q.pos for q in d.m5_pv] == [x for x in every if x >= m5_lo], (tf, d.side)
        assert fi.datas[0].look_lo == bot.FIB_BARS - leg_days_bars  # the leg's look in the setup frame
        assert any(s.pivot_pos < fi.datas[0].look_lo for s in fi.zz)  # the frame's pivots are all kept
        assert [q.pos for q in fi.datas[0].pv] == [s.pivot_pos for s in fi.zz]


# --- rule 3: the M5 trend at the decision (m5_trend now) ----------------------------------------------------------

PN = bot.Params(fib_entry=0.382)  # m5_trend now is the default


def view_pivots(highs, lows):
    """M5 pivots in the view, in time order H, L, H, L ... (positions 1, 2, 3, 4, before H100 at 10)."""
    out, pos = [], 1
    for i in range(max(len(highs), len(lows))):
        if i < len(highs):
            out.append(bot.VPivot(False, highs[i], pos))
            pos += 1
        if i < len(lows):
            out.append(bot.VPivot(True, lows[i], pos))
            pos += 1
    return out


def with_m5(d, highs, lows):
    return replace(d, m5_pv=view_pivots(highs, lows))


def test_m5_trend_now_up_down_mixed_equal_and_too_few_pivots() -> None:
    why = "fib: no M5 trend of its side"
    cases = (  # (view highs, view lows, the view's state)
        ((4080.0, 4090.0), (4000.0, 4010.0), "UP"),
        ((4090.0, 4080.0), (4010.0, 4000.0), "DOWN"),
        ((4080.0, 4090.0), (4010.0, 4000.0), "none"),  # higher high, lower low
        ((4090.0, 4080.0), (4000.0, 4010.0), "none"),  # lower high, higher low
        ((4080.0, 4080.0), (4000.0, 4010.0), "none"),  # equal highs: not strictly above
        ((4080.0, 4090.0), (4000.0, 4000.0), "none"),  # equal lows
        ((4080.0, 4080.0), (4000.0, 4000.0), "none"),
        ((4090.0,), (4000.0, 4010.0), "none"),  # fewer than two highs
        ((4080.0, 4090.0), (4000.0,), "none"),  # fewer than two lows
        ((), (), "none"),
    )
    for highs, lows, state in cases:
        assert bot.m5_state(view_pivots(highs, lows))[0] == state, (highs, lows)
        buy = bot.analyse_leg(with_m5(leg_data(), highs, lows), PN)
        sell = bot.analyse_leg(with_m5(as_sell(leg_data()), highs, lows), PN)
        # a BUY needs UP; in a SELL's view the real DOWN is "UP" - the same view data is a SELL's trend
        assert (buy.reason == why) == (state != "UP"), (highs, lows, buy.reason)
        assert (sell.reason == why) == (state != "UP"), (highs, lows, sell.reason)
        if state == "UP":
            assert buy.reason == "order written" and sell.reason == "order written"
            assert buy.info["r3"].startswith("M5 UP (") and "a BUY needs UP" in buy.info["r3"]
            assert sell.info["r3"].startswith("M5 DOWN (") and "a SELL needs DOWN" in sell.info["r3"]
            assert "M5 trend UP (" in buy.setup.detail and "M5 trend DOWN (" in sell.setup.detail  # type: ignore[union-attr]
        elif state == "DOWN":  # the real DOWN for the BUY, the real UP for the SELL: both against their side
            assert buy.info["r3"].startswith("M5 DOWN (") and sell.info["r3"].startswith("M5 UP (")
        else:
            assert buy.info["r3"].startswith("M5 no trend (")


def test_m5_trend_now_reads_the_latest_two_of_each_kind_wherever_they_fall() -> None:
    """Older pivots do not matter; the latest two highs and lows are taken after, around or before L0."""
    older_down = view_pivots((4090.0, 4080.0, 4085.0, 4095.0), (4010.0, 4000.0, 4005.0, 4015.0))
    assert bot.m5_state(older_down)[0] == "UP"  # latest highs 4085 -> 4095, lows 4005 -> 4015
    later_down = view_pivots((4070.0, 4090.0, 4080.0), (4000.0, 4010.0, 4005.0))
    assert bot.m5_state(later_down)[0] == "DOWN"  # latest highs 4090 -> 4080, lows 4010 -> 4005
    # pivots after L0 (positions 70, 80 in leg_data) count as well
    d = leg_data()
    late = [bot.VPivot(False, 4001.0, 85), bot.VPivot(True, 3990.0, 86), bot.VPivot(False, 4003.0, 87),
            bot.VPivot(True, 3995.0, 88)]  # fmt: skip
    assert bot.m5_state(late)[0] == "UP"
    assert bot.analyse_leg(replace(d, m5_pv=[*d.m5_pv, *late]), PN).reason != "fib: no M5 trend of its side"


def test_m5_trend_h100_is_unchanged_and_still_selectable() -> None:
    assert bot.Params().m5_trend == "now" and "m5_trend=now" in bot.Params().text()
    assert "m5_trend=h100" in bot.Params(m5_trend="h100", early_leg="off").text()
    with pytest.raises(ValueError):
        bot.Params(m5_trend="later")
    why = "fib: M5 trend (H100 not above the M5 high)"
    assert bot.analyse_leg(leg_data(m5_highs=(4090.0,)), PB).reason == "order written"
    assert bot.analyse_leg(leg_data(m5_highs=(4120.0,)), PB).reason == why
    # the h100 test ignores the M5 UP / DOWN reading: pivots that are no trend still pass when H100 is above
    mixed = with_m5(leg_data(m5_highs=()), (4080.0, 4090.0), (4010.0, 4000.0))
    assert bot.analyse_leg(mixed, PB).reason == "order written"
    assert bot.analyse_leg(mixed, PN).reason == "fib: no M5 trend of its side"
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--m5-trend", "h100"])
    finally:
        bot.run = orig  # type: ignore[assignment]
    assert seen["params"].m5_trend == "h100"
    with pytest.raises(SystemExit):
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--m5-trend", "x"])
    assert bot.RANK["fib: against the H4 trend"] < bot.RANK["fib: no live leg"]


def test_m5_trend_now_ignores_an_unfixed_pivot_and_a_pivot_outside_the_look() -> None:
    """Through fib_inputs on a seeded M5 walk: a pivot is read only once its confirm bar has closed, and only if
    its pivot bar lies in the last 2 x 274 M5 bars; M15 legs read the same M5 pivots."""
    h4 = walk_frame(1700, "4h", "2026-10-05 08:00", seed=2)
    m15 = walk_frame(1700, "15min", "2026-10-05 11:45", seed=3)
    m5 = walk_frame(1700, "5min", "2026-10-05 11:55", seed=7)
    zz = bot._zigzag(m5)
    target = next(q for q in reversed(zz) if q.confirm_pos < len(m5) - 5 and q.pivot_pos > len(m5) - 200)
    c = target.confirm_pos
    t_pivot = m5.index[target.pivot_pos]

    def read(upto: int, tf: str = "M5"):
        frames = {"H4": h4, "M15": m15, "M5": m5.iloc[:upto]}
        fi = bot.fib_inputs(frames, pd.Timestamp("2026-10-05 12:00", tz="UTC"), bot.Params(fib_tf=tf))
        d = fi.datas[0]
        return {pd.Timestamp(d.m5_ptimes[q.pos]) for q in d.m5_pv}, fi

    before, _ = read(c)  # the confirm bar (position c) has not closed
    after, fi = read(c + 1)
    assert t_pivot not in before and t_pivot in after  # the unfixed pivot is not read; once fixed it is
    # a pivot outside the look is not read: every pivot of the frame older than 2 days of M5 is absent
    lo_time = fi.datas[0].m5_ptimes[bot.FIB_BARS - 548]
    older = {pd.Timestamp(m5.iloc[: c + 1].tail(bot.FIB_BARS).index[s.pivot_pos]) for s in fi.m5_zz}
    assert any(t < lo_time for t in older) and all(t >= lo_time for t in after)
    # an M15 leg reads the same M5 pivots
    assert read(c + 1, "M15")[0] == after


# --- rule 2: the early leg, the latest fixed low, and the keys ---------------------------------------------------


def test_early_leg_parameter_default_text_validation_and_cli() -> None:
    assert bot.Params().early_leg == 0.382 and "early_leg=0.382" in bot.Params().text()
    assert (
        "early_leg=off" in bot.Params(early_leg="off").text()
        and bot.Params(early_leg=0.618).early_leg == 0.618
    )
    for bad in (0.5, 0.236, "on", 1, None):
        with pytest.raises(ValueError):
            bot.Params(early_leg=bad)  # type: ignore[arg-type]
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        for flag, want in (("0.618", 0.618), ("off", "off"), ("0.382", 0.382)):
            bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--early-leg", flag])
            assert seen["params"].early_leg == want
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02"])
        assert seen["params"].early_leg == 0.382
    finally:
        bot.run = orig  # type: ignore[assignment]
    with pytest.raises(SystemExit):
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--early-leg", "0.5"])


# --- rule 2: the leg traded with it (0 % at the start, 100 % at the end) --------------------------------------------


def lows_after(n: int, base: float = 4090.0):
    """Setup-frame highs and lows (view) at ``base`` and ``base - 1`` everywhere, for the leg unit tests."""
    return np.full(n, base), np.full(n, base - 1.0)


def test_rule2_fixed_leg_h100_is_the_latest_fixed_high_and_l0_the_low_before_it() -> None:
    _, lo = lows_after(90, 4090.0)
    spec = [("H", 4150.0, 5), ("L", 4000.0, 10), ("H", 4100.0, 20), ("L", 4040.0, 30), ("H", 4120.0, 40)]
    for sign in (1, -1):  # the SELL: the same shape negated, read through to_view
        pv = bot.to_view(swings_of(pv_of(spec), sign), sign)
        assert [(q.low, q.price, q.pos) for q in pv] == [(q.low, q.price, q.pos) for q in pv_of(spec)]
        leg = bot.fib_leg(pv, lo)
        assert leg is not None and not leg.early
        # the end: the latest fixed HIGH (4120); the start: the fixed LOW right before it (4040)
        assert (leg.l0.price, leg.h100.price) == (4040.0, 4120.0)
    # the latest fixed pivot being a LOW does not change the leg: it is still the latest HIGH and the low before it
    leg2 = bot.fib_leg(pv_of([*spec, ("L", 4060.0, 50)]), lo)
    assert leg2 is not None and (leg2.l0.price, leg2.h100.price) == (4040.0, 4120.0)
    # the 07/10 shape (SELL, in the view): HIGH 4184.25 -> LOW 4161.42 is a leg, start 4184.25 end 4161.42
    seven = bot.to_view(
        [
            Swing(SwingKind.LOW, 4154.21, 10, 13, 10, 13),
            Swing(SwingKind.HIGH, 4184.25, 20, 23, 20, 23),
            Swing(SwingKind.LOW, 4161.42, 30, 33, 30, 33),
        ],
        -1,
    )
    sell = bot.fib_leg(seven, lo)
    assert sell is not None and (sell.l0.price, sell.h100.price) == (-4184.25, -4161.42)
    # no leg: no pivots, no high, a high first, a high that is not above its low
    assert bot.fib_leg([], lo) is None and bot.fib_leg(pv_of([("L", 4000.0, 10)]), lo) is None
    assert bot.fib_leg(pv_of([("H", 4100.0, 10)]), lo) is None
    assert bot.fib_leg(pv_of([("L", 4100.0, 10), ("H", 4100.0, 20)]), lo) is None  # leg = 0
    assert bot.fib_leg(pv_of([("H", 4100.0, 10), ("L", 4000.0, 20), ("L", 3990.0, 25)]), lo) is None


def test_rule2_a_low_below_l0_after_h100_leaves_no_leg() -> None:
    pv = pv_of([("L", 4000.0, 10), ("H", 4100.0, 20)])
    _, lo = lows_after(60, 4090.0)
    assert bot.fib_leg(pv, lo) is not None
    lo[40] = 4000.0  # a touch of L0 is not below it
    assert bot.fib_leg(pv, lo) is not None
    lo[40] = 3999.9  # the start is broken
    assert bot.fib_leg(pv, lo) is None
    lo[40], lo[15] = 4050.0, 3900.0  # a low BEFORE H100's bar does not count
    assert bot.fib_leg(pv, lo) is not None
    # through the rules, both sides
    d = leg_data(edit=lambda hi, lo, cl, m, r: lo.__setitem__(70, 3999.0))
    for wrap in (lambda x: x, as_sell):
        assert bot.analyse_leg(wrap(d), PB).reason == "fib: no live leg"


def test_rule10_a_high_beyond_a_fixed_h100_retires_the_leg_but_the_next_leg_can_follow() -> None:
    why = "fib: leg has run (100 % traded)"
    for wrap in (lambda x: x, as_sell):
        assert (
            bot.analyse_leg(
                wrap(leg_data(edit=lambda hi, lo, cl, m, r: hi.__setitem__(70, 4100.05))), PB
            ).reason
            == why
        )
    # the break: the new high fixes as the next leg's end - the pivots now end ... L0, H100, Lf, H100' - and that
    # leg is the latest (its start is the low before it, not the retired L0)
    pv = pv_of([("L", 4000.0, 40), ("H", 4100.0, 60), ("L", 4070.0, 70), ("H", 4120.0, 80)])
    _, lo = lows_after(90, 4110.0)
    leg = bot.fib_leg(pv, lo)
    assert leg is not None and (leg.l0.price, leg.h100.price) == (4070.0, 4120.0)


def early_pv():
    """Pivots ending with a LOW: ... HIGH Hp 4100, LOW Lf 4000 - the early leg's frame (range 100)."""
    return pv_of([("H", 4100.0, 20), ("L", 4000.0, 30)])


def early_arrays(n: int = 90):
    hi, lo = np.full(n, 4010.0), np.full(n, 4005.0)  # after Lf: no low below 4000, highs low
    return hi, lo


def test_early_leg_triggers_exactly_at_the_threshold_for_both_fractions() -> None:
    for frac, thr in ((0.382, 4038.2), (0.618, 4061.8)):  # Lf + frac x (Hp - Lf)
        hi, lo = early_arrays()
        hi[40] = thr
        leg = bot.early_leg(early_pv(), hi, lo, frac)
        assert leg is not None and leg.early
        assert (leg.l0.price, leg.l0.pos, leg.l0.low) == (4000.0, 30, True)
        assert (leg.h100.price, leg.h100.pos, leg.h100.low) == (thr, 40, False)  # provisional end
        hi[40] = thr - 0.01  # just below the threshold: no early leg yet
        assert bot.early_leg(early_pv(), hi, lo, frac) is None
        hi[40] = thr + 20.0
        assert bot.early_leg(early_pv(), hi, lo, frac) is not None  # further is enough


def test_early_leg_provisional_end_moves_and_a_low_below_lf_kills_it() -> None:
    hi, lo = early_arrays()
    hi[40] = 4050.0
    first = bot.early_leg(early_pv(), hi, lo, 0.382)
    hi[45] = 4060.0  # a new high: the provisional end moves
    moved = bot.early_leg(early_pv(), hi, lo, 0.382)
    assert first is not None and moved is not None
    assert (first.h100.price, first.h100.pos, moved.h100.price, moved.h100.pos) == (4050.0, 40, 4060.0, 45)
    hi[50] = 4060.0  # the same high again later: the earliest bar holding it stays
    again = bot.early_leg(early_pv(), hi, lo, 0.382)
    assert again is not None and again.h100.pos == 45
    lo[48] = 4000.0  # a touch of Lf is not below it
    assert bot.early_leg(early_pv(), hi, lo, 0.382) is not None
    lo[48] = 3999.9  # a low below Lf: no early leg
    assert bot.early_leg(early_pv(), hi, lo, 0.382) is None
    lo[48], lo[25] = 4005.0, 3900.0  # a low BEFORE Lf's pivot bar does not count
    assert bot.early_leg(early_pv(), hi, lo, 0.382) is not None
    # the frame: the latest pivot must be a LOW with a HIGH before it
    assert bot.early_leg(pv_of([("L", 4000.0, 20), ("H", 4100.0, 30)]), hi, lo, 0.382) is None
    assert bot.early_leg(pv_of([("L", 3990.0, 10), ("L", 4000.0, 30)]), hi, lo, 0.382) is None
    assert bot.early_leg(pv_of([("L", 4000.0, 30)]), hi, lo, 0.382) is None
    assert (
        bot.early_leg(pv_of([("H", 4000.0, 20), ("L", 4000.0, 30)]), hi, lo, 0.382) is None
    )  # Hp not above Lf


def early_data(highs: dict[int, float], frac=0.382, **kw):
    """A BUY ``LegData`` in the early-leg frame (pivots HIGH 4100@20, LOW 4000@30), the given highs after Lf."""
    base = leg_data()
    n = len(base.times)
    hi, lo = np.full(n, 4010.0), np.full(n, 4005.0)
    for pos, v in highs.items():
        hi[pos] = v
    return replace(base, pv=early_pv(), hi_v=hi, lo_v=lo, m5_hi_v=hi, m5_lo_v=lo, m5_pv=list(early_pv()),
                   price_v=4041.0, **kw)  # fmt: skip


def test_early_leg_is_the_latest_leg_through_the_rules_both_sides() -> None:
    on = bot.Params(fib_entry=0.382, m5_trend="h100", early_leg=0.382, min_r=0.0, max_entry_frac=0.35)
    off = replace(on, early_leg="off")
    for wrap in (lambda x: x, as_sell):
        d = wrap(early_data({40: 4060.0, 41: 4050.0, 85: 4045.0}))
        found = bot.find_leg(d, on)
        assert found is not None and found.early and (found.l0.price, found.h100.price) == (4000.0, 4060.0)
        out = bot.analyse_leg(d, on)
        assert out.info["leg"].startswith("L0 4000.00@") or out.info["leg"].startswith("L0 -4000.00@")
        assert "H100? " in out.info["leg"]
        # off: fixed legs only - the pivots end with a LOW, so the fixed leg is HIGH 4100 and the low before it
        assert bot.find_leg(d, off) is None  # (no low before the HIGH 4100 in this frame)
        assert bot.analyse_leg(d, off).reason == "fib: no live leg"
    # the setup look needs the start and the provisional end's bar inside it
    d = early_data({40: 4060.0})
    assert bot.find_leg(replace(d, look_lo=30), on) is not None
    assert bot.find_leg(replace(d, look_lo=31), on) is None  # L0 (pos 30) outside
    assert bot.find_leg(replace(d, look_lo=41), on) is None  # the provisional end (pos 40) outside


def test_early_leg_with_the_provisional_end_on_the_last_bar_has_no_bounce_yet() -> None:
    on = bot.Params(fib_entry=0.382, early_leg=0.382, min_r=0.0)  # the M5 trend now (below: UP in the view)
    d = replace(early_data({89: 4060.0}), m5_pv=view_pivots((4000.0, 4010.0), (3990.0, 4000.0)))
    # the highest high is the last bar: no bar after H100's bar
    out = bot.analyse_leg(d, on)
    assert out.info["leg"].startswith("L0 4000.00@") and "H100? 4060.00" in out.info["leg"]
    assert out.reason == "fib: no bounce above the order price"


def test_the_key_is_the_start_shared_by_an_early_leg_and_the_fixed_leg_after_it_and_used_on_fill_only() -> (
    None
):
    on = bot.Params(fib_entry=0.382, m5_trend="h100", early_leg=0.382, min_r=0.0, max_entry_frac=0.35)
    d_early = early_data({40: 4060.0, 41: 4050.0})
    key = f"BUY|M5|{d_early.times[30]}"  # side, setup timeframe, L0's time
    assert bot.analyse_leg(d_early, on, frozenset({key})).reason == "fib: leg already used"
    # the next HIGH fixes: the pivots end ... LOW 4000, HIGH 4060 - the fixed leg has the same start, the same key
    fixed = replace(d_early, pv=pv_of([("H", 4100.0, 20), ("L", 4000.0, 30), ("H", 4060.0, 40)]))
    found = bot.find_leg(fixed, on)
    assert found is not None and not found.early and found.l0.pos == 30 and found.h100.pos == 40
    assert bot.analyse_leg(fixed, on, frozenset({key})).reason == "fib: leg already used"  # used once
    other = replace(
        fixed, pv=pv_of([("L", 3950.0, 10), ("H", 4100.0, 20), ("L", 4001.0, 35), ("H", 4060.0, 40)])
    )
    assert bot.analyse_leg(other, on, frozenset({key})).reason != "fib: leg already used"  # another start


def test_the_07_oct_sell_leg_numbers_from_the_stored_bars(full) -> None:
    """BOT_RULES rule 2, the owner's 07/10/2026 M5 example: start 4184.25 (02:00), end 4161.42 (05:50), leg 22.83 -
    entry 0.382 = 4175.53, stop 4184.75, the 161.8 % extension and target. At 07:00 Thai H4 reads DOWN (highs
    4315.65 -> 4228.63, lows 4244.12 -> 4110.78), so the SELL trend leg is the leg traded and the BUY side is
    refused (against the H4 trend). The bot's own M5 reading at that moment is no trend, so a hand-made UP view
    for the SELL is used to reach the rules after rule 3."""
    res, fi, p = at(full, "2026-10-07 07:00", early_leg="off", min_r=0.0)
    assert fi.h4 == "down" and fi.h4_text == "H4 down (highs 4315.65->4228.63, lows 4244.12->4110.78)"
    assert bot.analyse_leg(fi.datas[0], p).reason == "fib: against the H4 trend"
    sell = fi.datas[1]
    found = bot.find_leg(sell, p)
    assert found is not None and not found.fade and (found.l0.price, found.h100.price) == (-4184.25, -4161.42)
    assert bot.analyse_leg(sell, p).reason == "fib: no M5 trend of its side"  # the bot's own reading
    assert res.decision is None
    up = replace(sell, m5_pv=view_pivots((4000.0, 4010.0), (3990.0, 4000.0)))  # UP in the SELL's view
    out = bot.analyse_leg(up, p)
    assert out.info["leg"].startswith("L0 4184.25@07/10 02:00 H100 4161.42@07/10 05:50 leg 22.83")
    assert out.info["r6"].startswith("order price 4175.53")
    # the spec writes the extension 4147.32 and the target 4147.82 (the 36.94 extension rounded first); the exact
    # 1.618 x 22.83 = 36.93894 gives 4147.31 and 4147.81 - reported, not bent
    assert out.info["r7"].startswith("stop 4184.75") and out.info["r8"].startswith("target 4147.81")
    assert round(4184.25 - 1.618 * 22.83, 2) == 4147.31


def test_rule5_is_gone_no_trend_legs_anywhere() -> None:
    src = Path(bot.__file__).read_text(encoding="utf-8")
    assert "max_trend_legs" not in src and "trend run" not in src and "trend_legs" not in src
    assert "fib: trend run at the limit" not in bot.RANK
    assert "run_divergence" not in src and "count_reason" not in src and "fib: no divergence" not in bot.RANK
    assert bot.Params().fib_count == "off"


# --- rule 16: H4's clear trend, else a fade -------------------------------------------------------------------------


def h4_swings(highs, lows):
    """Fixed H4 pivots, time order H, L, H, L ... (kind, price)."""
    out, pos = [], 10
    for i in range(max(len(highs), len(lows))):
        for kind, seq in ((SwingKind.HIGH, highs), (SwingKind.LOW, lows)):
            if i < len(seq):
                out.append(Swing(kind, seq[i], pos, pos + 3, pos, pos + 3))
                pos += 10
    return out


def test_h4_up_down_not_clear_equal_prices_and_too_few_pivots() -> None:
    cases = (
        ((4300.0, 4350.0), (4100.0, 4150.0), "up"),
        ((4350.0, 4300.0), (4150.0, 4100.0), "down"),
        ((4300.0, 4350.0), (4150.0, 4100.0), "none"),  # higher high, lower low
        ((4350.0, 4300.0), (4100.0, 4150.0), "none"),  # lower high, higher low
        ((4300.0, 4300.0), (4100.0, 4150.0), "none"),  # equal highs are not strictly above
        ((4300.0, 4350.0), (4100.0, 4100.0), "none"),  # equal lows
        ((4350.0, 4350.0), (4150.0, 4100.0), "none"),  # DOWN: equal highs are not strictly below
        ((4350.0, 4300.0), (4150.0, 4150.0), "none"),  # DOWN: equal lows
        ((4350.0, 4350.0), (4150.0, 4150.0), "none"),  # both equal
        ((4300.0,), (4100.0, 4150.0), "none"),  # fewer than two highs
        ((4300.0, 4350.0), (4100.0,), "none"),  # fewer than two lows
        ((), (), "none"),
        # only the latest two of each kind count
        ((4500.0, 4300.0, 4350.0), (4000.0, 4100.0, 4150.0), "up"),
    )
    for highs, lows, want in cases:
        state, text = bot.h4_reading(h4_swings(highs, lows))
        assert state == want, (highs, lows, text)
        assert text.startswith({"up": "H4 up (", "down": "H4 down (", "none": "H4 not clear"}[want])
    state, text = bot.h4_reading(h4_swings((4300.0, 4350.0), (4100.0, 4150.0)))
    assert text == "H4 up (highs 4300.00->4350.00, lows 4100.00->4150.00)"  # rule 16 "Written"
    # fib_lean off: H4 is not read (its frame is not even looked at) - always a fade
    assert bot.read_h4({}, bot.Params(fib_lean="off")) == ("off", "H4 not read (fib_lean off)")


def test_h4_clear_trend_allows_only_its_trend_leg_and_the_trend_leg_is_unchanged() -> None:
    why = "fib: against the H4 trend"
    for h4, ok_side in (("up", "BUY"), ("down", "SELL")):
        for side in ("BUY", "SELL"):
            d = leg_data(h4="up")
            d = replace(as_sell(d) if side == "SELL" else d, h4=h4, h4_text=f"H4 {h4} (test)")
            out = bot.analyse_leg(d, PB)
            if side == ok_side:
                assert out.reason == "order written" and out.info["trade"] == f"trend leg {side}"
            else:
                assert out.reason == why and out.setup is None and bot.find_leg(d, PB) is None
        # fib_lean off: H4 is not read - the other side is not refused for its trend (a fade is wanted instead)
    off = replace(PB, fib_lean="off")
    d = replace(as_sell(leg_data()), h4="up", h4_text="H4 up (test)")  # a SELL against an H4 up
    assert bot.analyse_leg(d, off).reason != why
    # rule 3 still applies to a trend leg
    assert (
        bot.analyse_leg(leg_data(m5_highs=(4120.0,)), PB).reason
        == "fib: M5 trend (H100 not above the M5 high)"
    )
    # the leg numbers of the trend leg are the same as before (H4 clear)
    s_ = bot.analyse_leg(leg_data(), PB).setup
    assert s_ is not None and (s_.order, s_.stop) == (pytest.approx(4038.2), pytest.approx(3999.5))
    assert "H4 up (test). Leg: L0 4000.00" in s_.detail and "trade: trend leg BUY" in s_.detail


# --- rule 2: the fade leg -----------------------------------------------------------------------------------------


def fade_data(*, last=4060.0, prior=4050.0, edit=None, h4="none", with_prior=True) -> bot.LegData:
    """A BUY fade in the view, after a run down: P LOW ``prior`` (pos 20), S HIGH 4100 (pos 40), E LOW 4000
    (pos 60, 0 %), then the bounce rising to ``last`` (the price). The run S - E is 100; the leg before it P -> S."""
    n = 90
    path = np.interp(np.arange(n), [0, 20, 40, 60, n - 1], [prior, prior, 4100.0, 4000.0, last])
    hi, lo, close = path + 0.1, path - 0.1, path.copy()
    if edit is not None:
        edit(hi, lo, close, np.zeros(n), np.zeros(n))
    pv = [bot.VPivot(True, prior, 20)] if with_prior else []
    pv += [bot.VPivot(False, 4100.0, 40), bot.VPivot(True, 4000.0, 60)]
    times = pd.date_range(T_START, periods=n, freq="5min")
    return bot.LegData(
        side="BUY", sign=1, tf="M5", pv=pv, times=times, hi_v=hi, lo_v=lo, close_v=close, m5_times=times, m5_hi_v=hi,
        m5_lo_v=lo, price_v=float(close[-1]), m5_pv=list(pv), m5_ptimes=times, h4=h4, h4_text=f"H4 {h4} (test)",
    )  # fmt: skip


FADE = bot.Params(
    mode="fib", m5_trend="h100", early_leg="off"
)  # fade_entry 0.5, fade_min 1.0, fib_target 1.618


def test_fade_leg_buy_and_sell_levels_entry_stop_target_r_and_the_text() -> None:
    d = fade_data()
    leg = bot.find_leg(d, FADE)
    assert (
        leg is not None and leg.fade and (leg.l0.price, leg.h100.price) == (4000.0, 4100.0)
    )  # 0 % E, 100 % S
    levels = {x: 4000.0 + x * 100.0 for x in (0.0, 0.5, 1.0, 1.272, 1.618)}
    assert levels[1.272] == pytest.approx(4127.2) and levels[1.618] == pytest.approx(4161.8)  # beyond S
    out = bot.analyse_leg(d, FADE)
    s = out.setup
    assert out.reason == "order written" and s is not None
    assert (s.order, s.stop) == (pytest.approx(4050.0), pytest.approx(3999.5))  # E + 0.5 x run; beyond E
    assert s.target == pytest.approx(4161.3)  # E + 1.618 x run - buffer: the reachable level, no ladder
    assert s.r == pytest.approx((4161.3 - 4050.0 - 0.3) / (4050.0 - 3999.5)) and s.r >= 2.0
    assert s.key == f"BUY|M5|{d.times[60]}"  # side, timeframe, E's time
    assert s.marker == "withdraw under 4000.00"  # a new low under E withdraws the resting order
    assert out.info["trade"] == "fade BUY after the run down 4100.00 -> 4000.00"
    assert out.info["leg"].startswith("fade S 4100.00@") and " E 4000.00@" in out.info["leg"]
    for part in ("H4 none (test). Fade leg: S 4100.00@", "(100 %), E 4000.00@", "(0 %), run 100.00",
                 "rule 3 not applied to a fade", "trade: fade BUY after the run down", "stop 3999.50"):  # fmt: skip
        assert part in s.detail, part
    # the SELL: the same view data read as a SELL - after a run UP; real prices negated
    t = bot.analyse_leg(as_sell(d), FADE).setup
    assert t is not None and (t.order, t.stop, t.target) == (-4050.0, -3999.5, pytest.approx(-4161.3))
    assert t.marker == "withdraw over -4000.00"
    assert (
        bot.analyse_leg(as_sell(d), FADE).info["trade"] == "fade SELL after the run up -4100.00 -> -4000.00"
    )
    # fade_entry 0.382 / 0.618: the entry moves, the stop and the target stay
    for fe, order in ((0.382, 4038.2), (0.618, 4061.8)):
        q = replace(FADE, fade_entry=fe, min_r=0.0)
        o = bot.analyse_leg(fade_data(last=order + 5.0), q).setup
        assert o is not None and o.order == pytest.approx(order) and o.stop == pytest.approx(3999.5)


def test_fade_leg_r_under_the_floor_is_no_order_and_the_target_is_not_pushed() -> None:
    # 1.272: target 4126.7, entry 4050: R = (4126.7 - 4050 - 0.3) / 50.5 = 1.51 - no order (no ladder, no further target)
    q = replace(FADE, fib_target=1.272)
    for wrap in (lambda x: x, as_sell):
        out = bot.analyse_leg(wrap(fade_data()), q)
        sign = "-" if wrap is as_sell else ""
        assert out.reason == "reward under 2R" and out.setup is None
        assert out.info["r8"].startswith(f"target {sign}4126.70")
    # the target not beyond the order price: no order
    huge = replace(FADE, target_buffer=130.0, min_r=0.0)
    assert bot.analyse_leg(fade_data(), huge).reason == "fib: no target above the order price"


def test_fade_min_pass_fail_off_and_a_missing_prior_leg() -> None:
    # the leg before the run: P -> S = 4100 - prior; the run S - E is 100
    assert bot.analyse_leg(fade_data(prior=4050.0), FADE).reason == "order written"  # 100 >= 1.0 x 50
    assert bot.analyse_leg(fade_data(prior=4000.0), FADE).reason == "order written"  # equal: 100 >= 100
    fail = bot.analyse_leg(fade_data(prior=3999.9), FADE)  # 100 < 100.1: the run is not long
    assert fail.reason == "fib: no live leg" and fail.setup is None
    off = replace(FADE, fade_min="off")
    assert bot.analyse_leg(fade_data(prior=3900.0), off).reason == "order written"  # off: any run
    # no fixed pivot before S: nothing to compare - no fade leg, unless fade_min is off
    assert bot.find_leg(fade_data(with_prior=False), FADE) is None
    assert bot.find_leg(fade_data(with_prior=False), off) is not None
    # the run must be above zero and E the latest pivot
    assert bot.fade_leg([bot.VPivot(False, 4000.0, 40), bot.VPivot(True, 4100.0, 60)], "off") is None
    assert (
        bot.fade_leg([bot.VPivot(True, 4000.0, 20), bot.VPivot(False, 4100.0, 40)], "off") is None
    )  # E a HIGH
    assert bot.fade_leg([bot.VPivot(True, 4000.0, 20)], "off") is None
    with pytest.raises(ValueError):
        bot.Params(fade_min=0.5)
    with pytest.raises(ValueError):
        bot.Params(fade_entry=0.236)


def test_fade_rule_10_a_new_extreme_beyond_e_after_es_bar_ends_the_leg() -> None:
    why = "fib: leg has run (100 % traded)"
    for wrap in (lambda x: x, as_sell):

        def set_lo(k, v):
            return lambda hi, lo, cl, m, r: lo.__setitem__(k, v)

        assert (
            bot.analyse_leg(wrap(fade_data(edit=set_lo(70, 4000.0))), FADE).reason == "order written"
        )  # a touch
        out = bot.analyse_leg(wrap(fade_data(edit=set_lo(70, 3999.9))), FADE)
        assert out.reason == why and out.setup is None  # a low strictly under E
        assert (
            bot.analyse_leg(wrap(fade_data(edit=set_lo(60, 3990.0))), FADE).reason == "order written"
        )  # E's bar
        assert bot.analyse_leg(wrap(fade_data(edit=set_lo(61, 3999.9))), FADE).reason == why  # the next bar
        assert (
            bot.analyse_leg(wrap(fade_data(edit=set_lo(50, 3990.0))), FADE).reason == "order written"
        )  # before
        # a high above S is no break for a fade (the run is faded, not traded with)
        assert (
            bot.analyse_leg(
                wrap(fade_data(edit=lambda hi, lo, cl, m, r: hi.__setitem__(70, 4200.0))), FADE
            ).reason
            != why
        )


def test_fade_played_out_when_the_target_was_touched_before_the_fill() -> None:
    def touch(hi, lo, cl, macd, rsi):
        hi[75] = 4162.0  # the 4161.3 target is reached after the bounce above the order price

    for wrap in (lambda x: x, as_sell):
        out = bot.analyse_leg(wrap(fade_data(edit=touch)), FADE)
        assert out.reason == "setup already played out" and out.setup is None
    # the price at or under the order price: the limit is not written (a plain buy limit below the price)
    out = bot.analyse_leg(fade_data(last=4050.0), FADE)
    assert out.reason == "fib: price not above the order price"

    # no bounce above the order price after E's bar
    def no_bounce(hi, lo, cl, macd, rsi):
        hi[61:] = 4040.0

    assert bot.analyse_leg(fade_data(edit=no_bounce), FADE).reason == "fib: no bounce above the order price"
    # rule 9: the order price must be reachable - 0.25 x the run
    assert bot.analyse_leg(fade_data(last=4050.0 + 25.0), FADE).reason == "order written"
    far = bot.analyse_leg(fade_data(last=4050.0 + 25.1), FADE)
    assert far.reason == "fib: order price too far from price"


def test_fade_leg_ignores_rule_3_the_key_is_es_time_and_the_look_needs_s_and_e() -> None:
    # rule 3 refuses this data as a trend leg (the M5 view is DOWN / a high above H100) but not as a fade
    d = fade_data()
    down = replace(d, m5_pv=view_pivots((4020.0, 4010.0), (4000.0, 3990.0)))  # DOWN in the view
    p_now = replace(FADE, m5_trend="now")
    assert bot.analyse_leg(down, p_now).reason == "order written"  # m5_trend now would refuse a trend leg
    assert (
        bot.analyse_leg(replace(down, h4="up"), p_now).reason != "order written"
    )  # as a trend leg it is refused
    # the key is side, timeframe and E's time; used
    out = bot.analyse_leg(d, FADE)
    assert out.setup is not None
    again = bot.analyse_leg(d, FADE, frozenset({out.setup.key}))
    assert again.reason == "fib: leg already used" and again.setup is None
    # the setup look: E at 60 and S at 40 must both be inside - S before the look leaves no leg (the look check
    # on the leg's other end), and E before it as well
    assert bot.analyse_leg(replace(d, look_lo=40), FADE).reason == "order written"
    for lo in (41, 55, 60):
        assert (
            bot.analyse_leg(replace(d, look_lo=lo), FADE).reason
            == ("fib: no live leg" if lo < 60 else "order written")
            or lo == 60
        )
    assert bot.find_leg(replace(d, look_lo=41), FADE) is None  # S (pos 40) outside, E inside
    assert bot.find_leg(replace(d, look_lo=61), FADE) is None  # E outside
    assert bot.find_leg(replace(d, look_lo=60), FADE) is None  # S outside again (40 < 60)


def test_trend_leg_look_check_needs_h100_inside_with_l0_outside_impossible_but_early_h100_counts() -> None:
    """The look check on the leg's end: an early leg's provisional end must lie inside the look as well."""
    n = 90
    hi, lo = np.full(n, 4010.0), np.full(n, 4005.0)
    hi[40] = 4060.0
    base = leg_data()
    pv = pv_of([("H", 4100.0, 20), ("L", 4000.0, 30)])
    d = replace(base, pv=pv, hi_v=hi, lo_v=lo, m5_hi_v=hi, m5_lo_v=lo, m5_pv=list(pv), look_lo=0)
    on = bot.Params(early_leg=0.382)
    assert bot.find_leg(d, on) is not None
    assert (
        bot.find_leg(replace(d, look_lo=41), on) is None
    )  # the provisional end (pos 40) outside, L0 outside too


def test_fade_leg_scored_withdrawal_marker_under_for_a_buy_over_for_a_sell() -> None:
    """eye/score.py reads ``withdraw under E`` (BUY: a low under it before the fill) / ``withdraw over E`` (SELL: a
    high over it) for a fade order, the way it reads ``withdraw beyond H100`` for a trend leg."""
    cut_ = pd.Timestamp("2026-10-07 07:30", tz=TH).tz_convert("UTC")

    def row(side, entry, stop, target, marker):
        return {
            "id": "T-1", "cutoff_thai": "2026-10-07 07:00", "decided_at": "07/10 07:25", "side": side,
            "entry": f"{entry:.2f}", "stop": f"{stop:.2f}", "target": f"{target:.2f}", "trigger": "",
            "structure": f"bot2e fib x. {marker}. Parameters: mode=fib order_life_bars=24",
        }  # fmt: skip

    # an order BELOW E (as a hand-made row): a low 3995 under E 4000 comes before the fill bar - withdrawn
    gone = _bars([(4070, 4075, 4060, 4065), (4065, 4066, 3995, 4000), (4000, 4001, 3985, 3990)])
    out = score_mod.score(row("BUY", 3990.0, 3980.0, 4161.3, "withdraw under 4000.00"), gone, cut_)
    assert out["why"].startswith("no fill (withdrawn: beyond 4000.00)") and out["r_net"] == "0.0"
    # without the marker the same bars fill on the third bar
    assert score_mod.score(row("BUY", 3990.0, 3980.0, 4161.3, "x"), gone, cut_)["fill"]
    # a bar that fills AND goes under E keeps the fill (a fade BUY's limit lies above E: the usual case)
    both = _bars([(4070, 4075, 4060, 4065), (4065, 4066, 3995, 4000)])
    assert score_mod.score(row("BUY", 4050.0, 3999.5, 4161.3, "withdraw under 4000.00"), both, cut_)["fill"]
    # the SELL (a hand-made order above E): a high over E 4180 comes before the fill bar
    sgone = _bars([(4100, 4110, 4095, 4105), (4105, 4185, 4104, 4180), (4180, 4195, 4130, 4135)])
    sout = score_mod.score(row("SELL", 4190.0, 4200.0, 4000.0, "withdraw over 4180.00"), sgone, cut_)
    assert sout["why"].startswith("no fill (withdrawn: beyond 4180.00)")


@needs_data
def test_07_oct_h4_reading_and_the_fade_sell_example_on_the_stored_bars(full) -> None:
    """BOT_RULES rule 14 / rule 2 example, 07/10/2026 M5. H4 reads DOWN at 07:00 (so the bot's own default there
    is the SELL trend leg, refused by the M5 trend). With fib_lean off (H4 not read, always a fade) the run
    4154.21 (06/10 23:55) -> 4184.25 (07/10 02:00) is faded while it is the latest run (06:30 to 06:50 Thai): a SELL
    limit at 0.5 = 4169.23, stop 4184.75, target 4136.15 (1.618), R 2.11; on the stored bars it fills and the
    target is touched (decided 06:35: filled 07:10). At 07:00 the low 4161.42 (05:50) is fixed, the latest run is
    4184.25 -> 4161.42, shorter than the leg before it: no fade leg."""
    now = now_at("2026-10-07 06:35")
    p = bot.Params(fib_lean="off")
    res = bot.decide(bot.cut(full, now), now, p, windowed=False)
    d = res.decision
    assert d is not None and (d["side"], d["entry"], d["stop"], d["target"]) == (
        "SELL",
        "4169.23",
        "4184.75",
        "4136.15",
    )
    assert res.log["r"] == "2.11" and res.log["trade"] == "fade SELL after the run up 4154.21 -> 4184.25"
    assert res.log["rule16"] == "H4 not read (fib_lean off)"
    assert "Fade leg: S 4154.21@" in d["structure"] and "E 4184.25@" in d["structure"]
    assert "withdraw over 4184.25" in d["structure"]
    d["id"] = "X"
    got = score_mod.score(d, score_mod.bars(), score_mod.start_of(d, {}), p.spread)
    assert (got["fill"], got["exit"], got["why"], got["r_net"]) == (
        "07/10 07:10",
        "4136.15",
        "target",
        "2.11",
    )
    res7, fi, p7 = at(full, "2026-10-07 07:00", fib_lean="off")
    assert [bot.analyse_leg(x, p7).reason for x in fi.datas] == [
        "fib: no live leg"
    ] * 2 and res7.decision is None
    res7, fi, p7 = at(full, "2026-10-07 07:00")
    assert fi.h4 == "down" and res7.decision is None


def test_fade_parameters_text_validation_and_cli() -> None:
    d = bot.Params()
    assert (d.fade_min, d.fade_entry) == (1.0, 0.5)
    assert "fade_min=1.0" in d.text() and "fade_entry=0.5" in d.text()
    assert "fade_min=off" in bot.Params(fade_min="off").text()
    for kw in ({"fade_min": 2.0}, {"fade_min": "on"}, {"fade_entry": 0.236}, {"fade_entry": 0.7}):
        with pytest.raises(ValueError):
            bot.Params(**kw)
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--fade-min", "off", "--fade-entry", "0.382"])
        assert (seen["params"].fade_min, seen["params"].fade_entry) == ("off", 0.382)
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02"])
        assert (seen["params"].fade_min, seen["params"].fade_entry) == (1.0, 0.5)
    finally:
        bot.run = orig  # type: ignore[assignment]
    with pytest.raises(SystemExit):
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--fade-entry", "0.7"])


# --- rule 17: the break and its retest (trend legs only) ----------------------------------------------------------


def retest_data(
    pull: float = 4075.0, brk: float = 4104.0, n: int = 90, confirm: int = 63, edit=None, h4="up"
):
    """A BUY trend leg L0 4000 (pos 40) -> H100 4100 (pos 60, fixed on bar ``confirm``), a pullback to ``pull``
    (pos 70), a climb to 4098, and a last bar closing at ``brk`` - above H100: the break bar closes now."""
    path = np.interp(np.arange(n), [0, 40, 60, 70, n - 2, n - 1], [4020.0, 4000.0, 4100.0, pull, 4098.0, brk])
    hi, lo, close = path + 0.1, path - 0.1, path.copy()
    if edit is not None:
        edit(hi, lo, close, None, None)
    times = pd.date_range(T_START, periods=n, freq="5min")
    pv = [bot.VPivot(True, 4000.0, 40, 43), bot.VPivot(False, 4100.0, 60, confirm)]
    m5_pv = [bot.VPivot(False, 4090.0, 1), *pv]
    return bot.LegData(
        side="BUY", sign=1, tf="M5", pv=pv, times=times, hi_v=hi, lo_v=lo, close_v=close, m5_times=times,
        m5_hi_v=hi, m5_lo_v=lo, price_v=float(close[-1]), m5_pv=m5_pv, m5_ptimes=times, h4=h4,
        h4_text=f"H4 {h4} (test)",
    )  # fmt: skip


def test_rule17_the_break_is_the_first_close_beyond_a_fixed_h100_after_the_fixing_bar() -> None:
    d = retest_data()
    out = bot.analyse_retest(d, PB)
    assert out is not None and out.setup is not None  # the last bar is the first close above 4100, 4104

    # a close above H100 on the bar that fixed it (63) or before it does not count: no close there is "known"
    def early_close(hi, lo, cl, m, r):
        cl[62], cl[63] = 4101.0, 4102.0

    assert bot.analyse_retest(retest_data(edit=early_close), PB) is not None

    # a close above H100 on the next bar (64) is the break - and it is old now: no order at the later bar
    def old_break(hi, lo, cl, m, r):
        cl[64] = 4101.0

    assert bot.analyse_retest(retest_data(edit=old_break), PB) is None
    # no close beyond H100: no break
    assert bot.analyse_retest(retest_data(brk=4100.0), PB) is None  # a close AT H100 is not beyond it
    assert bot.analyse_retest(retest_data(brk=4099.9), PB) is None
    # a pivot whose confirm bar is unknown (provisional) has no break
    unknown = retest_data(confirm=-1)
    assert bot.retest_break(unknown, bot.Leg(unknown.pv[0], unknown.pv[1])) is None
    # the leg is used once an order filled (the same key): no retest order
    key = bot.analyse_retest(d, PB).setup.key  # type: ignore[union-attr]
    assert bot.analyse_retest(d, PB, frozenset({key})) is None


def test_rule17_lb_is_the_lowest_low_after_h100s_bar_up_to_the_bar_before_the_break() -> None:
    d = retest_data(pull=4075.0)
    s = bot.analyse_retest(d, PB).setup  # type: ignore[union-attr]
    assert s.order == pytest.approx(4100.0) and s.stop == pytest.approx(4074.9 - 0.5)  # Lb 4074.9, beyond it

    def low_on_break_bar(hi, lo, cl, m, r):
        lo[89] = 4000.0  # the break bar's own low is not in the window

    t = bot.analyse_retest(retest_data(edit=low_on_break_bar), PB).setup  # type: ignore[union-attr]
    assert t.stop == pytest.approx(4074.4)

    def low_before(hi, lo, cl, m, r):
        lo[88] = 4062.0  # the bar before the break counts
        lo[59] = 3990.0  # a bar before H100's bar does not

    u = bot.analyse_retest(retest_data(edit=low_before), PB).setup  # type: ignore[union-attr]
    assert u.stop == pytest.approx(4061.5)


def test_rule17_target_1_618_else_2_0_else_no_order_and_the_text() -> None:
    ok = bot.analyse_retest(retest_data(pull=4075.0), PB).setup  # R (4161.3 - 4100 - 0.3) / 25.6 = 2.38
    assert ok is not None and ok.step == "1.618" and ok.target == pytest.approx(4161.3) and ok.r >= 2.0
    two = bot.analyse_retest(retest_data(pull=4060.0), PB).setup  # 1.618 gives R 1.50: the 2.0 extension
    assert two is not None and two.step == "2" and two.target == pytest.approx(4199.5)
    assert two.r == pytest.approx((4199.5 - 4100.0 - 0.3) / (4100.0 - 4059.9 + 0.5)) and two.r >= 2.0
    none = bot.analyse_retest(retest_data(pull=4020.0), PB)  # 2.0 still under 2R: no order, no 261.8 %
    assert none is not None and none.setup is None and none.reason == "reward under 2R"
    assert none.info["r8"].startswith("target 4199.50")
    assert (
        ok.marker == "no H100 withdrawal (break and retest)" and ok.key == f"BUY|M5|{retest_data().times[40]}"
    )
    for part in ("break and retest: the M5 close at", "Lb 4074.90", "trade: trend leg BUY, break and retest",
                 "Limit at H100 4100.00", "H4 up (test). Leg: L0 4000.00"):  # fmt: skip
        assert part in ok.detail, part
    # rule 9 does not apply: the close 50 away from the limit (rule 9 would allow 25) still writes
    far = retest_data(brk=4150.0)
    assert bot.analyse_retest(far, PB).setup is not None  # type: ignore[union-attr]


def test_rule17_rule_3_and_rule_16_apply_and_the_sell_mirror() -> None:
    d = retest_data()
    refused = bot.analyse_retest(
        replace(d, m5_pv=[bot.VPivot(False, 4120.0, 1), *d.pv]), PB
    )  # H100 not above 4120
    assert refused is not None and refused.reason == "fib: M5 trend (H100 not above the M5 high)"
    assert refused.setup is None
    now_p = replace(PB, m5_trend="now")
    no_trend = bot.analyse_retest(d, now_p)
    assert no_trend is not None and no_trend.reason == "fib: no M5 trend of its side"
    up = replace(d, m5_pv=view_pivots((4000.0, 4010.0), (3990.0, 4000.0)))
    assert bot.analyse_retest(up, now_p).setup is not None  # type: ignore[union-attr]
    # rule 16: H4 not clear or against: no trend leg, no retest; fib_lean off: a fade is wanted
    for h4 in ("none", "down", "off"):
        assert bot.analyse_retest(replace(d, h4=h4), PB) is None, h4
    assert bot.analyse_retest(d, replace(PB, fib_lean="off")) is None
    # the SELL: the same data seen as a SELL (H4 down): real prices negated
    s = bot.analyse_retest(as_sell(d), PB).setup  # type: ignore[union-attr]
    t = bot.analyse_retest(d, PB).setup  # type: ignore[union-attr]
    assert (s.order, s.stop, s.target) == (
        pytest.approx(-t.order),
        pytest.approx(-t.stop),
        pytest.approx(-t.target),
    )
    assert s.side == "SELL" and s.r == pytest.approx(t.r) and "Hb -4074.90" in s.detail


def test_rule17_fade_legs_never_get_it_and_decide_writes_the_retest() -> None:
    assert (
        bot.analyse_retest(fade_data(h4="none"), FADE) is None
    )  # a fade leg: no retest, whatever the closes
    # an early leg is another leg: the retest is of the fixed leg, found with early_leg on as well
    assert bot.analyse_retest(retest_data(), replace(PB, early_leg=0.382)) is not None
    d = retest_data()
    retest = bot.analyse_retest(d, PB)
    assert retest is not None and retest.setup is not None and retest.setup.gap == pytest.approx(4.0)
    fi = bot.FibInputs(
        "up", "H4 up (test)", [d, as_sell(d)], pd.DataFrame(), pd.DatetimeIndex([]), [], [], 0.0
    )
    res = decide_inputs(fi, PB)
    assert res.decision is not None and res.decision["side"] == "BUY" and res.decision["entry"] == "4100.00"
    assert (
        "break and retest" in res.decision["structure"]
        and res.log["trade"] == "trend leg BUY, break and retest"
    )


def test_rule17_scoring_the_retest_is_not_withdrawn_by_h100_only_by_its_target() -> None:
    cut_ = pd.Timestamp("2026-10-07 07:30", tz=TH).tz_convert("UTC")
    ok = bot.analyse_retest(retest_data(), PB).setup  # type: ignore[union-attr]

    def row(marker, entry=4100.0, stop=4074.4, target=4161.3):
        return {
            "id": "T-1", "cutoff_thai": "2026-10-07 07:00", "decided_at": "07/10 07:25", "side": "BUY",
            "entry": f"{entry:.2f}", "stop": f"{stop:.2f}", "target": f"{target:.2f}", "trigger": "",
            "structure": f"bot2e fib x. {marker}. Parameters: mode=fib order_life_bars=24",
        }  # fmt: skip

    # a high above H100 on the way, then the retest bar fills: no H100 withdrawal for the retest order
    rise = _bars([(4104, 4110, 4102, 4108), (4108, 4109, 4099, 4101), (4101, 4102, 4100.5, 4101)])
    assert score_mod.score(row(ok.marker), rise, cut_)["fill"]
    # the pullback order of the same leg IS withdrawn by that high (rule 12), before the retest order is written
    pull = _bars([(4090, 4095, 4085, 4090), (4090, 4105, 4089, 4104), (4104, 4105, 4036, 4040)])
    gone = score_mod.score(row("withdraw beyond 4100.00", entry=4038.2, stop=3999.5), pull, cut_)
    assert gone["why"].startswith("no fill (withdrawn: beyond 4100.00)")
    # the retest's own withdrawal: its target touched before the fill
    target_first = _bars([(4104, 4165, 4103, 4160), (4160, 4161, 4099, 4100)])
    assert score_mod.score(row(ok.marker), target_first, cut_)["why"] == "no fill (stop or target first)"
    # a high above H100 alone does not withdraw it
    assert not score_mod.score(row(ok.marker), _bars([(4104, 4110, 4103, 4108)]), cut_)["fill"]


@needs_data
def test_rule17_07_oct_sell_retest_on_the_stored_bars(full) -> None:
    """BOT_RULES rule 17 example, 07/10/2026 M5 (H4 down): the SELL leg 4184.25 (02:00) -> 4161.42 (05:50), Hb 4169.89
    (06:30); the break - the M5 close at 07:30 Thai, 4160.09. The bot's own M5 trend at 07:30 is no trend (and under
    m5_trend h100 H100 4161.42 is not below the M5 low 4154.21 before it), so rule 3 REFUSES the order and the bot
    writes nothing. With a hand-made DOWN M5 trend the order is the spec's: sell limit 4161.42, stop 4170.39, the
    161.8 % target gives R 1.48 so the 200 % target 4139.09, R 2.46; scored it fills on the 07:40 bar and the target
    is reached (the first M5 low at or under 4139.09 is the 10:10 bar - the spec says 08:50; reported)."""
    res, fi, p = at(full, "2026-10-07 07:30")
    sell = fi.datas[1]
    refused = bot.analyse_retest(sell, p)
    assert refused is not None and refused.reason == "fib: no M5 trend of its side" and refused.setup is None
    assert res.decision is None and bot.analyse_retest(fi.datas[0], p) is None  # the BUY side: against H4
    h100 = replace(p, m5_trend="h100")
    again = bot.analyse_retest(sell, h100)
    assert again is not None and again.reason == "fib: M5 trend (H100 not above the M5 high)"
    down = replace(
        sell, m5_pv=view_pivots((4000.0, 4010.0), (3990.0, 4000.0))
    )  # UP in the SELL's view = DOWN
    out = bot.analyse_retest(down, p)
    assert out is not None and out.setup is not None
    st = out.setup
    assert (st.order, st.stop, st.target, st.step) == (4161.42, 4170.39, 4139.09, "2")
    assert round(st.r, 2) == 2.46 and st.key == f"SELL|M5|{pd.Timestamp('2026-10-06 19:00', tz='UTC')}"
    assert "Hb 4169.89" in st.detail and "break and retest" in st.detail
    # the 161.8 % target would give R 1.48 (the 200 % was needed)
    leg = 4184.25 - 4161.42
    assert round((4161.42 - (4184.25 - 1.618 * leg + 0.5) - 0.3) / (4170.39 - 4161.42), 2) == 1.48
    row = {
        "id": "X", "cutoff_thai": "2026-10-07 07:00", "decided_at": "07/10 07:25", "side": "SELL",
        "entry": "4161.42", "stop": "4170.39", "target": "4139.09", "trigger": "",
        "structure": f"bot2e fib x. {st.marker}. Parameters: mode=fib order_life_bars=24",
    }  # fmt: skip
    got = score_mod.score(row, score_mod.bars(), score_mod.start_of(row, {}), p.spread)
    assert (got["fill"], got["exit"], got["why"], got["r_net"]) == (
        "07/10 07:40",
        "4139.09",
        "target",
        "2.46",
    )


def test_m5_trend_off_applies_rule_3_nowhere_trend_legs_and_retests_alike() -> None:
    assert (
        bot.Params(m5_trend="off").m5_trend == "off" and "m5_trend=off" in bot.Params(m5_trend="off").text()
    )
    off = replace(PB, m5_trend="off")
    # a trend leg that the M5 trend refuses (a higher M5 high before it) is written with rule 3 off
    refused = leg_data(m5_highs=(4120.0,))
    assert bot.analyse_leg(refused, PB).reason == "fib: M5 trend (H100 not above the M5 high)"
    out = bot.analyse_leg(refused, off)
    assert out.reason == "order written" and out.info["r3"] == "rule 3 off (m5_trend off)"
    assert "rule 3 off" in out.setup.detail  # type: ignore[union-attr]
    for wrap in (lambda x: x, as_sell):
        assert (
            bot.analyse_leg(wrap(leg_data(m5_highs=())), off).reason == "order written"
        )  # no M5 pivot at all
    # now: a no-trend view refuses, off does not - for the retest as well
    d = retest_data()
    assert bot.analyse_retest(d, replace(PB, m5_trend="now")).reason == "fib: no M5 trend of its side"  # type: ignore[union-attr]
    assert bot.analyse_retest(d, off).setup is not None  # type: ignore[union-attr]
    # rule 16 and the fade leg are not touched by it
    assert bot.analyse_leg(replace(leg_data(), h4="down"), off).reason == "fib: against the H4 trend"
    assert bot.analyse_leg(fade_data(), replace(FADE, m5_trend="off")).reason == "order written"
    seen: dict[str, bot.Params] = {}
    orig = bot.run
    bot.run = lambda first, last, params, *a, **k: seen.update(params=params)  # type: ignore[assignment]
    try:
        bot.main(["--from", "2026-10-01", "--to", "2026-10-02", "--m5-trend", "off"])
    finally:
        bot.run = orig  # type: ignore[assignment]
    assert seen["params"].m5_trend == "off"
    with pytest.raises(ValueError):
        bot.Params(m5_trend="maybe")


def test_rule17_an_early_leg_never_breaks() -> None:
    """The retest belongs to a fixed leg: a leg marked early (a provisional end) has no break, whatever the closes."""
    d = retest_data()
    fixed = bot.Leg(d.pv[0], d.pv[1])
    early = bot.Leg(d.pv[0], d.pv[1], early=True)
    assert (
        bot.retest_break(d, fixed) == 89
    )  # the same data, the same close: a fixed leg breaks on the last bar
    assert bot.retest_break(d, early) is None
    assert bot.retest_break(d, bot.Leg(d.pv[0], d.pv[1], fade=True)) is None


def test_research_runner_variants_summary_kinds_and_trade_lines(tmp_path) -> None:
    research = importlib.import_module("eye.bot_research")
    assert research.DEFAULT_VARIANTS == {"r3_now": {}, "r3_off": {"m5_trend": "off"}}
    assert research.make_params(research.DEFAULT_VARIANTS["r3_off"]).m5_trend == "off"
    assert research.make_params({}).m5_trend == "now"
    for stale in ("h1_mode", "band_frac", "entry_tfs", "h1_tf", "div_mode", "counter_pivots"):
        with pytest.raises(SystemExit):
            research.make_params({stale: 1})
    base = {"why": "target", "r_net": "2.0", "entry": "4100.00", "stop": "4090.00", "target": "4120.00",
            "side": "BUY", "fill": "07/10 07:40", "decided_at": "07/10 07:30", "structure": "x"}  # fmt: skip
    rows = [
        {**base, "structure": "H4 up. Leg: L0 1; trade: trend leg BUY"},
        {
            **base,
            "why": "stop",
            "r_net": "-1.0",
            "side": "SELL",
            "fill": "08/10 09:00",
            "decided_at": "08/10 08:55",
            "structure": "H4 not clear. Fade leg: S 1, E 2; trade: fade SELL",
        },
        {
            **base,
            "fill": "09/10 10:00",
            "decided_at": "09/10 09:55",
            "structure": "x; break and retest: the M5 close",
        },
        {**base, "why": "no fill", "r_net": "0.0", "fill": "", "decided_at": "10/10 10:00"},
        {**base, "why": "open", "r_net": "", "fill": "11/10 10:00", "decided_at": "11/10 10:00"},
    ]
    assert [research.kind_of(r) for r in rows[:3]] == ["trend", "fade", "retest"]
    m = research.money(rows)
    assert (m["orders"], m["fills"], m["wins"], m["losses"], m["open"]) == (5, 3, 2, 1, 1)
    assert m["r_total"] == pytest.approx(3.0) and m["r_per_fill"] == pytest.approx(1.0)
    assert research.money([])["r_per_fill"] == 0.0
    lines = research.trade_lines(rows)
    assert len(lines) == 3 and lines[0].startswith("07/10 07:40  BUY   trend ")
    assert "SELL  fade" in lines[1] and "stop  R -1.00" in lines[1] and "retest" in lines[2]
    assert "entry 4100.00  stop 4090.00  target 4120.00  target  R +2.00" in lines[0]
    result = {"variant": "v", "params": "{}", "top_reasons": "a 1", **m}
    research.write_summary(result, tmp_path, "2026-10-01", "2026-10-28")
    got = list(csv.DictReader((tmp_path / "summary.csv").open(encoding="utf-8")))
    assert (
        len(got) == 1
        and got[0]["fills"] == "3"
        and got[0]["r_per_fill"] == "1.0"
        and got[0]["to"] == "2026-10-28"
    )
    assert list(got[0]) == research.SUMMARY_COLUMNS
    table = research.table([{**result, "r_total": 3.0}])
    assert "orders" in table and "R/fill" in table and "+1.000" in table


def test_research_runner_refuses_variant_names_that_leave_the_research_folder(tmp_path) -> None:
    research = importlib.import_module("eye.bot_research")
    root = tmp_path / "research"
    root.mkdir()
    for good in ("r3_now", "r3-off", "A1", "x"):
        assert research.variant_folder(good, root) == (root / good).resolve()
    for bad in (
        "", "..", ".", "../x", "..\\x", "a/b", "a\\b", "/abs", "C:\\x", "../../eye", "a b", "a.b",
        "a\\n", "-a/..",
    ):  # fmt: skip
        with pytest.raises(SystemExit):
            research.variant_folder(bad, root)
    # a name that passes the pattern but resolves elsewhere: a link inside root pointing outside it
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pass  # no symlink right on this machine: the pattern test above stands
    else:
        with pytest.raises(SystemExit):
            research.variant_folder("link", root)
    # run_variant refuses before it runs or writes anything
    with pytest.raises(SystemExit):
        research.run_variant("../../eye", {}, "2026-10-19", "2026-10-19", {}, None, root=root)
    assert list(root.iterdir()) == [] or [p.name for p in root.iterdir()] == ["link"]
    assert not (tmp_path / "eye").exists()
    with pytest.raises(SystemExit):  # the command line refuses a bad name in --variants before running
        research.main(
            ["--from", "2026-10-19", "--to", "2026-10-19", "--variants", str(_variants_file(tmp_path))]
        )


def _variants_file(tmp_path):
    path = tmp_path / "v.json"
    path.write_text('{"../../eye": {}}', encoding="utf-8")
    return path


def test_start_of_a_midnight_decision_starts_at_its_now() -> None:
    """``decided_at`` is the last bar's open: a 00:00 decision (cutoff the new day, last bar 23:55 of the day
    before) starts at that 00:00 - not a day later; a normal row is unchanged; also across New Year."""

    def row(cutoff: str, decided: str) -> dict[str, str]:
        return {"id": "B-x", "cutoff_thai": f"{cutoff} 07:00", "decided_at": decided}

    assert score_mod.start_of(row("2026-04-07", "06/04 23:55"), {}) == now_at("2026-04-07 00:00")
    assert score_mod.start_of(row("2026-04-07", "07/04 07:00"), {}) == now_at("2026-04-07 07:05")
    assert score_mod.start_of(row("2027-01-01", "31/12 23:55"), {}) == now_at("2027-01-01 00:00")
    assert score_mod.start_of(row("2027-01-01", "01/01 00:05"), {}) == now_at("2027-01-01 00:10")
