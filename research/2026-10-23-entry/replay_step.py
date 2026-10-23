"""Replay trading, one step (owner 2026-10-23): the M15 candles that formed between two times (only those), then the
every-timeframe read at the end of the step. Thai time printed.

    .venv/Scripts/python research/2026-10-23-entry/replay_step.py FROM_UTC TO_UTC
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zone_wait as ZW  # noqa: E402

a, b = pd.Timestamp(sys.argv[1], tz="UTC"), pd.Timestamp(sys.argv[2], tz="UTC")
m = ZW.load("M15")
x = m[(m.index >= a) & (m.index + pd.Timedelta(minutes=15) <= b)]
print(f"## M15 candles {a.tz_convert('Asia/Bangkok'):%H:%M} - {b.tz_convert('Asia/Bangkok'):%H:%M} Thai")
for t, r in x.iterrows():
    print(f"  {t.tz_convert('Asia/Bangkok'):%H:%M}  O {r.open:.2f}  H {r.high:.2f}  L {r.low:.2f}  C {r.close:.2f}  vol {int(r.tick_volume)}")
if len(x):
    print(f"  the step: high {x.high.max():.2f}, low {x.low.min():.2f}, last close {x.close.iloc[-1]:.2f}")
print()
subprocess.run([sys.executable, str(HERE / "rhythm_scan.py"), str(b.tz_convert("UTC").tz_localize(None))], check=True)
