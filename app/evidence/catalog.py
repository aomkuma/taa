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
from app.evidence.fibonacci import (
    FibCluster,
    FibExtension,
    FibExtensionLevel,
    FibGoldenZone,
    FibRetracement,
)
from app.evidence.framework import Detector
from app.evidence.harmonics import AbCd, Bat, Butterfly, Crab, Cypher, Gartley, Shark
from app.evidence.ichimoku import Chikou, KumoBreakout, TkCross
from app.evidence.levels import PivotPoints, PrevHighLow, RoundNumber, SRBreakout, SRZone
from app.evidence.momentum import CciExtreme, Divergence, MomentumCross, OverboughtOversold
from app.evidence.registry import DetectorRegistry
from app.evidence.sessions_ranges import AsianRangeBreakout, OpenRangeBreakout
from app.evidence.structure_smc import (
    BosChoch,
    DowStructure,
    FairValueGap,
    LiquiditySweep,
    OrderBlock,
    SupplyDemand,
    Trendline,
    WyckoffSpring,
)
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
    FibExtensionLevel(),  # TAA-2A10
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
    # Ichimoku, structure, smart money (TAA-2A6)
    KumoBreakout(),
    TkCross(),
    Chikou(),
    DowStructure(),
    BosChoch(),
    Trendline(),
    LiquiditySweep(),
    FairValueGap(),
    OrderBlock(),
    SupplyDemand(),
    WyckoffSpring(),
    # Harmonic patterns (TAA-2A7)
    Gartley(),
    Bat(),
    Butterfly(),
    Crab(),
    Cypher(),
    Shark(),
    AbCd(),
)


def default_registry() -> DetectorRegistry:
    return DetectorRegistry(ALL_DETECTORS)
