import os, sys, subprocess, pandas as pd
code = r'''
import sys; sys.path.insert(0, "research/2026-10-18-moments/agents/journal")
import liq_journal as L
J = L.journal(sys.argv[1], sys.argv[2]); J = J[J.piece == "Asia B2"]
J["inzone"] = J.sweep_zone != "-"
J[["t_in", "R", "inzone", "sweep_zone", "risk", "H1atr"]].to_parquet(sys.argv[3])
'''
out = []
for f, s, e in (("plan1_trades_learn_s0_x0.parquet", "2025-10-20", "2026-04-18"), ("plan1_trades_exam_s0_x0.parquet", "2026-04-18", "2026-05-30")):
    p = os.path.join(os.environ["TEMP"], f"b2sw_{s}.parquet")
    for i in range(4):
        if subprocess.run([sys.executable, "-c", code, s, e, p], env=dict(os.environ, PLAN1_TRADES=f)).returncode == 0:
            break
    X = pd.read_parquet(p); X["part"] = "w1-26" if "learn" in f else "w27-32"; out.append(X)
X = pd.concat(out)
print(X.groupby(["part", "inzone"]).R.agg(["count", "sum", "mean"]).round(3))
print(X.groupby("inzone").R.agg(["count", "sum", "mean"]).round(3))
