"""News agent: the event panel and the trade simulator (the bot's conventions, BRIEF.md).

Periods: A = 2021-09 .. 2023-10 (older design), B = 2023-11 .. 2026-02 (design), T = 2026-03-01 .. 2026-10-14
(the test, touched once per frozen rule).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

SLIP = 0.07
HERE = Path(__file__).parent
A0, B0, T0, T1 = (pd.Timestamp(x, tz="UTC") for x in ("2021-09-01", "2023-11-01", "2026-03-01", "2026-10-14 08:18"))
PRIORITY = ["FOMC", "PC", "MIN", "NFP", "CPI", "PCE", "PPI", "RET", "GDP", "CLM"]


def period(t: pd.Timestamp) -> str:
    return "A" if t < B0 else ("B" if t < T0 else "T")


class Gold:
    def __init__(self) -> None:
        m = gold.bars("M1")
        self.ot = m.index
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * 0.01
        self.pos = pd.Series(np.arange(len(m)), index=m.index)

    def fill(self, e: int, side: int) -> float:
        return self.o[e] + (self.sp[e] + SLIP if side > 0 else -SLIP)

    def trade(self, e: int, side: int, sl: float, tp: float | None, hz: int, be: float | None = None,
              trail: float | None = None, kind_tp: float | None = None) -> dict:
        """sl / tp: distances (USD) from the fill. be: share of tp at which the stop moves to the entry.
        trail: after +1R the stop trails the best price by *trail* USD. Losers' kind against *kind_tp*
        (default tp)."""
        entry = self.fill(e, side)
        stop, armed, mfe = entry - side * sl, False, 0.0
        end = min(e + hz, len(self.o) - 1)
        res = None
        for j in range(e, end):
            adv = self.lo[j] if side > 0 else self.h[j] + self.sp[j]
            fav = self.h[j] if side > 0 else self.lo[j] + self.sp[j]
            if (adv - stop) * side <= 0:
                px = stop - side * SLIP
                res = ("stop" if not armed else "be", (px - entry) * side, j)
                break
            if tp is not None and (fav - entry) * side >= tp:
                res = ("win", tp, j)
                break
            mfe = max(mfe, (fav - entry) * side)
            if be is not None and tp is not None and not armed and mfe >= be * tp:
                armed, stop = True, entry
            if trail is not None and mfe >= sl:
                armed = True
                best = entry + side * mfe
                new = best - side * trail
                if (new - stop) * side > 0:
                    stop = new
        if res is None:
            x = end - 1
            px = self.c[x] - (SLIP if side > 0 else -(self.sp[x] + SLIP))
            res = ("time", (px - entry) * side, x)
        kind = ""
        ktp = kind_tp if kind_tp is not None else tp
        if res[0] == "stop" and ktp is not None:
            later = range(res[2] + 1, min(e + 120, len(self.o)))
            hit = any(((self.h[k] if side > 0 else self.lo[k] + self.sp[k]) - entry) * side >= ktp for k in later)
            kind = "3" if hit else ("2" if mfe >= 0.5 * ktp else "1")
        return dict(exit=res[0], usd=res[1], mins=res[2] - e + 1, kind=kind, R=res[1] / (sl + SLIP))


def events(extra: bool = False) -> pd.DataFrame:
    """One row per release minute; the main event by PRIORITY. *extra*: add the calendars in this folder
    (extra_releases.csv: date,time_et,event,source)."""
    cal = gold.releases()[["t", "event"]]
    if extra and (HERE / "extra_releases.csv").exists():
        x = pd.read_csv(HERE / "extra_releases.csv", dtype=str, keep_default_na=False)
        local = pd.to_datetime(x["date"] + " " + x["time_et"]).dt.tz_localize(gold.NY)
        x["t"] = local.dt.tz_convert("UTC")
        cal = pd.concat([cal, x[["t", "event"]]], ignore_index=True)
    cal = cal[(cal.t >= A0) & (cal.t < T1)]
    ev = cal.groupby("t").event.apply(lambda v: sorted(set(v), key=PRIORITY.index)).reset_index()
    ev["main"] = ev.event.str[0]
    ev["all"] = ev.event.str.join("+")
    ev["per"] = ev.t.map(period)
    return ev.drop(columns="event")


def summary(r: pd.DataFrame, label: str = "") -> str:
    if not len(r):
        return f"{label:28}   0"
    k = r.kind[r.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    return (f"{label:28} {len(r):4} win {100 * (r.exit == 'win').mean():3.0f}% pos {100 * (r.usd > 0).mean():3.0f}% "
            f"USD/tr {r.usd.mean():+7.2f} R/tr {r.R.mean():+.3f} sum {r.usd.sum():+8.1f} "
            f"kinds {100 * k['1']:3.0f}/{100 * k['2']:3.0f}/{100 * k['3']:3.0f}")
