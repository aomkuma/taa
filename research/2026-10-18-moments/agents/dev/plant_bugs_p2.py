"""Planted bugs for p2_trades.py (Task P2): each a small edit of the source run against test_p2_trades.py in a temporary
copy (the harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT). The unedited source runs first.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_p2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "p2_trades.py", HERE / "test_p2_trades.py"
BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("B: the extreme touched does not cancel", [("if lo[k] <= extreme:", "if lo[k] < extreme:")]),
    ("B: a new-high bar is also checked as the pullback", [("            elif hi - lo[k] >= pb_atr * atr:", "            if hi - lo[k] >= pb_atr * atr:")]),
    ("B: the pullback needs more than 1 ATR", [("elif hi - lo[k] >= pb_atr * atr:", "elif hi - lo[k] > pb_atr * atr:")]),
    # (an earlier bug here - "a close above before any pullback confirms", the `continue` removed - was equivalent: in
    # the first phase the high bounds every close, so it changed nothing)
    ("B: the high not frozen after the pullback",
     [("        pull = min(pull, lo[k])\n        if c[k] > hi:", "        pull = min(pull, lo[k])\n        hi = max(hi, h[k])\n        if c[k] > hi:")]),
    ("B: a close at the high confirms", [("if c[k] > hi:", "if c[k] >= hi:")]),
    ("B: one bar more to wait", [("range(d + 1, min(d + max_wait, len(c) - 1) + 1)", "range(d + 1, min(d + max_wait + 1, len(c) - 1) + 1)")]),
    ("B: the pullback low is the first dip only", [("        pull = min(pull, lo[k])\n", "")]),
    ("B: the sell's mirror keeps the signs", [('dict(k=x["k"], hi=-x["hi"], pull=-x["pull"])', 'dict(k=x["k"], hi=x["hi"], pull=x["pull"])')]),
    ("pivots: troughs and peaks swapped", [("lt[pc[pk == -1]] = pp[pk == -1]", "lt[pc[pk == 1]] = pp[pk == 1]")]),
    ("pivots: placed at the pivot bar, not the confirming bar", [("lt[pc[pk == -1]] = pp[pk == -1]", "lt[pb[pk == -1]] = pp[pk == -1]")]),
    ("structure: the bar before the entry read too", [("b0 = int(np.searchsorted(t_open, t_entry, side=\"left\"))", "b0 = max(int(np.searchsorted(t_open, t_entry, side=\"left\")) - 1, 0)")]),
    ("structure: the bar closing at the limit left out", [("b1 = int(np.searchsorted(avail, t_limit, side=\"right\"))", "b1 = int(np.searchsorted(avail, t_limit, side=\"left\"))")]),
    ("structure: a buy exits on a close at the trough", [("np.nonzero(cc < lt[b0:b1])[0]", "np.nonzero(cc <= lt[b0:b1])[0]")]),
    ("structure: a sell reads the troughs", [("np.nonzero(cc > lp[b0:b1])[0]", "np.nonzero(cc > lt[b0:b1])[0]")]),
    ("simulate: the entry slippage the wrong way", [("entry = ask[f] + SLIP + extra if side > 0 else bid[f] - SLIP - extra", "entry = ask[f] - SLIP + extra if side > 0 else bid[f] + SLIP - extra")]),
    ("simulate: the news cost not paid", [("entry = ask[f] + SLIP + extra if side > 0 else bid[f] - SLIP - extra", "entry = ask[f] + SLIP if side > 0 else bid[f] - SLIP")]),
    ("simulate: a buy enters on the bid", [("entry = ask[f] + SLIP + extra if side > 0", "entry = bid[f] + SLIP + extra if side > 0")]),
    ("simulate: the stop filled at its level (the gap lost)", [('px = target if why == "target" else float(mkt[i])', 'px = target if why == "target" else (stop if why == "stop" else float(mkt[i]))')]),
    ("simulate: the stop needs a tick beyond it", [("s = np.nonzero(side * (mkt[seg] - stop) <= 0)[0]", "s = np.nonzero(side * (mkt[seg] - stop) < 0)[0]")]),
    ("simulate: a sell's stop read on the bid", [("mkt = bid if side > 0 else ask", "mkt = bid")]),
    ("simulate: the target filled at the tick", [('px = target if why == "target" else float(mkt[i])', "px = float(mkt[i])")]),
    ("simulate: the stop after the others on one tick", [('ORDER = {"stop": 0, "target": 1,', 'ORDER = {"stop": 5, "target": 1,')]),
    ("simulate: the structure before the stop on one tick", [('"structure": 2, "time": 3, "break": 4}', '"structure": -1, "time": 3, "break": 4}')]),
    ("simulate: a gap of exactly 30 minutes is a break", [("np.diff(t[f:end + 1]) > GAP_NS", "np.diff(t[f:end + 1]) >= GAP_NS")]),
    ("simulate: the break after the gap", [('ev.append((f + int(gaps[0]), "break"))', 'ev.append((f + int(gaps[0]) + 1, "break"))')]),
    ("simulate: the time exit one tick early", [('ev.append((end, "time"))', 'ev.append((end - 1, "time"))')]),
    ("simulate: the entry at the tick before t_entry", [("f = int(np.searchsorted(t, t_entry, side=\"left\"))", "f = max(int(np.searchsorted(t, t_entry, side=\"left\")) - 1, 0)")]),
    ("simulate: the structure exit one tick late", [("k = int(np.searchsorted(t, t_struct, side=\"left\"))", "k = int(np.searchsorted(t, t_struct, side=\"right\"))")]),
    ("simulate: R over the risk at the decision", [("R=float(pnl / risk)", "R=float(pnl / abs(stop))")]),
    ("is_news: 16 minutes", [("t_entry - news[k] <= NEWS_MIN * NS_MIN", "t_entry - news[k] <= (NEWS_MIN + 1) * NS_MIN")]),
    ("is_news: before the release counts", [("k = int(np.searchsorted(news, t_entry, side=\"right\")) - 1\n    return bool(k >= 0 and t_entry - news[k] <= NEWS_MIN * NS_MIN)",
                                            "k = int(np.searchsorted(news, t_entry, side=\"right\")) - 1\n    return bool(np.any(np.abs(news - t_entry) <= NEWS_MIN * NS_MIN))")]),
    ("agreement: a same-side pattern ignored", [("    if other_pattern:\n        return \"with\"\n", "")]),
    ("agreement: the side flipped", [('return "with" if (other_structure == "up") == (side > 0) else "against"', 'return "with" if (other_structure == "up") != (side > 0) else "against"')]),
    ("candidates: B1's stop on the wrong side", [('stop = conf["pull"] - r.side * STOP_ATR * float(r.atr)', 'stop = conf["pull"] + r.side * STOP_ATR * float(r.atr)')]),
    ("candidates: B1 uses the pattern's stop", [('if variant == "B1" else float(r.stop)', 'if variant == "X" else float(r.stop)')]),
    ("candidates: B enters at the breakout", [('t_entry, close = int(tf.avail[conf["k"]]), float(tf.c[conf["k"]])', "t_entry, close = int(r.t_dec), float(r.close)")]),
    ("candidates: ties by the larger risk", [('.sort_values(["t_entry", "risk_dec"], kind="stable")', '.sort_values(["t_entry", "risk_dec"], ascending=[True, False], kind="stable")')]),
    ("one_trade: a target within one risk", [('r.side * (r.next_level - x["entry"]) > x["risk"]', 'r.side * (r.next_level - x["entry"]) >= x["risk"]')]),
    ("one_trade: the time limit 61 bars", [("t_limit = int(r.t_entry + HOLD * tf.minutes * NS_MIN)", "t_limit = int(r.t_entry + (HOLD + 1) * tf.minutes * NS_MIN)")]),
    ("run_stream: an entry at the exit moment skipped", [("if r.t_entry < busy:", "if r.t_entry <= busy:")]),
    ("run_stream: no position limit", [("        busy = x[\"exit_t\"]\n", "")]),
    ("stats: the drawdown from the first trade", [("np.maximum.accumulate(np.r_[0.0, eq]) - np.r_[0.0, eq]", "np.maximum.accumulate(eq) - eq")]),
    ("stats: a flat trade counts as a loss", [("if v < 0:", "if v <= 0:")]),
    ("stats: the R range without the 1.96", [("half = 1.96 * sd / np.sqrt(n)", "half = sd / np.sqrt(n)")]),
    ("stats: not in time order", [('T = T.sort_values("entry_t")', "T = T")]),
    ("weekdays: the part's end day counted", [('pd.bdate_range(a, b, inclusive="left")', 'pd.bdate_range(a, b, inclusive="both")')]),
    ("reason: a sell read on the bid", [('fav = side * ((bid if side > 0 else ask)[f + 1:e + 1] - x["entry"])', 'fav = side * (bid[f + 1:e + 1] - x["entry"])')]),
    ("reason: the tick at the limit left out", [('fav = side * ((bid if side > 0 else ask)[f + 1:e + 1]', 'fav = side * ((bid if side > 0 else ask)[f + 1:e]')]),
    ("reason: ran later needs more than one risk", [('up, dn = np.nonzero(fav >= x["risk"])[0]', 'up, dn = np.nonzero(fav > x["risk"])[0]')]),
    ("Ticks: the exam day loaded", [("tk = learning_ticks(d) if d < EXAM_START else None", "tk = learning_ticks(d)")]),
]


LOSER_BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("losers: every variant", [("L = A[(A.variant == variant) & (A.news_cost == 0.0) & (A.pnl < 0)].copy()",
                                "L = A[(A.news_cost == 0.0) & (A.pnl < 0)].copy()")]),
    ("losers: every cost run", [("L = A[(A.variant == variant) & (A.news_cost == 0.0) & (A.pnl < 0)].copy()",
                                 "L = A[(A.variant == variant) & (A.pnl < 0)].copy()")]),
    ("losers: winners too", [("(A.news_cost == 0.0) & (A.pnl < 0)].copy()", "(A.news_cost == 0.0)].copy()")]),
    ("losers: joined without the side", [('KEY = ["tf", "t_dec", "family", "side"]', 'KEY = ["tf", "t_dec", "family"]')]),
    ("losers: a missing catch passes", [('    if out.level.isna().any():\n        raise ValueError("a loser without its catch")\n', "")]),
    ("title: UTC, not Thai time", [("{CP.thai(r.entry_t, '%Y-%m-%d %H:%M')} Thai", "{pd.Timestamp(int(r.entry_t), tz='UTC'):%Y-%m-%d %H:%M} Thai")]),
    ("title: the stop shown as the exit", [("out \"\n            f\"{r.exit} {r.exit_px:.2f}", "out \"\n            f\"{r.exit} {r.stop:.2f}")]),
]
ROOT = HERE.parents[3]
TARGETS = [  # (the module, its tests, the python that runs them, the bugs)
    (MOD, TEST, Path(sys.executable), BUGS),
    (HERE / "losers_p2.py", HERE / "test_losers_p2.py", ROOT / "data/venv-research/Scripts/python.exe", LOSER_BUGS),
]


def main() -> None:
    total = caught = 0
    for mod, test, py, bugs in TARGETS:
        src = mod.read_text(encoding="utf-8")
        ok, line = run(src, mod, test, py)
        print(f"\n{mod.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
        if not ok:
            raise SystemExit("the unedited source must pass first")
        for name, edits in bugs:
            total += 1
            ok, line = run(mutate(src, edits), mod, test, py)
            caught += not ok
            print(f"{'MISSED' if ok else 'CAUGHT'}  #{total:02d} {mod.stem}: {name}  ({line})", flush=True)
    print(f"\n{caught} of {total} planted bugs caught")


if __name__ == "__main__":
    main()
