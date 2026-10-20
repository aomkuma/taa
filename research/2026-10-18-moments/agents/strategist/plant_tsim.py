"""Planted bugs in tsim.py: each mutant is written to a temporary folder as tsim.py, test_tsim.py is run against it, and
the mutant must make at least one test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/plant_tsim.py > .../strategist/out_plant_tsim.txt
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "tsim.py").read_text(encoding="utf-8")
MUTANTS = {
    "a sell fills at the ask": ("e = ask[f] + slip if s > 0 else bid[f] - slip", "e = ask[f] + slip if s > 0 else ask[f] - slip"),
    "a sell exits on the bid": ("else (ask[f + 1:end + 1] + slip_exit)", "else (bid[f + 1:end + 1] + slip_exit)"),
    "the stop needs more than its distance": ("np.searchsorted(-cmin, d_s, side=\"left\")", "np.searchsorted(-cmin, d_s, side=\"right\")"),
    "the structure before the stop on one tick": ('"structure": 2', '"structure": -1'),
    "the surrender sees the tick at K": ("ran = r > 0 and cmax[r - 1] >= surr[1]", "ran = cmax[r] >= surr[1]"),
    "the structure exit for the other side too": ('if k_struct is not None and sname == "same":', "if k_struct is not None:"),
    "no gap break": ("GAP_NS = 30 * NS_MIN", "GAP_NS = 3000 * NS_MIN"),
    "the time exit one tick early": ('end = int(np.searchsorted(t, t_out, side="left"))', 'end = int(np.searchsorted(t, t_out, side="left")) - 1'),
    "R on the rule's risk": ("R=float(pnl / d_s)", "R=float(pnl / d_s0)"),
    "1R0 on the variant's risk": ("d_t = d_s0\n", "d_t = d_s\n"),
    "the exam guard removed": ("if d >= EXAM_START:\n        raise", "if False:\n        raise"),
    "the slippage default 0.07": ("slip: float = 0.0,\n         slip_exit", "slip: float = 0.07,\n         slip_exit"),
}

caught = 0
for name, (a, b) in MUTANTS.items():
    assert SRC.count(a) == 1, f"mutant '{name}': the pattern is not unique / missing"
    with tempfile.TemporaryDirectory() as d:
        Path(d, "tsim.py").write_text(SRC.replace(a, b), encoding="utf-8")
        shutil.copy(HERE / "test_tsim.py", d)
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_tsim.py"], cwd=d,
                           capture_output=True, text=True, env={"PYTHONDONTWRITEBYTECODE": "1", "SYSTEMROOT": "C:\\Windows"})
        ok = r.returncode != 0
        caught += ok
        last = [x for x in r.stdout.splitlines() if x.strip()][-1] if r.stdout.strip() else r.stderr[-200:]
        print(f"{'CAUGHT' if ok else 'MISSED'}  {name}  ({last})")
print(f"\n{caught} of {len(MUTANTS)} caught")
