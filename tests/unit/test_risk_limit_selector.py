"""The aggressive Trading-profile preset on the engine (PLAN §A36): wire format, cage, selector, refusals."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.advisory.preferences import TradingProfile
from app.config import AppConfig, HighRiskCage, HighRiskConfig, RiskConfig
from app.core.clock import ManualClock
from app.engine.risk_limits import RiskLimitSelector
from app.risk.limits import HighRiskRefused, ProfileLimits, RiskMode, RiskProfileDoc, effective_risk
from app.risk.reasons import Reason
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import AuditEvent
from app.storage.repositories import EngineStateRepository
from app.sync.risk_profile import RISK_PROFILE_PATH, RiskProfileClient

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
CAGE = RiskConfig(
    max_risk_per_trade_percent=3.0,
    max_total_open_risk_percent=10.0,
    max_daily_loss_percent=10.0,
    max_weekly_loss_percent=20.0,
    min_lot_fallback=True,
)
HIGH = HighRiskConfig(setups=["setup_harmonic_prz", "setup_breakout"]).cage(CAGE)


def aggressive(r: float = 7.5) -> ProfileLimits:
    return TradingProfile(risk_mode=RiskMode.AGGRESSIVE, aggressive_risk_percent=r).resolve().limits()


def standard() -> ProfileLimits:
    return TradingProfile(style=50).resolve().limits()


class Server:
    def __call__(self, target: str, etag: str | None) -> tuple[int | None, Any, str | None]:
        assert target == RISK_PROFILE_PATH
        return 304, None, etag


def config() -> AppConfig:
    cfg = AppConfig()
    prefs = {"trading_profile": {"style": 50}}
    return cfg.model_copy(
        update={"risk": CAGE, "advisory": cfg.advisory.model_copy(update={"preferences": prefs})}
    )


def client_with(db: Database, clock: ManualClock, limits: ProfileLimits) -> RiskProfileClient:
    client = RiskProfileClient(Server(), EngineStateRepository(db, clock), clock, refresh_seconds=60)
    client.current = RiskProfileDoc.of(limits, NOW)
    return client


def events(db: Database, kind: str) -> list[dict[str, Any]]:
    with db.session() as sess:
        rows = sess.scalars(select(AuditEvent).where(AuditEvent.event_type == kind)).all()
        return [dict(r.payload) for r in rows]


@pytest.fixture
def mclock() -> ManualClock:
    return ManualClock(NOW)


class TestWire:
    def test_standard_documents_keep_their_shape_and_version(self) -> None:
        limits = standard()
        assert "risk_mode" not in limits.to_dict()
        wire = RiskProfileDoc.of(limits, NOW).wire()
        assert "risk_mode" not in wire
        same = dataclasses.replace(limits, risk_mode=RiskMode.STANDARD)
        assert same.version() == limits.version()

    def test_aggressive_documents_carry_the_mode(self) -> None:
        doc = RiskProfileDoc.of(aggressive(), NOW)
        assert doc.wire()["risk_mode"] == "AGGRESSIVE"
        assert doc.limits().aggressive
        assert doc.risk_per_trade_percent == 7.5
        assert doc.total_open_risk_percent == 15.0 and doc.max_daily_loss_percent == 15.0
        assert doc.max_open_positions == 2
        assert doc.version != RiskProfileDoc.of(standard(), NOW).version

    def test_old_engines_refuse_only_aggressive_documents(self) -> None:
        """An engine from before PLAN §A36 knows every field but ``risk_mode`` and refuses unknown keys."""
        old_fields = set(RiskProfileDoc.model_fields) - {"risk_mode"}
        assert set(RiskProfileDoc.of(standard(), NOW).wire()) <= old_fields
        assert set(RiskProfileDoc.of(aggressive(), NOW).wire()) - old_fields == {"risk_mode"}
        with pytest.raises(ValidationError):
            RiskProfileDoc.model_validate(RiskProfileDoc.of(standard(), NOW).wire() | {"unknown": 1})

    def test_standard_document_above_the_standard_ceiling_is_refused(self) -> None:
        data = RiskProfileDoc.of(standard(), NOW).wire() | {"risk_per_trade_percent": 7.5}
        with pytest.raises(ValidationError, match="standard ceilings"):
            RiskProfileDoc.model_validate(data)

    def test_aggressive_document_above_ten_percent_is_refused(self) -> None:
        data = RiskProfileDoc.of(aggressive(), NOW).wire() | {"risk_per_trade_percent": 10.5}
        with pytest.raises(ValidationError):
            RiskProfileDoc.model_validate(data)

    def test_aggressive_document_takes_the_fallback(self) -> None:
        doc = RiskProfileDoc.of(aggressive(), NOW)
        assert doc.min_lot_fallback  # the cage caps the minimum lot's risk (owner, 2026-10-14)


class TestEffectiveRisk:
    def test_aggressive_against_a_standard_cage_is_refused(self) -> None:
        with pytest.raises(HighRiskRefused):
            effective_risk(CAGE, aggressive())

    def test_aggressive_inside_the_high_risk_cage(self) -> None:
        eff = effective_risk(HIGH, aggressive(7.5))
        assert isinstance(eff, HighRiskCage)
        assert eff.max_risk_per_trade_percent == 7.5
        assert eff.max_total_open_risk_percent == 15.0
        assert eff.max_daily_loss_percent == 15.0
        assert eff.max_open_positions == 2
        assert eff.max_weekly_loss_percent == 35.0
        assert eff.max_account_drawdown_percent == 60.0
        assert eff.min_lot_fallback is True and eff.min_lot_max_risk_percent == 15.0

    def test_ten_percent_is_the_most(self) -> None:
        assert effective_risk(HIGH, aggressive(10.0)).max_risk_per_trade_percent == 10.0
        with pytest.raises(ValidationError):
            TradingProfile(risk_mode=RiskMode.AGGRESSIVE, aggressive_risk_percent=10.5)

    def test_standard_profile_inside_the_high_risk_cage_keeps_its_values(self) -> None:
        eff = effective_risk(HIGH, standard())
        assert eff.max_risk_per_trade_percent == 0.75


class TestSelector:
    def test_aggressive_without_the_opt_in_is_refused_and_audited_once(
        self, db: Database, mclock: ManualClock
    ) -> None:
        audit = AuditLog(db, "engine:t", mclock)
        sel = RiskLimitSelector(config(), client_with(db, mclock, aggressive()), audit, mclock)
        applied = sel.current()
        sel.current()
        assert not applied.aggressive
        assert applied.refused is Reason.HIGH_RISK_NOT_ENABLED
        assert applied.effective.max_risk_per_trade_percent == 0.75  # the standard local profile
        assert not isinstance(applied.effective, HighRiskCage)
        refused = events(db, "HIGH_RISK_REFUSED")
        assert len(refused) == 1 and refused[0]["reason"] == "HIGH_RISK_NOT_ENABLED"
        snap = sel.snapshot()
        assert snap is not None
        assert snap["risk_mode"] == "STANDARD" and snap["refused"] == "HIGH_RISK_NOT_ENABLED"
        assert snap["high_risk"]["available"] is False
        assert sel.config_ok()

    def test_mode_not_allowed_is_reported(self, db: Database, mclock: ManualClock) -> None:
        sel = RiskLimitSelector(
            config(),
            client_with(db, mclock, aggressive()),
            None,
            mclock,
            high_risk_refusal="MODE_NOT_ALLOWED",
        )
        assert sel.current().refused is Reason.HIGH_RISK_MODE_NOT_ALLOWED

    def test_aggressive_with_the_cage_applies(self, db: Database, mclock: ManualClock) -> None:
        audit = AuditLog(db, "engine:t", mclock)
        sel = RiskLimitSelector(
            config(), client_with(db, mclock, aggressive(8.0)), audit, mclock, high_risk=HIGH
        )
        applied = sel.current()
        assert applied.aggressive and applied.refused is None
        assert isinstance(applied.cage, HighRiskCage)
        assert applied.effective.max_risk_per_trade_percent == 8.0
        assert applied.effective.max_account_drawdown_percent == 60.0
        recorded = events(db, "RISK_PROFILE_APPLIED")[-1]
        assert recorded["risk_mode"] == "AGGRESSIVE" and recorded["drawdown_percent"] == 60.0
        snap = sel.snapshot()
        assert snap is not None and snap["risk_mode"] == "AGGRESSIVE"
        assert snap["high_risk"]["available"] is True
        assert snap["high_risk"]["setups"] == ["setup_harmonic_prz", "setup_breakout"]
        assert snap["cage"]["risk_per_trade_percent"] == 10.0
        assert sel.config_ok()

    def test_the_scanner_never_sizes_aggressive(self, db: Database, mclock: ManualClock) -> None:
        sel = RiskLimitSelector(config(), client_with(db, mclock, aggressive()), None, mclock, high_risk=HIGH)
        assert sel.current().aggressive
        assert not sel.scan_limits().aggressive

    def test_a_standard_profile_ignores_the_available_cage(self, db: Database, mclock: ManualClock) -> None:
        sel = RiskLimitSelector(config(), client_with(db, mclock, standard()), None, mclock, high_risk=HIGH)
        applied = sel.current()
        assert not applied.aggressive and applied.cage is CAGE

    def test_no_entry_before_the_first_selection(self, mclock: ManualClock) -> None:
        sel = RiskLimitSelector(config(), None, None, mclock)
        assert not sel.config_ok()
        sel.current()
        assert sel.config_ok()
