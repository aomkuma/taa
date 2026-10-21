"""Row 60, descriptive (written after the TEST read): the frozen cells split by side (buy / sell), calm trades.
Re-derives the events (bars only; lt60.events) and joins them to the stored trades on (cand, t_in)."""

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lt60  # noqa: E402

fr = json.loads((HERE / "lt60_frozen.json").read_text())
for ph in ("learn", "test"):
    E = lt60.events(ph)[["cand", "t_in", "side"]]
    T = pd.read_parquet(HERE / f"lt60_{ph}.parquet").merge(E, on=["cand", "t_in"], how="left")
    T = T[T.atr < lt60.CALM]
    for cand, s in fr.items():
        x = T[(T.cand == cand) & (T.setting == s)]
        print(f"{ph:5s} {cand:6s} {s:14s} " + " | ".join(f"{'buy' if k > 0 else 'sell'} {len(g)} {g.R.mean():+.3f}"
                                                        for k, g in x.groupby("side")))
