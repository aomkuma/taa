"""Build app/strategy/edge_table.json - the edge of each side by condition (owner 2026-10-25: "trade the side with
the edge, and close the gap": the AI saw both sides' R but guessed their odds).

Trades: every M5 swing level of 2024-2025 (before the exam), two bare triggers per side - the reclaim
(reclaim_2025.py: swept, an M5 close back within 30 min, stop 1.0 ATR past the sweep) and following the break
(follow_regime.py: an M5 close 1.0 ATR past, stop 1.0 ATR back across) - target 0.7 R, two hours at most, R after
the spread. M5 is built from M1.
Condition: the app's own reading (app.strategy.knowledge.d1_regime) on the stored D1, H4 and H1 bars closed by
the trade's entry (the entry bar's close), so the table matches what the system reads live. The vectorised
labels are checked against the app's function on a sample before the table is written.

    .venv/Scripts/python research/2026-10-24-replay/edge_table.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from follow_regime import follow  # noqa: E402
from reclaim_2025 import ROOT, m5_from_m1, signals, trade  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.edge import EDGE_TABLE  # noqa: E402
from app.strategy.knowledge import REGIME_MEAN, REGIME_SLOPE, d1_regime  # noqa: E402

START, END = "2023-09-01", "2026-04-18"  # all the design data: M1 starts 2023-09, the exam 2026-04-18
STOP_ATR, TARGET_R = 1.0, 0.7


def frame(store: ParquetHistoryStore, tf: Timeframe) -> pd.DataFrame:
    df = store.load("FBS-Demo", "XAUUSD", tf, None, None)
    df = df.assign(avail=pd.to_datetime(df.close_time, utc=True)).drop_duplicates("avail", keep="last")
    return df.sort_values("avail").reset_index(drop=True)


def labels(df: pd.DataFrame) -> np.ndarray:
    """d1_regime after every bar, vectorised: the close vs its 50-bar mean, the mean vs 20 bars earlier."""
    c = df.close.astype(float)
    mean = c.rolling(REGIME_MEAN).mean()
    before = mean.shift(REGIME_SLOPE)
    lab = np.where((c > mean) & (mean > before), "up", np.where((c < mean) & (mean < before), "down", "none"))
    return np.where(before.isna(), "?", lab)


def at(df: pd.DataFrame, lab: np.ndarray, t: pd.DatetimeIndex) -> np.ndarray:
    i = df.avail.searchsorted(t, side="right") - 1  # the last bar closed by t
    return np.where(i >= 0, lab[np.maximum(i, 0)], "?")


def check(df: pd.DataFrame, lab: np.ndarray, t: pd.DatetimeIndex, name: str) -> None:
    """The vectorised label equals the app's d1_regime on 300 sampled times."""
    rng = np.random.default_rng(7)
    bad = 0
    for x in rng.choice(t, 300, replace=False):
        x = pd.Timestamp(x)
        app = d1_regime(df.close.to_numpy(float)[df.avail <= x]) or "?"
        bad += app != at(df, lab, pd.DatetimeIndex([x]))[0]
    print(f"check {name}: {300 - bad}/300 equal to the app's reading")
    assert bad == 0, name


def main() -> None:
    store = ParquetHistoryStore(ROOT / "data/history")
    m5 = m5_from_m1(store.load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None))
    part = m5[(m5.index >= START) & (m5.index < END)]
    rec = signals(part)
    rec = pd.DataFrame(
        {
            "t": part.index[rec.k.to_numpy()],
            "side": np.where(rec.up, "SELL", "BUY"),
            "trigger": "reclaim",
            "r": [trade(part, s, STOP_ATR, TARGET_R) for s in rec.itertuples()],
        }
    )
    fol = follow(part, 1.0)
    fol = pd.DataFrame(
        {"t": fol.t, "side": np.where(fol.up, "BUY", "SELL"), "trigger": "follow", "r": fol.r07}
    )
    ev = pd.concat([rec, fol], ignore_index=True).dropna(subset=["r"])
    entry = pd.DatetimeIndex(ev.t) + pd.Timedelta(minutes=5)  # known at the entry bar's close
    keys = {}
    for name, tf in (("d1", Timeframe.D1), ("h4", Timeframe.H4), ("h1", Timeframe.H1)):
        df = frame(store, tf)
        lab = labels(df)
        check(df, lab, entry, name)
        keys[name] = at(df, lab, entry)
    ev = ev.assign(key=[f"{a}/{b}/{c}" for a, b, c in zip(keys["d1"], keys["h4"], keys["h1"], strict=True)])
    ev = ev[~ev.key.str.contains(r"\?")]
    cells: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for (key, side, trig), g in ev.groupby(["key", "side", "trigger"]):
        cells.setdefault(key, {}).setdefault(side, {})[trig] = {
            "n": len(g),
            "win": round(float((g.r > 0).mean()), 3),
            "r": round(float(g.r.mean()), 3),
        }
    table = {
        "meta": {
            "period": "2023-09-01 .. 2026-04-17 (all the design data, before the exam)",
            "frame": "M5",
            "stop": f"{STOP_ATR:g} M5 ATR past the sweep / back across the level",
            "target": f"{TARGET_R:g} R",
            "built_by": "research/2026-10-24-replay/edge_table.py",
            "trades": len(ev),
        },
        "cells": dict(sorted(cells.items())),
    }
    EDGE_TABLE.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    print(f"{len(ev)} trades in {len(cells)} cells -> {EDGE_TABLE}")
    for key, cell in sorted(cells.items()):
        row = []
        for side in ("BUY", "SELL"):
            for trig in ("reclaim", "follow"):
                t = cell.get(side, {}).get(trig)
                row.append(f"{side[0]}-{trig[:3]} {t['r']:+.3f}/{t['n']}" if t else f"{side[0]}-{trig[:3]} -")
        print(f"{key:15s} " + "  ".join(row))


if __name__ == "__main__":
    main()
