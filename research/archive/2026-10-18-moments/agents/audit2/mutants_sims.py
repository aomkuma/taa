"""Planted bugs for audit 5: surrender.trade / run and tick_straddle.trade / span_ticks against audit2/test_simulators.py
and the earlier precursors/test_surrender.py, test_tick_straddle.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_sims
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PRE = ROOT / "research" / "2026-10-18-moments" / "agents" / "precursors"
TESTS = [
    "research/2026-10-18-moments/agents/audit2/test_simulators.py",
    "research/2026-10-18-moments/agents/precursors/test_surrender.py",
    "research/2026-10-18-moments/agents/precursors/test_tick_straddle.py",
]
SURRENDER = [
    ("a buy filled at the bid", "entry = ask[f] + SLIP if side > 0", "entry = bid[f] + SLIP if side > 0"),
    ("a sell read on the bid", "(entry - ask[seg])  # what closing", "(entry - bid[seg])  # what closing"),
    ("the stop filled at its level (no gap)", 'pnl = target if name == "win" else float(fav[i])',
     'pnl = target if name == "win" else (-stop if name == "stop" else float(fav[i]))'),
    ("the target pays the tick", 'pnl = target if name == "win" else float(fav[i])', "pnl = float(fav[i])"),
    ("the surrender before the stop on one tick", 'ORDER = {"stop": 0, "win": 1, "surrender": 2}',
     'ORDER = {"stop": 2, "win": 1, "surrender": 0}'),
    ("the entry at the last tick before the decision", 'f = int(np.searchsorted(t, t0, side="left"))\n    if f >= len(t):\n        return None\n    entry = ask',
     'f = max(int(np.searchsorted(t, t0, side="left")) - 1, 0)\n    if f >= len(t):\n        return None\n    entry = ask'),
    ("the time exit at the first tick after the hold", "x = max(end - 1, f)", "x = min(end, len(t) - 1)"),
    ("run cut at the UTC day again", "        tk = span_ticks(day)  # the next day joined: a trade open at midnight UTC runs on\n        if tk is None:\n            continue\n        t, bid, ask = tk\n        for r in D.itertuples():",
     "        tk = span_ticks(day)  # the next day joined: a trade open at midnight UTC runs on\n        if tk is None:\n            continue\n        t, bid, ask = tk\n        keep = t < (day + pd.Timedelta(days=1)).value\n        t, bid, ask = t[keep], bid[keep], ask[keep]\n        for r in D.itertuples():"),
]
STRADDLE = [
    ("no next day joined", "    b = day_ticks(nxt)\n", "    b = None\n"),
    ("the exam guard removed", "    if pd.Timestamp(day) < EXAM_START <= nxt:\n", "    if False:\n"),
    ("the buy stop triggered by the bid", "up = np.nonzero(ask[i0:i1] >= c0 + b)[0]", "up = np.nonzero(bid[i0:i1] >= c0 + b)[0]"),
    ("the straddle's stop without its gap", '        px = bid[x] if side > 0 else ask[x]\n        return dict(side=side, exit="stop"',
     '        px = entry - s * side\n        return dict(side=side, exit="stop"'),
    ("the straddle's R over b, not s", 'x["R"] = x["pnl"] / s', 'x["R"] = x["pnl"] / b'),
]
TARGETS = [
    ("surrender", PRE / "surrender.py", TESTS, SURRENDER),
    ("tick_straddle", PRE / "tick_straddle.py", TESTS, STRADDLE),
]

TOUCH_TESTS = ["research/2026-10-18-moments/agents/precursors/test_touches.py", "research/2026-10-18-moments/agents/audit2/test_simulators.py"]
TOUCHES = [
    ("the touch bar's back side counts", "    back[0] = -np.inf\n", ""),
    ("a bar reaching both is a reversal", "    if ri == bi < len(hh):\n        return dict(outcome=\"ambiguous\")\n", ""),
    ("reversed at x - 1", "r, b = np.nonzero(back >= x)[0], np.nonzero(past >= x)[0]", "r, b = np.nonzero(back >= x - 1)[0], np.nonzero(past >= x)[0]"),
    ("the approach from the earliest bar away", "    k = a + int(far[-1])", "    k = a + int(far[0])"),
    ("the approach ignores a touch in between", "    if np.any((lo[k + 1:j] <= level + d) & (h[k + 1:j] >= level - d)):\n        return 0\n", ""),
    ("the next level on the wrong side", "beyond = levels[levels < level - gap] if side > 0", "beyond = levels[levels > level + gap] if side > 0"),
]
TARGETS.append(("touches", PRE / "touches.py", TOUCH_TESTS, TOUCHES))
