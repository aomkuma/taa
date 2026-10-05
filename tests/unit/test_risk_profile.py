"""The engine owner's trading profile drives the engine's risk inside the local cage (PLAN §A33; TAA-710)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.advisory.preferences import TradingProfile
from app.config import AppConfig, RiskConfig
from app.core.clock import ManualClock
from app.core.enums import Side
from app.engine.risk_limits import RiskLimitSelector
from app.risk.limits import ProfileLimits, RiskProfileDoc, effective_risk, governed
from app.risk.position_sizer import PositionSizer
from app.risk.reasons import Reason
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import AuditEvent
from app.storage.repositories import EngineStateRepository
from app.sync.risk_profile import CACHE_KEY, RISK_PROFILE_PATH, RiskProfileClient
from tests.risk_data import XAUUSD_SPEC, TickCalculator, funds

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
CAGE = RiskConfig(
    max_risk_per_trade_percent=3.0,
    max_total_open_risk_percent=6.0,
    max_daily_loss_percent=6.0,
    max_weekly_loss_percent=12.0,
)


def doc(**over: Any) -> RiskProfileDoc:
    limits = dataclasses.replace(TradingProfile(style=50).resolve().limits(), **over)
    return RiskProfileDoc.of(limits, NOW)


class Server:
    def __init__(self, *answers: tuple[int | None, Any, str | None]) -> None:
        self.answers = list(answers)

    def __call__(self, target: str, etag: str | None) -> tuple[int | None, Any, str | None]:
        assert target == RISK_PROFILE_PATH
        return self.answers.pop(0) if self.answers else (304, None, etag)


def config(risk: RiskConfig = CAGE, style: int = 50) -> AppConfig:
    cfg = AppConfig()
    prefs = {"trading_profile": {"style": style}}
    return cfg.model_copy(
        update={"risk": risk, "advisory": cfg.advisory.model_copy(update={"preferences": prefs})}
    )


def events(db: Database, kind: str) -> list[dict[str, Any]]:
    with db.session() as sess:
        rows = sess.scalars(select(AuditEvent).where(AuditEvent.event_type == kind)).all()
        return [dict(r.payload) for r in rows]


@pytest.fixture
def mclock() -> ManualClock:
    return ManualClock(NOW)


def make_client(db: Database, clock: ManualClock, server: Server) -> RiskProfileClient:
    return RiskProfileClient(server, EngineStateRepository(db, clock), clock, refresh_seconds=60)


class TestWire:
    def test_round_trip_and_version(self) -> None:
        d = doc(risk_per_trade_percent=1.5)
        assert d.limits().risk_per_trade_percent == 1.5
        assert RiskProfileDoc.model_validate(d.model_dump(mode="json")) == d
        assert doc(risk_per_trade_percent=1.0).version != d.version  # the version follows the content

    @pytest.mark.parametrize(
        "bad",
        [
            {"risk_per_trade_percent": 3.5},  # above the hard ceiling
            {"risk_per_trade_percent": 0},
            {"max_open_positions": 0},
            {"min_risk_reward": float("nan")},
            {"extra": 1},
        ],
    )
    def test_the_engine_refuses_bad_documents(self, bad: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            RiskProfileDoc.model_validate(doc().model_dump(mode="json") | bad)

    def test_fields_map_one_to_one_onto_risk_config(self) -> None:
        """A field a profile governs must exist in ProfileLimits, the wire and ``governed`` alike."""
        names = {f.name for f in dataclasses.fields(ProfileLimits)}
        assert names == set(governed(CAGE)) == set(RiskProfileDoc.model_fields) - {"version", "updated_at"}
        lowered = effective_risk(CAGE, ProfileLimits(**{n: 1 for n in names}))
        assert all(v == 1 or n == "min_risk_reward" for n, v in governed(lowered).items())


class TestSelector:
    def test_without_a_cloud_the_local_profile_applies_never_the_bare_cage(
        self, db: Database, mclock: ManualClock
    ) -> None:
        sel = RiskLimitSelector(config(style=0), None, AuditLog(db, "engine:t", mclock), mclock)
        applied = sel.current()
        assert applied.origin == "local"
        assert applied.effective.max_risk_per_trade_percent == 0.25  # style 0, inside a 3 % cage
        assert events(db, "RISK_PROFILE_APPLIED")[0]["cage"]["risk_per_trade_percent"] == 3.0

    def test_a_cloud_value_below_the_cage_applies(self, db: Database, mclock: ManualClock) -> None:
        client = make_client(
            db, mclock, Server((200, doc(risk_per_trade_percent=1.5).model_dump(mode="json"), None))
        )
        client.poll_once()
        applied = RiskLimitSelector(config(), client, None, mclock).current()
        assert applied.origin == "cloud" and applied.effective.max_risk_per_trade_percent == 1.5

    def test_a_cloud_value_above_the_cage_is_clamped(self, db: Database, mclock: ManualClock) -> None:
        cage = RiskConfig()  # 0.5 % per trade
        client = make_client(
            db, mclock, Server((200, doc(risk_per_trade_percent=2.5).model_dump(mode="json"), None))
        )
        client.poll_once()
        applied = RiskLimitSelector(config(cage), client, None, mclock).current()
        assert applied.limits.risk_per_trade_percent == 2.5
        assert applied.effective.max_risk_per_trade_percent == 0.5

    def test_changes_are_audited_once(self, db: Database, mclock: ManualClock) -> None:
        server = Server(
            (200, doc(risk_per_trade_percent=1.0).model_dump(mode="json"), None),
            (200, doc(risk_per_trade_percent=2.0).model_dump(mode="json"), None),
        )
        client = make_client(db, mclock, server)
        sel = RiskLimitSelector(config(), client, AuditLog(db, "engine:t", mclock), mclock)
        sel.current()  # local
        client.poll_once()
        sel.current()
        sel.current()  # unchanged: no new event
        client.poll_once()
        sel.current()
        applied = events(db, "RISK_PROFILE_APPLIED")
        assert [e["effective"]["risk_per_trade_percent"] for e in applied] == [0.75, 1.0, 2.0]
        assert applied[-1]["previous"]["risk_per_trade_percent"] == 1.0
        assert applied[-1]["source"].startswith("cloud:")

    def test_a_document_the_cage_cannot_take_falls_back_to_local(
        self, db: Database, mclock: ManualClock
    ) -> None:
        # min RR 9 from the profile is valid on the wire, but this cage caps min_risk_reward at its own bound
        cage = CAGE.model_copy(update={"min_risk_reward": 1.5})
        client = make_client(db, mclock, Server())
        client.current = doc(min_risk_reward=10.0)
        sel = RiskLimitSelector(config(cage), client, AuditLog(db, "engine:t", mclock), mclock)
        original = RiskConfig.model_validate

        def strict(data: Any, *a: Any, **kw: Any) -> RiskConfig:
            if isinstance(data, dict) and data.get("min_risk_reward") == 10.0:
                raise ValueError("min_risk_reward out of range")
            return original(data, *a, **kw)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(RiskConfig, "model_validate", strict)
            assert sel.current().origin == "local"
            sel.current()
        assert len(events(db, "RISK_PROFILE_REJECTED")) == 1  # once per version

    def test_snapshot_reports_source_and_age(self, db: Database, mclock: ManualClock) -> None:
        client = make_client(db, mclock, Server((200, doc().model_dump(mode="json"), None)))
        client.poll_once()
        sel = RiskLimitSelector(config(), client, None, mclock)
        sel.current()
        mclock.advance(90)
        snap = sel.snapshot()
        assert snap is not None
        assert snap["source"] == "cloud" and snap["age_seconds"] == 90
        assert snap["effective"]["risk_per_trade_percent"] == 0.75


class TestClient:
    def test_fallback_survives_an_offline_cloud_and_a_restart(
        self, db: Database, mclock: ManualClock
    ) -> None:
        first = make_client(
            db, mclock, Server((200, doc(risk_per_trade_percent=1.2).model_dump(mode="json"), '"v"'))
        )
        assert first.poll_once()
        restarted = make_client(db, mclock, Server((None, None, None)))  # cloud offline
        assert restarted.source == "cache" and restarted.current is not None
        assert not restarted.poll_once()
        assert restarted.current.risk_per_trade_percent == 1.2  # the cached profile stays

    def test_invalid_answer_keeps_the_last_good_one(self, db: Database, mclock: ManualClock) -> None:
        bad = doc().model_dump(mode="json") | {"risk_per_trade_percent": 50}
        c = make_client(db, mclock, Server((200, doc().model_dump(mode="json"), None), (200, bad, None)))
        c.poll_once()
        assert not c.poll_once()
        assert c.current is not None and c.current.risk_per_trade_percent == 0.75 and c.failures == 1

    def test_404_keeps_the_fallback(self, db: Database, mclock: ManualClock) -> None:
        c = make_client(db, mclock, Server((404, {"code": "no_profile"}, None)))
        assert c.poll_once() and c.current is None and c.source == "local"
        assert EngineStateRepository(db, mclock).load(CACHE_KEY) is None


class TestXauusdOnASmallAccount:
    """The trigger (2026-10-05): ~$990 equity, a XAUUSD stop 13 USD away; 0.01 lot = 1 oz risks ~13 USD."""

    def size(self, risk: RiskConfig) -> Any:
        sizer = PositionSizer(risk, TickCalculator(XAUUSD_SPEC))
        return sizer.size(XAUUSD_SPEC, Side.BUY, 4147.83, 4134.83, funds(990.0), lot_limit=1.0)

    def test_rejected_at_half_a_percent(self) -> None:
        r = self.size(effective_risk(RiskConfig(), TradingProfile(style=50).resolve().limits()))
        assert not r.ok and r.reason is Reason.RISK_BELOW_MIN_LOT

    def test_accepted_at_a_one_and_a_half_percent_profile_in_a_three_percent_cage(self) -> None:
        r = self.size(effective_risk(CAGE, ProfileLimits(risk_per_trade_percent=1.5)))
        assert r.ok, r.detail
        assert str(r.volume) == "0.01"
