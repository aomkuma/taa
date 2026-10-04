"""Backtest API: create from presets, list, detail, trades, compare; only the user's own engines (TAA-807)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.clock import ManualClock
from app.storage.database import Database
from app.worker.backtests import BacktestService
from app.worker.backtests import handlers as backtest_handlers
from app.worker.jobs import JobQueue
from app.worker.service import Worker
from tests.backtest.test_cloud_backtests import NOW, period, upload
from tests.backtest.test_runner_cli import CONFIG
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, login, make_app, mutation_headers

Rig = tuple[FastAPI, TestClient, str, str, Any]


@pytest.fixture
def rig(db: Database, static_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Rig]:
    monkeypatch.setattr("app.worker.backtests.load_app_config", lambda: CONFIG)  # config.yaml in production
    clock = ManualClock(NOW)
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    ctx = app.state.ctx
    ids = []
    for name, role in (("alice", "OWNER"), ("bob", "SUBSCRIBER")):
        user = ctx.auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
        ids.append(ctx.engine.registry.register(user, f"{name} pc", actor=name).engine_id)
    m15 = upload(db, engine=ids[0])
    with TestClient(app, base_url="https://testserver") as client:
        assert login(client, clock, username="alice").status_code == 200
        yield app, client, ids[0], ids[1], m15


def body(m15: Any, **over: Any) -> dict[str, Any]:
    start, end = period(m15)
    return {"symbols": ["EURUSD"], "start": start.isoformat(), "end": end.isoformat()} | over


def run_worker(app: FastAPI) -> None:
    ctx = app.state.ctx
    service = BacktestService(ctx.db, ctx.clock, JobQueue(ctx.db, ctx.clock))  # config.yaml (patched)
    worker = Worker(ctx.db, ctx.clock, handlers=backtest_handlers(service), tasks=[], worker_id="w1")
    while worker.step():
        pass


def test_create_run_read_and_compare(rig: Rig) -> None:
    app, client, mine, _, m15 = rig
    assert client.get("/api/v1/backtests/presets").json()["presets"] == [
        "standard",
        "conservative",
        "high_costs",
    ]
    url = f"/api/v1/engines/{mine}/backtests"
    a = client.post(url, json=body(m15), headers=mutation_headers(client))
    b = client.post(url, json=body(m15, preset="high_costs"), headers=mutation_headers(client))
    assert a.status_code == 202 and a.json()["status"] == "QUEUED"
    third = client.post(url, json=body(m15), headers=mutation_headers(client))
    assert third.status_code == 409 and third.json()["error"]["code"] == "backtest_limit"
    early = client.get(f"{url}/compare?ids={a.json()['run_id']},{b.json()['run_id']}")
    assert early.status_code == 409 and early.json()["error"]["code"] == "backtest_not_finished"
    run_worker(app)
    listed = client.get(url).json()["items"]
    assert [r["run_id"] for r in listed] == [b.json()["run_id"], a.json()["run_id"]]
    assert all(r["status"] == "DONE" and r["metrics"]["trades"] == 4 for r in listed)
    detail = client.get(f"{url}/{a.json()['run_id']}").json()
    assert detail["summary"]["provenance"]["code_version"] and detail["equity"]
    trades = client.get(f"{url}/{a.json()['run_id']}/trades?limit=3").json()
    assert len(trades["items"]) == 3 and trades["total"] == 4
    compared = client.get(f"{url}/compare?ids={a.json()['run_id']},{b.json()['run_id']}").json()["runs"]
    assert [r["preset"] for r in compared] == ["standard", "high_costs"]
    assert compared[0]["metrics"]["net_profit"] != compared[1]["metrics"]["net_profit"]  # worse fills cost


def test_validation_and_ownership(rig: Rig) -> None:
    _, client, mine, theirs, m15 = rig
    url = f"/api/v1/engines/{mine}/backtests"
    bad = client.post(url, json=body(m15, strategies=["nope"]), headers=mutation_headers(client))
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_backtest"
    assert (
        client.post(url, json=body(m15, config={"x": 1}), headers=mutation_headers(client)).status_code == 422
    )
    assert client.post(url, json=body(m15)).status_code == 403  # CSRF
    run = client.post(url, json=body(m15), headers=mutation_headers(client)).json()
    for resp in (
        client.post(f"/api/v1/engines/{theirs}/backtests", json=body(m15), headers=mutation_headers(client)),
        client.get(f"/api/v1/engines/{theirs}/backtests"),
        client.get(f"/api/v1/engines/{theirs}/backtests/{run['run_id']}"),
    ):
        assert resp.status_code == 404 and resp.json()["error"]["code"] == "engine_not_found"
    missing = client.get(f"{url}/nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "backtest_not_found"
    assert client.get(f"{url}/compare?ids={run['run_id']}").json()["error"]["code"] == "invalid_query"
