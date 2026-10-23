"""Planted bugs for observe.py (the hour's scoring) against test_observe.py - the same rule as plant.py, for a
research module that is not in a package: the edited copy is registered as ``observe`` before the tests import it.

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_observe.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from plant import ROOT, mutate

HERE = Path(__file__).resolve().parent
PLUGIN = '''import importlib.util, sys
sys.path.insert(0, r"{here}")
spec = importlib.util.spec_from_file_location("observe", r"{path}")
mod = importlib.util.module_from_spec(spec)
sys.modules["observe"] = mod
spec.loader.exec_module(mod)
'''

BUGS = [
    ("the hour includes the bar at as_of (look-ahead)", [("(m1.index < as_of)]\n    if seg.empty", "(m1.index <= as_of)]\n    if seg.empty")]),
    ("the hour starts after the reading's bar", [("seg = m1[(m1.index >= pd.Timestamp", "seg = m1[(m1.index > pd.Timestamp")]),
    ("with / against swapped for a down rhythm", [("(up, down) if s > 0 else (down, up)", "(up, down)")]),
    ("held on a tie or worse", [('out["with"] > out["against"]', 'out["with"] >= out["against"] - 1')]),
    ("against strictly beyond 1 ATR", [('if out["against"] >= AGAINST * atr:', 'if out["against"] > AGAINST * atr:')]),
    ("the against surprise from the move with", [('if out["against"] >= AGAINST * atr:', 'if out["with"] >= AGAINST * atr:')]),
    ("the no-rhythm run at 1.0 ATR", [("BIG_RANGE, AGAINST, RUN = 2.0, 1.0, 1.5", "BIG_RANGE, AGAINST, RUN = 2.0, 1.0, 1.0")]),
    ("the big hour at 3 ATR", [("BIG_RANGE, AGAINST, RUN = 2.0, 1.0, 1.5", "BIG_RANGE, AGAINST, RUN = 3.0, 1.0, 1.5")]),
    ("the first line from the last bar, not the first", [("    for bar in seg.itertuples():", "    for bar in list(seg.itertuples())[::-1]:")]),
    ("the line above needs a close beyond", [('a, b = bar.high >= prev["line_above"]', 'a, b = bar.close >= prev["line_above"]')]),
    ("the scorecard counts hours without a rhythm", [('if r.get("score", {}).get("rhythm_held") is not None', 'if "with" in r.get("score", {}) or r.get("score")')]),
    ("the scorecard's means over all 20 slots", [('/ len(scored)\n    a = ', '/ 20\n    a = ')]),
]


def run(src: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "observe_planted.py").write_text(src, encoding="utf-8")
        (d / "plant_plugin.py").write_text(PLUGIN.format(here=HERE, path=d / "observe_planted.py"), encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": f"{d};{ROOT}"}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-p", "plant_plugin",  # noqa: S603
                            str(HERE / "test_observe.py")], cwd=ROOT, capture_output=True, text=True, check=False, env=env)
        failed = re.findall(r"FAILED \S+::(\S+)", r.stdout)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-300:]
        return r.returncode == 0, failed[0] if failed else last


def main() -> None:
    src = (HERE / "observe.py").read_text(encoding="utf-8")
    ok, line = run(src)
    print(f"observe.py: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (label, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits))
        if any(x in line for x in ("SyntaxError", "IndentationError", "source_to_code")):
            print(f"  {k:2d}. {label}: INVALID EDIT (the bug does not compile - not a catch)", flush=True)
            continue
        caught += not ok
        print(f"  {k:2d}. {label}: {'CAUGHT by ' + line if not ok else 'MISSED'}", flush=True)
    print(f"caught {caught} / {len(BUGS)}")


if __name__ == "__main__":
    main()
