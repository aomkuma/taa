"""The owner's three kinds of losers (2026-10-17), for every trade stopped out before its target:

1. wrong way - less than half the way to the target before the stop, and no run to the target afterwards;
2. right way, fell short - at least half the way to the target before the stop, then back to the stop, and no
   run to the target afterwards;
3. right way, entered too early - stopped first, then price reached the target (from the original entry)
   within 120 minutes of the entry: the run was real, the entry's volatility took the stop.

Kind 3 also shows how wide a stop would have survived (the adverse extreme before the target) and when that
extreme came (how much later an entry would have missed it); kind 2 how far it got (a break-even move or a
partial profit would have saved it).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/loser_kinds.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
from exits import SCALP_HOLD, Path  # noqa: E402
from select_fit import group  # noqa: E402

AFTER, HALF = 120, 0.5


def classify(P: Path, e: int, side: int, stop: float, tp_dist: float) -> dict | None:
    """None when the trade was not stopped before its target (a winner or a time-stop exit)."""
    entry = P.entry(e, side)
    tp = entry + side * tp_dist
    hit = None
    for j in range(e, min(e + SCALP_HOLD, len(P.o))):
        adverse = P.lo[j] if side > 0 else P.h[j] + P.sp[j]
        favour = P.h[j] if side > 0 else P.lo[j] + P.sp[j]
        if (adverse - stop) * side <= 0:
            hit = j
            break
        if (favour - tp) * side >= 0:
            return None
    if hit is None:
        return None
    fav = (lambda a, b: (P.h[a:b].max() - entry) if side > 0 else (entry - (P.lo[a:b] + P.sp[a:b]).min()))
    mfe_before = fav(e, hit) if hit > e else 0.0
    end = min(e + AFTER, len(P.o))
    reached, j_tp = False, None
    for j in range(hit + 1, end):
        favour = P.h[j] if side > 0 else P.lo[j] + P.sp[j]
        if (favour - tp) * side >= 0:
            reached, j_tp = True, j
            break
    kind = "3 entered too early" if reached else ("2 right way, fell short" if mfe_before >= HALF * tp_dist else "1 wrong way")
    out = {"kind": kind, "mfe_before": mfe_before / tp_dist, "stop_min": hit - e + 1, "risk": (entry - stop) * side}
    if reached:
        seg = slice(e, j_tp + 1)
        worst = (entry - P.lo[seg].min()) if side > 0 else ((P.h[seg] + P.sp[seg]).max() - entry)
        k_worst = int(np.argmin(P.lo[seg]) if side > 0 else np.argmax(P.h[seg] + P.sp[seg]))
        out |= {"survive_stop": worst, "worst_min": k_worst + 1, "tp_min": j_tp - e + 1}
    return out


def report(name: str, P: Path, t: pd.DataFrame) -> None:
    rows = []
    for row in t.itertuples():
        c = classify(P, row.e, row.side, row.stop_px, row.tp_dist)
        if c:
            rows.append({"session": row.session, "pb": row.pb, "u": row.u, "tp_dist": row.tp_dist} | c)
    d = pd.DataFrame(rows)
    n = len(t)
    print(f"\n== {name}: {n} trades, {len(d)} stopped before the target ({100 * len(d) / n:.0f}%)")
    tab = d.groupby("kind").agg(
        n=("kind", "size"),
        stop_min=("stop_min", "median"),
        mfe_before=("mfe_before", "median"),
        risk_usd=("risk", "median"),
    )
    tab["share"] = (tab.n / len(d)).round(2)
    print(tab.round(2).to_string())
    print("  by session:", d.groupby(["session", "kind"]).size().unstack(fill_value=0).to_dict("index"))
    k3 = d[d.kind.str.startswith("3")]
    if len(k3):
        ratio = k3.survive_stop / k3.risk
        print(f"  kind 3 ({len(k3)}): the stop that would have survived = {ratio.median():.2f}x the stop used (median),"
              f" q75 {ratio.quantile(0.75):.2f}x, in USD median {k3.survive_stop.median():.2f} vs used {k3.risk.median():.2f};"
              f" the adverse extreme came {k3.worst_min.median():.0f} min after the entry (q75 {k3.worst_min.quantile(0.75):.0f}),"
              f" the target {k3.tp_min.median():.0f} min after (q75 {k3.tp_min.quantile(0.75):.0f})")
    k2 = d[d.kind.str.startswith("2")]
    if len(k2):
        print(f"  kind 2 ({len(k2)}): got {k2.mfe_before.median():.2f} of the target before turning (median),"
              f" q25 {k2.mfe_before.quantile(0.25):.2f}; stopped {k2.stop_min.median():.0f} min after the entry")


def round1(prefix: str, start: str) -> None:
    P = Path(pd.Timestamp(start, tz="UTC"))
    t = pd.read_parquet(f"{prefix}_exits.parquet")
    t = t[(t.kind == "moment") & t.r_S70.notna()].copy()
    t["e"] = P.ot.searchsorted(t.te)
    t["session"] = t.tags.map(group)
    t["stop_px"] = [P.entry(e, s) - s * r for e, s, r in zip(t.e, t.side, t.risk_S70, strict=True)]
    report("Round 1, every moment entry (latest six months, q70 stop)", P, t)
    for pb in ("P1", "P2", "P3"):
        report(f"Round 1, {pb}", P, t[t.pb == pb])


def v2(prefix: str, start: str, name: str) -> None:
    P = Path(pd.Timestamp(start, tz="UTC"))
    t = pd.read_parquet(f"{prefix}_v2.parquet")
    t["e"] = P.ot.searchsorted(t.te)
    t["tp_dist"] = np.maximum(5.0, 0.5 * t.u)
    t["stop_px"] = [P.entry(e, s) - s * 0.38 * u for e, s, u in zip(t.e, t.side, t.u, strict=True)]
    report(name, P, t)


def main() -> None:
    round1("data/research/own_moments", "2026-04-14")
    v2("data/research/own_moments", "2026-04-14", "OWN v2, latest six months (development)")
    v2("data/research/own_moments_prev", "2025-10-14", "OWN v2, earlier six months (untouched test)")


if __name__ == "__main__":
    main()
