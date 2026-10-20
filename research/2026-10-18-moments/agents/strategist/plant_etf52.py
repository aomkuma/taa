"""Planted bugs in etf52.py / xlsx_min.py: each mutant must make test_etf52.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MUT = [
    ("etf52.py", "d = pd.Timestamp(day).normalize() + pd.Timedelta(days=1)", "d = pd.Timestamp(day).normalize()"),  # same day
    ("etf52.py", "    while d.weekday() >= 5:", "    while False:"),  # a weekend publication
    ("etf52.py", "return (d + pd.Timedelta(hours=16)).tz_localize(NY)", "return (d + pd.Timedelta(hours=0)).tz_localize(NY)"),
    ("etf52.py", '.tz_localize(NY).tz_convert("UTC")', '.tz_localize("UTC")'),
    ("etf52.py", '"ch20": s / s.shift(20) - 1', '"ch20": s / s.shift(19) - 1'),
    ("etf52.py", "up[s.diff().isna()] = np.nan", "pass"),
    ("etf52.py", "s.rolling(260, min_periods=200).max()", "s.shift(1).rolling(260, min_periods=200).max()"),
    ("etf52.py", "up = (s.diff() > 0).astype(float)", "up = (s.diff() >= 0).astype(float)"),
    ("xlsx_min.py", "x = shared[int(v.text)]", "x = v.text"),
    ("xlsx_min.py", "vals[_col(c.get(\"r\"))] = x", "vals[len(vals)] = x"),
]
for f, a, b in MUT:
    src = (HERE / f).read_text()
    assert a in src, a
    (HERE / f).write_text(src.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_etf52.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / f).write_text(src)
    print(("CAUGHT" if r.returncode else "MISSED") + f"  {f}: {b}")
