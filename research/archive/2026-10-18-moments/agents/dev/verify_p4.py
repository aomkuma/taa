"""The second, separate check of P4's numbers: verify_p3's re-derivation (no import of p2_trades / p3_trades /
p4_trades / patterns / sweep_detector) plus its own window function - every trade's entry decision must lie in its
window, and every metric per setting x part x news cost x window must agree with p4_metrics_W_WL.csv.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/verify_p4.py [TRADES METRICS]
"""

from __future__ import annotations

import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "precursors"))
sys.path.insert(0, str(HERE))
import verify_p2 as V2  # noqa: E402
import verify_p3 as V3  # noqa: E402

assert Path(V2.__file__).resolve().parent == HERE, "imported the wrong verify_p2"


def us_summer(day: datetime) -> bool:
    """US summer time by its own rule: from the second Sunday of March 02:00 to the first Sunday of November 02:00
    (local); day = the New York date (the hour-of-switch never falls inside 09:30 - 11:30)."""
    y = day.year
    march = datetime(y, 3, 8 + (6 - datetime(y, 3, 8).weekday()) % 7)  # the second Sunday
    nov = datetime(y, 11, 1 + (6 - datetime(y, 11, 1).weekday()) % 7)  # the first Sunday
    return march.date() <= day.date() < nov.date()


def window_of(t_ns: int, london_pad: int = 0) -> str | None:
    """Its own windows: Thai = UTC + 7 fixed; New York = UTC - 4 in US summer time, else UTC - 5."""
    t = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=t_ns // 1000)
    th = t + timedelta(hours=7)
    m = th.hour * 60 + th.minute + th.second / 60
    if 420 <= m < 540:
        return "Asia"
    if 780 - london_pad <= m < 840 + london_pad:
        return "London"
    return "NY" if 570 <= ny_minute(t_ns) < 690 else None


def ny_minute(t_ns: int) -> float:
    """The New York minute of the day by its own summer-time rule."""
    t = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=t_ns // 1000)
    ny = t - timedelta(hours=5)
    if us_summer(ny):
        ny = t - timedelta(hours=4)
    return ny.hour * 60 + ny.minute + ny.second / 60


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 2 else "p4_trades_W_WL_WN.parquet"
    met = sys.argv[2] if len(sys.argv) > 2 else "p4_metrics_W_WL_WN.csv"
    A = pd.read_parquet(HERE / src)
    M = pd.read_csv(HERE / met)
    pads = {"W": 0, "WL": 30, "WN": 0}
    wrong = sum(window_of(r.t_entry, pads[r.variant]) != r.window for r in A.itertuples())
    print(f"0. the window of every entry decision, by its own clock: {len(A) - wrong} of {len(A)} agree")
    wn = A[A.variant == "WN"]
    ten = sum(window_of(t) == "NY" and ny_minute(t) is not None and 600 <= ny_minute(t) < 630 for t in wn.t_entry)
    print(f"   WN entries at 10:00 - 10:30 NY by its own clock: {ten} (must be 0) of {len(wn)}")
    wrong += ten
    keys = ["n", "per_day", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd"] + [f"x_{e}" for e in V3.EXITS]
    agree = total = 0
    for m in M.itertuples(index=False):
        G = A[(A.variant == m.variant) & (A.part == m.part) & (A.news_cost == m.news_cost)]
        if m.window != "all":
            G = G[[window_of(t, pads[m.variant]) == m.window for t in G.t_entry]]
        if not len(G):
            ok = m.n == 0
            total, agree = total + 1, agree + ok
            continue
        mine = V3.metrics(G.to_dict("records"), m.part)
        for k in keys:
            total += 1
            a, b = mine[k], getattr(m, k)
            ok = (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1.0, abs(a))
            agree += ok
            if not ok:
                print(f"  DIFFERENT {m.variant} {m.part} {m.window} +{m.news_cost} {k}: {a} vs {b}")
    print(f"1. the metrics per window recomputed: {agree} of {total} values agree", flush=True)
    C = pd.read_parquet(HERE / "p_catches.parquet")
    bars = V3.Bars()
    rng = random.Random(20261019)
    days: dict = {}
    good = n = 0
    for v in A.variant.unique():
        rows = A[(A.variant == v) & (A.news_cost == 0.0)].to_dict("records")
        for tr in rng.sample(rows, min(20, len(rows))):
            d = pd.Timestamp(tr["entry_t"], tz="UTC").normalize()
            for dd in (d, d + pd.Timedelta(days=1)):
                if dd not in days:
                    days[dd] = V2.raw_ticks(dd)
            tk = pd.concat([days[d], days[d + pd.Timedelta(days=1)]], ignore_index=True)
            c = C[(C.tf == tr["tf"]) & (C.t_dec == tr["t_dec"]) & (C.family == tr["family"]) & (C.side == tr["side"])].iloc[0]
            inv = float(c.box_p[0] if tr["side"] > 0 else c.box_p[1]) if tr["family"] == "base" else float(c.pts_p[-1])
            bad = V3.rederive3(tr, tk, bars, inv)
            n += 1
            good += not bad
            if bad:
                print(f"  {v} {pd.Timestamp(tr['entry_t'], tz='UTC')} {tr['exit']}: {bad}")
    print(f"2. trades re-derived from the raw ticks and its own bars: {good} of {n} agree", flush=True)
    over = {(v, c): V2.one_at_a_time(G.to_dict("records")) for (v, c), G in A.groupby(["variant", "news_cost"])}
    print(f"3. one position at a time: entries before the previous exit {sum(over.values())} in {len(over)} streams")
    if wrong or agree != total or good != n or sum(over.values()):
        raise SystemExit("VERIFICATION FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
