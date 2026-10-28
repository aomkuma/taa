"""TS structure-break triggers straight from the evidence detector (no backtest engine, no chart reads), for the
behaviour rules B1-B5, which need only the trigger and raw prices. Mimics the engine: the detector runs on the last
``WINDOW`` closed M15 bars at every bar (the engine's warm-up window) and a trigger is a record fired on that bar.

usage: python ts_offline_triggers.py START END OUT_DIR   (writes OUT_DIR/triggers.csv like ts_dataset.py, minus the
chart-read columns)
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.config import load_app_config  # noqa: E402
from app.core.enums import Timeframe  # noqa: E402
from app.evidence.catalog import default_registry  # noqa: E402
from app.evidence.framework import Direction, EvidenceContext  # noqa: E402
from app.indicators.volatility import atr  # noqa: E402

start, end, out = pd.Timestamp(sys.argv[1], tz="UTC"), pd.Timestamp(sys.argv[2], tz="UTC"), Path(sys.argv[3])
cfg = load_app_config(ROOT / "data/research/config_ts_all_m15.yaml")
WINDOW = cfg.timeframes.warmup_bars
reg = default_registry()
plan = reg.plan_from_config(cfg.evidence, only={"structure.bos_choch"})
det, params = reg.get("structure.bos_choch"), plan.params["structure.bos_choch"]
m15 = pd.read_parquet(ROOT / (os.environ.get("TS_HISTORY", "data/history") + "/FBS-Demo/XAUUSD/M15.parquet")).sort_values("close_time").reset_index(drop=True)
m15["atr"] = atr(m15.high.astype(float), m15.low.astype(float), m15.close.astype(float), cfg.indicators.atr_period)
ct = m15.close_time
first = int(ct.searchsorted(start))
last = int(ct.searchsorted(end))
rows = []
for i in range(max(first, WINDOW), last):
    window = m15.iloc[i - WINDOW + 1 : i + 1]
    ctx = EvidenceContext("XAUUSD", Timeframe.M15, window, cfg.evidence)
    fired = [e for e in det.scan(ctx, params) if e.detected_at == ct.iloc[i] and e.direction is not Direction.NEUTRAL]
    if len({e.direction for e in fired}) != 1 or fired[0].invalidation is None:
        continue
    e = fired[0]
    a = float(m15.atr.iloc[i])
    close = float(m15.close.iloc[i])
    rows.append({
        "time": ct.iloc[i].isoformat(), "side": "BUY" if e.direction is Direction.BULL else "SELL",
        "kind": e.i18n_key.rsplit(".", 1)[-1], "close": close, "atr": a,
        "spread_points": float(m15.spread.iloc[i]), "pivot": e.invalidation,
        "pivot_atr": abs(close - e.invalidation) / a if a > 0 else np.nan,
    })
out.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(out / "triggers.csv", index=False)
print(f"{len(rows)} triggers {start:%Y-%m-%d} .. {end:%Y-%m-%d} -> {out / 'triggers.csv'}")
