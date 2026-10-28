"""Planted bugs in ns1.py, applied in memory before test_ns1 runs (the file on disk is never changed).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/plant_ns1.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUGS = [
    ("the buy trigger from the bid", "up, dn = rb.close + _s(rb) + TRIG, rb.close - TRIG", "up, dn = rb.close + TRIG, rb.close - TRIG"),
    ("no gap fill", "e = max(up, x.open + _s(x)) if side > 0 else min(dn, x.open)", "e = up if side > 0 else dn"),
    ("both reached: the better side", 'worst = min(res, key=lambda r: r["pnl"])', 'worst = max(res, key=lambda r: r["pnl"])'),
    ("the sell's stop on the bid", "(r.low + s, r.high + s, r.open + s)", "(r.low, r.high, r.open)"),
    ("target first in a bar with both", "        if (adverse - stop) * side <= 0:", "        if False:"),
    ("the time exit on the bid for a sell", "px = o.open if side > 0 else o.open + _s(o)", "px = o.open"),
    ("a gapped stop fills at the stop", "px = stop if (op - stop) * side > 0 or t == t0 else op", "px = stop"),
]
RUNNER = r'''
import sys, inspect, pytest
sys.path.insert(0, r"{here}")
import ns1 as M
src = inspect.getsource(M)
assert src.count({old!r}) == 1, "pattern"
exec(compile(src.replace({old!r}, {new!r}), M.__file__, "exec"), M.__dict__)
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", r"{here}\test_ns1.py"]))
'''


def main() -> None:
    caught = 0
    for name, old, new in BUGS:
        r = subprocess.run([sys.executable, "-c", RUNNER.format(here=HERE, old=old, new=new)], capture_output=True,
                           text=True, cwd=HERE, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if "pattern" in r.stderr and "AssertionError" in r.stderr and r.stdout.strip() == "":
            print(f"BAD PATTERN  {name}")
            continue
        ok = r.returncode != 0
        caught += ok
        print(f"{'CAUGHT' if ok else 'MISSED'}  {name}  | {(r.stdout.strip().splitlines() or [''])[-1]}")
    print(f"{caught} / {len(BUGS)} caught")


if __name__ == "__main__":
    main()
