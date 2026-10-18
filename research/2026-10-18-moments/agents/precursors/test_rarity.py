"""rarity.py: its parts together are the library's rule, and its tables by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_rarity.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from picture import as_arrays, same_mask, same_tf  # noqa: E402
from rarity import cumulative, part_masks, summarize, thirds  # noqa: E402


def random_library(n: int, seed: int) -> tuple[list[list[dict]], np.ndarray]:
    """Pictures on two timeframes drawn from few values so that every part both passes and fails, with flat thirds."""
    rng = np.random.default_rng(seed)
    feats = [[dict(size=float(rng.choice([4.0, 5.0, 9.0, np.nan], p=[0.4, 0.4, 0.15, 0.05])), pos=float(rng.choice([0.1, 0.25, 0.9])),
                   edge=int(rng.choice([-1, 0, 1])), leg_way=int(rng.choice([-1, 1])), leg=float(rng.choice([0.05, 1.0, 1.5, 3.0, np.nan])),
                   net_way=int(rng.choice([-1, 0, 1])), struct=int(rng.choice([-1, 0, 1, 9])), brk=int(rng.choice([-1, 0, 1])),
                   retr=float(rng.choice([0.2, 0.8, 2.0, 3.5])), er=float(rng.choice([0.1, 0.15, 0.4])),
                   **{f"seg{j}": int(rng.choice([-1, 0, 1])) for j in range(3)}) for _ in range(2)] for _ in range(n)]
    base = rng.normal(size=(3, 40))  # a few outlines plus noise: correlations land on both sides of the thresholds
    shapes = base[rng.integers(0, 3, size=(n, 2))] + rng.normal(scale=0.6, size=(n, 2, 40))
    shapes[rng.random((n, 2)) < 0.1, 13:27] = 0.0  # some flat middle thirds
    shapes -= shapes.mean(axis=-1, keepdims=True)
    shapes /= np.linalg.norm(shapes, axis=-1, keepdims=True)
    return feats, shapes


def test_the_parts_together_are_the_library_rule():
    feats, shapes = random_library(300, 5)
    A, segs = as_arrays(feats), thirds(shapes)
    cand = np.arange(300)
    hits = 0
    for row in range(0, 300, 7):
        m = part_masks(A, shapes, segs, row, cand)
        assert set(m) == {"outline", "thirds' way", "thirds' outline", "120 bars' way", "structure", "last top/bottom",
                          "pullback", "smoothness", "size", "last leg", "position"}
        together = np.logical_and.reduce([v.all(axis=1) for v in m.values()])
        assert np.array_equal(together, same_mask(A, shapes, row, cand))
        # each part per timeframe against the scalar rule's reasons (picture.same_tf)
        for k in range(0, 300, 11):
            for t in range(2):
                why = " ".join(same_tf(feats[row][t], feats[k][t], shapes[row][t], shapes[k][t]))
                assert m["structure"][k, t] == ("swing structure" not in why)
                assert m["last top/bottom"][k, t] == ("last top / bottom" not in why)
                assert m["outline"][k, t] == ("outline " not in why.replace("'s outline", ""))
                assert m["thirds' outline"][k, t] == ("'s outline" not in why)
                assert m["size"][k, t] == ("size" not in why)
                assert m["position"][k, t] == ("position" not in why)
                assert m["pullback"][k, t] == ("pullback" not in why)
                assert m["smoothness"][k, t] == ("smoothness" not in why)
                assert m["120 bars' way"][k, t] == ("120 bars' way" not in why)
                assert m["thirds' way"][k, t] == ("'s way" not in why)
                assert m["last leg"][k, t] == ("last leg" not in why and "no last leg" not in why)
                hits += int(not why)
    assert hits > 0  # some pairs pass every part (the test sees both outcomes)


def test_tables_by_hand():
    # two snaps, two parts: snap 1 - a passes candidate 1, b candidate 2 (no candidate passes both);
    # snap 2 - a passes both candidates, b the first
    per = [dict(a=np.array([True, False]), b=np.array([False, True])), dict(a=np.array([True, True]), b=np.array([True, False]))]
    s = summarize(per, ("a", "b"))
    assert s.rule.tolist() == ["every part", "without a", "without b"]
    assert s.snaps_with_a_match.tolist() == [0.5, 1.0, 1.0]
    assert s.median_matches.tolist() == [0.5, 1.0, 1.5]
    assert s.part_alone_passes.iloc[1:].tolist() == [0.75, 0.5]
    c = cumulative(per, ("b", "a"))  # the least selective first: a (0.75), then b
    assert c.added.tolist() == ["a", "b"]
    assert c.snaps_with_a_match.tolist() == [1.0, 0.5]
    assert c.median_matches.tolist() == [1.5, 0.5]
