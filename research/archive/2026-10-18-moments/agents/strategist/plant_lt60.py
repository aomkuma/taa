"""Planted bugs in lt60.py: each mutant must make test_lt60.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "lt60.py").read_text()
MUT = [
    ("e = ask[f] if side > 0 else bid[f]", "e = bid[f]"),
    ("px = bid[f + 1:end + 1] if side > 0 else ask[f + 1:end + 1]", "px = bid[f + 1:end + 1]"),
    ('end = int(np.searchsorted(t, t_out, side="left")) - 1', 'end = int(np.searchsorted(t, t_out, side="left"))'),
    ("cand.append((int(i_s[0]), 0, \"stop\", float(fav[i_s[0]])))", "cand.append((int(i_s[0]), 0, \"stop\", -d))"),
    ("cand.append((int(i_t[0]), 1, \"target\", float(k_tgt * d)))", "cand.append((int(i_t[0]), 1, \"target\", float(fav[i_t[0]])))"),
    ("return pnl, pnl / d, why, int(t[f + 1 + i])", "return pnl, pnl / d, why, int(t[f + i])"),
    ("if f >= len(t) or t[f] - t_in > max_lag or not d > 0:", "if f >= len(t) or not d > 0:"),
    ("return int(np.sign(close[j] - close[j - n]))", "return int(np.sign(close[j] - close[j - n + 1]))"),
    ("return np.minimum(nxt, open_ns + period_ns)", "return nxt"),
    ("    if day >= end:\n        return None", "    if day > end:\n        return None"),
    ('        if not FROZEN.exists():\n            raise RuntimeError', '        if False:\n            raise RuntimeError'),
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "lt60.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_lt60.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "lt60.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + "  " + b.splitlines()[0][:100])
