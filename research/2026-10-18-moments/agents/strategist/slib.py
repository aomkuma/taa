"""The strategist's shared helpers (quick checks only). The exam period (2026-04-18 .. 2026-10-17) is never loaded:
the M1 store is read with a row filter that stops before EXAM_START, ticks are read only for days before it, and the
developers' trade files are cut to P1 / P2 by their own `part` column (asserted).

Thai time = UTC+7 (no summer time). Parts as in m15_trades.PARTS: P1 2025-10-18 .. 2026-01-16, P2 2026-01-16 .. 2026-04-18.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
DEV = HERE.parent / "dev"
M1_PATH = ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet"
TICKS = ROOT / "data/ticks/XAUUSD"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
P1 = (pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-01-16", tz="UTC"))
P2 = (pd.Timestamp("2026-01-16", tz="UTC"), EXAM_START)
PARTS = {"P1": P1, "P2": P2}
TH = "Asia/Bangkok"


def m1(start: str = "2025-10-18") -> pd.DataFrame:
    """M1 bars (UTC open-time index) from `start` up to, never including, the exam."""
    s = pd.Timestamp(start, tz="UTC")
    d = pd.read_parquet(M1_PATH, filters=[("open_time", ">=", s), ("open_time", "<", EXAM_START)])
    d.index = pd.DatetimeIndex(pd.to_datetime(d["open_time"], utc=True)).as_unit("ns")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    assert d.index.max() < EXAM_START
    return d[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


def part_of(t: pd.DatetimeIndex) -> np.ndarray:
    out = np.full(len(t), "", dtype=object)
    for k, (a, b) in PARTS.items():
        out[(t >= a) & (t < b)] = k
    return out


def ticks(day: pd.Timestamp) -> pd.DataFrame | None:
    day = pd.Timestamp(day).tz_convert("UTC") if pd.Timestamp(day).tzinfo else pd.Timestamp(day, tz="UTC")
    assert day < EXAM_START, "exam day requested"
    f = TICKS / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f)
    x["t"] = pd.to_datetime(x.time_utc, utc=True)
    return x.sort_values("t", kind="stable")


def dev_trades(name: str, variant: str | None = None, news_cost: float = 0.0) -> pd.DataFrame:
    """A developer's trade file (read-only), P1 / P2 rows only."""
    d = pd.read_parquet(DEV / name)
    if variant is not None:
        d = d[d.variant == variant]
    if "news_cost" in d:
        d = d[d.news_cost == news_cost]
    d = d[d.part.isin(["P1", "P2"])].copy()
    t = pd.to_datetime(d.t_entry, utc=True)
    assert t.max() < EXAM_START
    d["t"] = t
    return d.reset_index(drop=True)


def ci95(x: np.ndarray, n_boot: int = 4000, seed: int = 7) -> tuple[float, float]:
    x = np.asarray(x, float)
    if len(x) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(1)
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def row(x: pd.DataFrame, r: str = "R") -> str:
    if len(x) == 0:
        return "n 0"
    lo, hi = ci95(x[r].to_numpy())
    usd = x["pnl"].sum() if "pnl" in x else np.nan
    return f"n {len(x):4d}  R {x[r].mean():+.3f} ({lo:+.2f}..{hi:+.2f})  win {np.mean(x[r] > 0):.2f}  USD {usd:+8.1f}"
