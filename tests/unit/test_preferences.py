from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.advisory.confidence import break_even_probability, expected_value_r
from app.advisory.preferences import (
    PRESETS,
    AdvisoryPreferences,
    AlertMetric,
    AlertPreferences,
    ConflictPolicy,
    EntryPlanPreferences,
    ProfileOverrides,
    TheoryPreferences,
    TradingProfile,
    UserWindow,
    Watchlist,
    WatchlistKind,
    local_preferences,
    parse_preferences,
    required_win_probability,
    symbols_union,
    validate_against_catalogs,
)
from app.config import CEILING_RISK_PER_TRADE_PCT, load_settings
from app.core.enums import Timeframe
from app.core.errors import ConfigError
from app.evidence.catalog import default_registry as evidence_registry
from app.evidence.framework import Family
from app.risk.position_sizer import SplitMode
from app.strategy.catalog import default_registry as strategy_registry
from tests.unit.test_market_data import ENV

EVIDENCE = evidence_registry()
STRATEGIES = strategy_registry()


class TestWatchlists:
    def test_defaults(self) -> None:
        prefs = AdvisoryPreferences()
        kinds = [w.kind for w in prefs.watchlists]
        assert kinds == [WatchlistKind.FAVOURITES, WatchlistKind.AUTO_TOP_N]
        assert prefs.watchlists[1].size == 30 and prefs.watchlists[0].size is None

    def test_rules(self) -> None:
        with pytest.raises(ValidationError, match="ranking"):
            Watchlist(name="auto", kind=WatchlistKind.AUTO_TOP_N, symbols=["EURUSD"])
        with pytest.raises(ValidationError, match="top_n"):
            Watchlist(name="mine", top_n=5)
        with pytest.raises(ValidationError, match="invalid symbol"):
            Watchlist(name="mine", symbols=["EUR USD"])
        assert Watchlist(name="mine", symbols=["EURUSD", "#GSK", "EURUSD"]).symbols == ["EURUSD", "#GSK"]
        assert Watchlist(name="auto", kind=WatchlistKind.AUTO_TOP_N, top_n=10).size == 10

    def test_list_set_rules(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            AdvisoryPreferences(watchlists=[Watchlist(name="Swing"), Watchlist(name="swing")])
        with pytest.raises(ValidationError, match="at most one FAVOURITES"):
            AdvisoryPreferences(
                watchlists=[
                    Watchlist(name="a", kind=WatchlistKind.FAVOURITES),
                    Watchlist(name="b", kind=WatchlistKind.FAVOURITES),
                ]
            )

    def test_listed_symbols_and_union(self) -> None:
        a = AdvisoryPreferences(
            watchlists=[
                Watchlist(name="Fav", kind=WatchlistKind.FAVOURITES, symbols=["XAUUSD", "EURUSD"]),
                Watchlist(name="Swing", symbols=["EURUSD", "US30"]),
            ]
        )
        b = AdvisoryPreferences(watchlists=[Watchlist(name="x", symbols=["BTCUSD", "US30"])])
        assert a.listed_symbols() == ["XAUUSD", "EURUSD", "US30"]
        assert symbols_union([a, b]) == ["XAUUSD", "EURUSD", "US30", "BTCUSD"]
        assert a.watchlist("swing") is a.watchlists[1]


class TestAlerts:
    def test_thresholds(self) -> None:
        assert AlertPreferences().effective_threshold() == 55.0
        assert AlertPreferences(metric=AlertMetric.SETUP_STRENGTH).effective_threshold() == 75.0
        alerts = AlertPreferences(threshold=60.0)
        assert alerts.effective_threshold(Watchlist(name="w")) == 60.0
        assert alerts.effective_threshold(Watchlist(name="w", threshold=70.0)) == 70.0

    def test_user_windows_in_the_user_timezone(self) -> None:
        evening = UserWindow(days=[0, 1, 2, 3, 4], start="18:00", end="01:00")  # Bangkok, spans midnight
        alerts = AlertPreferences(windows=[evening])
        wed_1930_bkk = datetime(2026, 9, 30, 12, 30, tzinfo=UTC)
        assert alerts.window_end(wed_1930_bkk) == datetime(2026, 9, 30, 18, 0, tzinfo=UTC)  # 01:00 Thu BKK
        assert alerts.window_end(datetime(2026, 9, 30, 5, 0, tzinfo=UTC)) is None  # 12:00 BKK
        assert alerts.window_end(datetime(2026, 10, 3, 12, 30, tzinfo=UTC)) is None  # Saturday
        always = AlertPreferences().window_end(wed_1930_bkk)
        assert always is not None and always.year == 9999

    def test_validation(self) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            AlertPreferences(timezone="Mars/Olympus")
        with pytest.raises(ValidationError, match="HH:MM"):
            UserWindow(start="25:00")
        with pytest.raises(ValidationError, match="Monday"):
            UserWindow(days=[7])


class TestTheories:
    def test_presets_and_overrides(self) -> None:
        assert TheoryPreferences().enabled_families() == frozenset(Family)
        classic = TheoryPreferences(preset="CLASSIC_TA", families={"FIBONACCI": True, "CANDLESTICK": False})
        assert classic.enabled_families() == (PRESETS["CLASSIC_TA"] | {Family.FIBONACCI}) - {
            Family.CANDLESTICK
        }
        assert TheoryPreferences(preset=None, families={"TREND": True}).enabled_families() == {Family.TREND}
        with pytest.raises(ValidationError, match="preset"):
            TheoryPreferences(preset="MAGIC")
        with pytest.raises(ValidationError, match="families"):
            TheoryPreferences(families={"ASTROLOGY": True})

    def test_enabled_detectors(self) -> None:
        fib = TheoryPreferences(
            preset=None,
            families={"FIBONACCI": True},
            detectors={"fib.cluster": False, "levels.round_number": True},
        )
        ids = fib.enabled_detectors(EVIDENCE)
        assert "fib.retracement" in ids and "fib.cluster" not in ids and "levels.round_number" in ids
        assert all(EVIDENCE.get(d).family is Family.FIBONACCI for d in ids - {"levels.round_number"})

    def test_catalog_validation(self) -> None:
        good = AdvisoryPreferences(
            theories=TheoryPreferences(
                params={"fib.retracement": {"tol_atr": 0.5}}, pattern_strategies={"setup_fib_pullback": False}
            )
        )
        assert validate_against_catalogs(good, EVIDENCE, STRATEGIES) == []
        bad = AdvisoryPreferences(
            theories=TheoryPreferences(
                detectors={"astro.moon": True},
                params={"fib.retracement": {"tol_atr": 99}},
                pattern_strategies={"nope": True, "example_trend_pullback": True},
            )
        )
        problems = validate_against_catalogs(bad, EVIDENCE, STRATEGIES)
        assert len(problems) == 4
        assert any("astro.moon" in p for p in problems) and any("tol_atr" in p for p in problems)
        assert any("not a pattern strategy" in p for p in problems)
        with pytest.raises(ConfigError, match=r"astro.moon"):
            parse_preferences(bad.model_dump(mode="json"), evidence=EVIDENCE, strategies=STRATEGIES)


class TestTradingProfile:
    @pytest.mark.parametrize(
        ("style", "risk", "heat", "positions", "daily", "rr", "wp", "n", "policy", "htf"),
        [
            (0, 0.25, 0.5, 1, 1.0, 2.5, 62.0, 4, ConflictPolicy.BLOCK, True),
            (25, 0.5, 1.0, 2, 1.5, 2.0, 58.0, 3, ConflictPolicy.BLOCK, True),
            (50, 0.75, 2.0, 3, 2.0, 1.5, 55.0, 2, ConflictPolicy.PENALIZE, True),
            (75, 1.0, 3.0, 4, 3.0, 1.3, 52.0, 2, ConflictPolicy.PENALIZE, False),
            (100, 1.5, 4.0, 5, 4.0, 1.2, 50.0, 1, ConflictPolicy.IGNORE, False),
        ],
    )
    def test_anchors_match_the_plan_table(
        self,
        style: int,
        risk: float,
        heat: float,
        positions: int,
        daily: float,
        rr: float,
        wp: float,
        n: int,
        policy: ConflictPolicy,
        htf: bool,
    ) -> None:
        p = TradingProfile(style=style).resolve()
        assert (p.risk_per_signal_percent, p.portfolio_heat_percent, p.max_positions) == (
            risk,
            heat,
            positions,
        )
        assert (p.max_daily_loss_percent, p.min_rr, p.min_win_probability) == (daily, rr, wp)
        assert (p.min_supporting_families, p.conflict_policy, p.require_htf_alignment) == (n, policy, htf)
        assert p.custom == frozenset()

    def test_interpolation_rounds_to_the_defensive_side(self) -> None:
        p = TradingProfile(style=60).resolve()
        assert p.risk_per_signal_percent == pytest.approx(0.85)
        assert p.max_positions == 3  # 3.4 -> 3
        assert p.conflict_policy is ConflictPolicy.PENALIZE and p.require_htf_alignment is True
        assert TradingProfile(style=10).resolve().min_supporting_families == 4  # 3.6 -> 4
        assert TradingProfile(style=99).resolve().conflict_policy is ConflictPolicy.PENALIZE

    def test_overrides_are_custom_and_bounded(self) -> None:
        profile = TradingProfile(style=100, overrides=ProfileOverrides(min_rr=2.0, max_positions=2))
        p = profile.resolve()
        assert p.min_rr == 2.0 and p.max_positions == 2 and p.custom == {"min_rr", "max_positions"}
        with pytest.raises(ValidationError):
            ProfileOverrides(risk_per_signal_percent=CEILING_RISK_PER_TRADE_PCT + 0.1)
        assert TradingProfile(holding_style="SWING").resolve().timeframes == (Timeframe.H1, Timeframe.H4)

    @given(a=st.integers(0, 100), b=st.integers(0, 100))
    def test_more_offensive_never_means_more_defensive(self, a: int, b: int) -> None:
        lo, hi = sorted((a, b))
        p, q = TradingProfile(style=lo).resolve(), TradingProfile(style=hi).resolve()
        assert q.risk_per_signal_percent >= p.risk_per_signal_percent
        assert q.portfolio_heat_percent >= p.portfolio_heat_percent
        assert q.max_positions >= p.max_positions
        assert q.min_rr <= p.min_rr and q.min_win_probability <= p.min_win_probability
        assert q.min_supporting_families <= p.min_supporting_families
        assert q.risk_per_signal_percent <= CEILING_RISK_PER_TRADE_PCT

    @given(
        style=st.integers(0, 100),
        rr=st.floats(1.0, 10.0, allow_nan=False),
        cost=st.floats(0.0, 0.5, allow_nan=False),
    )
    def test_required_probability_always_has_positive_ev(self, style: int, rr: float, cost: float) -> None:
        p = TradingProfile(style=style).resolve()
        required = required_win_probability(p, rr, cost)
        assert required >= break_even_probability(rr, cost) + 2
        assert expected_value_r(required, rr, cost) > 0

    def test_break_even_example(self) -> None:
        p = TradingProfile(style=100).resolve()  # min win probability 50%
        assert break_even_probability(1.2, 0.1) == pytest.approx(50.0)
        assert required_win_probability(p, 1.2, 0.1) == pytest.approx(52.0)


class TestEntryPlan:
    def test_modes(self) -> None:
        assert EntryPlanPreferences().take_profits_r == []
        same = EntryPlanPreferences(mode=SplitMode.SAME_PRICE, parts=3, partial_tp_r=[1.0, 2.0, 3.0])
        assert same.take_profits_r == [1.0, 2.0]
        with pytest.raises(ValidationError, match="exactly one part"):
            EntryPlanPreferences(parts=2)
        with pytest.raises(ValidationError, match="at least two"):
            EntryPlanPreferences(mode=SplitMode.SCALE_IN)
        with pytest.raises(ValidationError, match="one partial take-profit"):
            EntryPlanPreferences(mode=SplitMode.SAME_PRICE, parts=4, partial_tp_r=[1.0, 2.0])
        with pytest.raises(ValidationError, match="increasing"):
            EntryPlanPreferences(mode=SplitMode.SAME_PRICE, parts=3, partial_tp_r=[2.0, 1.0])


class TestDocuments:
    def test_config_yaml_fallback(self) -> None:
        config = load_settings(env_file=None, config_file="config.yaml", environ=ENV).config
        prefs = local_preferences(config)
        assert prefs.listed_symbols() == ["EURUSD", "XAUUSD"]
        assert prefs.alerts.language == "th" and prefs.trading_profile.style == 50

    def test_round_trip_and_errors(self) -> None:
        prefs = AdvisoryPreferences()
        assert parse_preferences(prefs.model_dump(mode="json")) == prefs
        with pytest.raises(ConfigError, match="invalid advisory preferences"):
            parse_preferences({"alerts": {"metric": "LUCK"}})
        with pytest.raises(ConfigError):
            parse_preferences({"unknown_section": {}})
