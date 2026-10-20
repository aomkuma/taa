"""Planted bugs in m1sim.py (row 45): each mutant must make test_m1sim.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "m1sim.py").read_text()
MUT = [
    ("entry = o[i_in] + spr[i_in] + slip", "entry = o[i_in] + slip"),  # the buy fills at the bid
    ("if h[k] + spr[k] >= stop", "if h[k] >= stop"),  # the sell stop read on the bid
    ("lo[k] + spr[k] <= target", "lo[k] <= target"),  # the sell target on the bid
    ("(min(o[k], stop) if k > i_in else stop)", "stop"),  # no gap fill
    ("if lo[k] <= stop:", "if lo[k] < stop - 1e9:"),  # the buy stop never fires
    ("px = c[last] if side > 0 else c[last] + spr[last]", "px = c[last]"),  # the sell time exit on the bid
    ("for k in range(i_in, last + 1):", "for k in range(i_in + 1, last + 1):"),  # the entry bar skipped
    ("if risk <= 0:", "if risk < -1e9:"),  # a fill past the stop accepted
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "m1sim.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_m1sim.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "m1sim.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + f"  {b}")
