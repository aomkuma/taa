"""Analytics and recommendations over the API: scopes, validation, ownership (TAA-1005)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.web.conftest import mutation_headers
from tests.web.test_backtests_api import Rig, body, run_worker
from tests.web.test_backtests_api import rig as backtest_rig  # noqa: F401  (fixture)
from tests.web.test_data_api import rig  # noqa: F401  (fixture)


def test_paper_and_shadow_reports(rig: tuple[TestClient, str, str]) -> None:  # noqa: F811
    client, mine, theirs = rig
    paper = client.get(f"/api/v1/engines/{mine}/analytics?days=366")
    assert paper.status_code == 200
    doc = paper.json()
    assert doc["scope"] == "PAPER" and doc["kpis"]["trades"] + doc["skipped"] >= 1
    assert {"kpis", "curve", "r_histogram", "by_style", "mae_mfe", "attribution"} <= set(doc)
    shadow = client.get(f"/api/v1/engines/{mine}/analytics?scope=SHADOW&variant=MANAGED&days=366")
    assert shadow.status_code == 200 and shadow.json()["scope"] == "SHADOW"
    recs = client.get(f"/api/v1/engines/{mine}/recommendations?days=366").json()
    assert recs["scope"] == "PAPER" and isinstance(recs["items"], list) and recs["after_stop_bars"] == 20
    assert client.get(f"/api/v1/engines/{theirs}/analytics").status_code == 404


def test_the_bots_broker_trades_are_a_scope_of_their_own(rig: tuple[TestClient, str, str]) -> None:  # noqa: F811
    client, mine, _ = rig
    demo = client.get(f"/api/v1/engines/{mine}/analytics?scope=DEMO&days=366").json()
    assert demo["scope"] == "DEMO" and demo["kpis"]["trades"] == 1  # the sample broker trade
    assert demo["mae_mfe"] == []  # MT5 records no excursions
    recs = client.get(f"/api/v1/engines/{mine}/recommendations?scope=DEMO&days=366").json()
    assert recs["trades"] == 1 and recs["hypothetical"] is False  # real fills on the demo account
    live = client.get(f"/api/v1/engines/{mine}/analytics?scope=LIVE&days=366").json()
    assert live["kpis"]["trades"] == 0


def test_invalid_queries(rig: tuple[TestClient, str, str]) -> None:  # noqa: F811
    client, mine, _ = rig
    for query in ("scope=OTHER", "scope=BACKTEST", "variant=OTHER", "days=0", "days=400"):
        resp = client.get(f"/api/v1/engines/{mine}/analytics?{query}")
        assert resp.status_code in (400, 422), query
    missing = client.get(f"/api/v1/engines/{mine}/analytics?scope=BACKTEST&run=nope")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "backtest_not_found"


def test_a_backtest_run_and_its_recommendations(backtest_rig: Rig) -> None:  # noqa: F811
    app, client, mine, theirs, m15 = backtest_rig
    run = client.post(f"/api/v1/engines/{mine}/backtests", json=body(m15), headers=mutation_headers(client))
    run_id = run.json()["run_id"]
    pending = client.get(f"/api/v1/engines/{mine}/analytics?scope=BACKTEST&run={run_id}")
    assert pending.status_code == 400  # not finished yet
    run_worker(app)
    report = client.get(f"/api/v1/engines/{mine}/analytics?scope=BACKTEST&run={run_id}").json()
    assert report["kpis"]["trades"] == 4 and report["hypothetical"] is True
    assert sum(b["count"] for b in report["r_histogram"]) == report["kpis"]["rated"]
    recs = client.get(f"/api/v1/engines/{mine}/recommendations?scope=BACKTEST&run={run_id}")
    assert recs.status_code == 200 and recs.json()["trades"] == 4
    assert client.get(f"/api/v1/engines/{theirs}/analytics?scope=BACKTEST&run={run_id}").status_code == 404
