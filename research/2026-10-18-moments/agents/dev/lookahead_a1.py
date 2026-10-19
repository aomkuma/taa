"""The no-look-ahead check for sweep_detector (checkpoint A1), on the real ticks of every learning event (the 08:30 /
10:00 New York minutes and the calendar's release minutes, P1 and P2; each minute once).

1. The decision readings (`first_minute`, both side rules): every tick at / after the decision (the release + 60 s)
   is replaced by other prices - (a) a seeded random path at other times and another count, (b) the real future
   mirrored around p0 - and every reading must stay exactly equal.
2. Power: the same replacement changes the label (`race`) on many events, and moving only the last tick before the
   decision by 5 USD changes the readings on every event with a first-minute tick - the check can see a change.
3. The label reads only its windows: every tick at / after the release + WIN_MIN + BACK_MIN minutes replaced, the
   label (`race`) stays exactly equal.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_a1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_detector import (  # noqa: E402
    BACK_MIN,
    FIRST_S,
    NS_MIN,
    NS_S,
    WIN_MIN,
    calendar_events,
    first_minute,
    fixed_events,
    learning_ticks,
    race,
)


def same(a: dict, b: dict) -> bool:
    return a.keys() == b.keys() and all(a[k] == b[k] for k in a)


def replaced(t: np.ndarray, mid: np.ndarray, cut: int, how: str, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Ticks before cut kept; from cut on: 'random' = 3,000 ticks every 0.37 s around p +- 40 USD, 'mirror' = the real
    later ticks mirrored around the last price before cut."""
    k = int(np.searchsorted(t, cut, side="left"))
    p = mid[k - 1]
    if how == "random":
        tn = cut + (np.arange(3000) * 0.37 * NS_S).astype(np.int64)
        pn = p + 40 * np.sin(np.arange(3000) / 90) + np.cumsum(rng.normal(0, 0.8, 3000))
    else:
        tn, pn = t[k:], 2 * p - mid[k:]
    return np.concatenate([t[:k], tn]), np.concatenate([mid[:k], pn])


def main() -> None:
    ev = pd.concat([fixed_events()[["t"]], calendar_events()[["t"]]]).drop_duplicates().sort_values("t")
    rng = np.random.default_rng(20261019)
    n = eq = label_changed = power = power_n = win_eq = 0
    bad = []
    for day, D in ev.groupby(pd.DatetimeIndex(ev.t).normalize(), sort=True):
        tk = learning_ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        mid = (bid + ask) / 2
        for r in D.itertuples(index=False):
            rel = pd.Timestamp(r.t).value
            cut = rel + FIRST_S * NS_S
            for rule in ("larger", "first"):
                fm = first_minute(t, mid, rel, side_rule=rule)
                if fm is None:
                    continue
                lab = race(t, mid, rel, fm)
                for how in ("random", "mirror"):
                    t2, m2 = replaced(t, mid, cut, how, rng)
                    fm2 = first_minute(t2, m2, rel, side_rule=rule)
                    n += 1
                    if same(fm, fm2):
                        eq += 1
                    else:
                        bad.append((r.t, rule, how))
                    label_changed += race(t2, m2, rel, fm2) != lab
                # power: the last tick before the decision moved by 5 USD
                k = int(np.searchsorted(t, cut, side="left")) - 1
                if t[k] >= rel:
                    m3 = mid.copy()
                    m3[k] += 5.0
                    power_n += 1
                    power += not same(first_minute(t, m3, rel, side_rule=rule), fm)
                # the label's own windows
                t4, m4 = replaced(t, mid, rel + (WIN_MIN + BACK_MIN) * NS_MIN, "random", rng)
                win_eq += race(t4, m4, rel, first_minute(t4, m4, rel, side_rule=rule)) == lab
    n_ev = n // 4
    print(f"events checked: {n_ev} release minutes x 2 side rules x 2 replacements = {n} comparisons")
    print(f"1. the decision readings equal after the future was replaced: {eq} of {n}" + (f"; DIFFERENT: {bad[:10]}" if bad else ""))
    print(f"2. power: the label changed on {label_changed} of {n} replacements; moving the last tick before the decision "
          f"by 5 USD changed the readings on {power} of {power_n}")
    print(f"3. the label equal after every tick from the release + {WIN_MIN + BACK_MIN} min was replaced: {win_eq} of {n // 2}")
    if eq != n or win_eq != n // 2 or power != power_n:
        raise SystemExit("LOOK-AHEAD CHECK FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
