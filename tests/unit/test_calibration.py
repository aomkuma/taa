"""Calibration and evidence-model builder: training rows, versions, reliability, schedule (TAA-6C3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import func, select

from app.advisory.calibration import (
    CalibrationService,
    build,
    latest_version,
    load_latest,
    next_nightly,
    outcomes_from_shadows,
    reliability,
    save,
)
from app.advisory.confidence import Calibration, Outcome, Query, Source
from app.advisory.shadow import ShadowExit, ShadowResult, Variant, new_state
from app.advisory.shadow_tracker import EntryQuote, SignalFacts, apply_close, new_row
from app.config import CalibrationConfig
from app.core.clock import ManualClock
from app.core.enums import ExitReason, Side
from app.storage.database import Database
from app.storage.models import CalibrationTableRow, EvidenceModelVersionRow

T0 = datetime(2026, 6, 1, tzinfo=UTC)
CFG = CalibrationConfig(min_group=50, folds=4)
INFORMATIVE = "ev:FIBONACCI:fib.retracement"
NOISE = "ev:MOMENTUM:momentum.rsi_divergence"


def outcomes(
    n: int, *, p: float = 0.4, seed: int = 1, informative: bool = False, **kw: object
) -> list[Outcome]:
    """Synthetic outcomes; with *informative*, the Fibonacci feature lifts P(win) from 0.25 to 0.65."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        features: dict[str, float] = {"ctx:rr=2-3": 1.0}
        prob = p
        if informative:
            fib = rng.random() < 0.5
            if fib:
                features[INFORMATIVE] = 0.8
            if rng.random() < 0.5:
                features[NOISE] = 0.7
            prob = 0.65 if fib else 0.25
        args: dict[str, object] = {
            "strategy": "s",
            "symbol": "EURUSD",
            "asset_class": "FOREX_MAJOR",
            "strength": 70.0,
            "rr": 2.0,
            "win": bool(rng.random() < prob),
            "features": features,
            "at": T0 + timedelta(hours=i),
            "timeframe": "M15",
        } | kw
        out.append(Outcome(**args))  # type: ignore[arg-type]
    return out


def q(**kw: object) -> Query:
    args: dict[str, object] = {
        "strategy": "s",
        "symbol": "EURUSD",
        "asset_class": "FOREX_MAJOR",
        "strength": 70.0,
        "rr": 2.0,
    } | kw
    return Query(**args)  # type: ignore[arg-type]


def shadow(db: Database, oid: str, *, variant: Variant = Variant.PLAN, reason: ExitReason | None = ExitReason.TAKE_PROFIT, source: str = "LIVE", rr: float | None = 2.0, void: bool = False) -> None:  # fmt: skip
    facts = SignalFacts(
        opportunity_id=oid, source=source, server="FBS-Demo", strategy="s", symbol="EURUSD",
        asset_class="FOREX_MAJOR", timeframe="M15", side="BUY", session="LONDON", setup_strength=72.0, rr=rr,
        features={INFORMATIVE: 0.9}, atr=0.001, signal_at=T0, lot=0.1, equity=10_000.0, currency="USD",
    )  # fmt: skip
    sl = 1.1010 if void else 1.0950
    state = new_state(side=Side.BUY, entry=1.1, entry_at=T0, sl=sl, tp=1.11, time_stop=timedelta(hours=72))
    row = new_row(facts, variant, state, EntryQuote(1.0999, 1.1, 1.0, 1.0), (), T0)
    if reason is not None and not void:
        result = ShadowResult(
            reason is ExitReason.TAKE_PROFIT, 2.0, 1.9, 0.1, 2.0, 0, 20.0, -0.7, 0.0, 19.3, 10.0, frozenset()
        )
        apply_close(row, ShadowExit(reason, 1.11, T0 + timedelta(hours=1)), result)
    with db.session() as sess:
        sess.add(row)


class TestTrainingRows:
    def test_only_closed_plan_rows_with_an_rr(self, db: Database) -> None:
        shadow(db, "win")
        shadow(db, "loss", reason=ExitReason.STOP_LOSS, source="REPLAY")
        shadow(db, "time", reason=ExitReason.TIME_STOP)
        shadow(db, "managed", variant=Variant.MANAGED)
        shadow(db, "open", reason=None)
        shadow(db, "void", void=True)
        shadow(db, "no_rr", rr=None)
        got = outcomes_from_shadows(db, server="FBS-Demo")
        assert sorted(o.win for o in got) == [False, False, True]  # the time stop is not a TP-first
        loss = next(o for o in got if o.source is Source.REPLAY)
        assert not loss.win and loss.features == {INFORMATIVE: 0.9} and loss.strength == 72.0
        assert all(o.rr == 2.0 and o.timeframe == "M15" for o in got)
        assert outcomes_from_shadows(db, server="FBS-Demo", variant=Variant.MANAGED)[0].win
        assert outcomes_from_shadows(db, server="other") == []


class TestBuild:
    def test_known_probability_is_recovered(self) -> None:
        b = build(outcomes(600, p=0.6), CFG, server="FBS-Demo", built_at=T0)
        est = b.model.explain(q()).estimate
        assert est.low < 60 < est.high and abs(est.p - 60) < 5 and not est.insufficient
        assert est.calibration is Calibration.LIVE and b.n_live == 600 and b.n_replay == 0

    def test_informative_and_uninformative_detectors(self, db: Database) -> None:
        b = build(outcomes(3000, informative=True), CFG, server="FBS-Demo", built_at=T0)
        assert b.model.uses_evidence and b.report is not None and b.report.n_test > 0
        save(db, b)
        loaded = load_latest(db, "FBS-Demo")
        assert loaded is not None and loaded.model.uses_evidence and loaded.model.evidence is not None
        model = loaded.model.evidence.model_for(q())
        assert model is not None
        coef = dict(zip(model.names, model.coef, strict=True))
        assert coef[INFORMATIVE] > 1.0  # the right sign and a clear effect
        # a raw weight is not the measure (NOISE also moves ctx:n_families); what users see is its share of p
        both = q(features={INFORMATIVE: 0.8, NOISE: 0.7, "ctx:rr=2-3": 1.0})
        points = {c.feature: c.points for c in loaded.model.explain(both).contributions or ()}
        assert points[INFORMATIVE] > 10 and abs(points[NOISE]) < 2

    def test_replay_is_a_capped_prior(self) -> None:
        live = outcomes(60, p=0.6, seed=2)
        replay = outcomes(2000, p=0.2, seed=3, source=Source.REPLAY)
        b = build(live + replay, CFG, server="FBS-Demo", built_at=T0)
        est = b.model.explain(q()).estimate
        assert est.calibration is Calibration.MIXED and (b.n_live, b.n_replay) == (60, 2000)
        assert est.p > 35  # 2000 replay rows count as at most 50 pseudo-trades per cell

    def test_brier_and_reliability_are_out_of_sample(self) -> None:
        b = build(outcomes(800, p=0.4), CFG, server="FBS-Demo", built_at=T0)
        assert not b.model.uses_evidence  # no real signal: the bucket model is kept (min Brier improvement)
        assert b.report is not None and b.brier == pytest.approx(b.report.brier_bucket)
        assert (
            sum(r.n for r in b.reliability) == b.report.n_test and len(b.reliability) == CFG.reliability_bins
        )
        busy = max(b.reliability, key=lambda r: r.n)
        assert busy.low <= 0.4 < busy.high + 0.1 and busy.observed is not None

    def test_empty_build(self, db: Database) -> None:
        b = build([], CFG, server="FBS-Demo", built_at=T0)
        assert b.brier is None and b.report is None and b.window == (None, None)
        save(db, b)
        loaded = load_latest(db, "FBS-Demo")
        assert loaded is not None and loaded.model.explain(q()).estimate.p == pytest.approx(100 / 3)


def test_reliability_bins() -> None:
    bins = reliability([0.05, 0.15, 0.17, 0.95, 1.0], [0, 1, 0, 1, 1], bins=10)
    assert [b.n for b in bins] == [1, 2, 0, 0, 0, 0, 0, 0, 0, 2]
    assert (
        bins[1].observed == 0.5 and bins[1].mean_predicted == pytest.approx(0.16) and bins[2].observed is None
    )


class TestVersions:
    def test_round_trip_explains_identically(self, db: Database) -> None:
        b = build(outcomes(1500, informative=True, seed=4), CFG, server="FBS-Demo", built_at=T0)
        version = save(db, b)
        loaded = load_latest(db, "FBS-Demo")
        assert loaded is not None and loaded.version == version == b.version
        query = q(features={INFORMATIVE: 0.8, "ctx:rr=2-3": 1.0})
        original, again = b.model.explain(query), loaded.model.explain(query)
        assert again.estimate.p == pytest.approx(original.estimate.p)
        assert again.estimate.low == pytest.approx(original.estimate.low)
        assert again.base_rate == pytest.approx(original.base_rate)
        assert loaded.model.uses_evidence == b.model.uses_evidence

    def test_versions_are_kept_and_pruned(self, db: Database) -> None:
        for day in range(4):
            save(
                db,
                build(outcomes(50 + day), CFG, server="FBS-Demo", built_at=T0 + timedelta(days=day)),
                keep=2,
            )
        with db.session() as sess:
            assert sess.execute(select(func.count()).select_from(CalibrationTableRow)).scalar_one() == 2
        latest = latest_version(db, "FBS-Demo")
        assert latest is not None and latest[1] == T0 + timedelta(days=3)
        assert latest[0].startswith("20260604T000000Z-")

    def test_evidence_rows_follow_their_version(self, db: Database) -> None:
        for day in range(3):
            b = build(
                outcomes(1500, informative=True, seed=day),
                CFG,
                server="FBS-Demo",
                built_at=T0 + timedelta(days=day),
            )
            save(db, b, keep=1)
        with db.session() as sess:
            versions = set(sess.execute(select(EvidenceModelVersionRow.version)).scalars())
        latest = latest_version(db, "FBS-Demo")
        assert latest is not None and versions == {latest[0]}


class TestService:
    def test_nightly(self) -> None:
        at = datetime(2026, 10, 4, 22, 30, tzinfo=UTC)
        assert next_nightly(at, 23) == datetime(2026, 10, 4, 23, 0, tzinfo=UTC)
        assert next_nightly(at.replace(hour=23), 23) == datetime(2026, 10, 5, 23, 0, tzinfo=UTC)

    def test_first_start_then_nightly_then_on_demand(self, db: Database) -> None:
        clock = ManualClock(datetime(2026, 10, 4, 12, 0, tzinfo=UTC))
        rows = outcomes(100)
        svc = CalibrationService(
            db, CFG, clock, server="FBS-Demo", executor=CalibrationService.inline(), outcomes=lambda: rows
        )
        assert svc.load() is None and svc.due(clock.now_utc())
        first = svc.tick()
        assert first is not None and svc.current == first and svc.builds == 1
        clock.advance(3600)
        assert svc.tick() is None  # built today; next after 23:00 UTC
        clock.set(datetime(2026, 10, 4, 23, 0, 1, tzinfo=UTC))
        second = svc.tick()
        assert second is not None and second.version != first.version
        svc.request_rebuild()
        clock.advance(1)
        assert svc.tick() is not None and svc.builds == 3

    def test_a_failed_build_keeps_the_previous_version_and_backs_off(self, db: Database) -> None:
        clock = ManualClock(datetime(2026, 10, 4, 12, 0, tzinfo=UTC))
        calls = {"n": 0}

        def broken() -> list[Outcome]:
            calls["n"] += 1
            raise RuntimeError("db gone")

        svc = CalibrationService(
            db, CFG, clock, server="FBS-Demo", executor=CalibrationService.inline(), outcomes=broken
        )
        assert svc.tick() is None and svc.failures == 1 and svc.last_error.startswith("RuntimeError")
        clock.advance(60)
        assert svc.tick() is None and calls["n"] == 1  # no retry storm
        clock.advance(CalibrationService.RETRY_SECONDS)
        svc.tick()
        assert calls["n"] == 2

    def test_rebuild_from_the_database(self, db: Database) -> None:
        shadow(db, "a")
        shadow(db, "b", reason=ExitReason.STOP_LOSS)
        clock = ManualClock(datetime(2026, 10, 4, 12, 0, tzinfo=UTC))
        loaded = CalibrationService(
            db, CFG, clock, server="FBS-Demo", executor=CalibrationService.inline()
        ).rebuild()
        assert (loaded.n_live, loaded.n_replay) == (2, 0)


def test_cli_calibrate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from app.cli.__main__ import main
    from app.storage.database import upgrade_schema

    url = f"sqlite:///{(tmp_path / 'engine.db').as_posix()}"
    upgrade_schema(url)
    db = Database(url)
    shadow(db, "a")
    shadow(db, "b", reason=ExitReason.STOP_LOSS, source="REPLAY")
    env = tmp_path / ".env"
    env.write_text(f"TRADING_MODE=BACKTEST\nENGINE_DB_URL={url}\n", encoding="utf-8")
    assert main(["--env-file", str(env), "advisory", "calibrate", "--server", "FBS-Demo"]) == 0
    out = capsys.readouterr().out
    assert "1 live + 1 replay" in out and "not used" in out
    assert latest_version(db, "FBS-Demo") is not None
    db.dispose()
