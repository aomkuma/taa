"""Measure decision-time readings against shipped-bot trade outcomes.

Run from the repository root with ``.venv\\Scripts\\python.exe
research/2026-10-26-three-bots/weights.py``. This reads the frozen trade CSV and
prints summaries; it does not regenerate the trade history or write any files.

Only columns known at entry are treated as candidate readings. ``r``, exit
labels, excursions, and counterfactual stops are outcomes and never predictors.
The momentum columns are changed to "behind the trade" by multiplying the
stored signed value by +1 for BUY and -1 for SELL; side is known at entry.
The momentum producer's read_at() accepts a frame bar only when its readable
time (bar open + frame duration) is <= the decision time. In particular, for
a trade at 2026-10-27 10:00 UTC, an H4 bar opened at 08:00 closes at 12:00 and
is not readable; the preceding H4 bar opened at 04:00 closes at 08:00 and is
readable. The history index is the bar OPEN. The app frames are close-stamped;
momentum.py explicitly uses the history convention and does not shift the
decision timestamp. This hand-worked boundary case is the point-in-time check.

No indicators beyond the CSV are introduced here, so there are no additional
bar joins or timing assumptions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CSV = HERE / "momentum_trades.csv"
NUMERIC = ("mom_H1", "mom_H4", "mom_D1", "risk")
CATEGORICAL = ("bot", "side", "regime", "window")
SEED = 20261027
PERMUTATIONS = 5000


def auc_higher_is_better(values: np.ndarray, wins: np.ndarray) -> float:
    """Pairwise win/loss AUC; 0.5 is chance, >0.5 favors larger readings."""
    positive, negative = values[wins], values[~wins]
    if not len(positive) or not len(negative):
        return float("nan")
    pair = positive[:, None] - negative[None, :]
    return float(((pair > 0).sum() + 0.5 * (pair == 0).sum()) / pair.size)


def halves(df: pd.DataFrame):
    yield "fit", df[df.fitted]
    yield "unseen", df[~df.fitted]


def numeric_summary(df: pd.DataFrame, col: str) -> dict:
    x = df[[col, "r", "win"]].dropna()
    med = x[col].median()
    high, low = x[x[col] > med], x[x[col] <= med]
    positive, negative = x[x[col] >= 0], x[x[col] < 0]
    return {
        "n": len(x),
        "wins": int(x.win.sum()),
        "auc": auc_higher_is_better(x[col].to_numpy(), x.win.to_numpy(bool)),
        "corr_r": x[col].corr(x.r),
        "median": med,
        "hi_n": len(high),
        "hi_win": high.win.mean(),
        "hi_r": high.r.mean(),
        "lo_n": len(low),
        "lo_win": low.win.mean(),
        "lo_r": low.r.mean(),
        "median_win_delta": high.win.mean() - low.win.mean(),
        "median_r_delta": high.r.mean() - low.r.mean(),
        "pos_n": len(positive),
        "pos_win": positive.win.mean(),
        "pos_r": positive.r.mean(),
        "neg_n": len(negative),
        "neg_win": negative.win.mean(),
        "neg_r": negative.r.mean(),
        "zero_r_delta": positive.r.mean() - negative.r.mean(),
    }


def categorical_summary(df: pd.DataFrame, col: str, level: str) -> dict:
    inside = df[col].eq(level)
    a, b = df[inside], df[~inside]
    return {
        "level_n": len(a),
        "other_n": len(b),
        "level_win": a.win.mean() if len(a) else float("nan"),
        "other_win": b.win.mean() if len(b) else float("nan"),
        "win_delta": a.win.mean() - b.win.mean() if len(a) and len(b) else float("nan"),
        "level_r": a.r.mean() if len(a) else float("nan"),
        "other_r": b.r.mean() if len(b) else float("nan"),
        "r_delta": a.r.mean() - b.r.mean() if len(a) and len(b) else float("nan"),
    }


def candidate_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """16 predeclared linear candidates for the best-of-N null calculation."""
    out = df[list(NUMERIC)].copy()
    for col in NUMERIC:
        out[col] = out[col].fillna(out[col].median())
    for col in CATEGORICAL:
        dummies = pd.get_dummies(df[col], prefix=col, dtype=float)
        out = pd.concat([out, dummies], axis=1)
    return out


def best_of_n_null(df: pd.DataFrame) -> tuple[int, float, float]:
    """Permutation null for max absolute feature/R correlation over 16 candidates."""
    x = candidate_matrix(df).to_numpy(float)
    y = df.r.to_numpy(float)
    x = (x - x.mean(axis=0)) / x.std(axis=0)
    # Candidate columns are nonconstant in this dataset. Centering y after each
    # shuffle preserves its observed distribution while breaking all alignment.
    x = x[:, np.std(x, axis=0) > 0]
    x = x / np.sqrt((x * x).sum(axis=0))
    y = y - y.mean()
    observed = float(np.max(np.abs(x.T @ y) / np.sqrt((y * y).sum())))
    rng = np.random.default_rng(SEED)
    maxima = np.empty(PERMUTATIONS)
    for i in range(PERMUTATIONS):
        yp = rng.permutation(y)
        maxima[i] = np.max(np.abs(x.T @ yp) / np.sqrt((yp * yp).sum()))
    return x.shape[1], observed, float(np.quantile(maxima, 0.95))


def fmt(value: float, digits: int = 3) -> str:
    return "—" if pd.isna(value) else f"{value:+.{digits}f}"


def main() -> None:
    d = pd.read_csv(CSV)
    d["at"] = pd.to_datetime(d["at"], utc=True)
    d["fitted"] = d["fitted"].astype(bool)
    d["mom_D1"] = pd.to_numeric(d["mom_D1"], errors="coerce")
    d["win"] = d.r > 0
    for col in ("mom_H1", "mom_H4", "mom_D1"):
        d[col] = d[col] * np.where(d.side.eq("BUY"), 1.0, -1.0)

    print(f"Trades: {len(d)}; fit={int(d.fitted.sum())}; unseen={int((~d.fitted).sum())}")
    print("\nNUMERIC (AUC: larger reading ranks winners; median/zero splits are descriptive)")
    for col in NUMERIC:
        print(f"\n{col}")
        for name, frame in halves(d):
            s = numeric_summary(frame, col)
            print(
                f" {name:6s} n={s['n']:3d} wins={s['wins']:3d} auc={s['auc']:.3f} "
                f"corrR={fmt(s['corr_r'])} med={s['median']:.3f}; "
                f"above-median {s['hi_n']} win={s['hi_win']:.3f} R={fmt(s['hi_r'])}, "
                f"at/below {s['lo_n']} win={s['lo_win']:.3f} R={fmt(s['lo_r'])}; "
                f"deltaR={fmt(s['median_r_delta'])}; "
                f">=0 {s['pos_n']} R={fmt(s['pos_r'])}, <0 {s['neg_n']} R={fmt(s['neg_r'])}, "
                f"deltaR={fmt(s['zero_r_delta'])}"
            )

    print("\nCATEGORICAL (each level versus all other levels; winDelta and RDelta)")
    for col in CATEGORICAL:
        print(f"\n{col}")
        for level in sorted(d[col].dropna().unique()):
            cells = []
            for name, frame in halves(d):
                s = categorical_summary(frame, col, level)
                cells.append(
                    f"{name} {s['level_n']}/{s['other_n']} "
                    f"win={fmt(s['level_win'])}/{fmt(s['other_win'])} "
                    f"dWin={fmt(s['win_delta'])} R={fmt(s['level_r'])}/{fmt(s['other_r'])} "
                    f"dR={fmt(s['r_delta'])}"
                )
            print(f" {level}: " + " | ".join(cells))

    print("\nMOMENTUM OVERLAP: Pearson correlations of behind-trade values")
    for name, frame in halves(d):
        print(f"\n{name}\n{frame[['mom_H1', 'mom_H4', 'mom_D1']].corr().round(3)}")
    print("\nBOT x SIDE counts")
    print(pd.crosstab(d.bot, d.side).to_string())
    print("\nBOT x REGIME counts")
    print(pd.crosstab(d.bot, d.regime).to_string())
    k, obs, null95 = best_of_n_null(d)
    print(
        f"\nBest-of-N null: {k} predeclared numeric/one-hot columns; observed max |corr(R)|="
        f"{obs:.3f}; 95th percentile after {PERMUTATIONS} R permutations={null95:.3f}"
    )
    print("\nHALF BASELINES")
    for name, frame in halves(d):
        print(f"{name}: n={len(frame)} win={frame.win.mean():.3f} meanR={frame.r.mean():+.3f}")
    print(f"D1 missing: {int(d.mom_D1.isna().sum())} trades")


if __name__ == "__main__":
    main()
