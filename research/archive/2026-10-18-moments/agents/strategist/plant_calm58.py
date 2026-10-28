"""Planted bugs in calm58.py: each mutant must make test_calm58.py fail. (calm58.py is restored after each run; the
LEARN run in progress imported it before this script started.)"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "calm58.py").read_text()
MUT = [
    ('        if not FROZEN.exists():\n            raise RuntimeError', '        if False:\n            raise RuntimeError'),
    ("    if day >= end:\n        return None", "    if day > end:\n        return None"),
    ("if (side < 0 and cl[k] < ah) or (side > 0 and cl[k] > al):", "if (side < 0 and cl[k] < ah and k > i0 + 99) or (side > 0 and cl[k] > al):"),
    ("ext = max(ext, hi[k]) if side < 0 else min(ext, lo[k])", "pass"),
    ("return int(o_ns[k] + MIN), side, float(ext)", "return int(o_ns[k]), side, float(ext)"),
    ("i0, i1 = int(np.searchsorted(o_ns, h0)), int(np.searchsorted(o_ns, h1))", "i0, i1 = int(np.searchsorted(o_ns, h0)), len(o_ns)"),
    ("x = T[(T.cand == cand) & (T.setting == name) & (T.atr < CALM)]\n            r = x.R.mean()",
     "x = T[(T.cand == cand) & (T.setting == name)]\n            r = x.R.mean()"),
    ("if best is None or r > best[1] + 1e-12:", "if best is None or r < best[1] - 1e-12:"),
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "calm58.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_calm58.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "calm58.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + "  " + b.splitlines()[0][:100])
