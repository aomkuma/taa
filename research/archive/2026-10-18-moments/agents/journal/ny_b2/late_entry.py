"""Root-cause audit (owner 2026-10-23: "you have not found the core of the losses"): is the B2 entry late? Per bot
trade (learning ../trades.csv and exam ../exam + ../exam_w25), from its decision record: the pattern's extreme and
height, the entry's distance from the extreme in pattern heights (how much of the move had already happened), the
stop in pattern heights, and what price did after the entry (best / worst in R from the bot's MFE / MAE).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/late_entry.py
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def load(folder: Path, part: str) -> pd.DataFrame:
    T = pd.read_csv(folder / "trades.csv")
    J = {}
    for line in open(folder / "journal.jsonl", encoding="utf-8"):
        j = json.loads(line)
        p = j.get("conditions", {}).get("pattern", "")
        m = re.search(r"extreme ([0-9.]+), height ([0-9.]+)", p)
        if m:
            J[j["signal_id"]] = (float(m.group(1)), float(m.group(2)))
    T["extreme"] = T.signal_id.map(lambda s: J.get(s, (np.nan, np.nan))[0])
    T["height"] = T.signal_id.map(lambda s: J.get(s, (np.nan, np.nan))[1])
    T["part"] = part
    return T


X = pd.concat([load(HERE, "learning"), load(HERE / "exam", "exam"), load(HERE / "exam_w25", "exam")]).dropna(subset=["height"])
X["risk"] = (X.entry_price - X.sl_initial).abs()
X["late"] = (X.entry_price - X.extreme).abs() / X.height  # 1 = the entry is one pattern height past the extreme
X["stop_h"] = X.risk / X.height
X["best"], X["worst"] = X.mfe / X.risk, X.mae / X.risk
pd.set_option("display.width", 200)
for part, g in X.groupby("part"):
    print(f"\n{part}: {len(g)} trades, R {g.r_multiple.mean():+.3f} a trade | entry past the extreme: median {g.late.median():.2f} heights | "
          f"stop median {g.stop_h.median():.2f} heights | best median {g.best.median():.2f} R, worst median {g.worst.median():.2f} R")
    b = pd.cut(g.late, [0, 0.75, 1.0, 1.25, 1.5, np.inf])
    print(g.groupby(b, observed=True).agg(n=("r_multiple", "size"), r=("r_multiple", "mean"), win=("r_multiple", lambda s: (s > 0).mean() * 100),
                                         best=("best", "median"), worst=("worst", "median")).round(3).to_string())
