"""The measurer's own planted bugs in the auditor's round-2 changes (item 1 win = pnl > 0 in wf.weekly; item 4
plib.load_learning / gold.bars(before=)), applied in memory only (the module's source is edited and re-executed in its
own namespace before pytest imports the tests), so no file on disk changes.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/plant_audit2_r2.py
"""

from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
from pathlib import Path

AG = Path(__file__).resolve().parents[1]
BUGS = [
    ("wf", "weekly: break-even counts as a win", '"win": g.pnl.agg(lambda x: (x > 0).mean())', '"win": g.pnl.agg(lambda x: (x >= 0).mean())'),
    ("wf", "walk_forward: win from R > -0.5", "win=round((got.pnl > 0).mean(), 3)", "win=round((got.R > -0.5).mean(), 3)"),
    ("plib", "load_learning keeps the exam's first minute", "learn = learn.loc[(learn.index >= start) & (learn.index < EXAM_START)]",
     "learn = learn.loc[(learn.index >= start) & (learn.index <= EXAM_START)]"),
    ("plib", "load_learning reads the stores unfiltered", 'learn = gold.bars("M1", before=EXAM_START)', 'learn = gold.bars("M1")'),
    ("gold", "bars(before=) filters with <=", 'flt = None if before is None else [("open_time", "<", pd.Timestamp(before).tz_convert("UTC"))]',
     'flt = None if before is None else [("open_time", "<=", pd.Timestamp(before).tz_convert("UTC"))]'),
]
RUNNER = r'''
import sys, importlib, inspect, pytest
sys.path[:0] = [r"{pre}", r"{root}", r"{audit}"]
mod = importlib.import_module("{mod}")
src = inspect.getsource(mod)
assert src.count({old!r}) == 1, "pattern not unique"
exec(compile(src.replace({old!r}, {new!r}), mod.__file__, "exec"), mod.__dict__)
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", "-x", r"{audit}", "-k", "not real"]))
'''


def main() -> None:
    caught = 0
    for mod, name, old, new in BUGS:
        code = RUNNER.format(pre=AG / "precursors", root=AG.parent, audit=AG / "audit2", mod=mod, old=old, new=new)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=AG / "audit2",
                           env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
        tail = (r.stdout.strip().splitlines() or [r.stderr[-300:]])[-1]
        ok = r.returncode not in (0,) and "pattern not unique" not in r.stderr
        caught += ok
        print(f"{'CAUGHT' if ok else 'MISSED'}  {mod}: {name}  | {tail}")
    print(f"{caught} / {len(BUGS)} caught")


if __name__ == "__main__":
    main()
