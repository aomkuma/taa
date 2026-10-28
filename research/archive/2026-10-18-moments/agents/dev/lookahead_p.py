"""The no-look-ahead check for patterns.py (Task P), on the real M1 of the learning parts.

1. Truncation: the production ZigZag runs over the whole series; at a sample of decision bars its pivots confirmed by
   bar d must equal the ZigZag run on the bars up to d only (M1 and M5).
2. Replacement: for every located catch (and a sample of other bars), everything read at the decision - the patterns
   breaking out at that bar, the owner's H1 levels at that moment, the other TF's structure - computed on a window of
   M1 around it, then again with every M1 bar from the decision on replaced by other prices; all must stay equal.
   Power: moving only the decision bar's close changes the patterns found at it.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_p.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patterns as P  # noqa: E402

NS_MIN = 60 * 10**9


def canon(ps: list[dict]) -> list[tuple]:
    """Patterns as comparable tuples (times instead of bar numbers are not needed: both windows share the bars)."""
    out = []
    for p in ps:
        out.append((p["family"], p["side"], p["variant"], round(p["trigger"], 9), round(p["extreme"], 9),
                    round(p["stop"], 9), tuple((b, round(x, 9), lab) for b, x, lab in p["points"])))
    return sorted(out)


def readings(m: pd.DataFrame, t_dec: int, minutes: int) -> dict:
    """Everything read at the decision t_dec on the TF of `minutes`, from this M1 window."""
    from zones import levels_at  # noqa: PLC0415

    tf, other = P.TF(m, minutes), P.TF(m, 5 if minutes == 1 else 1)
    d = int(np.searchsorted(tf.avail, t_dec))
    assert tf.avail[d] == t_dec
    L, a = levels_at(P.level_inputs(m), t_dec, float(tf.c[d]))
    return dict(patterns=canon(P.patterns_at(tf.h, tf.lo, tf.c, tf.atr, tf.piv, d)), levels=L.round(9).values.tolist(),
                h1_atr=round(a, 9), other=P.m_structure(other.piv, other.last_complete(t_dec)), d=d)


def replaced(m: pd.DataFrame, t_dec: int, rng: np.random.Generator) -> pd.DataFrame:
    """Every M1 bar opening at / after t_dec replaced by a random path +- 40 USD (other highs, lows, closes)."""
    x = m.copy()
    k = int(np.searchsorted(x.index.as_unit("ns").asi8, t_dec))
    n = len(x) - k
    if n <= 0:
        return x
    p = float(x.close.iloc[k - 1]) + 40 * np.sin(np.arange(n) / 37) + np.cumsum(rng.normal(0, 2, n))
    x.iloc[k:, x.columns.get_loc("open")] = p
    x.iloc[k:, x.columns.get_loc("close")] = p + rng.normal(0, 1, n)
    x.iloc[k:, x.columns.get_loc("high")] = np.maximum(p, x.close.iloc[k:]) + rng.uniform(0, 3, n)
    x.iloc[k:, x.columns.get_loc("low")] = np.minimum(p, x.close.iloc[k:]) - rng.uniform(0, 3, n)
    return x


def main() -> None:
    rng = np.random.default_rng(20261019)
    m = P.load_m1()
    C = pd.read_parquet(P.HERE / "p_catches.parquet")
    # 1. truncation of the production ZigZag
    for minutes, n_s in ((1, 150), (5, 150)):
        tf = P.TF(m, minutes)
        a = int(np.searchsorted(tf.avail, P.LEARN_START.value))
        ds = np.sort(rng.choice(np.arange(a, len(tf.c)), n_s, replace=False))
        same = 0
        for d in ds:
            full = [x[tf.piv[3] <= d] for x in tf.piv]
            cut = P.zigzag(tf.h[:d + 1], tf.lo[:d + 1], tf.atr[:d + 1])
            same += all(np.array_equal(u, v) for u, v in zip(full, cut, strict=True))
        print(f"1. M{minutes}: the pivots confirmed by d equal the ZigZag on the bars up to d: {same} of {len(ds)}", flush=True)
        if same != len(ds):
            raise SystemExit("LOOK-AHEAD CHECK FAILED (truncation)")
    # 2. replacement, on every located catch and 300 other M1 / 150 other M5 decisions
    t_all = {1: P.TF(m, 1).avail, 5: P.TF(m, 5).avail}
    cases = [(int(r.t_dec), int(r.tf[1:])) for r in C.itertuples()]
    for minutes, n_s in ((1, 300), (5, 150)):
        av = t_all[minutes]
        av = av[(av >= P.LEARN_START.value) & (av < P.EXAM_START.value - 2 * 86400 * 10**9)]
        cases += [(int(t), minutes) for t in rng.choice(av, n_s, replace=False)]
    eq = changed = power = power_n = 0
    bad = []
    idx = m.index.as_unit("ns").asi8
    for k, (t_dec, minutes) in enumerate(cases):
        a = int(np.searchsorted(idx, t_dec - 7 * 1440 * NS_MIN))
        b = int(np.searchsorted(idx, t_dec + 1440 * NS_MIN))
        w = m.iloc[a:b]
        r0 = readings(w, t_dec, minutes)
        w2 = replaced(w, t_dec, rng)
        r1 = readings(w2, t_dec, minutes)
        if r0 == r1:
            eq += 1
        else:
            bad.append((pd.Timestamp(t_dec, tz="UTC"), minutes))
        if k % 4 == 0:  # power: the same window, only the decision bar's close (on its TF) moved by 3 ATR
            tf = P.TF(w, minutes)
            d = r0["d"]
            c2 = tf.c.copy()
            c2[d] += (3 if k % 8 == 0 else -3) * tf.atr[d]
            before = canon(P.patterns_at(tf.h, tf.lo, tf.c, tf.atr, tf.piv, d))
            after = canon(P.patterns_at(tf.h, tf.lo, c2, tf.atr, tf.piv, d))
            if before:
                power_n += 1
                power += before != after
        changed += _after(w2, t_dec, minutes) != _after(w, t_dec, minutes)
        if (k + 1) % 500 == 0:
            print(f"   {k + 1} of {len(cases)} checked", flush=True)
    print(f"2. the readings at the decision equal after every later M1 bar was replaced: {eq} of {len(cases)}"
          + (f"; DIFFERENT: {bad[:10]}" if bad else ""))
    print(f"   power: the structure 10 bars after the decision changed in {changed} of {len(cases)}; moving the decision "
          f"bar's close by 3 ATR changed the patterns found at it in {power} of {power_n} (decisions with a pattern)")
    if eq != len(cases):
        raise SystemExit("LOOK-AHEAD CHECK FAILED (replacement)")
    print("PASSED")


def _after(w: pd.DataFrame, t_dec: int, minutes: int) -> list[tuple]:
    """The structure 10 bars after the decision on window w (to show the replacement is real)."""
    tf = P.TF(w, minutes)
    d = min(int(np.searchsorted(tf.avail, t_dec)) + 10, len(tf.c) - 1)
    return P.structure(tf.piv, tf.h, tf.lo, d)


if __name__ == "__main__":
    main()
