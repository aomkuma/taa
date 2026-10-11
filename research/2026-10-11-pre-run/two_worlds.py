"""Two-world backtest summary (owner, 2026-10-11): the original and the inverted backtest of one setup, side by
side, plus how price moved in each trade relative to the setup's own direction and target.

For each trade (``trades.csv`` of ``app.cli backtest``; ``mae``/``mfe`` are price distances):

- losers: how far price went toward the target before turning to the stop, as a share of the target distance
  (MFE / |TP - entry|): under 25 % "turned at once", then 25-50 %, 50-75 %, 75 %+ ("ran first, then turned");
- winners: how far price went against the trade before reaching the target, as a share of the stop distance
  (MAE / |entry - SL|).

    .venv/Scripts/python research/2026-10-11-pre-run/two_worlds.py setup_harmonic_prz [data/backtests/inv]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BANDS = [(0.0, 0.25, "<25%"), (0.25, 0.5, "25-50%"), (0.5, 0.75, "50-75%"), (0.75, np.inf, "75%+")]


def ci(xs: np.ndarray, seed: int = 0, n: int = 4000) -> tuple[float, float]:
    if len(xs) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    m = xs[rng.integers(0, len(xs), (n, len(xs)))].mean(1)
    return float(np.quantile(m, 0.05)), float(np.quantile(m, 0.95))


def max_dd_r(r: np.ndarray) -> float:
    eq = np.cumsum(r)
    return float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:] - eq)) if len(r) else 0.0


def bands(values: np.ndarray) -> str:
    if not len(values):
        return "-"
    return "  ".join(f"{lab} {100 * np.mean((values >= lo) & (values < hi)):.0f}%" for lo, hi, lab in BANDS)


def world(folder: Path) -> dict:
    t = pd.read_csv(folder / "trades.csv").sort_values("exit_time")
    risk = (t["entry_price"] - t["sl_initial"]).abs()
    target = (t["tp_initial"] - t["entry_price"]).abs()
    r = t["r_multiple"].to_numpy(dtype=float)
    lose = t["net"] <= 0
    lo, hi = ci(r)
    return {
        "n": len(t),
        "win": 100 * float((~lose).mean()) if len(t) else float("nan"),
        "mean_r": float(r.mean()) if len(t) else float("nan"),
        "ci": (lo, hi),
        "net": float(t["net"].sum()),
        "dd_r": max_dd_r(r),
        "avg_win": float(t.loc[~lose, "r_multiple"].mean()),
        "avg_loss": float(t.loc[lose, "r_multiple"].mean()),
        "exits": t["exit_reason"].value_counts().to_dict(),
        "losers_run": bands((t.loc[lose, "mfe"] / target[lose]).to_numpy(dtype=float)),
        "winners_heat": bands((t.loc[~lose, "mae"] / risk[~lose]).to_numpy(dtype=float)),
        "symbols": t.groupby("symbol")["r_multiple"].agg(["count", "mean"]).round(3).to_dict("index"),
    }


def main(setup: str, root: Path) -> None:
    rows = {"normal": world(root / f"{setup}_4m"), "inverted": world(root / f"{setup}_inverted_4m")}
    print(f"=== {setup}: two worlds, 2026-06-05 .. 2026-10-05, 8 symbols (bar-based backtest) ===")
    print(f"{'world':9} {'trades':>6} {'win%':>5} {'R/trade':>8} {'90% CI':>16} {'net':>10} {'maxDD R':>8} {'avg win':>8} {'avg loss':>8}")
    for name, w in rows.items():
        print(
            f"{name:9} {w['n']:>6} {w['win']:>5.0f} {w['mean_r']:>+8.3f} [{w['ci'][0]:+.2f}, {w['ci'][1]:+.2f}] "
            f"{w['net']:>10,.2f} {w['dd_r']:>8.1f} {w['avg_win']:>+8.2f} {w['avg_loss']:>+8.2f}"
        )
    for name, w in rows.items():
        print(f"\n{name}: exits {w['exits']}")
        print(f"  losers, share of the way to the target before turning to the stop: {w['losers_run']}")
        print(f"  winners, share of the stop distance against them before the target: {w['winners_heat']}")
        print(f"  by symbol (n, mean R): {w['symbols']}")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2] if len(sys.argv) > 2 else "data/backtests/inv"))
