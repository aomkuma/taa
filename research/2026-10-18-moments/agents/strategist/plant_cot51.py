"""Planted bugs in cot51.py's release-lag alignment: each mutant must make test_cot51.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "cot51.py").read_text()
MUT = [
    ("    if key in SHUTDOWN:", "    if False:"),  # the shutdown table ignored
    ("day = fri + pd.Timedelta(days=3) if any(d in holidays for d in span) else fri", "day = fri"),  # holidays ignored
    ("fri = a + pd.Timedelta(days=(4 - a.weekday()) % 7)", "fri = a"),  # known on the report date (Tuesday)
    ("return (day + pd.Timedelta(hours=15, minutes=30)).tz_localize(NY)", "return (day + pd.Timedelta(hours=0)).tz_localize(NY)"),
    (".tz_localize(NY).tz_convert(\"UTC\")", ".tz_localize(\"UTC\")"),  # 15:30 read as UTC
    ('k = int(np.searchsorted(pub_ns, t_ns, side="right")) - 1', 'k = int(np.searchsorted(pub_ns, t_ns, side="right"))'),
    ('k = int(np.searchsorted(pub_ns, t_ns, side="right")) - 1', 'k = int(np.searchsorted(pub_ns, t_ns, side="left")) - 1'),
    ("return float(np.mean(w <= x[i]))", "return float(np.mean(w < x[i]))"),
    ("w = x[max(0, i - n + 1):i + 1]", "w = x[max(0, i - n + 1):i]"),
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "cot51.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_cot51.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "cot51.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + "  " + b)
