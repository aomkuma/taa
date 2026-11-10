"""The pieces the zone runner stands on (eye/ZONE_LIVE.md L1, L3, L8, L9): the order modify, FakeMT5's pending-order
history, the reserved magic, the ``zone_live`` settings and the store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.broker import mt5_constants as c
from app.broker.execution import ExecutionGateway, RequestBuilder
from app.broker.factory import build_trading
from app.config import REPO_ROOT, AppConfig, ZoneLiveConfig
from app.core.clock import ManualClock
from app.core.enums import Side
from app.engine.magic_registry import MagicRegistry
from app.storage.database import Database
from app.zone.store import ZoneStore
from tests.unit.test_execution_gateway import settings

MON = datetime(2025, 1, 6, 10, 0, tzinfo=UTC)


def broker() -> tuple[object, ExecutionGateway, ManualClock]:
    clock = ManualClock(MON)
    bundle = build_trading(settings(), fake=True, clock=clock)
    bundle.client.connect()
    assert bundle.fake is not None
    bundle.fake.price_override["XAUUSD"] = 103.0
    return bundle, ExecutionGateway(bundle.client), clock


def limit(bundle: object, price: float, comment: str, minutes: int = 61) -> dict[str, object]:
    spec = bundle.gateway.symbol_spec("XAUUSD")  # type: ignore[attr-defined]
    exp = bundle.gateway.server_clock.utc_to_server_epoch(MON + timedelta(minutes=minutes))  # type: ignore[attr-defined]
    return RequestBuilder(50).limit_entry(
        spec,
        Side.BUY,
        0.01,
        price,
        95.0,
        110.0,
        magic=7_310_100,
        comment=comment,
        filling=c.ORDER_FILLING_RETURN,
        expiration_server=exp,
    )


def test_a_limit_order_carries_a_specified_expiry_and_modify_changes_only_that() -> None:
    bundle, exe, _clock = broker()
    res = exe.send(limit(bundle, 101.32, "Z1-P1-0"))
    assert res.ok
    [order] = bundle.gateway.orders("XAUUSD")  # type: ignore[attr-defined]
    assert order.expiration_utc == MON + timedelta(minutes=61)
    spec = bundle.gateway.symbol_spec("XAUUSD")  # type: ignore[attr-defined]
    assert spec.expiration_mode & c.SYMBOL_EXPIRATION_SPECIFIED
    new = bundle.gateway.server_clock.utc_to_server_epoch(MON + timedelta(minutes=121))  # type: ignore[attr-defined]
    req = RequestBuilder(50).modify_order(spec, order, expiration_server=new)
    assert req["action"] == c.TRADE_ACTION_MODIFY
    assert (req["price"], req["sl"], req["tp"], req["type_time"], req["expiration"]) == (
        101.32,
        95.0,
        110.0,
        c.ORDER_TIME_SPECIFIED,
        new,
    )
    assert exe.send(req).ok
    [order] = bundle.gateway.orders("XAUUSD")  # type: ignore[attr-defined]
    assert order.expiration_utc == MON + timedelta(minutes=121) and order.price_open == 101.32


def test_modify_is_refused_for_a_gone_order_or_a_past_expiry() -> None:
    bundle, exe, clock = broker()
    spec = bundle.gateway.symbol_spec("XAUUSD")  # type: ignore[attr-defined]
    assert exe.send(limit(bundle, 101.32, "Z1-P1-0")).ok
    [order] = bundle.gateway.orders("XAUUSD")  # type: ignore[attr-defined]
    past = bundle.gateway.server_clock.utc_to_server_epoch(MON - timedelta(minutes=1))  # type: ignore[attr-defined]
    assert not exe.send(RequestBuilder(50).modify_order(spec, order, expiration_server=past)).ok
    assert exe.send(RequestBuilder.remove_order(order.ticket)).ok
    again = RequestBuilder(50).modify_order(spec, order, expiration_server=past + 7200)
    assert not exe.send(again).ok
    del clock


def test_the_history_tells_what_became_of_an_order() -> None:
    bundle, exe, clock = broker()
    gw = bundle.gateway  # type: ignore[attr-defined]
    for price, comment in ((101.32, "Z1-P1-0"), (98.03, "Z1-P2-0"), (97.0, "Z1-P2-1")):
        assert exe.send(limit(bundle, price, comment, minutes=30)).ok
    assert [o.comment for o in gw.orders_by_comment("Z1-P2")] == ["Z1-P2-0", "Z1-P2-1"]
    first = next(o for o in gw.orders() if o.comment == "Z1-P2-0")
    assert exe.send(RequestBuilder.remove_order(first.ticket)).ok  # cancelled
    bundle.fake.price_override["XAUUSD"] = 101.0  # Z1-P1-0 fills
    clock.advance(1)
    gw.positions()
    clock.advance(31 * 60)  # Z1-P2-1 expires
    gw.orders()
    states = {
        h.comment: h.state for h in gw.history_orders(MON - timedelta(hours=1), MON + timedelta(hours=2))
    }
    assert states == {
        "Z1-P2-0": c.ORDER_STATE_CANCELED,
        "Z1-P1-0": c.ORDER_STATE_FILLED,
        "Z1-P2-1": c.ORDER_STATE_EXPIRED,
    }
    deal = [
        d for d in gw.deals(MON - timedelta(hours=1), MON + timedelta(hours=2)) if d.entry == c.DEAL_ENTRY_IN
    ]
    assert [d.comment for d in deal] == ["Z1-P1-0"]


def test_the_zone_runner_has_one_stable_magic_of_its_own() -> None:
    db = Database("sqlite://")
    db.create_all()
    reg = MagicRegistry(db, 7_310_000, ManualClock(MON))
    reg.ensure(["a", "b"])  # the engine's default bot
    magic = reg.zone_magic()
    assert magic == reg.zone_magic() and magic not in {7_310_000, 7_310_001}
    assert 7_310_000 <= magic < 7_320_000
    assert reg.all()[magic] == ("zone", "run_zone")
    db.dispose()


def test_zone_live_settings_are_validated_and_config_yaml_has_them() -> None:
    cfg = ZoneLiveConfig()
    assert (cfg.lot, cfg.cycle_seconds, cfg.stale_quote_seconds, cfg.preclose_seconds) == (
        0.01,
        2.0,
        30.0,
        15.0,
    )
    assert cfg.epoch.isoformat() == "2023-10-01"
    raw = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(encoding="utf-8"))
    assert AppConfig.model_validate(raw).zone_live == cfg
    with pytest.raises(ValidationError):
        ZoneLiveConfig.model_validate({"lott": 0.01})  # unknown fields are refused
    with pytest.raises(ValidationError):
        ZoneLiveConfig(lot=0)
    with pytest.raises(ValidationError):
        ZoneLiveConfig(cycle_seconds=40, stale_quote_seconds=30)
    with pytest.raises(ValidationError):
        ZoneLiveConfig(preclose_seconds=400)
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"zone_live": {"nope": 1}})


def test_the_store_round_trips_and_the_comment_is_unique(tmp_path: Path) -> None:
    db = Database(f"sqlite:///{(tmp_path / 'e.db').as_posix()}")
    db.create_all()
    now = MON
    store = ZoneStore(db, 1, "S")
    other = ZoneStore(db, 2, "S")
    fields = dict(
        market="XAUUSD",
        zone_set="default",
        set_version=1,
        hour_open=MON,
        side="BUY",
        line=100.0,
        step=10.0,
        p1=101.3,
        p2=98.0,
        sl=95.0,
        tp=110.0,
        p1_sent=101.32,
        p2_sent=98.03,
        sl_sent=95.0,
        tp_sent=110.0,
        state="live",
        chosen=False,
    )
    sid = store.add_setup(now, **fields)
    store.update_setup(sid, now, chosen=True)
    assert store.setup(sid).chosen and store.setups(states=("live",))[0].id == sid  # type: ignore[union-attr]
    assert other.setups() == [] and len(other.setups(all_accounts=True)) == 1
    rid = store.add_request(now, setup_id=sid, kind="place", name="P1", comment="Z1-P1-0")
    assert store.count_places(sid, "P1") == 1
    with pytest.raises(IntegrityError):
        store.add_request(now, setup_id=sid, kind="place", name="P1", comment="Z1-P1-0")
    store.update_request(rid, state="sent", order_ticket=5)
    assert store.request_by_comment("Z1-P1-0").state == "sent"  # type: ignore[union-attr]
    stop = store.request_stop(now, "me", now_flag=True)
    assert store.pending_stop().id == stop  # type: ignore[union-attr]
    store.acknowledge_stop(stop, now, "ok")
    assert store.pending_stop() is None
    store.set_state("status", "{}", now)
    assert store.get_state("status") == "{}"
    db.dispose()


def test_a_set_can_be_read_at_an_earlier_version(tmp_path: Path) -> None:
    from app.zone.params import load_params, load_params_at, seed, set_values

    db = tmp_path / "bot_config.db"
    v1 = seed(db, "XAUUSD", "default", "t", MON)
    v2 = set_values(db, "XAUUSD", "default", "t", MON, "why", {"away_frac": "0.6", "be_mode": "off"})
    assert v2 > v1
    old, new = load_params_at(db, "XAUUSD", "default", v1), load_params_at(db, "XAUUSD", "default", v2)
    assert (old.away_frac, old.be_mode) == (0.5, "entry") and (new.away_frac, new.be_mode) == (0.6, "off")
    assert load_params(db, "XAUUSD", "default") == (new, v2)  # the existing reader is unchanged
