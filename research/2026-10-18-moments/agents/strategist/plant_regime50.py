"""Planted bugs in regime50.py's helpers: each mutant must make test_regime50.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "regime50.py").read_text()
MUT = [
    ("ref = (bid[k - 1] + ask[k - 1]) / 2", "ref = (bid[k] + ask[k]) / 2"),  # the reference after t0
    ('e = int(np.searchsorted(t, t0 + span_ns, side="left"))', 'e = int(np.searchsorted(t, t0 + span_ns, side="right"))'),
    ("return float(np.max(np.abs((bid[k:e] + ask[k:e]) / 2 - ref)))", "return float(np.max((bid[k:e] + ask[k:e]) / 2 - ref))"),
    ("on = ok & ((x < c) if lower else (x > c))", "on = ok & ((x < c) if lower else (x >= c))"),
    ("elif abs(s - best[1]) <= 1e-12 and ((c > best[0]) if lower else (c < best[0])):", "elif False:"),
    ("ok = np.isfinite(x)\n    best", "ok = np.ones(len(x), bool)\n    best"),
    ('k = int(np.searchsorted(dates, day, side="left"))', 'k = int(np.searchsorted(dates, day, side="right"))'),
    ("v = v[np.isfinite(v)][-n:]", "v = v[-n:]"),
    ("if len(v) < max(1, n // 2):", "if len(v) < 1:"),
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "regime50.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_regime50.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "regime50.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + "  " + b.splitlines()[0])
