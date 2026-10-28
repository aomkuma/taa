"""Planted bugs in wf_process.py's fold logic: each mutant must make test_wf_process.py fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "wf_process.py").read_text()
MUT = [
    ("return ((T.t_in >= fit_start) & (T.t_exit < trade_start)).to_numpy()",
     "return ((T.t_in >= fit_start) & (T.t_in < trade_start)).to_numpy()"),  # a trade still open at the start
    ("return ((T.t_in >= fit_start) & (T.t_exit < trade_start)).to_numpy()",
     "return ((T.t_in >= fit_start) & (T.t_exit < trade_start + pd.Timedelta(days=1))).to_numpy()"),  # sees its months
    ("return ((T.t_in >= fit_start) & (T.t_exit < trade_start)).to_numpy()",
     "return (T.t_exit < trade_start).to_numpy()"),  # no 12-month start
    ("out.append((s - pd.DateOffset(months=fit_months), s, e))", "out.append((s - pd.DateOffset(months=fit_months), s, e + pd.DateOffset(months=1)))"),
    ("e = min(s + pd.DateOffset(months=months), end)", "e = s + pd.DateOffset(months=months)"),  # past the end
    ("q = np.r_[-np.inf, np.quantile(atr, [0.25, 0.5, 0.75]), np.inf]",
     "q = np.r_[atr.min(), np.quantile(atr, [0.25, 0.5, 0.75]), atr.max()]"),  # closed outer edges
    ("if n < min_n:", "if n < 1:"),
    ("if best is None or best[1] < min_r:", "if best is None:"),  # no stand-aside
    ("(abs(r - best[1]) <= 1e-12 and n > best[2])", "(abs(r - best[1]) <= 1e-12 and n < best[2])"),
    ("return (atr >= band[0]) & (atr < band[1])", "return (atr >= band[0]) & (atr <= band[1])"),
    ("y = t.dt.year.where(t.dt.month >= 10, t.dt.year - 1)", "y = t.dt.year"),
]
for a, b in MUT:
    assert a in SRC, a
    (HERE / "wf_process.py").write_text(SRC.replace(a, b, 1))
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(HERE / "test_wf_process.py")],
                           capture_output=True, text=True, cwd=HERE)
    finally:
        (HERE / "wf_process.py").write_text(SRC)
    print(("CAUGHT" if r.returncode else "MISSED") + "  " + b[:110])
