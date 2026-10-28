"""Planted bugs for plan1.py (the PLAN-1 runner), each run against test_plan1.py in a temporary copy (the harness of
plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_plan1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import run  # noqa: E402
from plant_bugs_a1 import mutate  # noqa: E402

BUGS = [
    ("guard: the learning period may reach the exam's end", [("if not exam and end > EXAM_START:", "if not exam and end > EXAM_END:")]),
    ("guard: --exam may read any period", [("if exam and (start != EXAM_START or end != EXAM_END):", "if False:")]),
    ("m1: read past 2026-04-18 without the switch", [("if end > EXAM_START and not exam:", "if end > EXAM_END and not exam:")]),
    ("m1: the filter includes the end", [('("open_time", "<", end)]', '("open_time", "<=", end)]')]),
    ("m1: a row at the end let through", [("if len(m) and m.index.max() >= end:", "if len(m) and m.index.max() > end:")]),
    ("ticks: a day at / after the end opened", [("tk = self.read(d) if d < self.end else None", "tk = self.read(d)")]),
    ("locate's bounds not restored", [("        P.LEARN_START, P.EXAM_START = old", "        pass")]),
    ("the slippage not set for B2", [("    P2.SLIP = float(slip)", "    P2.SLIP = P2.SLIP")]),
    ("the default slippage 0.07", [('default=0.0, help="entry slippage', 'default=0.07, help="entry slippage')]),
    ("parts: the end included", [("        if a <= t < b:", "        if a < t <= b:")]),
    ("Asia: the London window taken", [('return cands[cands.window == "Asia"]', 'return cands[cands.window == "London"]')]),
    ("exit: the time one tick late", [("        if t[k] >= t_out:", "        if t[k] > t_out:")]),
    ("exit: the target filled at the market", [('            return (target - entry) * side, "target", k', '            return (px - entry) * side, "target", k')]),
    ("tick_run: the copy not checked", [("    if r[1] != x[1] or r[0] != x[0]:", "    if False:")]),
    ("orb: a sell filled at the bid + slip", [("e = ask[f] + slip if side > 0 else bid[f] - slip", "e = ask[f] + slip if side > 0 else bid[f] + slip")]),
    ("orb: a fill at 5 min refused", [("if f >= len(t) or t[f] - t_dec > ORB_FILL:", "if f >= len(t) or t[f] - t_dec >= ORB_FILL:")]),
    ("orb: the target 3 R", [("e + side * ORB_K * risk, int(", "e + side * 3.0 * risk, int(")]),
    ("orb: the hour from the decision", [("int(t[f] + ORB_X * NS_MIN))", "int(t_dec + ORB_X * NS_MIN))")]),
    ("straddle: the buy stop from the bid", [("up, dn = ask[i0] + STR_TRIG, bid[i0] - STR_TRIG", "up, dn = bid[i0] + STR_TRIG, bid[i0] - STR_TRIG")]),
    ("straddle: the reference the tick at 08:30:00", [('    i0 = int(np.searchsorted(t, t0, side="left")) - 1', '    i0 = int(np.searchsorted(t, t0, side="right")) - 1')]),
    ("straddle: live 61 s", [("k_end = int(np.searchsorted(t, t0 + 60 * NS_S, side=\"left\"))", "k_end = int(np.searchsorted(t, t0 + 61 * NS_S, side=\"left\"))")]),
    ("straddle: the stop from the trigger", [("    stop = e - side * STR_STOP", "    stop = (up if side > 0 else dn) - side * STR_STOP")]),
    ("straddle: no release slippage", [("hit = (j, 1, max(up, ask[j]) + slip + extra)", "hit = (j, 1, max(up, ask[j]) + slip)")]),
    ("straddle: held 15 minutes", [("t0 + STR_HOLD * NS_MIN)", "t0 + 15 * NS_MIN)")]),
    ("straddle: 999 ticks enough", [("if len(t) < 1000 or", "if len(t) < 999 or")]),
    ("straddle: New York time read as UTC", [('tz_localize("America/New_York").tz_convert("UTC").value', 'tz_localize("UTC").value')]),
    ("stream: a fill at the exit dropped", [("        if a < busy:", "        if a <= busy:")]),
    ("stream: not in time order", [('    T = T.sort_values("t_in", kind="stable").reset_index(drop=True)\n    keep', "    T = T.reset_index(drop=True)\n    keep")]),
    ("stream: busy until the fill", [("        busy = b", "        busy = a")]),
    ("state: read one day later", [("pd.to_datetime(np.asarray(t_ns, np.int64), utc=True)", "pd.to_datetime(np.asarray(t_ns, np.int64) + 86400 * NS_S, utc=True)")]),
    ("weights: London full in a trend", [('("London ORB", "trend"): 0.5, ', "")]),
    ("weights: the default half", [("W.get((p, s), 1.0)", "W.get((p, s), 0.5)")]),
    ("weights: the P1 table with NY mixed", [('W_P1 = {("Asia B2", "trend"): 0.5, ("NY straddle", "sideways"): 0.5}', 'W_P1 = {("Asia B2", "trend"): 0.5, ("NY straddle", "sideways"): 0.5, ("NY straddle", "mixed"): 0.5}')]),
    ("P1 rule: a mean of 0 halves", [("if g.R.mean() < 0}", "if g.R.mean() <= 0}")]),
    ("P1 rule: both parts", [('    G = T[T.part == "P1"]\n    return', "    G = T\n    return")]),
    ("summary: the weighted mean over n", [("mean = float(np.sum(r * w) / np.sum(w))", "mean = float(np.sum(r * w) / n)")]),
    ("summary: the DD from the first trade", [("eq = np.r_[0.0, np.cumsum(pnl)]", "eq = np.cumsum(pnl)")]),
    ("summary: a 0 trade continues a streak", [("        if v < 0:", "        if v <= 0:")]),
    ("summary: not in time order", [('o = np.argsort(T.t_in.to_numpy(np.int64), kind="stable")', "o = np.arange(n)")]),
    ("weekly: UTC weeks", [('.tz_convert("Asia/Bangkok")\n    wk', '.tz_convert("UTC")\n    wk')]),
]


def main() -> None:
    py = Path(sys.executable)
    mod, test = HERE / "plan1.py", HERE / "test_plan1.py"
    src = mod.read_text(encoding="utf-8")
    ok, line = run(src, mod, test, py)
    print(f"plan1.py: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits), mod, test, py)
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
