"""Hand-worked weighted-score cases; every expected score is calculated in the test comments."""

from __future__ import annotations

import pytest

from app.strategy.weighing import Scale, Weight, score


def test_all_readings_agree():
    scale = Scale((Weight("a", 2.0, "true"), Weight("b", 1.0, "high")), 1.0)
    got = score({"a": True, "b": 1.0}, scale)
    assert got.score == 1.0  # (2 + 1) / (2 + 1)
    assert got.supported == ["a", "b"]
    assert got.opposed == [] and got.missing == [] and got.meets_threshold


def test_all_readings_disagree():
    scale = Scale((Weight("a", 2.0, "true"), Weight("b", 1.0, "high")), 0.5)
    got = score({"a": False, "b": 0.0}, scale)
    assert got.score == 0.0  # (0 + 0) / 3
    assert got.supported == [] and got.opposed == ["a", "b"]
    assert not got.meets_threshold


def test_mixed_readings_use_weighted_contributions():
    scale = Scale((Weight("yes", 2.0, "true"), Weight("trend", 3.0, "high")), 0.5)
    got = score({"yes": True, "trend": 0.4}, scale)
    assert got.score == pytest.approx(3.2 / 5.0)  # (2 + 3 * .4) / 5
    assert got.supported == ["yes"] and got.opposed == ["trend"]
    assert got.meets_threshold


def test_missing_reading_is_removed_from_the_denominator():
    scale = Scale((Weight("yes", 1.0, "true"), Weight("absent", 3.0, "true")), 0.9)
    got = score({"yes": True}, scale)
    assert got.score == 1.0  # 1 / 1, not 1 / 4
    assert got.supported == ["yes"] and got.missing == ["absent"]
    assert got.meets_threshold


def test_low_numeric_reading_scores_the_complement():
    scale = Scale((Weight("noise", 4.0, "low"),), 0.5)
    got = score({"noise": 0.25}, scale)
    assert got.score == 0.75  # 4 * (1 - .25) / 4
    assert got.supported == ["noise"] and got.meets_threshold


def test_empty_scale_scores_zero_and_has_no_readings():
    got = score({}, Scale((), 0.0))
    assert got.score == 0.0
    assert got.supported == [] and got.opposed == [] and got.missing == []
    assert not got.meets_threshold


def test_zero_weight_is_readable_but_cannot_create_a_score():
    got = score({"signal": True}, Scale((Weight("signal", 0.0, "true"),), 0.0))
    assert got.score == 0.0
    assert got.supported == ["signal"] and got.opposed == []
    assert not got.meets_threshold


def test_threshold_is_met_at_equality():
    got = score({"signal": 0.75}, Scale((Weight("signal", 2.0, "high"),), 0.75))
    assert got.score == 0.75  # (2 * .75) / 2
    assert got.meets_threshold  # The documented comparison is >=.


def test_none_is_reported_as_missing():
    got = score({"signal": None}, Scale((Weight("signal", 1.0, "true"),), 0.0))
    assert got.score == 0.0 and got.missing == ["signal"]
    assert got.supported == [] and got.opposed == [] and not got.meets_threshold
