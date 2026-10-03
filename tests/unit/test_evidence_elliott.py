"""Elliott Wave (heuristic tier): golden 5-wave and A-B-C counts, hard rules, ranking and immutability."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import pytest

from app.evidence.elliott import ElliottParams, ElliottWave, guideline
from app.evidence.framework import Direction, Evidence, EvidenceContext, EvidenceSnapshot, Tier
from app.evidence.registry import DetectorRegistry, EvidenceEngine
from tests.evidence_harness import assert_no_lookahead, scan_one
from tests.evidence_paths import path, path_frame

STEP = 4.0  # price per bar; legs get bars in proportion to their length


def legs(vertices: Sequence[float]) -> list[int]:
    return [max(2, round(abs(b - a) / STEP)) for a, b in pairwise(vertices)]


def hpath(vertices: Sequence[float]) -> EvidenceContext:
    return path(vertices, legs(vertices))


def run(
    vertices: Sequence[float], params: ElliottParams | None = None
) -> tuple[EvidenceContext, list[Evidence]]:
    ctx = hpath(vertices)
    return ctx, scan_one(ElliottWave(), ctx, params=params)


def state(ev: Evidence) -> str:
    return ev.i18n_key.rsplit(".", 1)[-1]


def waves(ev: Evidence) -> list[float]:
    return [round(k.price) for k in ev.key_levels if k.name.startswith("wave_")]


# lead-in high 1080, then wave 0 = 1000 (a lower low), wave 1 = 1100 (through 1080), wave 2 = 1040 (60 %),
# wave 3 = 1200 (1.6 x wave 1), wave 4 = 1140 (37.5 % of wave 3), wave 5 = 1240 (= wave 1)
IMPULSE = [1040, 1080, 1000, 1100, 1040, 1200, 1140, 1240, 1200]
WAVE2_BAR, WAVE4_BAR = 91, 146  # confirmation bars of waves 2 and 4 (minor degree)
# prior leg 1000 -> 1200, A = 1140, B = 1170 (50 %), C = A reaches 1110 (45 % of the prior leg)
ABC = [1040, 1000, 1200, 1140, 1170, 1110, 1160]


class TestImpulse:
    def test_possible_wave3(self) -> None:
        ctx, out = run(IMPULSE)
        (ev,) = [e for e in out if ctx.pos_of(e.detected_at) == WAVE2_BAR]
        assert state(ev) == "wave3" and ev.direction is Direction.BULL
        assert waves(ev) == [1000, 1100, 1040]
        assert ev.detail("count") == "primary" and ev.quality == pytest.approx(1.0)
        assert ev.invalidation == pytest.approx(999.9)  # wave 2 may not go beyond the start of wave 1
        assert ev.targets == pytest.approx([1039.9 + r * 100.2 for r in (1.0, 1.618)])

    def test_possible_wave5_with_alternate(self) -> None:
        ctx, out = run(IMPULSE)
        at = sorted(
            (e for e in out if ctx.pos_of(e.detected_at) == WAVE4_BAR),
            key=lambda e: int(e.detail("rank") or 0),
        )
        primary, alternate = at
        assert state(primary) == "wave5" and waves(primary) == [1000, 1100, 1040, 1200, 1140]
        assert primary.invalidation == pytest.approx(1100.1)  # wave 4 may not overlap wave 1
        assert primary.targets[0] == pytest.approx(1139.9 + 100.2)  # wave 5 = wave 1
        # the alternate reads waves 3-4 as a new 1-2
        assert state(alternate) == "wave3" and alternate.detail("count") == "alternate"
        assert waves(alternate) == [1040, 1200, 1140]
        assert primary.quality > alternate.quality
        assert primary.quality + alternate.quality <= 1.0 + 1e-9

    def test_max_counts_keeps_only_the_primary(self) -> None:
        ctx, out = run(IMPULSE, ElliottParams(max_counts=1))
        assert [state(e) for e in out if ctx.pos_of(e.detected_at) == WAVE4_BAR] == ["wave5"]

    def test_hard_rule_wave2_beyond_wave1_start(self) -> None:
        _, out = run([1040, 1080, 1000, 1100, 990, 1150, 1100])
        assert not [e for e in out if state(e) == "wave3" and waves(e)[:2] == [1000, 1100]]

    def test_hard_rule_wave4_overlaps_wave1(self) -> None:
        _, out = run([1040, 1080, 1000, 1100, 1040, 1200, 1090, 1240], ElliottParams(min_score=0))
        assert not [e for e in out if state(e) == "wave5"]

    def test_wave3_shorter_than_wave1_caps_wave5(self) -> None:
        # wave 1 = 100, wave 3 = 90: wave 3 may not be the shortest, so wave 5 must stay under 90
        _, out = run([1040, 1080, 1000, 1100, 1060, 1150, 1120, 1180], ElliottParams(min_score=0))
        (ev,) = [e for e in out if state(e) == "wave5"]
        cap = ev.detail("wave5_cap")
        assert cap == pytest.approx(1119.9 + 90.2)
        assert isinstance(cap, float) and max(ev.targets) <= cap

    def test_weak_counts_are_not_reported(self) -> None:
        _, out = run([1040, 1080, 1000, 1100, 1060, 1150, 1120, 1180])
        assert not [e for e in out if state(e) == "wave5"]  # score 0.48 < min_score 0.5


class TestCorrection:
    def test_possible_c_completion(self) -> None:
        ctx, out = run(ABC)
        (ev,) = [e for e in out if state(e) == "c_completion"]
        assert ctx.pos_of(ev.detected_at) == 117  # the first bar reaching C = 95 % of A
        assert ev.direction is Direction.BULL  # the prior trend is expected to resume
        levels = {k.name: k.price for k in ev.key_levels}
        assert levels["c_zone_near"] == pytest.approx(1170.1 - 0.95 * 60.2)
        assert levels["c_zone_far"] == pytest.approx(1170.1 - 1.618 * 1.05 * 60.2)
        assert ev.targets == pytest.approx([1170.1, 1200.1])  # B, then the start of the correction

    def test_near_miss_c_blows_through(self) -> None:
        vertices = [1040, 1000, 1200, 1140, 1170, 1040, 1100]
        bars = legs(vertices)
        bars[4] = 1  # B -> 1040 in one bar, closing far beyond the C zone
        ctx = path(vertices, bars)
        assert not [e for e in scan_one(ElliottWave(), ctx) if state(e) == "c_completion"]

    def test_near_miss_b_beyond_the_start(self) -> None:
        # B at 1210 is above the start of A (1200): an expanded flat, not a zigzag
        _, out = run([1040, 1000, 1200, 1140, 1210, 1110, 1160])
        assert not [e for e in out if state(e) == "c_completion" and round(e.key_levels[1].price) == 1200]


class TestHeuristicTier:
    def test_labelled_heuristic(self) -> None:
        _, out = run(IMPULSE)
        assert out and all(e.tier is Tier.T3 and e.detail("heuristic") is True for e in out)
        assert all("heuristic" in e.name for e in out)

    def test_guideline(self) -> None:
        assert guideline(0.55, (0.5, 0.618), 0.25) == 1.0
        assert guideline(0.25, (0.5, 0.618), 0.25) == 0.0
        assert guideline(0.618 + 0.125, (0.5, 0.618), 0.25) == pytest.approx(0.5)

    def test_no_lookahead_on_the_impulse(self) -> None:
        found = assert_no_lookahead(
            ElliottWave(),
            path_frame(IMPULSE, legs(IMPULSE)),
            positions=(WAVE2_BAR, WAVE2_BAR + 20, WAVE4_BAR),
        )
        assert len(found) >= 3

    def test_snapshot_survives_a_recount(self) -> None:
        """The wave-3 count stored at bar 91 stays as it was after price breaks the count."""
        # identical bars up to 94; then the "impulse" fails below wave 0 (1000): the count is broken
        failed = [1040, 1080, 1000, 1100, 1040, 1060, 960, 1000]
        good, bad = hpath(IMPULSE), hpath(failed)
        assert good.candles.iloc[:95].equals(bad.candles.iloc[:95])
        registry = DetectorRegistry([ElliottWave()])
        engine = EvidenceEngine(registry, registry.plan(["elliott.wave"]))
        stored = engine.evaluate(bad.prefix(WAVE2_BAR))
        (item,) = stored.items
        assert state(item.evidence) == "wave3"
        # later: the count is invalidated (a close below wave 0) and no longer active ...
        later = engine.evaluate(bad)
        assert item.evidence.evidence_id not in {i.evidence.evidence_id for i in later.items}
        # ... but the full rescan still holds the identical record, and the stored snapshot is unchanged
        rescan = scan_one(ElliottWave(), bad)
        assert item.evidence in rescan
        assert EvidenceSnapshot.from_json(stored.to_json(), expected_digest=stored.digest) == stored
