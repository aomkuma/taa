"""The two-way sweep at the news - part 1, the description (notes.md, written before it is computed; owner, 2026-10-19:
"to really buy, wait for the fake drop in the first minute - then it sweeps up, and then it comes down"; "that is the
case of the fake break upward"). On the real ticks (the mid price), at each weekday's 08:30 and 10:00 New York minute
of the learning parts: the first leg, then continued or faked (the sweep the other way), the sweep's size and the
third leg back.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/news_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

NEWS = ((8, 30), (10, 0))  # New York
FIRST_S, LEG, RUN, WIN_MIN, BACK_MIN = 60, 3.0, 10.0, 15, 15
NS_S = 10**9
NS_MIN = 60 * NS_S


def sweep(t: np.ndarray, mid: np.ndarray, t_rel: int) -> dict | None:
    """The path from the release (t_rel, ns). p0 = the last mid before it; the first leg = the side of the first LEG-USD
    move from p0 within FIRST_S seconds ('quiet' if none), leg1 = its extreme in that minute. Then, after the first
    minute and within WIN_MIN minutes of the release: a new extreme beyond leg1 first ('continued'), p0 + RUN the
    other way first ('faked' - the sweep; owner 2026-10-19: the first minute fakes, then it sweeps the other way), or
    'neither'. For a faked one: the sweep's extreme beyond p0 in those minutes, its minute, the move back from it within
    BACK_MIN minutes, and whether price crosses p0 again (the third leg). USD signed: + = the first leg's way."""
    k0 = int(np.searchsorted(t, t_rel, side="left")) - 1
    if k0 < 0:
        return None
    p0 = float(mid[k0])
    a = k0 + 1
    b1 = int(np.searchsorted(t, t_rel + FIRST_S * NS_S, side="left"))
    hit = np.nonzero(np.abs(mid[a:b1] - p0) >= LEG)[0]
    if not len(hit):
        return dict(p0=p0, first=0, outcome="quiet")
    i1 = a + int(hit[0])
    s1 = int(np.sign(mid[i1] - p0))
    leg1 = float(np.max(s1 * (mid[a:b1] - p0)))
    end = int(np.searchsorted(t, t_rel + WIN_MIN * NS_MIN, side="left"))
    e = s1 * (mid[b1:end] - p0)
    c, f = np.nonzero(e > leg1)[0], np.nonzero(e <= -RUN)[0]
    ci, fi = (int(c[0]) if len(c) else len(e)), (int(f[0]) if len(f) else len(e))
    out = dict(p0=p0, first=s1, leg1=leg1, t_leg=int(t[i1]),
               outcome="continued" if ci < fi else "faked" if fi < ci else "neither")
    if out["outcome"] != "faked":
        return out
    j = b1 + int(np.argmin(e))  # the sweep's extreme (the most the other way)
    back_end = int(np.searchsorted(t, t[j] + BACK_MIN * NS_MIN, side="left"))
    after = s1 * (mid[j + 1:back_end] - p0)
    out.update(sweep=float(-e[j - b1]), t_sweep=int(t[j]), sweep_min=(t[j] - t_rel) / NS_MIN,
               back=float(np.max(after) - e[j - b1]) if len(after) else 0.0,
               third=bool(len(after) and np.max(after) >= 0))
    return out


def events(days: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, str]]:
    """The release seconds of the weekdays, in UTC, with their names."""
    out = []
    for d in days:
        if d.weekday() >= 5:
            continue
        for hh, mm in NEWS:
            ny = pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hh, minute=mm, tz="America/New_York")
            out.append((ny.tz_convert("UTC"), f"{hh:02d}:{mm:02d} NY"))
    return out


def main() -> None:
    from m15_trades import PARTS, part_of  # noqa: PLC0415
    from tick_straddle import day_ticks  # noqa: PLC0415

    X = pd.read_parquet(HERE / "m1_features.parquet").set_index("t")
    days = pd.date_range(PARTS["P1"][0], PARTS["P2"][1], freq="D", tz="UTC", inclusive="left")
    rows = []
    for day in days:
        tk = day_ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        mid = (bid + ask) / 2
        for t_rel, name in events(pd.DatetimeIndex([day])):
            x = sweep(t, mid, t_rel.value)
            if x is None:
                continue
            v = X.vol1.get(t_rel, np.nan)
            rows.append(dict(t=t_rel, news=name, vol1=v, released=bool(v >= 2), **x))
    T = pd.DataFrame(rows)
    T["part"] = part_of(pd.DatetimeIndex(T.t))
    T.to_parquet(HERE / "news_sweep.parquet")
    pd.set_option("display.width", 220)
    for news, G in T.groupby("news"):  # vol1 >= 2 marked only 5 releases (the same UTC minute is busy most days): not split
        print(f"\n{news}: {len(G)} days")
        for p, D in G.groupby("part"):
            n = len(D)
            oc = D.outcome.value_counts()
            Fk = D[D.outcome == "faked"]
            print(f"  {p}: n {n}; first leg up {int((D['first'] > 0).sum())} / down {int((D['first'] < 0).sum())}; "
                  + ", ".join(f"{k} {oc.get(k, 0) / n:.2f}" for k in ("continued", "faked", "neither", "quiet"))
                  + (f"; faked: the sweep median {Fk.sweep.median():.1f} USD at minute {Fk.sweep_min.median():.1f}, back "
                     f"{Fk.back.median():.1f}, the third leg {Fk.third.mean():.2f}" if len(Fk) else ""))
    print("\nthe faked ones:")
    print(T[T.outcome == "faked"][["news", "part", "vol1", "first", "leg1", "sweep", "sweep_min", "back", "third"]]
          .round(2).assign(t=T.t).to_string(index=False))


if __name__ == "__main__":
    main()
