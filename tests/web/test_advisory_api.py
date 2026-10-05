"""Advisory APIs: preferences, watchlists, catalog, ranking, opportunities with contributions, shadow stats,
the engine's advisory-config, the user's profile (TAA-809)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.advisory.calibration import build, save
from app.core.clock import ManualClock
from app.security.hmac_auth import Signer
from app.storage.database import Database
from app.storage.models import (
    CalibrationTableRow,
    EvidenceModelVersionRow,
    OpportunityRow,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
)
from app.sync.advisory_config import ADVISORY_CONFIG_PATH
from tests.sync_data import sample_rows
from tests.unit.test_calibration import CFG, INFORMATIVE, outcomes, shadow
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, login, make_app, mutation_headers

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
SERVER = "FBS-Demo"
SECRET = "engine-hmac-secret-0123456789abcdef-xyz"


def fill(db: Database, engine_id: str) -> str:
    """Ranking (two hours), one opportunity with a calibration version, three closed shadow trades."""
    version = save(db, build(outcomes(1500, informative=True, seed=4), CFG, server=SERVER, built_at=NOW))
    for oid in ("o1", "o2", "o3"):
        shadow(db, oid)
    with db.session() as sess:
        for model in (CalibrationTableRow, EvidenceModelVersionRow, ShadowTradeRow):
            sess.execute(update(model).values(engine_id=engine_id))
        samples = {type(r): r for r in sample_rows()}
        for hour, (eur_rank, gold_rank) in ((NOW - timedelta(hours=1), (2, 1)), (NOW, (1, 2))):
            for symbol, rank, eligible in (("EURUSD", eur_rank, True), ("XAUUSD", gold_rank, False)):
                sess.add(
                    SuitabilitySnapshotRow(
                        engine_id=engine_id,
                        server=SERVER,
                        symbol=symbol,
                        hour=hour,
                        computed_at=hour,
                        asset_class="FOREX_MAJOR" if symbol == "EURUSD" else "METAL",
                        rank=rank,
                        eligible=eligible,
                        overall=80.0 - rank,
                        now_score=60.0,
                        failed_gates=[] if eligible else ["G2"],
                        payload={"scores": {"S1": 90.0}},
                    )
                )
        opp = samples[OpportunityRow]
        assert isinstance(opp, OpportunityRow)
        opp.engine_id, opp.opportunity_id, opp.strategy = engine_id, "o1", "s"
        opp.asset_class, opp.calibration_version = "FOREX_MAJOR", version
        opp.features = {INFORMATIVE: 0.8, "ctx:rr=2-3": 1.0}
        opp.signal = {
            "evidence": [{"detector": "fib.retracement", "quality": 0.8}],
            "confluence": {"score": 72},
        }
        sess.add(opp)
    return version


@pytest.fixture
def rig(db: Database, static_dir: Path) -> Iterator[tuple[FastAPI, TestClient, str, str]]:
    clock = ManualClock(NOW)
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    ctx = app.state.ctx
    alice = ctx.auth.create_user("alice", PASSWORD, TOTP_SECRET, role="OWNER")
    bob = ctx.auth.create_user("bob", PASSWORD, TOTP_SECRET, role="SUBSCRIBER")
    ctx.engine.registry.import_env(alice, "eng-a", SECRET, None, actor="t")
    theirs = ctx.engine.registry.register(bob, "bob pc", actor="bob").engine_id
    fill(db, "eng-a")
    with TestClient(app, base_url="https://testserver") as client:
        assert login(client, clock, username="alice").status_code == 200
        yield app, client, "eng-a", theirs


def put(client: TestClient, path: str, body: Any) -> Any:
    return client.put(f"/api/v1{path}", json=body, headers=mutation_headers(client))


def post(client: TestClient, path: str, body: Any = None) -> Any:
    return client.post(f"/api/v1{path}", json=body, headers=mutation_headers(client))


class TestPreferences:
    def test_defaults_round_trip_and_validation(self, rig: Any) -> None:
        _, client, _, _ = rig
        prefs = client.get("/api/v1/advisory/preferences").json()
        assert [w["kind"] for w in prefs["watchlists"]] == ["FAVOURITES", "AUTO_TOP_N"]
        prefs["alerts"]["threshold"] = prefs["alerts"].get("threshold", 60)
        assert put(client, "/advisory/preferences", prefs).status_code == 200
        bad = prefs | {"theories": prefs["theories"] | {"detectors": {"no.such.detector": True}}}
        resp = put(client, "/advisory/preferences", bad)
        assert resp.status_code == 400 and resp.json()["error"]["code"] == "invalid_preferences"
        assert put(client, "/advisory/preferences", prefs | {"unknown": 1}).status_code == 400
        theories = put(
            client,
            "/advisory/preferences/theories",
            prefs["theories"] | {"detectors": {"fib.retracement": False}},
        )
        assert theories.status_code == 200 and theories.json()["theories"]["detectors"] == {
            "fib.retracement": False
        }

    def test_watchlists_and_favourites(self, rig: Any) -> None:
        _, client, _, _ = rig
        resp = post(client, "/advisory/watchlists", {"name": "Metals", "symbols": ["XAUUSD", "XAGUSD"]})
        assert resp.status_code == 201 and [w["name"] for w in resp.json()["watchlists"]][-1] == "Metals"
        assert (
            post(client, "/advisory/watchlists", {"name": "metals"}).json()["error"]["code"]
            == "watchlist_exists"
        )
        changed = put(client, "/advisory/watchlists/Metals", {"name": "Metals", "symbols": ["XAUUSD"]})
        assert changed.json()["watchlists"][-1]["symbols"] == ["XAUUSD"]
        bad = post(client, "/advisory/watchlists", {"name": "Bad", "symbols": ["EUR/USD"]})
        assert bad.status_code == 422
        on = post(client, "/advisory/favourites/EURUSD").json()
        assert on == {"symbol": "EURUSD", "favourite": True, "favourites": ["EURUSD"]}
        assert post(client, "/advisory/favourites/EURUSD").json()["favourite"] is False
        assert (
            client.delete("/api/v1/advisory/watchlists/Metals", headers=mutation_headers(client)).status_code
            == 204
        )
        gone = client.delete("/api/v1/advisory/watchlists/Metals", headers=mutation_headers(client))
        assert gone.status_code == 404 and gone.json()["error"]["code"] == "watchlist_not_found"

    def test_detector_catalog(self, rig: Any) -> None:
        _, client, _, _ = rig
        body = client.get("/api/v1/advisory/detectors").json()
        assert len(body["detectors"]) >= 61 and body["pattern_strategies"]
        fib = next(d for d in body["detectors"] if d["id"] == "fib.retracement")
        assert fib["family"] == "FIBONACCI" and "params" in fib

    def test_profile(self, rig: Any) -> None:
        _, client, _, _ = rig
        assert put(client, "/auth/profile", {"locale": "en", "timezone": "Europe/London"}).status_code == 200
        user = client.get("/api/v1/auth/session").json()["user"]
        assert (user["locale"], user["timezone"]) == ("en", "Europe/London")
        bad = put(client, "/auth/profile", {"locale": "en", "timezone": "Mars/Base"})
        assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_timezone"
        assert put(client, "/auth/profile", {"locale": "fr", "timezone": "UTC"}).status_code == 422


def get(client: TestClient, engine: str, route: str) -> Any:
    return client.get(f"/api/v1/engines/{engine}/{route}")


class TestEngineData:
    def test_ranking(self, rig: Any) -> None:
        _, client, mine, _ = rig
        body = get(client, mine, "ranking").json()
        assert body["computed_at"] == NOW.isoformat()
        assert [(i["symbol"], i["rank"]) for i in body["items"]] == [("EURUSD", 1), ("XAUUSD", 2)]
        assert "payload" not in body["items"][0]
        gold = body["items"][1]
        assert gold["gates"] == [] and gold["flags"] == [] and gold["market_open"] is None  # no payload parts
        assert body["account"] is None and body["universe"] is None  # rows from before TAA-916
        assert [i["symbol"] for i in get(client, mine, "ranking?eligible=true").json()["items"]] == ["EURUSD"]
        assert get(client, mine, "ranking/EURUSD").json()["payload"] == {"scores": {"S1": 90.0}}
        history = get(client, mine, "ranking/EURUSD/history?hours=24").json()["items"]
        assert [h["rank"] for h in history] == [2, 1]
        assert (
            get(client, mine, "ranking/EURUSD/history?hours=99999").json()["error"]["code"] == "invalid_query"
        )

    def test_opportunity_detail_explains_the_probability(self, rig: Any) -> None:
        _, client, mine, _ = rig
        [item] = get(client, mine, "opportunities").json()["items"]
        assert item["opportunity_id"] == "o1" and "signal" not in item and "features" not in item
        assert item["supporting"] == 0 and item["conflicting"] == 0  # the sample evidence has no relation
        detail = get(client, mine, "opportunities/o1").json()
        assert detail["evidence"] == [{"detector": "fib.retracement", "quality": 0.8}]
        assert detail["confluence"] == {"score": 72} and len(detail["shadow"]) == 1
        assert detail["plan"] == [] and detail["heat_after"] is None  # (rev. 3) no decision replicated here
        prob = detail["probability"]
        assert prob["available"] and 0 < prob["estimate"]["p"] < 100
        [fib] = [c for c in prob["contributions"] if c["detector"] == "fib.retracement"]
        assert fib["points"] > 0  # the informative theory raises the probability
        assert sum(c["points"] for c in prob["contributions"]) == pytest.approx(
            prob["estimate"]["p"] - prob["base_rate"]
        )
        # the list card carries the same % without the Shapley split
        brief = item["probability"]
        assert brief["estimate"]["p"] == pytest.approx(prob["estimate"]["p"])
        assert brief["contributions"] is None and brief["base_rate"] is None
        # the same opportunity for a user who switched Fibonacci off: no contribution from it
        prefs = client.get("/api/v1/advisory/preferences").json()
        put(
            client,
            "/advisory/preferences/theories",
            prefs["theories"] | {"detectors": {"fib.retracement": False}},
        )
        again = get(client, mine, "opportunities/o1").json()["probability"]
        assert not [c for c in again["contributions"] or [] if c["detector"] == "fib.retracement"]
        assert get(client, mine, "opportunities/nope").json()["error"]["code"] == "opportunity_not_found"

    def test_shadow_statistics(self, rig: Any) -> None:
        _, client, mine, _ = rig
        page = get(client, mine, "shadow-trades?status=CLOSED").json()
        assert len(page["items"]) == 3 and "features" not in page["items"][0]
        acc = get(client, mine, "accuracy").json()
        assert acc["hypothetical"] is True and acc["server"] == SERVER and acc["live"]["summary"]["n"] == 3
        assert acc["currency"] == "USD"  # of the money results
        assert get(client, mine, "threshold-explorer?source=LIVE").json()["in_sample"] is True
        assert "items" in get(client, mine, "theory-scoreboard").json()
        calib = get(client, mine, "calibration").json()
        assert calib["server"] == SERVER and "cells" not in calib
        assert get(client, mine, "accuracy?variant=OTHER").status_code == 422
        assert (
            get(client, mine, "accuracy?since=2026-01-01T00:00:00").json()["error"]["code"] == "invalid_query"
        )

    def test_another_users_engine(self, rig: Any) -> None:
        _, client, _, theirs = rig
        for route in ("ranking", "opportunities", "opportunities/o1", "accuracy", "calibration"):
            assert get(client, theirs, route).json()["error"]["code"] == "engine_not_found", route


class TestAdvisoryConfig:
    def test_the_engine_gets_its_owners_requirements_with_an_etag(self, rig: Any) -> None:
        app, client, _, _ = rig
        clock = app.state.ctx.clock

        def fetch(etag: str | None = None) -> Any:
            headers = Signer("eng-a", SECRET.encode(), clock).headers("GET", ADVISORY_CONFIG_PATH)
            if etag:
                headers["If-None-Match"] = etag
            return client.get(ADVISORY_CONFIG_PATH, headers=headers)

        first = fetch()
        assert first.status_code == 200 and first.json()["auto_top_n"] == 30
        etag = first.headers["etag"]
        assert fetch(etag).status_code == 304
        post(client, "/advisory/favourites/XAUUSD")
        changed = fetch(etag)
        assert changed.status_code == 200 and changed.json()["favourites"] == ["XAUUSD"]
        assert changed.headers["etag"] != etag
        assert client.get(ADVISORY_CONFIG_PATH).status_code == 401  # a web session is not an engine


def test_the_engines_own_client_follows_the_config(rig: Any) -> None:
    """``AdvisoryConfigClient`` (engine) against the real route: 200, then 304, then a change."""
    from app.storage.repositories import EngineStateRepository
    from app.sync.advisory_config import AdvisoryConfigClient
    from app.sync.client import CloudClient

    app, client, _, _ = rig
    clock = app.state.ctx.clock
    engine_db = Database("sqlite://")
    engine_db.create_all()
    cloud = CloudClient("https://testserver", Signer("eng-a", SECRET.encode(), clock), http=client)
    poller = AdvisoryConfigClient(cloud.get_conditional, EngineStateRepository(engine_db, clock), clock)
    assert poller.poll_once() and poller.source == "cloud" and poller.current is not None
    version = poller.current.version
    assert poller.poll_once() and poller.current.version == version  # 304: unchanged
    post(client, "/advisory/favourites/EURUSD")
    poller.poll_once()
    assert poller.current.favourites == ["EURUSD"] and poller.current.version != version


def test_the_engine_pulls_its_owners_risk_profile(rig: Any) -> None:
    """``RiskProfileClient`` (engine) against the real route (TAA-710): 404 until the owner saves a profile,
    then the resolved limits with an ETag, then the change."""
    from app.storage.repositories import EngineStateRepository
    from app.sync.client import CloudClient
    from app.sync.risk_profile import RISK_PROFILE_PATH, RiskProfileClient

    app, client, _, _ = rig
    clock = app.state.ctx.clock
    assert client.get(RISK_PROFILE_PATH).status_code == 401  # a web session is not an engine
    engine_db = Database("sqlite://")
    engine_db.create_all()
    cloud = CloudClient("https://testserver", Signer("eng-a", SECRET.encode(), clock), http=client)
    poller = RiskProfileClient(cloud.get_conditional, EngineStateRepository(engine_db, clock), clock)
    assert poller.poll_once() and poller.current is None  # 404 no_profile: the engine keeps its fallback
    prefs = client.get("/api/v1/advisory/preferences").json()
    prefs["trading_profile"]["overrides"]["risk_per_signal_percent"] = 1.5
    assert put(client, "/advisory/preferences", prefs).status_code == 200
    assert poller.poll_once() and poller.current is not None and poller.source == "cloud"
    assert poller.current.risk_per_trade_percent == 1.5
    version = poller.current.version
    assert poller.poll_once() and poller.current.version == version  # 304
    prefs["trading_profile"]["overrides"]["risk_per_signal_percent"] = 0.4
    put(client, "/advisory/preferences", prefs)
    poller.poll_once()
    assert poller.current.risk_per_trade_percent == 0.4 and poller.current.version != version
