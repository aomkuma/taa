"""Planted bugs in sw20.switch_ok: each mutant must make test_sw20.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "sw20.py").read_text()
MUT = [
    ('k = int(np.searchsorted(te, t, side="left"))', 'k = int(np.searchsorted(te, t, side="right"))'),  # exits <= t
    ("if k >= n:", "if k >= 1:"),  # no warm-up
    ("out[i] = rr[k - n:k].mean() > 0", "out[i] = rr[:n].mean() > 0"),  # the first n, not the last
    ("out[i] = rr[k - n:k].mean() > 0", "out[i] = rr[k - n:k].mean() >= 0"),  # >= 0
    ("o = np.argsort(te, kind=\"stable\")", "o = np.arange(len(te))"),  # not ordered by exit time
    ("ok = np.isfinite(R) & (t_exit > 0)", "ok = t_exit > 0"),  # NaN results kept
    ("out[i] = rr[k - n:k].mean() > 0", "out[i] = rr[:k].mean() > 0"),  # every earlier exit, not the last n
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "sw20.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_sw20.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "sw20.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + f"  {b}")
