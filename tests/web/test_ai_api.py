"""AI assessments over the API: summary, agreement against outcomes, ownership (TAA-1304)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.storage.database import Database
from app.storage.models import ShadowTradeRow
from tests.web.test_data_api import rig  # noqa: F401  (fixture)


def test_assessments_with_agreement_and_cost(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
) -> None:
    client, mine, theirs = rig
    doc = client.get(f"/api/v1/engines/{mine}/ai-assessments?days=366").json()
    s = doc["summary"]
    assert (s["calls"], s["answered"], s["agree"], s["passed"]) == (1, 1, 1, 1)
    assert s["cost_usd"] == 0.0108 and s["models"] == ["claude-opus-5-5"] and s["agreement_rate"] == 1.0
    [item] = doc["items"]
    assert item["verdict"] == "AGREE" and item["reasons"] == ["H1 trend agrees"]
    with db.session() as sess:  # the signal's shadow trade closes as a loss: the AI agreed and was wrong
        shadow = sess.get(ShadowTradeRow, (mine, "k1:PLAN"))
        assert shadow is not None
        shadow.status, shadow.win, shadow.r_multiple = "CLOSED", False, -1.0
    s = client.get(f"/api/v1/engines/{mine}/ai-assessments?days=366").json()["summary"]
    assert (s["with_outcome"], s["right_rate"], s["win_rate_when_agree"]) == (1, 0.0, 0.0)
    assert client.get(f"/api/v1/engines/{theirs}/ai-assessments").status_code == 404
    assert client.get(f"/api/v1/engines/{mine}/ai-assessments?days=0").status_code == 422
