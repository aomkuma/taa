"""AI notes on advisory in the cloud API (TAA-1305, TAA-1304): read, gated by the AI_NARRATIVES feature."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.clock import ManualClock
from app.storage.database import Database
from app.storage.models import EntitlementOverrideRow, UserRow
from tests.web.test_data_api import rig  # noqa: F401  (fixture)


def test_notes_with_accuracy_and_the_opportunitys_opinion(rig: tuple[TestClient, str, str]) -> None:  # noqa: F811
    client, mine, _ = rig
    doc = client.get(f"/api/v1/engines/{mine}/ai-notes?kind=OPPORTUNITY&days=366").json()
    assert doc["kind"] == "OPPORTUNITY" and [i["subject"] for i in doc["items"]] == ["k1"]
    assert doc["items"][0]["text_th"] and doc["stats"]["simulated"] is True
    assert doc["filter"]["offered"] is False  # far too few judged opinions
    detail = client.get(f"/api/v1/engines/{mine}/opportunities/k1").json()
    assert detail["ai"]["verdict"] == "AGREE" and detail["ai"]["confidence"] == 66
    ranking = client.get(f"/api/v1/engines/{mine}/ai-notes?kind=RANKING").json()
    assert ranking["items"] == [] and ranking["stats"] is None
    assert client.get(f"/api/v1/engines/{mine}/ai-notes?kind=NOPENOPE").status_code == 400


def test_a_plan_without_ai_gets_neither(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
    clock: ManualClock,
) -> None:
    client, mine, _ = rig
    with db.session() as sess:
        alice = sess.scalars(select(UserRow).where(UserRow.username == "alice")).one()
        sess.add(
            EntitlementOverrideRow(
                user_id=alice.id, key="AI_NARRATIVES", value=False, created_at=clock.now_utc()
            )
        )
    resp = client.get(f"/api/v1/engines/{mine}/ai-notes")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "plan_feature"
    assert client.get(f"/api/v1/engines/{mine}/opportunities/k1").json()["ai"] is None
