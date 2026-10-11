"""Two variants of one world side by side, in the two-world report's pattern (owner, 2026-10-11): e.g. harmonic
as configured vs harmonic without break-even/trailing, each a joined year (``combine_periods.py``).

    .venv/Scripts/python research/2026-10-11-pre-run/compare_variants.py \
        setup_harmonic_prz_1y "as configured" setup_harmonic_prz_nobe1y "no break-even/trailing"
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from two_worlds import world  # type: ignore[import-not-found]

ROOT = Path("data/backtests/inv")
SPLIT = pd.Timestamp("2026-04-09", tz="UTC")


def halves(folder: Path) -> str:
    t = pd.read_csv(folder / "trades.csv")
    at = pd.to_datetime(t["entry_time"], utc=True)
    return f"{t.loc[at < SPLIT, 'r_multiple'].mean():+.3f} / {t.loc[at >= SPLIT, 'r_multiple'].mean():+.3f}"


def main(pairs: list[tuple[str, str]]) -> None:
    rows = {label: (world(ROOT / name), halves(ROOT / name)) for name, label in pairs}
    print(f"{'variant':26} {'trades':>6} {'win%':>5} {'R/trade':>8} {'90% CI':>16} {'halves':>17} {'net':>10} {'maxDD R':>8} {'avg win':>8} {'avg loss':>8}")
    for label, (w, h) in rows.items():
        print(
            f"{label:26} {w['n']:>6} {w['win']:>5.0f} {w['mean_r']:>+8.3f} [{w['ci'][0]:+.2f}, {w['ci'][1]:+.2f}] "
            f"{h:>17} {w['net']:>10,.2f} {w['dd_r']:>8.1f} {w['avg_win']:>+8.2f} {w['avg_loss']:>+8.2f}"
        )
    for label, (w, _) in rows.items():
        print(f"\n{label}: exits {w['exits']}")
        print(f"  losers, share of the way to the target before turning to the stop: {w['losers_run']}")
        print(f"  winners, share of the stop distance against them before the target: {w['winners_heat']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main([(args[i], args[i + 1]) for i in range(0, len(args), 2)])
