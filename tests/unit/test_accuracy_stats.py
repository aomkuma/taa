"""Accuracy statistics and the theory scoreboard (TAA-6C4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.advisory.confidence import Source
from app.advisory.shadow import ShadowExit, ShadowResult, Variant, new_state
from app.advisory.shadow_tracker import EntryQuote, SignalFacts, apply_close, new_row
from app.advisory.stats import (
    DIMENSIONS,
    IN_SAMPLE_WARNING,
    TradeRecord,
    accuracy_report,
    breakdown,
    equity_curve,
    load_records,
    scoreboard,
    summarize,
    threshold_explorer,
    watchlist_key,
)
from app.advisory.stats_math import wilson_interval
from app.core.enums import ExitReason, Side
from app.storage.database import Database

T0 = datetime(2026, 9, 1, tzinfo=UTC)
FIB = "ev:FIBONACCI:fib.retracement"
FIB2 = "ev:FIBONACCI:fib.cluster"
RSI = "ev:MOMENTUM:momentum.rsi_divergence"


def trade(i: int, win: bool, **kw: object) -> TradeRecord:
    r = 2.0 if win else -1.0
    args: dict[str, object] = {
        "shadow_id": f"t{i:04d}:PLAN",
        "source": Source.LIVE,
        "variant": "PLAN",
        "strategy": "s",
        "symbol": "EURUSD",
        "asset_class": "FOREX_MAJOR",
        "timeframe": "M15",
        "session": "LONDON",
        "side": "BUY",
        "strength": 70.0,
        "rr": 2.0,
        "win": win,
        "r_net": r,
        "net_pnl": 50.0 * r,
        "signal_at": T0 + timedelta(hours=i),
        "exit_at": T0 + timedelta(hours=i, minutes=30),
        "exit_reason": "TP" if win else "SL",
    } | kw
    return TradeRecord(**args)  # type: ignore[arg-type]


class TestSummary:
    def test_core_metrics(self) -> None:
        trades = [trade(0, True), trade(1, False), trade(2, False), trade(3, True), trade(4, False)]
        s = summarize(trades)
        low, high = wilson_interval(2, 5)
        assert (s.n, s.wins, s.hit_rate) == (5, 2, 40.0)
        assert s.hit_low == pytest.approx(100 * low) and s.hit_high == pytest.approx(100 * high)
        assert s.expectancy_r == pytest.approx(0.2) and s.profit_factor_r == pytest.approx(4 / 3)
        assert s.expectancy_money == pytest.approx(10.0) and s.total_pnl == 50.0
        assert s.profit_factor_money == pytest.approx(200 / 150)
        # curve: +100, 50, 0, 100, 50 -> peak 100, worst 0
        assert s.max_drawdown == pytest.approx(100.0) and s.max_drawdown_r == pytest.approx(2.0)

    def test_not_tradable_counts_in_r_only(self) -> None:
        s = summarize([trade(0, True), trade(1, False, net_pnl=None)])
        assert s.n == 2 and s.n_money == 1 and s.expectancy_r == pytest.approx(0.5)
        assert s.total_pnl == 100.0 and s.expectancy_money == pytest.approx(100.0)

    def test_empty_and_no_losses(self) -> None:
        s = summarize([])
        assert s.n == 0 and s.hit_rate is None and s.expectancy_r is None and s.max_drawdown == 0.0
        assert summarize([trade(0, True)]).profit_factor_r is None  # no loss: undefined, not infinite

    def test_curve_is_in_exit_order(self) -> None:
        late = trade(0, True, exit_at=T0 + timedelta(days=2))
        early = trade(1, False)
        curve = equity_curve([late, early])
        assert [p.pnl for p in curve] == [-50.0, 50.0] and curve[0].drawdown == pytest.approx(50.0)


class TestBreakdowns:
    def test_dimensions(self) -> None:
        trades = [
            trade(0, True, symbol="XAUUSD", asset_class="METAL", alerted=True),
            trade(1, False, strength=85.0, followed=True),
            trade(2, True, session="NEW_YORK"),
        ]
        assert set(breakdown(trades, DIMENSIONS["symbol"])) == {"EURUSD", "XAUUSD"}
        assert breakdown(trades, DIMENSIONS["asset_class"])["METAL"].n == 1
        assert breakdown(trades, DIMENSIONS["bucket"])["80+"].wins == 0
        assert breakdown(trades, DIMENSIONS["alerted"])["alerted"].n == 1
        assert breakdown(trades, DIMENSIONS["followed"])["not_followed"].n == 2
        assert breakdown(trades, DIMENSIONS["session"])["NEW_YORK"].hit_rate == 100.0

    def test_a_trade_counts_in_every_watchlist_holding_its_symbol(self) -> None:
        key = watchlist_key({"Fav": ["EURUSD", "XAUUSD"], "Gold": ["XAUUSD"], "Empty": []})
        trades = [trade(0, True, symbol="XAUUSD"), trade(1, False), trade(2, True, symbol="BTCUSD")]
        by = breakdown(trades, key)
        assert {k: v.n for k, v in by.items()} == {"Fav": 2, "Gold": 1}


class TestThresholds:
    def test_follow_every_opportunity_above_x(self) -> None:
        trades = [trade(i, win=s >= 80, strength=float(s)) for i, s in enumerate(range(50, 100, 5))]
        ex = threshold_explorer(trades, thresholds=(50, 80, 95))
        assert ex.in_sample and ex.warning == IN_SAMPLE_WARNING and ex.metric == "SETUP_STRENGTH"
        assert [r.summary.n for r in ex.rows] == [10, 4, 1]
        assert [r.summary.hit_rate for r in ex.rows] == [40.0, 100.0, 100.0]

    def test_a_custom_metric(self) -> None:
        trades = [trade(0, True), trade(1, False)]
        ex = threshold_explorer(
            trades,
            metric="WIN_PROBABILITY",
            value=lambda t: 60.0 if t.win else None,  # unscored trades never qualify
            thresholds=(55,),
        )
        assert ex.metric == "WIN_PROBABILITY" and ex.rows[0].summary.n == 1


class TestScoreboard:
    def test_detector_and_family_records_with_lift(self) -> None:
        rng = np.random.default_rng(3)
        trades = []
        for i in range(2000):
            fib, rsi = rng.random() < 0.5, rng.random() < 0.5
            win = bool(rng.random() < (0.6 if fib else 0.2))
            feats = {FIB: 0.8} if fib else {}
            if rsi:
                feats[RSI] = 0.7
            if fib and rng.random() < 0.5:
                feats[FIB2] = 0.5
            trades.append(trade(i, win, features=feats))
        board = {(s.theory, s.level): s for s in scoreboard(trades)}
        fib_d, rsi_d, fam = board[(FIB, "detector")], board[(RSI, "detector")], board[("FIBONACCI", "family")]
        assert fib_d.lift is not None and fib_d.lift > 1.3 and fib_d.low < fib_d.hit_rate < fib_d.high
        assert rsi_d.lift is not None and abs(rsi_d.lift - 1) < 0.1  # adds nothing
        assert fam.n == fib_d.n  # a trade counts once per family, however many of its detectors fired
        assert fib_d.expectancy_r > rsi_d.expectancy_r and fib_d.group == ("FOREX_MAJOR", "M15")

    def test_conflicting_evidence_is_not_support(self) -> None:
        board = scoreboard([trade(0, True, features={RSI: -0.9})])
        assert board == []


class TestReport:
    def test_live_and_replay_are_never_mixed(self) -> None:
        live = [trade(i, True) for i in range(3)]
        replay = [trade(10 + i, False, source=Source.REPLAY) for i in range(5)]
        rep = accuracy_report(live + replay, watchlists={"Fav": ["EURUSD"]})
        assert (rep.live.summary.n, rep.live.summary.hit_rate) == (3, 100.0)
        assert (rep.replay.summary.n, rep.replay.summary.hit_rate) == (5, 0.0)
        assert rep.live.breakdowns["watchlist"]["Fav"].n == 3 and len(rep.replay.curve) == 5
        assert rep.live.explorer.in_sample and "symbol" in rep.replay.breakdowns


def test_load_records(db: Database) -> None:
    def add(oid: str, *, variant: Variant = Variant.PLAN, close: bool = True, source: str = "LIVE") -> None:
        facts = SignalFacts(
            opportunity_id=oid, source=source, server="FBS-Demo", strategy="s", symbol="EURUSD",
            asset_class="FOREX_MAJOR", timeframe="M15", side="BUY", session="LONDON", setup_strength=70.0, rr=2.0,
            features={FIB: 0.8}, atr=0.001, signal_at=T0, lot=0.1, equity=10_000.0, currency="USD", alerted=True,
        )  # fmt: skip
        state = new_state(
            side=Side.BUY, entry=1.1, entry_at=T0, sl=1.095, tp=1.11, time_stop=timedelta(hours=72)
        )
        row = new_row(facts, variant, state, EntryQuote(1.0999, 1.1, 1.0, 1.0), (), T0)
        if close:
            result = ShadowResult(True, 2.0, 1.95, 0.1, 2.0, 0, 100.0, -0.7, 0.0, 99.3, 50.0, frozenset())
            apply_close(row, ShadowExit(ExitReason.TAKE_PROFIT, 1.11, T0 + timedelta(hours=1)), result)
        with db.session() as sess:
            sess.add(row)

    add("a")
    add("b", variant=Variant.MANAGED)
    add("c", close=False)
    add("d", source="REPLAY")
    records = load_records(db, server="FBS-Demo")
    assert [r.shadow_id for r in records] == ["a:PLAN", "d:PLAN"]
    a = records[0]
    assert a.win and a.r_net == 1.95 and a.net_pnl == 99.3 and a.alerted and a.features == {FIB: 0.8}
    assert [r.source for r in load_records(db, server="FBS-Demo", source=Source.REPLAY)] == [Source.REPLAY]
    assert len(load_records(db, server="FBS-Demo", variant=Variant.MANAGED)) == 1
    assert replace(a, win=False).win is False  # records are plain values


class TestEdge:
    def test_live_counts_fully_replay_is_a_capped_prior(self) -> None:
        from app.advisory.stats import edge_estimates

        live = [trade(i, True) for i in range(10)]  # +2R each
        replay = [trade(100 + i, False, source=Source.REPLAY) for i in range(500)]  # -1R each
        edges = edge_estimates(live + replay + [trade(900, True, symbol="XAUUSD")], replay_cap=50)
        eur = edges["EURUSD"]
        assert eur.trades == 60 and eur.expectancy_r == pytest.approx((10 * 2 - 50) / 60)
        assert edges["XAUUSD"].trades == 1 and edges["XAUUSD"].expectancy_r == 2.0
        few = edge_estimates([trade(i, False, source=Source.REPLAY) for i in range(20)], replay_cap=50)
        assert few["EURUSD"].trades == 20  # under the cap: every replay trade counts

    def test_edge_book_reloads_hourly(self, db: Database) -> None:
        from app.advisory.stats import EdgeBook

        now = {"t": 0.0}
        book = EdgeBook(db, server="FBS-Demo", monotonic=lambda: now["t"], refresh_seconds=3600)
        calls = {"n": 0}
        original = book.refresh

        def counted():  # type: ignore[no-untyped-def]
            calls["n"] += 1
            return original()

        book.refresh = counted  # type: ignore[method-assign]
        assert book("EURUSD") is None and calls["n"] == 1
        now["t"] = 100
        book("XAUUSD")
        assert calls["n"] == 1
        now["t"] = 3600
        book("EURUSD")
        assert calls["n"] == 2
