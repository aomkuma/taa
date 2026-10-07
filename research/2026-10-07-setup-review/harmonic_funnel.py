"""Why so few harmonic signals? Count, over three months, the zigzag swings, the harmonic patterns that touch
their PRZ and those that would pass the setup's geometry (RR >= 1.5 to a target, stop <= 3 ATR), on M15 and M5,
with the configured swing size and ratio tolerance and looser ones. Read-only.

usage: python harmonic_funnel.py [SYMBOL]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.config import load_app_config  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.evidence.catalog import default_registry  # noqa: E402
from app.evidence.framework import EvidenceContext  # noqa: E402

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
START, END = "2026-07-01", "2026-10-01"
DETECTORS = ["harmonic.gartley", "harmonic.bat", "harmonic.butterfly", "harmonic.crab", "harmonic.cypher",
             "harmonic.shark", "harmonic.abcd"]

cfg = load_app_config(ROOT / "config.yaml")
reg = default_registry()
plan = reg.plan_from_config(cfg.evidence, only=set(DETECTORS))


def frame(tf: str) -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data" / "history" / "FBS-Demo" / SYMBOL / f"{tf}.parquet")
    df = df.set_index(pd.DatetimeIndex(df["close_time"])).sort_index()
    return df.loc[START:END]


def funnel(tf: str, minor_atr: float, tol: float) -> str:
    df = frame(tf)
    evidence_cfg = cfg.evidence.model_copy(
        update={"zigzag_degrees": {**cfg.evidence.zigzag_degrees, "minor": minor_atr}}
    )
    ctx = EvidenceContext(SYMBOL, Timeframe(tf), df, evidence_cfg)
    swings = len(ctx.zigzag("minor"))
    atr = ctx.atr_array()
    touches = passed = 0
    for det_id in DETECTORS:
        det = reg.get(det_id)
        params = plan.params[det_id].model_copy(update={"ratio_tol": tol})
        for ev in det.scan(ctx, params):
            touches += 1
            t = int(df.index.get_indexer([ev.detected_at], method="nearest")[0])
            a = float(atr[t]) if np.isfinite(atr[t]) else None
            if a is None or ev.invalidation is None:
                continue
            entry = float(df["close"].iloc[t])
            sign = 1 if ev.direction.sign > 0 else -1
            stop = ev.invalidation - sign * 0.1 * a
            risk = (entry - stop) * sign
            if risk <= 0 or risk > 3 * a:
                continue
            if any((tp - entry) * sign / risk >= 1.5 for tp in ev.targets):
                passed += 1
    days = max(1, (df.index[-1] - df.index[0]).days)
    return (f"{tf:4} swing>={minor_atr:<4} ATR tol {tol:.2f}: swings {swings:5d}  PRZ touches {touches:4d} "
            f"({touches / days * 7:5.1f}/week)  pass RR>=1.5 & stop<=3 ATR {passed:4d} ({passed / days * 7:4.1f}/week)")


print(f"{SYMBOL} {START}..{END}, all seven harmonic patterns")
for tf in ("M15", "M5"):
    for minor_atr, tol in ((1.5, 0.05), (1.5, 0.10), (1.0, 0.05), (1.0, 0.10), (0.75, 0.10)):
        print(funnel(tf, minor_atr, tol), flush=True)
