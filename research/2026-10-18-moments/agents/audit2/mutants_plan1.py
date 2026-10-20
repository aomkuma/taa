"""Planted bugs for the audit of dev/plan1.py (mutated in memory only; the file is never changed). Each mutant runs
twice: against the developer's own tests alone, then with the auditor's tests added - which gaps the new tests close.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_plan1
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEV = ROOT / "research" / "2026-10-18-moments" / "agents" / "dev"
THEIRS = ["research/2026-10-18-moments/agents/dev/test_plan1.py"]
MINE = ["research/2026-10-18-moments/agents/audit2/test_plan1_audit.py"]

MUTANTS = [
    ("main: the exam built by default", "    every, A = build(a.exam, a.slippage, a.extra)", "    every, A = build(True, a.slippage, a.extra)"),
    ("parse: --exam on by default", '    ap.add_argument("--exam", action="store_true",', '    ap.add_argument("--exam", action="store_false",'),
    ("main: the slippage argument ignored (0.07)", "    every, A = build(a.exam, a.slippage, a.extra)", "    every, A = build(a.exam, 0.07, a.extra)"),
    ("main: the release extra ignored", "    every, A = build(a.exam, a.slippage, a.extra)", "    every, A = build(a.exam, a.slippage, 0.0)"),
    ("repro: M1 read to the exam's end", "        repro(load_m1(EXAM_START, False))", "        repro(load_m1(EXAM_END, True))"),
    ("build: the ticks read to the exam's end", "    ticks = PlanTicks(end)", "    ticks = PlanTicks(EXAM_END)"),
    ("build: the trade-period guard removed",
     "    if len(every) and ((every.t_in < start.value) | (every.t_in >= end.value)).any():", "    if False:"),
    ("build: Asia from the learning start in every mode", "    asia = asia_b2(m, start, end, ticks, slip)",
     "    asia = asia_b2(m, LEARN_START, end, ticks, slip)"),
    ("build: London at slippage 0.07", "    london = london_orb(D1.Market(m), days, ticks, slip)",
     "    london = london_orb(D1.Market(m), days, ticks, 0.07)"),
    ("build: NY without the release extra", "    ny = ny_straddle(days, ticks, slip, extra)", "    ny = ny_straddle(days, ticks, slip, 0.0)"),
    ("build: the state from H4 bars, not D1", '    d1 = bars(m, "1D")', '    d1 = bars(m, "4h")'),
    ("asia_b2: B2 at slippage 0.07", "    with entry_slippage(slip):", "    with entry_slippage(0.07):"),
    ("asia_b2: locate bounded to the exam's end", "    with located_in(start, end):", "    with located_in(start, EXAM_END):"),
    ("asia_b2: entries past the period kept", "            if start.value <= r.t_entry < end.value]", "            if start.value <= r.t_entry]"),
    ("asia_b2: the fill time = the decision", "t_in=int(r.entry_t), t_out", "t_in=int(r.t_entry), t_out"),
    ("asia_b2: the scan from the first bar", "            a = int(np.searchsorted(tf.avail, start.value))", "            a = 0"),
    ("stream: ordered by the exit", '    T = T.sort_values("t_in", kind="stable").reset_index(drop=True)',
     '    T = T.sort_values("t_out", kind="stable").reset_index(drop=True)'),
    ("stream: a dropped trade blocks the next", "        if a < busy:\n            continue", "        if a < busy:\n            busy = max(busy, b)\n            continue"),
]

TARGETS = [("plan1", DEV / "plan1.py", THEIRS, MUTANTS), ("plan1", DEV / "plan1.py", THEIRS + MINE, MUTANTS)]
