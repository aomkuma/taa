"""Selective computation on the real catalog (PLAN §A30): only the selected detectors and their prerequisites
run; the cloud's union can only narrow what the local config enables."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.config import DetectorSettings, EvidenceConfig
from app.core.errors import ConfigError
from app.evidence.candlesticks import Hammer
from app.evidence.catalog import ALL_DETECTORS, default_registry
from app.evidence.framework import Family
from app.evidence.registry import EvidenceEngine
from tests.evidence_harness import context
from tests.indicator_data import random_ohlc


@pytest.fixture(scope="module")
def frame() -> Any:
    return random_ohlc(300, seed=11)


def test_prerequisites_run_first_but_only_requested_report(frame: Any) -> None:
    registry = default_registry()
    plan = registry.plan(["candle.hammer"])
    assert plan.order[-1] == "candle.hammer"
    assert set(plan.order) == {"candle.hammer", *Hammer.depends_on}
    engine = EvidenceEngine(registry, plan)
    out = engine.scan(context(frame))
    assert list(out) == ["candle.hammer"]
    assert set(engine.stats) == set(plan.order)
    assert all(s.calls == 1 for s in engine.stats.values())


def test_unselected_detectors_are_never_executed(frame: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    selected = {"harmonic.gartley", "elliott.wave", "candle.shooting_star"}
    registry = default_registry()
    plan = registry.plan_from_config(
        EvidenceConfig(default_enabled=False, detectors={d: DetectorSettings(enabled=True) for d in selected})
    )
    needed = set(plan.order)

    def boom(*_: object) -> list[Any]:
        raise AssertionError("an unselected detector was executed")

    for det in ALL_DETECTORS:
        if det.id not in needed:
            monkeypatch.setattr(det, "scan", boom)
    engine = EvidenceEngine(registry, plan)
    assert set(engine.scan(context(frame))) == selected
    assert set(engine.stats) == needed  # the selection plus the shooting star's location sources


def test_cloud_union_only_narrows() -> None:
    registry = default_registry()
    local = EvidenceConfig(detectors={"harmonic.bat": DetectorSettings(enabled=False)})
    plan = registry.plan_from_config(local, only={"harmonic.bat", "harmonic.gartley"})
    assert plan.outputs == {"harmonic.gartley"}  # the cloud cannot turn on what the engine disables


def test_unknown_union_ids_are_logged_and_skipped(caplog: pytest.LogCaptureFixture) -> None:
    registry = default_registry()
    with caplog.at_level(logging.WARNING, logger="app.evidence.registry"):
        plan = registry.plan_from_config(EvidenceConfig(), only={"harmonic.gartley", "future.detector"})
    assert plan.outputs == {"harmonic.gartley"}
    assert "future.detector" in caplog.text


def test_family_selection() -> None:
    registry = default_registry()
    harmonics = registry.ids_in_families(["HARMONIC"])
    assert harmonics == {d.id for d in ALL_DETECTORS if d.family is Family.HARMONIC} and len(harmonics) == 7
    both = registry.ids_in_families([Family.FIBONACCI, Family.ELLIOTT])
    assert "elliott.wave" in both and "fib.extension_level" in both and "harmonic.bat" not in both
    plan = registry.plan_from_config(EvidenceConfig(), only=harmonics)
    assert plan.outputs == harmonics
    with pytest.raises(ConfigError, match="family"):
        registry.ids_in_families(["ASTROLOGY"])


def test_counters_and_timing_accumulate(frame: Any) -> None:
    registry = default_registry()
    engine = EvidenceEngine(registry, registry.plan(["elliott.wave"]))
    first = engine.scan(context(frame))["elliott.wave"]
    engine.scan(context(frame))
    stats = engine.stats["elliott.wave"]
    assert stats.calls == 2 and stats.records == 2 * len(first) and stats.seconds > 0
