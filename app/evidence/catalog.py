"""The detector catalog: every production detector, listed explicitly (no import-time registration magic).

Each entry must be documented in docs/PATTERNS.md. ``tests/unit/test_evidence_catalog.py`` checks that and
runs the look-ahead harness against every entry.
"""

from __future__ import annotations

from app.evidence.candlesticks import (
    Doji,
    Engulfing,
    Hammer,
    Harami,
    InsideOutside,
    Marubozu,
    ShootingStar,
    Star,
    ThreeSoldiersCrows,
    Tweezer,
)
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
from app.evidence.momentum import CciExtreme, Divergence, MomentumCross, OverboughtOversold
from app.evidence.registry import DetectorRegistry
from app.evidence.sessions_ranges import AsianRangeBreakout, OpenRangeBreakout
from app.evidence.trend import AdxStrength, MaAlignment
from app.evidence.volatility import (
    AtrExpansion,
    BollingerSqueeze,
    DonchianBreakout,
    KeltnerBreakout,
    SessionVwap,
    TickVolumeSpike,
)

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
    # Candlesticks (TAA-2A4)
    Engulfing(),
    Hammer(),
    ShootingStar(),
    Doji(),
    InsideOutside(),
    Star(),
    ThreeSoldiersCrows(),
    Harami(),
    Tweezer(),
    Marubozu(),
    # Momentum, trend, volatility/volume, sessions (TAA-2A5)
    Divergence(),
    OverboughtOversold(),
    MomentumCross(),
    CciExtreme(),
    MaAlignment(),
    AdxStrength(),
    BollingerSqueeze(),
    KeltnerBreakout(),
    DonchianBreakout(),
    AtrExpansion(),
    TickVolumeSpike(),
    SessionVwap(),
    AsianRangeBreakout(),
    OpenRangeBreakout(),
)


def default_registry() -> DetectorRegistry:
    return DetectorRegistry(ALL_DETECTORS)
