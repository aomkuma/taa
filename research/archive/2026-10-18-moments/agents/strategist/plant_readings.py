"""Planted bugs in readings.py (row 45): each mutant must make test_readings.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "readings.py").read_text()
MUT = [
    ("v = rng[j - recent + 1:j + 1].mean()", "v = rng[j - recent + 2:j + 2].mean()"),  # one bar ahead
    ("np.mean(rng[j - hist + 1:j + 1] <= v)", "np.mean(rng[j - hist + 1:j + 1] < v)"),  # < for <=
    ("np.median(rng[j - base + 1:j + 1])", "np.mean(rng[j - base + 1:j + 1])"),  # mean for median
    ("path = np.abs(np.diff(c[j - n:j + 1])).sum()", "path = np.abs(np.diff(c[j - n + 1:j + 1])).sum()"),  # short path
    ("m = (t_break >= t_from) & (t_settle <= t)", "m = (t_break >= t_from) & (t_break <= t)"),  # unsettled breaks
    ("prev = np.r_[np.nan, atr[:-1]]", "prev = atr"),  # the bar's own ATR
    ("return min(cap, (t - avail[k[-1]]) / NS_H)", "return min(cap, (t - avail[k[0]]) / NS_H)"),  # the first big bar
    ("m = (t_exit <= t) & np.isfinite(R) & (t_exit > 0)", "m = np.isfinite(R) & (t_exit > 0)"),  # future exits
    ("return float(R[m][o][-n:].mean())", "return float(R[m][o][:n].mean())"),  # the first n, not the last
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "readings.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_readings.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "readings.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + f"  {b}")
