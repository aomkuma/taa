"""The assessment, version 1 (SPEC.md section 3), on candidates.parquet. Written before any result was read:

- Each component's reading becomes +1 (favours the trade), -1 or 0 by a map fixed here, not fitted.
- FIT = 2023-09-01 .. 2025-03-31, split into two halves at 2024-06-01. A component is kept when its effect (the
  mean R of its +1 candidates minus that of its -1 candidates) is positive in BOTH halves, with at least 30
  candidates on each side in each half. No other selection.
- The score = the sum of the kept components (equal weights - the owner's order is the prior, the data only
  keeps or drops); trade when score > 0. One rule, no threshold search.
- JUDGE = 2025-04-01 .. 2025-09-30 (not used to design anything here), read once; then 2025-10 .. 2026-04-17 (the
  NY-B2 journal's learning weeks) and 2026-04-18 .. 10-16 (the exam months - seen before, shown for information).

    .venv/Scripts/python research/2026-10-23-entry/assess.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
FIT = (T("2023-09-01"), T("2025-04-01"))
HALF = T("2024-06-01")
PERIODS = [("JUDGE 2025-04 .. 09", T("2025-04-01"), T("2025-10-01")), ("2025-10 .. 2026-04-17", T("2025-10-01"), T("2026-04-18")),
           ("2026-04-18 .. 10-16 (seen)", T("2026-04-18"), T("2026-10-17"))]


def through(x: pd.DataFrame) -> pd.Series:
    """The triggers that trade with the break (T1, T4 through) vs the bounces (T2, T4 bounce)."""
    return x.trig.isin(["T1", "T4 through"])


MAPS = {
    "c1 stop outside the pools": lambda x: np.where(x.c1_stop_in_pool, -1, 1),
    "c1 entry not late (< 0.15 step from the line)": lambda x: np.where(x.c1_late_step < 0.15, 1, -1),
    "c2 H1 structure with the trade": lambda x: np.sign(x.c2_h1_struct),
    "c2 H1 picture clear": lambda x: np.where(x.c2_h1_clear, 1, -1),
    "c3 trend M15+H1+H4+D1 with the trade": lambda x: np.sign(x.c3_m15 + x.c3_h1 + x.c3_h4 + x.c3_d1),
    "c3 D1 trend with the trade": lambda x: np.sign(x.c3_d1),
    "c3 a 3-day run with the trade": lambda x: np.sign(x.c3_phase),
    "c4 level worn: helps a break, hurts a bounce": lambda x: np.where(x.c4_worn, np.where(through(x), 1, -1), 0),
    "c4 many touches (5+): helps a break, hurts a bounce": lambda x: np.where(x.c4_touches >= 5, np.where(through(x), 1, -1), 0),
    "c4 a fast approach (> 2 ATR): hurts a bounce": lambda x: np.where((x.c4_approach > 2) & ~through(x), -1, 0),
    "c4 a long time at the line (8+ M15 bars): helps a break": lambda x: np.where(x.c4_bars_at_line >= 8, np.where(through(x), 1, -1), 0),
    "c5b room to the first strong level >= 2 R": lambda x: np.where(x.c5b_room_r >= 2, 1, -1),
    "c5b a strong line (5+ swing touches): helps a bounce, hurts a break": lambda x: np.where(x.c5b_line_touches >= 5, np.where(through(x), -1, 1), 0),
    "c6 volatility normal (H1 ATR <= 1.1 x median)": lambda x: np.where(x.c6_vol > 1.1, -1, 1),
    "c7 not 0-30 min after 10:00 New York": lambda x: np.where((x.c7_min_10ny > 0) & (x.c7_min_10ny <= 30), -1, 1),
    "c7 inside the owner's windows (Asia 7-9, London 13-15, NY 19-23 Thai)": lambda x: np.where(
        x.c7_thai_hour.isin([7, 8, 13, 14, 19, 20, 21, 22]), 1, -1),
    "c8 volume >= 1.2 x usual on the entry bar": lambda x: np.where(x.c8_rel_vol >= 1.2, 1, np.where(x.c8_rel_vol < 0.8, -1, 0)),
    "c9 yesterday's D1 bar with the trade": lambda x: np.sign(x.c9_day_dir),
    "c9 yesterday strong and with the trade": lambda x: np.where(x.c9_day_strong, np.sign(x.c9_day_dir), 0),
    "c9 the day not already run > 1 step the trade's way": lambda x: np.where(x.c9_run > 1, -1, 1),
}


def effect(x: pd.DataFrame, f: np.ndarray) -> tuple[float, int, int]:
    pos, neg = x.r[f > 0], x.r[f < 0]
    return (pos.mean() - neg.mean() if len(pos) and len(neg) else np.nan), len(pos), len(neg)


def main() -> None:
    X = pd.read_parquet(HERE / "candidates.parquet").dropna(subset=["r"])
    F = {name: np.asarray(fn(X), float) for name, fn in MAPS.items()}
    fit = (X.t >= FIT[0]) & (X.t < FIT[1])
    h1, h2 = fit & (X.t < HALF), fit & (X.t >= HALF)
    print(f"FIT {fit.sum()} candidates ({h1.sum()} / {h2.sum()}); all triggers raw in FIT {X.r[fit].mean():+.3f} R")
    print(f"\n{'component':72s} {'half 1':>8s} {'half 2':>8s}  kept")
    kept = []
    for name, f in F.items():
        e1, p1, n1 = effect(X[h1], f[h1])
        e2, p2, n2 = effect(X[h2], f[h2])
        ok = e1 > 0 and e2 > 0 and min(p1, n1, p2, n2) >= 30
        kept.append(name) if ok else None
        print(f"{name:72s} {e1:+8.3f} {e2:+8.3f}  {'KEPT' if ok else ''}  (n {p1}/{n1}, {p2}/{n2})")
    score = sum(F[n] for n in kept)
    X["score"] = score
    take = X.score > 0
    print(f"\nkept {len(kept)} of {len(F)} components; trade when the sum > 0")
    print(f"\n{'period':32s} {'all R':>8s} {'n':>6s} {'taken R':>8s} {'n':>6s} {'won':>5s}  by trigger (taken R / n)")
    for name, a, b in [("FIT 2023-09 .. 2025-03", *FIT), *PERIODS]:
        p = (X.t >= a) & (X.t < b)
        tk = X[p & take]
        by = "  ".join(f"{g}: {d.r.mean():+.3f}/{len(d)}" for g, d in tk.groupby("trig"))
        print(f"{name:32s} {X.r[p].mean():+8.3f} {p.sum():6d} {tk.r.mean():+8.3f} {len(tk):6d} {(tk.r > 0).mean() * 100:4.0f}%  {by}")


if __name__ == "__main__":
    main()
