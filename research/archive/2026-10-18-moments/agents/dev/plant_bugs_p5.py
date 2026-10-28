"""Planted bugs for p5_patterns.py (Task P5), run against test_p5_patterns.py in a temporary copy (the harness of
plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_p5.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "p5_patterns.py", HERE / "test_p5_patterns.py"
BUGS = [
    ("map_to_m1: the bar complete AT the close left out", [('k = np.searchsorted(b_avail, m1_close, side="right") - 1', 'k = np.searchsorted(b_avail, m1_close, side="left") - 1')]),
    ("day H: the last bar's true range only", [("exp = np.cumsum(tr) / np.arange(1, len(tr) + 1)", "exp = tr")]),
    ("double: the sweep twice as deep", [("if above_p2 and t2[1] - sw <= t3[1] <= t2[1] + eq and", "if above_p2 and t2[1] - 2 * sw <= t3[1] <= t2[1] + eq and")]),
    ("double: a higher 2nd low counts as equal", [("if above_p2 and t2[1] - sw <= t3[1] <= t2[1] + eq and", "if above_p2 and t2[1] - sw <= t3[1] <= t2[1] + 2 * eq and")]),
    ("double: no height rule", [("p2[1] - min(t2[1], t3[1]) >= main and d - t2[0] <= SPAN5:", "d - t2[0] <= SPAN5:")]),
    ("triple: the 2nd low not checked", [("if (above_p2 and t1[1] - sw <= t2[1] <= t1[1] + eq and min", "if (above_p2 and min")]),
    ("triple: the trigger the first high", [('extreme=min(lows), trigger=p2[1],', 'extreme=min(lows), trigger=p1[1],')]),
    ("ihs: the head need not be below by EQ", [("if (t2[1] < min(t1[1], t3[1]) - eq and", "if (t2[1] < min(t1[1], t3[1]) and")]),
    ("ihs: no height rule", [("and hgt >= main and P.first_close_above(c, line, t3[0], d)):", "and P.first_close_above(c, line, t3[0], d)):")]),
    ("retest: the level need not have risen a main swing", [("or pk[1] - before[1] < main:", "or pk[1] - before[1] < 0:")]),
    ("retest: the retest may sit far below the level", [("not (pk[1] - eq <= t3[1] <= pk[1] + eq)", "not (pk[1] - 4 * eq <= t3[1] <= pk[1] + eq)")]),
    ("retest: no bounce rule", [("if top - t3[1] >= inn and P.first_close_above", "if P.first_close_above")]),
    ("mirror: the labels kept", [("q[\"points\"] = [(b, -x, SELL_LABELS5.get(lab, lab)) for b, x, lab in p[\"points\"]]", "q[\"points\"] = [(b, -x, lab) for b, x, lab in p[\"points\"]]")]),
    ("channel: not parallel accepted", [("if abs(su - sl) > CH_PAR * max(abs(su), abs(sl)):", "if abs(su - sl) > 10 * max(abs(su), abs(sl)):")]),
    ("channel: an earlier close outside ignored", [("if len(bars) and (np.any(c[last:d] > up(bars)) or np.any(c[last:d] < dn(bars))):\n        return []\n    side = 1 if c[d] > up(d) else -1 if c[d] < dn(d) else 0\n    if not side:\n        return []\n    return [dict(family=\"channel\"",
                                                    "if False:\n        return []\n    side = 1 if c[d] > up(d) else -1 if c[d] < dn(d) else 0\n    if not side:\n        return []\n    return [dict(family=\"channel\"")]),
    ("channel: too short accepted", [("not (CH_MIN_BARS <= d - first <= SPAN5)", "not (0 <= d - first <= SPAN5)")]),
    ("triangle: no size rule", [("or abs(a[1] - b[1]) < main:", ":")]),
    ("triangle: C above A accepted", [("if not (s * (a[1] - cc[1]) > 0 and", "if not (True and")]),
    ("base: the width read at the breakout bar", [("w = main[d - 1]", "w = main[d]")]),
    # (an earlier bug - "base: 19 bars enough" - was equivalent: the fast test r20[d - 1] <= the width means the 20 bars
    # ending at d - 1 fit, so the run always reaches 20 bars before a 19-bar run could be the last one kept)
    ("base: the shortest run, not the longest", [("        if n >= BASE5_MIN:\n            best = (n, hi, low)", "        if n >= BASE5_MIN and best is None:\n            best = (n, hi, low)")]),
    ("base: a close at the top breaks", [("side = 1 if c[d] > hi else -1 if c[d] < low else 0", "side = 1 if c[d] >= hi else -1 if c[d] < low else 0")]),
    ("opens: Saturdays", [("if t.weekday() < 5 and start <= t.tz_convert(\"UTC\") < end:", "if t.weekday() < 6 and start <= t.tz_convert(\"UTC\") < end:")]),
    ("opens: New York at UTC-5 always", [('(("Asia/Bangkok", 7, 0, "Asia"), ("Asia/Bangkok", 13, 0, "London"),\n                                   ("America/New_York", 9, 30, "NY"))',
                                          '(("Asia/Bangkok", 7, 0, "Asia"), ("Asia/Bangkok", 13, 0, "London"),\n                                   ("Etc/GMT+5", 9, 30, "NY"))')]),
    ("fake open: the leg allowed after 15 minutes", [("            if t_open[j] >= o + FO_LEG * NS_MIN:", "            if t_open[j] >= o + 4 * FO_LEG * NS_MIN:")]),
    ("fake open: the reversal allowed after 60 minutes", [("            if t_open[k] >= o + FO_WIN * NS_MIN:", "            if t_open[k] >= o + 2 * FO_WIN * NS_MIN:")]),
    ("fake open: the trade the same side as the leg", [("out.append(dict(family=\"fake_open\", variant=name, side=-s1,", "out.append(dict(family=\"fake_open\", variant=name, side=s1,")]),
    ("forming: no pullback needed", [("if not (c[d] <= pb[1] - eq and c[d] > t[1])", "if not (c[d] > t[1])")]),
    ("forming: a broken top still forming", [("or np.any(c[pb[0] + 1:d + 1] > top):", ":")]),
    ("forming: P_b may be far above", [("if not (pa[1] - eq <= pb[1] <= pa[1] + sw)", "if not (pa[1] - eq <= pb[1] <= pa[1] + 3 * sw)")]),
    ("forming: A's stop below the top", [("a=dict(side=-1, trigger=low, stop=top + STOP_IN * inn, target=low - hgt),", "a=dict(side=-1, trigger=low, stop=top - STOP_IN * inn, target=low - hgt),")]),
    ("forming: B's target from the low", [("b=dict(side=1, trigger=top, stop=low - STOP_IN * inn, target=top + hgt))", "b=dict(side=1, trigger=top, stop=low - STOP_IN * inn, target=low + hgt))")]),
]


def main() -> None:
    py = Path(sys.executable)
    src = MOD.read_text(encoding="utf-8")
    ok, line = run(src, MOD, TEST, py)
    print(f"{MOD.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits), MOD, TEST, py)
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
