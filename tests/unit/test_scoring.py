from __future__ import annotations

import dataclasses
import functools
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.advisory.asset_classes import AssetClass
from app.advisory.correlations import correlation, max_correlation, return_correlations
from app.advisory.scoring import (
    NOW,
    OVERALL,
    Candidate,
    DynamicMetrics,
    EdgeEstimate,
    Score,
    diversification_score,
    edge_score,
    holding_cost_score,
    liquidity_score,
    rank,
    regime_score,
    score_candidate,
    sizing_score,
    swap_per_night,
    volatility_score,
    weighted,
)
from app.advisory.suitability import Gate, Suitability, SymbolFacts, assess, collect_facts
from app.broker import mt5_constants as c
from app.config import RiskConfig, ScoringConfig, SuitabilityConfig
from app.core.enums import Regime, Side
from app.risk.position_sizer import AccountFunds
from tests.unit.test_market_data import setup

WED = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
RISK = RiskConfig()
SUIT = SuitabilityConfig()
CFG = ScoringConfig()
ATR = {"EURUSD": 0.0010, "GBPUSD": 0.0012, "USDJPY": 0.15, "XAUUSD": 5.0}


@functools.cache
def facts(symbol: str) -> SymbolFacts:
    _, _, gw = setup(WED)
    cls = AssetClass.METAL if symbol == "XAUUSD" else AssetClass.FOREX_MAJOR
    return collect_facts(
        gw.symbol_spec(symbol), cls, gw, SUIT, tick=gw.tick(symbol), atr=ATR[symbol], candles=500, now=WED,
        market_open=True,
    )  # fmt: skip


def funds(equity: float, balance: float | None = None) -> AccountFunds:
    return AccountFunds(
        equity=equity, balance=equity if balance is None else balance, margin=0.0, margin_free=equity
    )


def suit(symbol: str, equity: float = 10_000.0, balance: float | None = None) -> Suitability:
    return assess(facts(symbol), funds(equity, balance), RISK, SUIT, currency="USD")


def clone(symbol: str, name: str, metrics: DynamicMetrics | None = None) -> Candidate:
    f = facts(symbol)
    f = dataclasses.replace(f, spec=dataclasses.replace(f.spec, name=name))
    s = dataclasses.replace(suit(symbol), symbol=name)
    return Candidate(f, s, metrics or DynamicMetrics())


class TestSingleScores:
    def test_sizing_is_log2_of_headroom(self) -> None:
        s = suit("EURUSD")
        assert s.risk_budget is not None and s.min_lot_risk is not None
        x = float(s.risk_budget / s.min_lot_risk)
        assert sizing_score(s) == pytest.approx(min(1.0, np.log2(x) / 4) * 100)
        assert sizing_score(suit("XAUUSD", 100.0)) == 0.0  # below the minimum lot

    @pytest.mark.parametrize(
        ("ratio", "score"), [(None, 0.0), (0.0, 0.0), (1.0, 50.0), (2.0, 100.0), (5.0, 100.0)]
    )
    def test_liquidity(self, ratio: float | None, score: float) -> None:
        assert liquidity_score(ratio) == score

    @pytest.mark.parametrize(
        ("p", "score"), [(None, None), (0, 0.0), (10, 50.0), (20, 100.0), (80, 100.0), (95, 25.0)]
    )
    def test_volatility_band(self, p: float | None, score: float | None) -> None:
        assert volatility_score(p) == score

    def test_regime(self) -> None:
        preferred = [Regime.TRENDING]
        assert regime_score(Regime.TRENDING, preferred) == 100
        assert regime_score(Regime.UNCLEAR, preferred) == 50
        assert regime_score(Regime.VOLATILE, preferred) == 0
        assert regime_score(None, preferred) is None

    def test_diversification(self) -> None:
        assert diversification_score(None) == 100
        assert diversification_score(0.8) == pytest.approx(20)

    def test_edge_is_shrunk_and_neutral_when_thin(self) -> None:
        assert edge_score(None, CFG) is None
        assert edge_score(EdgeEstimate(29, 1.0), CFG) is None
        assert edge_score(EdgeEstimate(30, 0.5), CFG) == pytest.approx(80.0)  # 30/50 x 0.5 = 0.3R
        assert edge_score(EdgeEstimate(1000, -2.0), CFG) == 0.0

    def test_swap(self) -> None:
        f = facts("EURUSD")
        assert swap_per_night(f.spec, Side.BUY) == pytest.approx(f.spec.swap_long)  # points x 1 USD
        assert f.loss_per_lot is not None
        q = -f.spec.swap_long / f.loss_per_lot
        assert holding_cost_score(f, CFG) == pytest.approx(max(0.0, 1 - q / 0.05) * 100)
        credit = dataclasses.replace(f, side=Side.SELL)
        assert holding_cost_score(credit, CFG) == 100.0
        interest = dataclasses.replace(f, spec=dataclasses.replace(f.spec, swap_mode=5))
        assert holding_cost_score(interest, CFG) is None
        disabled = dataclasses.replace(f.spec, swap_mode=c.SYMBOL_SWAP_MODE_DISABLED)
        assert swap_per_night(disabled, Side.BUY) == 0.0


class TestCombination:
    def test_overall_and_now(self) -> None:
        r = score_candidate(Candidate(facts("EURUSD"), suit("EURUSD")), CFG, RISK)
        assert set(r.scores) == set(Score)
        assert r.overall == weighted(r.scores, OVERALL, CFG)
        assert r.now == weighted(r.scores, NOW, CFG)
        assert set(r.flags) == {"unknown_volatility", "unknown_regime", "insufficient_history"}
        assert r.scores[Score.S4_LIQUIDITY] == 0  # no liquidity data: not usable now

    def test_weights(self) -> None:
        scores = dict.fromkeys(Score, 0.0) | {Score.S1_SIZING: 100.0}
        only_s1 = ScoringConfig(weights={k: 0.0 for k in CFG.weights} | {"S1": 1.0})
        assert weighted(scores, NOW, only_s1) == 100.0
        assert weighted(scores, OVERALL, CFG) == pytest.approx(100 / 4.5, abs=0.01)
        with pytest.raises(ValueError):
            ScoringConfig(weights={"S10": 1.0})
        with pytest.raises(ValueError):
            ScoringConfig(weights={"S1": -1.0})

    def test_now_reacts_to_dynamic_metrics(self) -> None:
        quiet = score_candidate(Candidate(facts("EURUSD"), suit("EURUSD")), CFG, RISK)
        busy = Candidate(facts("EURUSD"), suit("EURUSD"), DynamicMetrics(2.0, 50.0, Regime.TRENDING))
        active = score_candidate(busy, CFG, RISK)
        assert active.overall == quiet.overall and active.now > quiet.now


class TestCorrelations:
    def closes(self) -> dict[str, pd.Series]:
        rng = np.random.default_rng(7)
        idx = pd.date_range("2026-09-01", periods=300, freq="h", tz="UTC")
        a = np.cumsum(rng.normal(0, 0.001, 300))
        b = a + rng.normal(0, 0.0002, 300)
        other = np.cumsum(rng.normal(0, 0.001, 300))
        return {
            "AAA": pd.Series(np.exp(a), index=idx),
            "BBB": pd.Series(np.exp(b), index=idx),
            "CCC": pd.Series(np.exp(other), index=idx),
            "SHORT": pd.Series(np.exp(other[:50]), index=idx[:50]),
        }

    def test_matrix(self) -> None:
        m = return_correlations(self.closes(), min_overlap=100)
        aa_bb, aa_cc = correlation(m, "AAA", "BBB"), correlation(m, "AAA", "CCC")
        assert aa_bb is not None and aa_bb > 0.9
        assert aa_cc is not None and abs(aa_cc) < 0.3
        assert correlation(m, "AAA", "SHORT") is None  # too little overlap
        assert correlation(m, "AAA", "AAA") == 1.0 and correlation(None, "AAA", "BBB") is None
        assert max_correlation(m, "BBB", ["CCC", "AAA"])[1] == "AAA"
        assert max_correlation(m, "BBB", []) == (None, None)


class TestRanking:
    def matrix(self, pairs: dict[tuple[str, str], float]) -> pd.DataFrame:
        names = sorted({n for p in pairs for n in p})
        m = pd.DataFrame(np.eye(len(names)), index=names, columns=names)
        for (a, b), v in pairs.items():
            m.loc[a, b] = m.loc[b, a] = v
        return m

    def test_deterministic_tie_break(self) -> None:
        cands = [clone("EURUSD", n) for n in ("CCC", "AAA", "BBB")]
        assert [r.symbol for r in rank(cands, CFG, RISK)] == ["AAA", "BBB", "CCC"]
        assert [r.rank for r in rank(cands, CFG, RISK)] == [1, 2, 3]

    def test_greedy_diversification(self) -> None:
        cands = [clone("EURUSD", n) for n in ("AAA", "BBB", "CCC")]
        m = self.matrix({("AAA", "BBB"): 0.9, ("AAA", "CCC"): 0.1, ("BBB", "CCC"): 0.2})
        ranked = rank(cands, CFG, RISK, correlations=m)
        assert [r.symbol for r in ranked] == ["AAA", "CCC", "BBB"]
        assert ranked[2].correlated_with == "AAA" and ranked[2].correlation == pytest.approx(0.9)

    def test_open_exposure_penalizes(self) -> None:
        cands = [clone("EURUSD", n) for n in ("AAA", "BBB")]
        ranked = rank(cands, CFG, RISK, exposure=["AAA"])
        assert [r.symbol for r in ranked] == ["BBB", "AAA"]
        assert ranked[1].scores[Score.S7_DIVERSIFICATION] == 0.0  # already held

    def test_eligible_first(self) -> None:
        small = 100.0
        cands = [
            Candidate(
                facts(s), suit(s, small), DynamicMetrics(3.0, 50.0, Regime.TRENDING, EdgeEstimate(500, 1.0))
            )
            for s in ("XAUUSD", "EURUSD")
        ]
        rich = Candidate(facts("USDJPY"), suit("USDJPY"))
        ranked = rank([*cands, rich], CFG, RISK)
        assert ranked[0].symbol == "USDJPY" and ranked[0].eligible
        assert all(not r.eligible for r in ranked[1:])
        assert ranked[1].now >= ranked[2].now


@settings(max_examples=60, deadline=None)
@given(
    equity=st.floats(min_value=20, max_value=2_000_000, allow_nan=False),
    factor=st.floats(min_value=1.0, max_value=50.0, allow_nan=False),
    symbol=st.sampled_from(["EURUSD", "USDJPY", "XAUUSD"]),
    equity_only=st.booleans(),
)
def test_more_equity_never_lowers_s1_or_fails_g2(
    equity: float, factor: float, symbol: str, equity_only: bool
) -> None:
    low = suit(symbol, equity)
    high = suit(symbol, equity * factor, equity if equity_only else None)  # balance may stay behind
    assert sizing_score(high) >= sizing_score(low)
    if low.gate(Gate.G2_MIN_LOT).passed:
        assert high.gate(Gate.G2_MIN_LOT).passed
    r = score_candidate(Candidate(facts(symbol), high), CFG, RISK)
    assert 0 <= r.overall <= 100 and 0 <= r.now <= 100
