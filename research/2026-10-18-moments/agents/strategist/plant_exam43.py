"""Planted bugs in exam43.py: each mutant must make test_exam43.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "exam43.py").read_text()
MUT = [
    ("allow_abbrev=False", "allow_abbrev=True"),
    ('ap.add_argument("--exam", action="store_true"', 'ap.add_argument("--exam", action="store_false"'),
    ("    if not exam and len(d) and d.index.max() >= EXAM_START:", "    if False:"),
    ('d = reader(M1_PATH, [("open_time", ">=", start - WARMUP), ("open_time", "<", end)])',
     'd = reader(M1_PATH, [("open_time", ">=", start - WARMUP), ("open_time", "<", EXAM_END)])'),
    ("    if d >= EXAM_START and not exam:", "    if False:"),
    ("    if not exam and nxt >= EXAM_START:\n        return a", "    if False:\n        return a"),
    ("    if d >= EXAM_END:\n        return None", "    if False:\n        return None"),
    ('return ["exam"] if exam else ["P1", "P2"]', 'return ["P1", "P2", "exam"]'),
    ("run = run + 1 if p <= 0 else 0", "run = run + 1 if p < 0 else 0"),
    ("eq = np.r_[0.0, np.cumsum(pnl)]", "eq = np.cumsum(pnl)"),
    ('x = T.sort_values("t_exit")', "x = T"),
    ("win=float((x.pnl > 0).mean())", "win=float((x.pnl >= 0).mean())"),
    ('.dt.tz_convert(TH).dt.tz_localize(None)', '.dt.tz_localize(None)'),
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "exam43.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_exam43.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "exam43.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + "  " + b.splitlines()[0])
