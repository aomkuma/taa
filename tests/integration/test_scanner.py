"""The market opportunity scanner on a multi-asset FakeMT5 with a simulated clock (TAA-6B3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from app.advisory.preferences import AdvisoryPreferences, TheoryPreferences, Watchlist, WatchlistKind
from app.advisory.requirements import ComputeRequirements, compute_requirements
from app.advisory.scanner import OpportunityScanner
from app.broker.fake_mt5 import ALL_SYMBOLS, FakeMT5
from app.config import AppConfig, load_settings
from app.core.clock import ManualClock
from app.core.enums import Action
from app.engine.decision_engine import DecisionEngine, DecisionStore
from app.evidence.catalog import default_registry as evidence_registry
from app.market_data.trading_sessions import TradingSessions
from app.news.calendar import ManualBlackouts, NewsFilter
from app.storage.database import Database
from app.storage.models import DecisionRecordRow, OpportunityRow
from app.strategy.catalog import STRATEGIES
from app.strategy.catalog import default_registry as strategy_registry
from app.strategy.registry import StrategyRegistry
from app.strategy.signal_models import Signal
from tests.integration.test_engine_paper import BuyEveryBar, harness
from tests.unit.test_market_data import ENV, setup

WED = datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC)  # London open, just after the 10:00 M15 close
SAT = datetime(2026, 10, 3, 12, 0, 30, tzinfo=UTC)
CONFIG = load_settings(env_file=None, config_file="config.yaml", environ=ENV).config
REGISTRY = StrategyRegistry([*STRATEGIES, BuyEveryBar])
REQ = ComputeRequirements(("EURUSD", "XAUUSD"), frozenset({"fib.retracement"}), frozenset({"buy_every_bar"}))


def config(budget: float = 3.0) -> AppConfig:
    advisory = CONFIG.advisory.model_copy(
        update={"scanner": CONFIG.advisory.scanner.model_copy(update={"budget_seconds": budget})}
    )
    return CONFIG.model_copy(update={"advisory": advisory})


def scanner(
    db: Database, at: datetime = WED, req: ComputeRequirements = REQ, cfg: AppConfig | None = None
) -> tuple[OpportunityScanner, ManualClock, FakeMT5]:
    clock, fake, gateway = setup(at, ALL_SYMBOLS)
    cfg = cfg or config()
    decisions = DecisionEngine(
        cfg,
        load_settings(env_file=None, config_file="config.yaml", environ=ENV).mode,
        gateway,
        clock,
        sessions=TradingSessions(cfg.sessions, cfg.symbols),
        news=NewsFilter(ManualBlackouts([])),
        magic_base=500_000,
        config_hash="cfg",
        store=DecisionStore(db),
    )
    state = {"req": req}
    s = OpportunityScanner(
        db,
        gateway,
        cfg,
        clock,
        decisions=decisions,
        requirements=lambda: state["req"],
        server="FBS-Demo",
        strategy_catalog=REGISTRY,
    )
    s.state = state  # type: ignore[attr-defined]
    return s, clock, fake


def rows(db: Database) -> list[OpportunityRow]:
    with db.session() as sess:
        return list(sess.execute(select(OpportunityRow).order_by(OpportunityRow.symbol)).scalars())


class TestScan:
    def test_a_new_bar_becomes_market_opportunities(self, db: Database) -> None:
        s, _, _ = scanner(db)
        report = s.tick()
        assert report.scanned == ("EURUSD", "XAUUSD") and len(report.created) == 2 and report.pending == 0
        eur, xau = rows(db)
        assert (eur.symbol, eur.side, eur.strategy, eur.status) == (
            "EURUSD",
            "BUY",
            "buy_every_bar",
            "CANDIDATE",
        )
        assert eur.bar_close_at == datetime(2026, 9, 30, 10, 0, tzinfo=UTC) and eur.timeframe == "M15"
        assert (
            eur.lot is not None
            and eur.lot > 0
            and eur.risk_money is not None
            and eur.reward_money is not None
        )
        assert eur.reward_money == pytest.approx(2 * eur.risk_money, rel=0.05)  # RR 2 (risk includes costs)
        assert eur.rr == pytest.approx(2.0) and eur.currency == "USD" and eur.equity == 10_000.0
        assert eur.features["ctx:rr=2-3"] == 1.0 and "ctx:htf_aligned" in eur.features
        assert eur.requirements_version == REQ.version and xau.asset_class == "METAL"
        assert eur.bid is not None and eur.ask is not None and eur.ask > eur.bid  # shadow entry (§A27)
        assert eur.entry == eur.ask and eur.quote_at is not None and eur.alerted_at is None
        sig = Signal.from_dict(eur.signal)
        assert sig.idempotency_key == eur.opportunity_id and sig.action is Action.BUY
        with db.session() as sess:
            profiles = sess.execute(select(DecisionRecordRow.profile)).scalars().all()
        assert set(profiles) == {"ADVISORY"}

    def test_each_bar_once_and_idempotent(self, db: Database) -> None:
        s, clock, _ = scanner(db)
        s.tick()
        clock.advance(60)
        assert s.tick().scanned == ()  # no new bar
        s._last_bar.clear()  # e.g. a restart: the same bar is scanned again ...
        clock.advance(60)
        assert s.tick().created == ()  # ... and records nothing twice
        assert len(rows(db)) == 2
        clock.advance(15 * 60)
        assert len(s.tick().created) == 2  # the next bar
        assert len(rows(db)) == 4

    def test_a_queued_symbol_is_scanned_after_it_leaves_the_monitored_set(self, db: Database) -> None:
        s, clock, _ = scanner(db, cfg=config(budget=3.0))
        original = s.plan().builder.build

        def slow(*args: Any, **kwargs: Any) -> Any:
            clock.advance(4.0)  # one symbol uses the whole cycle budget
            return original(*args, **kwargs)

        s.plan().builder.build = slow  # type: ignore[method-assign]
        first = s.tick()
        assert first.scanned == ("EURUSD",) and first.pending == 1
        # the ranking's top N moved on before XAUUSD's turn: its queued bar is still scanned, not refused
        s.state["req"] = ComputeRequirements(("EURUSD",), REQ.detectors, REQ.strategies)  # type: ignore[attr-defined]
        second = s.tick()
        assert second.scanned == ("XAUUSD",) and len(second.created) == 1
        with db.session() as sess:
            refused = sess.execute(
                select(func.count())
                .select_from(DecisionRecordRow)
                .where(DecisionRecordRow.decision == "REJECT")
            ).scalar_one()
        assert refused == 0

    def test_scanning_is_time_boxed(self, db: Database) -> None:
        req = ComputeRequirements(("EURUSD", "GBPUSD", "USDJPY", "XAUUSD"), REQ.detectors, REQ.strategies)
        s, clock, _ = scanner(db, req=req, cfg=config(budget=3.0))
        original = s.plan().builder.build

        def slow(*args: Any, **kwargs: Any) -> Any:
            clock.advance(2.0)  # evidence scans are expensive
            return original(*args, **kwargs)

        s.plan().builder.build = slow  # type: ignore[method-assign]
        pulses: list[float] = []
        first = s.tick(between=lambda: pulses.append(clock.monotonic()))
        assert first.scanned == ("EURUSD", "GBPUSD") and first.pending == 2
        # the engine's heartbeat runs after every detector and every symbol, not once per cycle
        engine = s.plan().builder.evidence
        assert engine is not None
        per_symbol = len(engine.plan.order) * 2  # two enabled timeframes
        assert len(pulses) == 2 * (per_symbol + 1)
        assert engine.pulse is None  # only while the scanner runs
        second = s.tick()
        assert second.scanned == ("USDJPY", "XAUUSD") and second.pending == 0

    def test_hard_failures_are_hidden(self, db: Database) -> None:
        s, _, _ = scanner(db, at=SAT)  # weekend: the market is closed
        report = s.tick()
        assert report.scanned and report.created == () and s.stats.hidden == 2 and rows(db) == []

    def test_only_the_required_detectors_run(self, db: Database) -> None:
        s, _, _ = scanner(db)
        s.tick()
        engine = s.plan().builder.evidence
        assert engine is not None
        ran = {d for d, st in engine.stats.items() if st.calls}
        assert "fib.retracement" in ran
        assert ran <= set(engine.plan.order) and len(engine.plan.outputs) == 1
        assert not any(d.startswith(("harmonic.", "elliott.", "pattern.")) for d in ran)

    def test_the_plan_follows_the_requirements(self, db: Database) -> None:
        s, _, _ = scanner(db)
        first = s.plan()
        assert s.plan() is first
        s.state["req"] = ComputeRequirements(("EURUSD",), REQ.detectors, REQ.strategies)  # type: ignore[attr-defined]
        assert s.plan() is not first and s.plan().universe == {"EURUSD"}


class TestRequirements:
    def test_union_of_users(self) -> None:
        owner = AdvisoryPreferences(
            watchlists=[
                Watchlist(name="Fav", kind=WatchlistKind.FAVOURITES, symbols=["XAUUSD", "EURUSD"]),
                Watchlist(name="Top", kind=WatchlistKind.AUTO_TOP_N, top_n=2),
            ],
            theories=TheoryPreferences(preset=None, families={"FIBONACCI": True}, pattern_strategies={}),
        )
        other = AdvisoryPreferences(
            watchlists=[
                Watchlist(name="Swing", symbols=["US30"]),
                Watchlist(name="T", kind="AUTO_TOP_N", top_n=3),
            ],
            theories=TheoryPreferences(
                preset=None, families={"TREND": True}, pattern_strategies={"setup_breakout": False}
            ),
        )
        evidence, strategies = evidence_registry(), strategy_registry()
        cfg = CONFIG.model_copy(update={"symbols": CONFIG.symbols.model_copy(update={"allowed": ["EURUSD"]})})
        req = compute_requirements(
            [owner, other], cfg, ranked=["GBPUSD", "BTCUSD", "AAPL", "USOIL"], evidence=evidence,
            strategies=strategies,
        )  # fmt: skip
        assert req.symbols == ("EURUSD", "XAUUSD", "US30", "GBPUSD", "BTCUSD", "AAPL")
        assert "fib.retracement" in req.detectors and "trend.ma_alignment" in req.detectors
        assert not any(d.startswith("harmonic.") for d in req.detectors)
        assert "setup_breakout" in req.strategies  # the owner still allows it
        assert "example_trend_pullback" in req.strategies  # enabled for trading in config.yaml
        only_owner = compute_requirements(
            [owner], cfg, ranked=["GBPUSD"], evidence=evidence, strategies=strategies
        )
        assert only_owner.version != req.version
        assert (
            only_owner.version
            == compute_requirements(
                [owner], cfg, ranked=["GBPUSD"], evidence=evidence, strategies=strategies
            ).version
        )


class TestEngine:
    def test_engine_scans_in_its_loop(self, tmp_path: Path) -> None:
        advisory = CONFIG.advisory  # scanner enabled, as in config.yaml
        h = harness(tmp_path, advisory=advisory)
        h.engine.start()
        assert h.engine.scanner is not None and h.engine.lifecycle is not None
        h.engine.run(max_cycles=3)
        status = h.engine.status()["scanner"]
        assert status["bars"] >= 1 and status["failures"] == 0
        assert h.engine.last_error == ""

    def test_a_scanner_failure_never_stops_the_engine(self, tmp_path: Path) -> None:
        h = harness(tmp_path, advisory=CONFIG.advisory)
        h.engine.start()
        assert h.engine.scanner is not None

        def boom(**_: object) -> None:
            raise RuntimeError("scanner exploded")

        h.engine.scanner.tick = boom  # type: ignore[method-assign]
        h.engine.run(max_cycles=2)
        assert h.engine.last_error == "" and h.engine.status()["scanner"]["last_error"].startswith(
            "RuntimeError"
        )


def test_counts_do_not_include_hold_signals(db: Database) -> None:
    s, _, _ = scanner(db)
    s.tick()
    assert s.stats.signals == 2 and s.stats.bars == 2
    with db.session() as sess:
        assert sess.execute(select(func.count()).select_from(OpportunityRow)).scalar_one() == 2
