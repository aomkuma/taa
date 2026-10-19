"""Planted bugs for p3_trades.py (Task P3): each a small edit run against test_p3_trades.py in a temporary copy (the
harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_p3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "p3_trades.py", HERE / "test_p3_trades.py"
BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("invalidation: the base's other edge", [("return float(box_p[0] if side > 0 else box_p[1])", "return float(box_p[1] if side > 0 else box_p[0])")]),
    ("invalidation: the pattern's extreme, not its last point", [("    return float(pts_p[-1])", "    return float(pts_p[0])")]),
    ("close exit: a close AT the price exits", [("hit = np.nonzero(side * (c[b0:b1] - price) < 0)[0]", "hit = np.nonzero(side * (c[b0:b1] - price) <= 0)[0]")]),
    ("close exit: the bar before the entry read", [("    b0 = int(np.searchsorted(t_open, t_entry, side=\"left\"))\n    b1 = int(np.searchsorted(avail, t_limit, side=\"right\"))\n    if b1 <= b0:",
                                                   "    b0 = max(int(np.searchsorted(t_open, t_entry, side=\"left\")) - 1, 0)\n    b1 = int(np.searchsorted(avail, t_limit, side=\"right\"))\n    if b1 <= b0:")]),
    ("close exit: the side ignored", [("hit = np.nonzero(side * (c[b0:b1] - price) < 0)[0]", "hit = np.nonzero(c[b0:b1] - price < 0)[0]")]),
    ("trail schedule: no buffer", [("v = lt[b0:b1] - buffer if side > 0 else lp[b0:b1] + buffer", "v = lt[b0:b1] if side > 0 else lp[b0:b1] + buffer")]),
    ("trail schedule: a sell trails the troughs", [("v = lt[b0:b1] - buffer if side > 0 else lp[b0:b1] + buffer", "v = lt[b0:b1] - buffer if side > 0 else lt[b0:b1] + buffer")]),
    ("trail: break-even needs more than one risk", [("up = np.nonzero(side * (ms - entry) >= risk)[0]", "up = np.nonzero(side * (ms - entry) > risk)[0]")]),
    ("trail: no break-even, only the steps", [("lv[i1:] = np.maximum(side * entry, best)", "lv[i1:] = np.maximum(side * stop, best)")]),
    ("trail: a step before break-even counts", [("sel = tt > t_be", "sel = tt >= 0")]),
    ("trail: the stop can move back", [("steps = np.maximum.accumulate(np.where(np.isnan(vv[sel]), -np.inf, side * vv[sel])) if sel.any() else np.empty(0)",
                                        "steps = np.where(np.isnan(vv[sel]), -np.inf, side * vv[sel]) if sel.any() else np.empty(0)")]),
    ("trail: a step applies one tick late", [("k = np.searchsorted(steps_t, ts[i1:], side=\"right\") - 1", "k = np.searchsorted(steps_t, ts[i1:], side=\"left\") - 1")]),
    ("trail: a moved stop named 'stop'", [('ev.append((f + 1 + int(s[0]), "trail" if moved else "stop"))', 'ev.append((f + 1 + int(s[0]), "stop"))')]),
    ("trail: a moved stop filled at its level (the gap lost)", [('px = target if why == "target" else float(mkt[i])', 'px = target if why == "target" else (stop_exit if why == "trail" else float(mkt[i]))')]),
    ("trail: the stop hit needs a tick beyond", [("s = np.nonzero(side * ms <= lv)[0]", "s = np.nonzero(side * ms < lv)[0]")]),
    ("simulate3: the close exit always named structure", [("            ev.append((k, close_name))", '            ev.append((k, "structure"))')]),
    ("simulate3: the close exit before the stop on one tick", [('ORDER = {"stop": 0, "trail": 0, "target": 1, "structure": 2, "invalid": 2,', 'ORDER = {"stop": 0, "trail": 0, "target": 1, "structure": 2, "invalid": -1,')]),
    ("m5_turned: a lower low counts", [("return bool(len(x) == 2 and side * (x[1] - x[0]) > 0)", "return bool(len(x) == 2 and side * (x[1] - x[0]) != 0)")]),
    ("m5_turned: the pivots confirmed AT b left out", [("n = int(np.searchsorted(pc, b, side=\"right\"))\n    x = pp", "n = int(np.searchsorted(pc, b, side=\"left\"))\n    x = pp")]),
    ("m5_turned: a sell reads the troughs", [("x = pp[:n][pk[:n] == (-1 if side > 0 else 1)][-2:]", "x = pp[:n][pk[:n] == -1][-2:]")]),
    ("L: a close exactly at the measured move is not late", [('if setting.get("late") and r.side * (close - r.trigger) >= r.height:', 'if setting.get("late") and r.side * (close - r.trigger) > r.height:')]),
    ("L: measured from the level", [('if setting.get("late") and r.side * (close - r.trigger) >= r.height:', 'if setting.get("late") and r.side * (close - r.level) >= r.height:')]),
    ("ST: the M5 pattern not accepted", [('or (r.tf == "M1" and bool(r.other_pattern))', "or False")]),
    ("ST: an M1 pattern accepted for an M5 entry", [('or (r.tf == "M1" and bool(r.other_pattern))', "or bool(r.other_pattern)")]),
    ("ST: every family filtered", [('if setting.get("st_m5") and r.family == "st":', 'if setting.get("st_m5"):')]),
    ("one_trade3: the invalid mode uses the structure exit", [('elif "invalid" in exit_mode:\n        t_close, name = close_exit_time(tf.t_open, tf.avail, tf.c, r.invalid, r.side, r.t_entry, t_limit), "invalid"',
                                                              'elif "invalid" in exit_mode:\n        t_close, name = P2.structure_exit_time(tf.t_open, tf.avail, tf.c, lt, lp, r.side, r.t_entry, t_limit), "invalid"')]),
    ("one_trade3: M5 held 60 minutes", [("t_limit = int(r.t_entry + P2.HOLD * tf.minutes * NS_MIN)", "t_limit = int(r.t_entry + P2.HOLD * NS_MIN)")]),
    ("one_trade3: the trail mode keeps the structure exit", [("        t_close, name = None, \"structure\"", "        t_close, name = P2.structure_exit_time(tf.t_open, tf.avail, tf.c, lt, lp, r.side, r.t_entry, t_limit), \"structure\"")]),
    ("trail: the break-even time read after the exit", [("    if t_be is not None and t_be > int(t[i]):\n        t_be = None", "    pass")]),
    ("LEAD: M5 entries dropped", [('if setting.get("lead") and not (r.family == "ihs" or r.tf == "M5"):', 'if setting.get("lead") and not (r.family == "ihs"):')]),
    ("LEAD: the H&S on M1 dropped", [('if setting.get("lead") and not (r.family == "ihs" or r.tf == "M5"):', 'if setting.get("lead") and not (r.tf == "M5"):')]),
    ("a stale fill taken", [("if f >= len(t) or t[f] - t_entry > MAX_LAG_NS:", "if f >= len(t):")]),
    ("ns times stored as floats", [("dtype=\"Int64\")", "dtype=\"float64\")")]),
    ("metrics: the trail exits not counted", [('ORDER = {"stop": 0, "trail": 0,', 'ORDER = {"stop": 0,')]),
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
