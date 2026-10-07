"""Manual trades and their signals in the cloud (PLAN §A34; TAA-1006): read, candidates, the owner's correction."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.storage.database import Database
from app.storage.models import AuditEvent, BrokerTradeRow, ManualTradeLinkRow, OrderIntentRow
from tests.sync_data import sample_rows
from tests.web.conftest import mutation_headers
from tests.web.test_data_api import rig  # noqa: F401  (fixture)

POSITION = 2078278005  # tests/sync_data: a manual EURUSD BUY at 1.1002 linked HIGH to opportunity k1


def path(engine: str, rest: str = "") -> str:
    return f"/api/v1/engines/{engine}/manual-trades{rest}"


def put_link(client: TestClient, engine: str, body: dict[str, Any]) -> Any:
    return client.put(path(engine, f"/{POSITION}/link"), json=body, headers=mutation_headers(client))


def test_lists_the_engines_link_and_closed_comparison(
    rig: tuple[TestClient, str, str],  # noqa: F811
) -> None:
    client, mine, theirs = rig
    [item] = client.get(path(mine)).json()["items"]
    assert item["position_id"] == POSITION and item["status"] == "OPEN"
    assert item["effective"] == {
        "source": "AUTO",
        "followed": True,
        "confidence": "HIGH",
        "signal_key": "k1",
        "strategy": "example_trend_pullback",
        "decision_id": "d1",
        "opportunity_id": "k1",
    }
    assert set(item["compare"]) == {"signal_r", "signal_status", "bot_r", "bot_status", "bot_source"}
    assert client.get(path(mine) + "?status=CLOSED").json()["items"] == []
    assert client.get(path(mine) + "?status=MAYBE").status_code == 400
    assert client.get(path(theirs)).status_code == 404  # another user's engine


def test_the_owner_corrects_a_link_and_it_is_audited(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
) -> None:
    client, mine, _ = rig
    [option] = client.get(path(mine, f"/{POSITION}/candidates")).json()["items"]
    assert option["signal_key"] == "k1" and option["qualifies"] is True

    own = put_link(client, mine, {"choice": "OWN_IDEA"})
    assert own.status_code == 200
    assert own.json()["effective"]["followed"] is False and own.json()["effective"]["source"] == "OWNER"
    picked = put_link(client, mine, {"choice": "SIGNAL", "signal_key": "k1"}).json()["effective"]
    assert picked["confidence"] == "OWNER" and picked["opportunity_id"] == "k1"
    assert put_link(client, mine, {"choice": "SIGNAL", "signal_key": "nope"}).status_code == 400
    assert put_link(client, mine, {"choice": "MAYBE"}).status_code == 400
    assert (
        client.put(path(mine, f"/{POSITION}/link"), json={"choice": "OWN_IDEA"}).status_code == 403
    )  # no CSRF

    cleared = client.delete(path(mine, f"/{POSITION}/link"), headers=mutation_headers(client))
    assert cleared.json()["effective"]["source"] == "AUTO"
    with db.session() as sess:
        kinds = [
            e.event_type for e in sess.scalars(select(AuditEvent)) if e.event_type.startswith("manual_trade")
        ]
        link = sess.get(ManualTradeLinkRow, (mine, POSITION))
    assert kinds == ["manual_trade.link", "manual_trade.link", "manual_trade.link_cleared"]
    assert link is not None and link.confidence == "HIGH"  # the engine's own match is never rewritten


def test_unknown_trades_are_not_found(rig: tuple[TestClient, str, str]) -> None:  # noqa: F811
    client, mine, _ = rig
    assert client.get(path(mine, "/1/candidates")).status_code == 404
    assert put_link(client, mine, {"choice": "OWN_IDEA"}).status_code == 200
    resp = client.put(path(mine, "/1/link"), json={"choice": "OWN_IDEA"}, headers=mutation_headers(client))
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "manual_trade_not_found"


def test_a_closed_trade_compares_signal_bot_and_me(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
) -> None:
    client, mine, _ = rig
    with db.session() as sess:
        link = sess.get(ManualTradeLinkRow, (mine, POSITION))
        assert link is not None
        link.status, link.r_multiple, link.net_profit = "CLOSED", 1.25, 62.5
    [item] = client.get(path(mine) + "?status=CLOSED").json()["items"]
    assert item["r_multiple"] == 1.25 and item["net_profit"] == 62.5
    compare = item["compare"]  # the sample shadow trade of k1 (PLAN) and the bot's paper position of d1
    assert compare["signal_status"] is not None and compare["bot_status"] is not None


def test_the_bot_result_is_its_broker_trade_when_the_decision_filled_there(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
) -> None:
    client, mine, _ = rig

    def compare() -> dict[str, Any]:
        [item] = client.get(path(mine)).json()["items"]
        return {k: v for k, v in item["compare"].items() if k.startswith("bot")}

    # decision d1 filled on the broker account as position 3 (the sample intent), still open there
    assert compare() == {"bot_r": None, "bot_status": "OPEN", "bot_source": "DEMO"}
    with db.session() as sess:
        trade = next(r for r in sample_rows() if isinstance(r, BrokerTradeRow))
        trade.engine_id, trade.position_ticket, trade.r_multiple = mine, 3, -1.0
        sess.add(trade)
    assert compare() == {"bot_r": -1.0, "bot_status": "CLOSED", "bot_source": "DEMO"}
    with db.session() as sess:  # no broker fill for d1: the paper position answers, as before
        sess.query(OrderIntentRow).filter(OrderIntentRow.engine_id == mine).delete()
    assert compare()["bot_source"] == "PAPER"
