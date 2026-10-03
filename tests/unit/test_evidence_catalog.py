"""Every production detector: look-ahead harness, documentation, and well-formed metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evidence.catalog import ALL_DETECTORS, default_registry
from app.evidence.framework import Detector
from tests.evidence_harness import assert_no_lookahead

PATTERNS_DOC = (Path(__file__).resolve().parents[2] / "docs" / "PATTERNS.md").read_text(encoding="utf-8")
IDS = [d.id for d in ALL_DETECTORS]


def test_registry_builds_with_every_detector_once() -> None:
    registry = default_registry()  # validates unique ids, known prerequisites, no cycles
    assert sorted(registry.ids) == sorted(IDS)
    for det_id in registry.ids:
        position = registry.ids.index(det_id)
        assert all(registry.ids.index(dep) < position for dep in registry.get(det_id).depends_on)


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=IDS)
def test_no_lookahead(detector: Detector) -> None:
    catalog = [d for d in ALL_DETECTORS if d is not detector]
    assert_no_lookahead(detector, catalog=catalog)


@pytest.mark.parametrize("detector", ALL_DETECTORS, ids=IDS)
def test_documented_and_well_formed(detector: Detector) -> None:
    assert f"`{detector.id}`" in PATTERNS_DOC, f"{detector.id} is missing from docs/PATTERNS.md"
    assert detector.id.count(".") >= 1 and detector.id == detector.id.lower()
    assert detector.name and detector.version >= 1
    detector.Params()  # defaults must validate
