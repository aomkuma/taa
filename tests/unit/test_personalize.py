from __future__ import annotations

import dataclasses
import subprocess
import sys
from datetime import timedelta
from typing import Any

import numpy as np
import pytest

from app.advisory.confidence import Outcome, WinProbability, build_win_probability, signal_features
from app.advisory.personalize import (
    Badge,
    Entitlements,
    MarketOpportunity,
    NoAlert,
    SentAlert,
    UserContext,
    badge,
    personalize,
    replacement,
)
from app.advisory.preferences import (
    AdvisoryPreferences,
    AlertMetric,
    AlertPreferences,
    ConflictPolicy,
    ProfileOverrides,
    TheoryPreferences,
    TradingProfile,
    UserWindow,
    Watchlist,
    WatchlistKind,
)
from app.config import ConfluenceConfig
from app.evidence.framework import Direction, EvidenceSnapshot, Family
from app.storage.models import OpportunityRow
from app.strategy.enrichment import enrich
from app.strategy.signal_models import StrategyContext
from tests.unit.test_strategy_confluence import item
from tests.unit.test_strategy_models import BAR, make_context, make_signal

CFG = ConfluenceConfig()
NOW = BAR + timedelta(minutes=1)
FIB = "ev:FIBONACCI:fib.retracement"
TREND = "ev:TREND:trend.ma_alignment"
RSI = "ev:MOMENTUM:momentum.rsi_divergence"


def opportunity(**kw: Any) -> MarketOpportunity:
    items = (
        item("fib.retracement", Family.FIBONACCI),
        item("trend.ma_alignment", Family.TREND),
        item("momentum.rsi_divergence", Family.MOMENTUM, Direction.BEAR, quality=0.8),
    )
    snap = EvidenceSnapshot("EURUSD", items[0].evidence.timeframe, BAR, items, (), "digest")
    market = make_context()
    signal = enrich(
        make_signal(evidence=()), StrategyContext(market, {}, BAR, None, {snap.timeframe: snap}), CFG
    )
    base: dict[str, Any] = {
        "opportunity_id": signal.idempotency_key,
        "strategy": signal.strategy,
        "symbol": "EURUSD",
        "asset_class": "FOREX_MAJOR",
        "side": "BUY",
        "entry": 1.1,
        "stop_loss": 1.098,
        "take_profit": 1.104,
        "rr": 2.0,
        "signal": signal,
        "features": signal_features(signal, market) | {"ctx:htf_aligned": 1.0},
        "created_at": BAR,
        "valid_until": BAR + timedelta(minutes=30),
        "valid_reason": "SIGNAL_LIFETIME",
        "status": "CANDIDATE",
        "lot": 0.25,
        "risk_money": 50.0,
        "reward_money": 100.0,
        "currency": "USD",
        "equity": 10_000.0,
    }
    return MarketOpportunity(**(base | kw))


def outcomes(n: int, informative: bool = True, seed: int = 0) -> list[Outcome]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        feats = {
            FIB: float(rng.random() < 0.5),
            TREND: float(rng.random() < 0.5),
            RSI: -float(rng.random() < 0.3),
        }
        z = 0.2 + (1.0 * feats[FIB] + 0.8 * feats[TREND] + 0.9 * feats[RSI] if informative else 0.0)
        win = bool(rng.random() < 1 / (1 + np.exp(-z)))
        rows.append(
            Outcome("example_trend_pullback", "EURUSD", "FOREX_MAJOR", 60.0, 2.0, win, features=feats,
                    at=BAR - timedelta(hours=n - i))
        )  # fmt: skip
    return rows


@pytest.fixture(scope="module")
def model() -> WinProbability:
    wp = build_win_probability(outcomes(4000), min_group=50)
    assert wp.uses_evidence
    return wp


def prefs(**kw: Any) -> AdvisoryPreferences:
    base: dict[str, Any] = {
        "watchlists": [
            Watchlist(name="Favourites", kind=WatchlistKind.FAVOURITES, symbols=["EURUSD"]),
            Watchlist(name="Top 30", kind=WatchlistKind.AUTO_TOP_N),
        ]
    }
    return AdvisoryPreferences(**(base | kw))


def run(
    model: WinProbability, user: UserContext | None = None, opp: MarketOpportunity | None = None, **kw: Any
):  # type: ignore[no-untyped-def]
    return personalize(
        opp or opportunity(),
        user or UserContext(prefs()),
        model,
        CFG,
        now=kw.get("now", NOW),
        market_open=kw.get("market_open", True),
    )


class TestDecision:
    def test_owner_is_alerted_with_a_thai_push(self, model: WinProbability) -> None:
        r = run(model, UserContext(prefs(), active_alerts=2))
        assert r.alert, r.reasons
        assert r.watchlist == "Favourites" and r.supporting_families == ("FIBONACCI", "TREND")
        assert r.metric is AlertMetric.WIN_PROBABILITY and r.metric_value is not None and r.metric_value >= 55
        assert r.badge is Badge.ACTIVE and r.valid_until == BAR + timedelta(minutes=30)
        p = r.payload
        assert p is not None and p["tag"] == r.opportunity_id and p["badge"] == 3 and not p["silent"]
        assert p["title"] == "EURUSD ซื้อ"
        assert "เหตุผล: ฟีโบนัชชี +" in p["body"] and "ล็อต 0.25" in p["body"]
        assert "ใช้ได้ถึง 17:45 (เวลาไทย)" in p["body"]  # 10:45 UTC

    def test_english_and_non_owner_payload(self, model: WinProbability) -> None:
        user = UserContext(prefs(alerts=AlertPreferences(language="en")), is_owner=False)
        p = run(model, user).payload
        assert p is not None and p["title"] == "EURUSD BUY" and "Reasons: Fibonacci +" in p["body"]
        assert "Lot" not in p["body"]  # other users get sizing from their own account profile (8A)

    def test_threshold_override_and_insufficient_data(self, model: WinProbability) -> None:
        strict = prefs(
            watchlists=[
                Watchlist(name="Fav", kind=WatchlistKind.FAVOURITES, symbols=["EURUSD"], threshold=95)
            ]
        )
        assert NoAlert.BELOW_THRESHOLD in run(model, UserContext(strict)).reasons
        empty = build_win_probability([])
        r = run(empty)
        assert NoAlert.INSUFFICIENT_DATA in r.reasons and r.metric_value is None

    def test_setup_strength_metric(self, model: WinProbability) -> None:
        user = UserContext(prefs(alerts=AlertPreferences(metric=AlertMetric.SETUP_STRENGTH, threshold=30)))
        r = run(model, user)
        assert r.alert and r.metric_value == pytest.approx(r.setup_strength) and r.threshold == 30

    def test_theory_subset(self, model: WinProbability) -> None:
        full = run(model)
        only_fib = UserContext(prefs(theories=TheoryPreferences(preset=None, families={"FIBONACCI": True})))
        r = run(model, only_fib)
        assert r.setup_strength < full.setup_strength
        assert r.supporting_families == ("FIBONACCI",) and NoAlert.FEW_SUPPORTING_FAMILIES in r.reasons
        contributions = r.explanation.contributions
        assert contributions is not None and [c.feature for c in contributions] == [FIB]

    def test_entitlements(self, model: WinProbability) -> None:
        crypto_only = UserContext(prefs(), entitlements=Entitlements(asset_classes=frozenset({"CRYPTO"})))
        assert NoAlert.ENTITLEMENT_ASSET_CLASS in run(model, crypto_only).reasons
        no_trend = UserContext(prefs(), entitlements=Entitlements(families=frozenset({Family.FIBONACCI})))
        assert run(model, no_trend).supporting_families == ("FIBONACCI",)
        capped = UserContext(
            prefs(),
            entitlements=Entitlements(alerts_per_day=1),
            sent=[SentAlert("other", "GBPUSD", NOW - timedelta(hours=3))],
        )
        assert NoAlert.DAILY_LIMIT in run(model, capped).reasons

    def test_watchlists(self, model: WinProbability) -> None:
        unwatched = UserContext(prefs(watchlists=[Watchlist(name="Swing", symbols=["XAUUSD"])]))
        assert NoAlert.NOT_WATCHED in run(model, unwatched).reasons
        muted = UserContext(prefs(watchlists=[Watchlist(name="Swing", symbols=["EURUSD"], alerts=False)]))
        assert NoAlert.LIST_ALERTS_OFF in run(model, muted).reasons
        auto = prefs(watchlists=[Watchlist(name="Top", kind=WatchlistKind.AUTO_TOP_N, top_n=2)])
        assert run(model, UserContext(auto, ranked_top=["XAUUSD", "EURUSD"])).alert
        assert (
            NoAlert.NOT_WATCHED
            in run(model, UserContext(auto, ranked_top=["XAUUSD", "GBPUSD", "EURUSD"])).reasons
        )

    def test_conflict_policies(self, model: WinProbability) -> None:
        def with_policy(policy: ConflictPolicy) -> Any:
            profile = TradingProfile(overrides=ProfileOverrides(conflict_policy=policy))
            return run(model, UserContext(prefs(trading_profile=profile)))

        block, penalize, ignore = (
            with_policy(p) for p in (ConflictPolicy.BLOCK, ConflictPolicy.PENALIZE, ConflictPolicy.IGNORE)
        )
        assert NoAlert.STRONG_CONFLICT in block.reasons
        assert NoAlert.STRONG_CONFLICT not in penalize.reasons
        assert ignore.setup_strength > penalize.setup_strength

    def test_profile_limits(self, model: WinProbability) -> None:
        defensive = UserContext(prefs(trading_profile=TradingProfile(style=0)))  # min RR 2.5
        assert NoAlert.RR_BELOW_PROFILE in run(model, defensive).reasons
        misaligned = opportunity(features=opportunity().features | {"ctx:htf_aligned": 0.0})
        assert NoAlert.HTF_NOT_ALIGNED in run(model, opp=misaligned).reasons
        pattern_off = UserContext(
            prefs(theories=TheoryPreferences(pattern_strategies={"example_trend_pullback": False})),
            pattern_strategies={"example_trend_pullback"},
        )
        assert NoAlert.PATTERN_STRATEGY_OFF in run(model, pattern_off).reasons

    def test_pattern_toggle_only_applies_to_pattern_strategies(self, model: WinProbability) -> None:
        user = UserContext(
            prefs(theories=TheoryPreferences(pattern_strategies={"example_trend_pullback": False}))
        )
        assert NoAlert.PATTERN_STRATEGY_OFF not in run(model, user).reasons


class TestWindows:
    def test_market_and_user_windows(self, model: WinProbability) -> None:
        assert NoAlert.MARKET_CLOSED in run(model, market_open=False).reasons
        ignore_sessions = UserContext(prefs(alerts=AlertPreferences(respect_market_sessions=False)))
        assert run(model, ignore_sessions, market_open=False).alert
        night = UserContext(prefs(alerts=AlertPreferences(windows=[UserWindow(start="20:00", end="23:00")])))
        assert NoAlert.OUTSIDE_USER_WINDOW in run(model, night).reasons  # 17:16 in Bangkok
        short = UserContext(prefs(alerts=AlertPreferences(windows=[UserWindow(start="17:00", end="17:30")])))
        r = run(model, short)
        assert r.alert and r.window_reason == "USER_WINDOW" and r.valid_until == BAR + timedelta(minutes=15)

    def test_passed_windows_and_badges(self, model: WinProbability) -> None:
        assert NoAlert.WINDOW_PASSED in run(model, opp=opportunity(status="EXPIRED")).reasons
        late = run(model, now=BAR + timedelta(minutes=27))
        assert late.badge is Badge.EXPIRING
        start, end = BAR, BAR + timedelta(minutes=30)
        assert badge("CANDIDATE", start, end, BAR + timedelta(minutes=5)) is Badge.ACTIVE
        assert badge("ACTIVE", start, end, end) is Badge.EXPIRED
        assert badge("INVALIDATED", start, end, BAR) is Badge.INVALIDATED
        assert badge("FOLLOWED", start, end, BAR) is Badge.FOLLOWED


class TestRateLimits:
    def test_duplicates_cooldown_and_hourly(self, model: WinProbability) -> None:
        opp = opportunity()
        dup = UserContext(prefs(), sent=[SentAlert(opp.opportunity_id, "EURUSD", NOW - timedelta(hours=2))])
        assert NoAlert.DUPLICATE in run(model, dup).reasons
        cool = UserContext(prefs(), sent=[SentAlert("x", "EURUSD", NOW - timedelta(minutes=10))])
        assert NoAlert.SYMBOL_COOLDOWN in run(model, cool).reasons
        busy = UserContext(
            prefs(), sent=[SentAlert(f"x{i}", f"S{i}", NOW - timedelta(minutes=5 * i)) for i in range(6)]
        )
        assert NoAlert.HOURLY_LIMIT in run(model, busy).reasons


class TestReplacement:
    def test_silent_same_tag_update(self) -> None:
        opp = opportunity()
        user = UserContext(prefs(), active_alerts=3)
        p = replacement(opp, user, status="EXPIRED", reason="SESSION_END:LONDON")
        assert p is not None and p["tag"] == opp.opportunity_id and p["silent"] and not p["renotify"]
        assert p["body"] == "หมดเวลาที่เหมาะสมแล้ว: ช่วงตลาดปิด" and p["badge"] == 2
        en = UserContext(prefs(alerts=AlertPreferences(language="en")))
        p = replacement(opp, en, status="INVALIDATED", reason="PRICE_DRIFT")
        assert p is not None and p["body"] == "conditions no longer hold: price moved away from the entry"
        off = UserContext(prefs(alerts=AlertPreferences(expiry_updates=False)))
        assert replacement(opp, off, status="EXPIRED", reason="SIGNAL_LIFETIME") is None


def test_from_row_round_trip(model: WinProbability) -> None:
    opp = opportunity()
    row = OpportunityRow(
        **{
            f.name: getattr(opp, f.name)
            for f in dataclasses.fields(opp)
            if f.name not in ("signal", "cost_r")
        },
        signal=opp.signal.to_dict(),
    )
    assert MarketOpportunity.from_row(row) == opp
    assert run(model, opp=MarketOpportunity.from_row(row)).alert


def test_the_cloud_can_import_it_without_broker_code() -> None:
    code = (
        "import sys, app.advisory.personalize; "
        "bad = [m for m in sys.modules if m.startswith(('app.broker.gateway', 'app.broker.mt5_client', "
        "'app.broker.factory', 'app.broker.fake_mt5', 'MetaTrader5'))]; print(bad)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)  # noqa: S603
    assert out.stdout.strip() == "[]"
