"""Diagnose the filtered rule's trades (trades_GEOM.parquet from dump.py) with diag.flags."""
import sys, warnings
import pandas as pd
from diag import flags, report, situations
from exp import Lab
warnings.filterwarnings("ignore")
L = Lab(); S = situations(L)
t = pd.read_parquet(f"research/2026-10-18-moments/agents/reversion/trades_{sys.argv[1]}.parquet").reset_index(drop=True)
f = flags(S, t)
pd.set_option("display.width", 250)
print(len(t), t.R.mean())
print(report(t, f).round(3).to_string())
t.join(f).to_parquet(f"research/2026-10-18-moments/agents/reversion/diag2_{sys.argv[1]}.parquet")
