"""The detector catalog: every production detector, listed explicitly (no import-time registration magic).

Each entry must be documented in docs/PATTERNS.md. ``tests/unit/test_evidence_catalog.py`` checks that and
runs the look-ahead harness against every entry.
"""

from __future__ import annotations

from app.evidence.chart_patterns import (
    CupHandle,
    DoubleTopBottom,
    FlagPennant,
    HeadShoulders,
    Rectangle,
    Triangle,
    TripleTopBottom,
    Wedge,
)
from app.evidence.fibonacci import FibCluster, FibExtension, FibGoldenZone, FibRetracement
from app.evidence.framework import Detector
from app.evidence.levels import PivotPoints, PrevHighLow, RoundNumber, SRBreakout, SRZone
from app.evidence.registry import DetectorRegistry

ALL_DETECTORS: tuple[Detector, ...] = (
    # Fibonacci (TAA-2A2)
    FibRetracement(),
    FibGoldenZone(),
    FibExtension(),
    FibCluster(),
    # Levels (TAA-2A2)
    RoundNumber(),
    PivotPoints(),
    PrevHighLow(),
    SRZone(),
    SRBreakout(),
    # Chart patterns (TAA-2A3)
    DoubleTopBottom(),
    TripleTopBottom(),
    HeadShoulders(),
    Triangle(),
    Wedge(),
    Rectangle(),
    FlagPennant(),
    CupHandle(),
)


def default_registry() -> DetectorRegistry:
    return DetectorRegistry(ALL_DETECTORS)
