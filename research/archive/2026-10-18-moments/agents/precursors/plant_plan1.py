"""The measurer's own planted bugs in dev1's plan1.py, applied in memory (source edited and re-executed in the module's
namespace before pytest imports test_plan1), so dev/ is never touched.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/plant_plan1.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DEV = Path(__file__).resolve().parents[1] / "dev"
BUGS = [
    ("the sell stop checked before the buy stop", "        if ask[j] >= up:\n            hit = (j, 1, max(up, ask[j]) + slip + extra)\n            break\n        if bid[j] <= dn:\n            hit = (j, -1, min(dn, bid[j]) - slip - extra)\n            break",
     "        if bid[j] <= dn:\n            hit = (j, -1, min(dn, bid[j]) - slip - extra)\n            break\n        if ask[j] >= up:\n            hit = (j, 1, max(up, ask[j]) + slip + extra)\n            break"),
    ("the straddle fills at the trigger, never worse on a gap", "hit = (j, 1, max(up, ask[j]) + slip + extra)", "hit = (j, 1, up + slip + extra)"),
    ("the straddle reference is the first tick at t0", "i0 = int(np.searchsorted(t, t0, side=\"left\")) - 1", "i0 = int(np.searchsorted(t, t0, side=\"left\"))"),
    ("a trade filled exactly at the exit is dropped", "        if a < busy:", "        if a <= busy:"),
    ("the P1 rule includes P2", '    G = T[T.part == "P1"]', "    G = T"),
    ("the P1 rule halves at <= 0", "if g.R.mean() < 0}", "if g.R.mean() <= 0.01}"),
    ("unknown state weighs 0.5", "W.get((p, s), 1.0)", "W.get((p, s), 0.5)"),
]
RUNNER = r'''
import sys, importlib, inspect, pytest
sys.path.insert(0, r"{dev}")
mod = importlib.import_module("plan1")
src = inspect.getsource(mod)
assert src.count({old!r}) == 1, "pattern not unique"
exec(compile(src.replace({old!r}, {new!r}), mod.__file__, "exec"), mod.__dict__)
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", "-x", r"{dev}\test_plan1.py"]))
'''


def main() -> None:
    caught = 0
    for name, old, new in BUGS:
        r = subprocess.run([sys.executable, "-c", RUNNER.format(dev=DEV, old=old, new=new)], capture_output=True, text=True,
                           cwd=DEV, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if "pattern not unique" in r.stderr:
            print(f"BAD PATTERN  {name}")
            continue
        tail = (r.stdout.strip().splitlines() or [r.stderr[-200:]])[-1]
        ok = r.returncode != 0
        caught += ok
        print(f"{'CAUGHT' if ok else 'MISSED'}  {name}  | {tail}")
    print(f"{caught} / {len(BUGS)} caught")


if __name__ == "__main__":
    main()
