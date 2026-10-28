"""Setup OWN's exits on the moments' entries (docs/OWN_SETUP_ROUNDS.md "Exits"), with the stop measured from the data.

For every playbook entry of ``moments.py``: the scalp target max(5 USD, 0.5 U), time stop 60 minutes; in a
clear picture (H1 and M15 swing structure both the trade's way) the target arms a stop that locks half the
target and trails 0.5 U behind the best price, time stop 180 minutes. Stops: the playbook's invalidation (S0)
and the 70th / 80th / 90th percentile of the adverse excursion the fit window's winners took before the target
(S70 / S80 / S90, per playbook, in units of U). Results in R and in USD at 0.01 lot (1 USD per 1.00 of price).
Only the fit months (2026-04-14 .. 07-14) are printed; the judged months are saved, never read here.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/exits.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from moments import FIT_END, OUT, POINT, SLIP, START  # noqa: E402

TARGET_USD, TARGET_U = 5.0, 0.5
SCALP_HOLD, TREND_HOLD = 60, 180
LOCK, TRAIL_U = 0.5, 0.5
QUANTILES = (70, 80, 90)


class Path:
    def __init__(self, start: pd.Timestamp = START) -> None:
        m1 = gold.bars("M1")
        m1 = m1[m1.index >= start - pd.Timedelta(days=3)]
        self.ot = m1.index
        self.o, self.h, self.lo, self.c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m1["spread"].to_numpy(float) * POINT

    def entry(self, e: int, side: int) -> float:
        return self.o[e] + (self.sp[e] + SLIP if side > 0 else -SLIP)

    def mae_to_target(self, e: int, side: int, tp_dist: float) -> float:
        """The adverse excursion before the scalp target (inclusive of its bar); NaN when the target is not
        reached within the scalp hold."""
        entry = self.entry(e, side)
        tp, worst = entry + side * tp_dist, 0.0
        for j in range(e, min(e + SCALP_HOLD, len(self.o))):
            adverse = self.lo[j] if side > 0 else self.h[j] + self.sp[j]
            favour = self.h[j] if side > 0 else self.lo[j] + self.sp[j]
            worst = max(worst, (entry - adverse) * side)
            if (favour - tp) * side >= 0:
                return worst
        return np.nan

    def run(self, e: int, side: int, stop: float, tp_dist: float, hold: bool, u: float) -> tuple[float, float, int]:
        """(R, USD at 0.01 lot, minutes held) of one trade."""
        entry = self.entry(e, side)
        risk = (entry - stop) * side
        if risk <= 0 or e + (TREND_HOLD if hold else SCALP_HOLD) >= len(self.o):
            return np.nan, np.nan, 0
        tp = entry + side * tp_dist
        cur, armed, best = stop, False, np.nan
        end = e + (TREND_HOLD if hold else SCALP_HOLD)
        for j in range(e, end):
            adverse = self.lo[j] if side > 0 else self.h[j] + self.sp[j]
            favour = self.h[j] if side > 0 else self.lo[j] + self.sp[j]
            if (adverse - cur) * side <= 0:
                px = cur - side * SLIP
                return (px - entry) * side / risk, (px - entry) * side, j - e + 1
            if armed:
                best = max(best, favour) if side > 0 else min(best, favour)
                trail = best - side * TRAIL_U * u
                cur = max(cur, trail) if side > 0 else min(cur, trail)
            elif (favour - tp) * side >= 0:
                if not hold:
                    return (tp - entry) * side / risk, (tp - entry) * side, j - e + 1
                armed, best = True, favour
                lock = entry + side * LOCK * tp_dist
                cur = max(cur, lock) if side > 0 else min(cur, lock)
        x = end - 1
        px = self.c[x] - (SLIP if side > 0 else -(self.sp[x] + SLIP))
        return (px - entry) * side / risk, (px - entry) * side, end - e


def main() -> None:
    gold.below_normal_priority()
    P = Path()
    f = pd.read_parquet(f"{OUT}_features.parquet")
    t = pd.read_parquet(f"{OUT}_trades.parquet").merge(
        f[["rid", "tags", "kind", "u", "squeeze", "pool_side", "flow", "clear", "spread"]], on="rid"
    )
    t["e"] = P.ot.searchsorted(t["te"])
    assert (P.ot[t["e"]] == t["te"]).all()
    t["tp_dist"] = np.maximum(TARGET_USD, TARGET_U * t["u"])
    t["hold"] = t["clear"] == t["side"]
    t["fit"] = t["t"] < FIT_END
    t["mae_u"] = [
        P.mae_to_target(e, s, d) / u for e, s, d, u in zip(t.e, t.side, t.tp_dist, t.u, strict=True)
    ]
    q = {
        pb: {k: float(np.nanpercentile(g.loc[g.fit, "mae_u"], k)) for k in QUANTILES}
        for pb, g in t.groupby("pb")
    }
    print("Stop distances from the fit winners' adverse excursion (units of U):")
    for pb, v in q.items():
        n = int(t[(t.pb == pb) & t.fit].mae_u.notna().sum())
        print(f"  {pb}: " + ", ".join(f"q{k} {x:.2f}" for k, x in v.items()) + f"  (winners {n})")
    for name in ("S0", *(f"S{k}" for k in QUANTILES)):
        res = []
        for row in t.itertuples():
            entry = P.entry(row.e, row.side)
            stop = row.stop if name == "S0" else entry - row.side * q[row.pb][int(name[1:])] * row.u
            res.append(P.run(row.e, row.side, stop, row.tp_dist, bool(row.hold), row.u))
        t[f"r_{name}"] = [x[0] for x in res]
        t[f"usd_{name}"] = [x[1] for x in res]
        t[f"min_{name}"] = [x[2] for x in res]
        t[f"risk_{name}"] = [
            (P.entry(e, s) - (st if name == "S0" else P.entry(e, s) - s * q[pb][int(name[1:])] * u)) * s
            for e, s, st, pb, u in zip(t.e, t.side, t.stop, t.pb, t.u, strict=True)
        ]
    t.to_parquet(f"{OUT}_exits.parquet")
    fit = t[t.fit & (t.kind == "moment")]
    days = fit.t.dt.normalize().nunique()
    print(f"\nFit months, moments only ({days} days), every entry (no one-at-a-time yet):")
    print("  pb  stop   n   R/trade  win%  USD/trade  risk USD  min held  hold share")
    for pb, g in fit.groupby("pb"):
        for name in ("S0", *(f"S{k}" for k in QUANTILES)):
            r = g[f"r_{name}"].dropna()
            print(
                f"  {pb}  {name:4} {len(r):4}  {r.mean():+.3f}  {100 * (r > 0).mean():4.0f}"
                f"  {g[f'usd_{name}'].mean():+8.2f}  {g[f'risk_{name}'].median():8.2f}"
                f"  {g[f'min_{name}'].median():8.0f}  {g.hold.mean():.2f}"
            )


if __name__ == "__main__":
    main()
