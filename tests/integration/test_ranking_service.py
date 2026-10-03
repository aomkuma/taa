"""The ranking service end to end on a multi-asset FakeMT5 with a simulated clock (TAA-6A5)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from app.advisory.asset_classes import AssetClass
from app.advisory.ranking_report import format_ranking
from app.advisory.ranking_service import RankingService
from app.advisory.universe import SymbolCatalog
from app.broker.fake_mt5 import ALL_SYMBOLS, FakeMT5
from app.config import AppConfig, load_settings
from app.core.clock import ManualClock
from app.core.errors import SymbolUnavailable
from app.storage.database import Database
from app.storage.models import SuitabilitySnapshotRow
from tests.integration.test_engine_paper import harness
from tests.unit.test_market_data import ENV, setup

WED = datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC)  # London open; FakeMT5 history ends at the current bar
CONFIG = load_settings(env_file=None, config_file="config.yaml", environ=ENV).config
ENABLED = sorted(s for s in ALL_SYMBOLS if s != "USDZAR")  # exotics are opt-in


def config(**ranking: object) -> AppConfig:
    advisory = CONFIG.advisory.model_copy(
        update={"ranking": CONFIG.advisory.ranking.model_copy(update=ranking)}
    )
    return CONFIG.model_copy(update={"advisory": advisory})


def service(db: Database, cfg: AppConfig | None = None) -> tuple[RankingService, ManualClock, FakeMT5]:
    clock, fake, gateway = setup(WED, ALL_SYMBOLS)
    cfg = cfg or CONFIG
    catalog = SymbolCatalog(db, gateway, cfg.advisory.universe, clock, server="FBS-Demo")
    return RankingService(db, gateway, catalog, cfg, clock, server="FBS-Demo"), clock, fake


def stored(db: Database) -> int:
    with db.session() as sess:
        return int(sess.execute(select(func.count()).select_from(SuitabilitySnapshotRow)).scalar_one())


class TestFirstRun:
    def test_multi_asset_ranking_is_ranked_and_stored(self, db: Database) -> None:
        svc, _, _ = service(db)
        run = svc.tick()
        assert run is not None
        assert sorted(r.symbol for r in run.ranked) == ENABLED
        assert {r.suitability.asset_class for r in run.ranked} == set(AssetClass) - {
            AssetClass.FOREX_EXOTIC,
            AssetClass.OTHER,
        }
        assert [r.rank for r in run.ranked] == list(range(1, len(ENABLED) + 1))
        eligible = [r.eligible for r in run.ranked]
        assert eligible == sorted(eligible, reverse=True)  # eligible symbols first
        rows = svc.latest()
        assert [r.symbol for r in rows] == [r.symbol for r in run.ranked]
        eur = next(r for r in rows if r.symbol == "EURUSD")
        assert eur.payload["session"]["open"] is True and "LONDON" in eur.payload["session"]["active"]
        assert set(eur.payload["scores"]) == {f"S{i}" for i in range(1, 10)}
        assert [g["gate"][:2] for g in eur.payload["gates"]] == [f"G{i}" for i in range(1, 7)]
        assert eur.payload["metrics"]["currency"] == "USD" and eur.payload["metrics"]["lot"] > 0
        assert len(eur.payload["best_hours_utc"]) == 3
        assert svc.stats.runs == 1 and svc.stats.refreshed == len(ENABLED) and svc.stats.failures == 0

    def test_small_account_excludes_xauusd(self, db: Database) -> None:
        svc, _, fake = service(db)
        fake.account.balance = 100.0
        run = svc.tick()
        assert run is not None
        xau = next(r for r in svc.latest() if r.symbol == "XAUUSD")
        assert not xau.eligible and xau.failed_gates == ["G2_MIN_LOT"]
        g2 = next(g for g in xau.payload["gates"] if g["gate"] == "G2_MIN_LOT")
        assert g2["key"] == "g2.min_lot_risk"
        assert g2["params"]["required_equity"] == pytest.approx(
            xau.payload["metrics"]["required_equity"], abs=0.01
        )
        table = format_ranking(run, language="th")
        assert "ต้องมีเงินทุน (equity) อย่างน้อย" in table and "XAUUSD" in table


class TestSchedule:
    def test_round_robin_batches_and_now_cadence(self, db: Database) -> None:
        svc, clock, _ = service(db, config(batch_size=4))
        first = svc.tick()
        assert first is not None and len(first.ranked) == 4
        clock.advance(30)
        assert svc.tick() is None  # Now score once a minute; this tick still refreshed the next batch
        clock.advance(30)
        run = svc.tick()
        assert run is not None and len(run.ranked) == len(ENABLED)
        assert svc.stats.refreshed == len(ENABLED)
        clock.advance(60)
        svc.tick()
        assert svc.stats.refreshed == len(ENABLED)  # nothing is stale within the hour

    def test_dynamic_horizon_and_rescan(self, db: Database) -> None:
        svc, clock, _ = service(db)
        svc.tick()
        clock.advance(61 * 60)
        svc.tick()
        assert svc.stats.refreshed == 2 * len(ENABLED)
        svc.request_rescan()
        run = svc.tick()
        assert run is not None and svc.stats.refreshed == 3 * len(ENABLED)

    def test_equity_move_triggers_a_structural_refresh(self, db: Database) -> None:
        svc, clock, fake = service(db)
        svc.tick()
        assert svc.stats.structural == 1
        clock.advance(60)
        fake.account.balance = 10_400.0  # +4%: below the 5% trigger
        svc.tick()
        assert svc.stats.structural == 1
        clock.advance(60)
        fake.account.balance = 10_600.0
        svc.tick()
        assert svc.stats.structural == 2 and svc.stats.refreshed == 2 * len(ENABLED)

    def test_hourly_history_and_retention(self, db: Database) -> None:
        svc, clock, _ = service(db)
        svc.tick()
        clock.advance(60)
        svc.tick()
        assert stored(db) == len(ENABLED)  # same hour: rows are rewritten
        clock.advance(3600)
        svc.tick()
        assert stored(db) == 2 * len(ENABLED)
        assert {r.computed_at for r in svc.latest()} == {clock.now_utc()}
        with db.session() as sess:
            old = datetime(2026, 6, 1, tzinfo=UTC)
            sess.add(
                SuitabilitySnapshotRow(
                    server="FBS-Demo", symbol="EURUSD", hour=old, computed_at=old, asset_class="FOREX_MAJOR",
                    rank=1, eligible=True, overall=1.0, now_score=1.0, failed_gates=[], payload={},
                )
            )  # fmt: skip
        clock.advance(3600)
        svc.tick()
        assert stored(db) == 3 * len(ENABLED)  # the 120-day-old row is purged

    def test_a_failing_symbol_is_skipped(self, db: Database) -> None:
        svc, clock, _ = service(db)
        svc.tick()
        original = svc.candles.closed_candles

        def failing(symbol: str, *args: Any, **kwargs: Any) -> Any:
            if symbol == "BTCUSD":
                raise SymbolUnavailable("BTCUSD is gone")
            return original(symbol, *args, **kwargs)

        svc.candles.closed_candles = failing  # type: ignore[method-assign]
        clock.advance(61 * 60)
        run = svc.tick()
        assert run is not None and svc.stats.failures == 1 and "BTCUSD" in svc.stats.last_error
        assert len(run.ranked) == len(ENABLED)  # the cached metrics still rank until the next refresh

    def test_a_vanished_symbol_is_not_suitable(self, db: Database) -> None:
        svc, clock, fake = service(db)
        svc.tick()
        del fake.symbols["BTCUSD"]
        clock.advance(61 * 60)
        run = svc.tick()
        assert run is not None
        btc = next(r for r in run.ranked if r.symbol == "BTCUSD")
        assert not btc.eligible and btc.rank > sum(r.eligible for r in run.ranked)


class TestEngine:
    def test_engine_ranks_in_its_loop(self, tmp_path: Path) -> None:
        h = harness(tmp_path)
        h.engine.start()
        h.engine.run(max_cycles=4)
        status = h.engine.status()["ranking"]
        assert status["runs"] == 2 and status["failures"] == 0 and status["symbols"] == len(ENABLED)
        assert h.engine.request_rescan()

    def test_a_ranking_failure_never_stops_the_engine(self, tmp_path: Path) -> None:
        h = harness(tmp_path)
        h.engine.start()
        assert h.engine.ranking is not None

        def boom() -> None:
            raise RuntimeError("ranking exploded")

        h.engine.ranking.tick = boom  # type: ignore[method-assign]
        h.engine.run(max_cycles=3)
        assert h.engine.last_error == ""
        assert h.engine.status()["ranking"]["last_error"] == "RuntimeError: ranking exploded"

    def test_ranking_can_be_disabled(self, tmp_path: Path) -> None:
        advisory = CONFIG.advisory.model_copy(
            update={"ranking": CONFIG.advisory.ranking.model_copy(update={"enabled": False})}
        )
        h = harness(tmp_path, advisory=advisory)
        h.engine.start()
        assert h.engine.ranking is None and h.engine.status()["ranking"] is None
        assert not h.engine.request_rescan()


def test_cli_rank_with_the_fake_broker(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from app.cli.__main__ import main

    env = tmp_path / ".env"
    env.write_text(
        "TRADING_MODE=PAPER\nMT5_LOGIN=12345678\nMT5_PASSWORD=investor-pass\nMT5_SERVER=FBS-Demo\n"
        "MT5_TERMINAL_PATH=x\n"
        f"ENGINE_DB_URL=sqlite:///{(tmp_path / 'engine.db').as_posix()}\n",
        encoding="utf-8",
    )
    assert main(["--env-file", str(env), "advisory", "rank", "--fake", "--top", "3", "--lang", "th"]) == 0
    out = capsys.readouterr().out
    assert "Suitability ranking" in out and "ไม่ใช่การคาดการณ์" in out
    assert len([line for line in out.splitlines() if line[:3].strip().isdigit()]) == 3
    assert not (tmp_path / "engine.db").exists()  # --fake never writes the engine database
