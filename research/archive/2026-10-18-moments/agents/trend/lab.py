"""Shared helpers for the "trend" agent: gold M1 arrays from 2021-09, session opens, H1 context and a trade
simulator with a fixed target, a fixed stop, an optional break-even, an optional trailing stop and a time exit
(the brief's conventions: decide at a bar's close, fill at the next bar's open; a BUY at the ask + 0.07, a SELL at
the bid - 0.07; a SELL's stop/target on the ask; stop and target in one bar = the stop; a stop pays 0.07; a time
exit at the bar's close with slippage)."""

from __future__ import annotations

import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

SLIP = 0.07
LON = ZoneInfo("Europe/London")
NY = ZoneInfo("America/New_York")
DESIGN_END = pd.Timestamp("2026-03-01", tz="UTC")
TEST_END = pd.Timestamp("2026-10-15", tz="UTC")

HALVES = [
    ("2021-09..2022-02", "2021-09-01", "2022-03-01"),
    ("2022-03..2022-08", "2022-03-01", "2022-09-01"),
    ("2022-09..2023-02", "2022-09-01", "2023-03-01"),
    ("2023-03..2023-08", "2023-03-01", "2023-09-01"),
    ("2023-09..2024-02", "2023-09-01", "2024-03-01"),
    ("2024-03..2024-08", "2024-03-01", "2024-09-01"),
    ("2024-09..2025-02", "2024-09-01", "2025-03-01"),
    ("2025-03..2025-08", "2025-03-01", "2025-09-01"),
    ("2025-09..2026-02", "2025-09-01", "2026-03-01"),
]


class Bars:
    def __init__(self) -> None:
        m = gold.bars("M1")
        m = m[m.index < TEST_END]
        self.ot = m.index
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(np.float64) * 0.01
        self.ns = np.asarray(self.ot.as_unit("ns").asi8)

    def idx_at(self, ts: pd.Timestamp) -> int:
        """Index of the first bar opening at or after *ts*."""
        return int(np.searchsorted(self.ns, ts.as_unit("ns").value))

    def entry_px(self, e: int, side: int) -> float:
        return self.o[e] + (self.sp[e] + SLIP if side > 0 else -SLIP)

    def trade(self, e: int, side: int, sl: float, tp: float | None, hz_end: int, be: float | None = None,
              trail: float | None = None, trail_start: float = 0.0, stop_px: float | None = None) -> dict:
        """One trade entered at bar *e*'s open. *sl*: the stop distance (USD) from the fill unless *stop_px* is given;
        *tp*: the target distance (None = none); *hz_end*: exit at the close of bar hz_end - 1 at the latest;
        *be*: move the stop to the entry once the best move reaches be x sl (R multiple);
        *trail*: a trailing stop at *trail* USD behind the best price once the best move reaches trail_start USD
        (updated on bar close: the new stop applies from the next bar)."""
        entry = self.entry_px(e, side)
        stop = stop_px if stop_px is not None else entry - side * sl
        risk = (entry - stop) * side
        best, armed, res = 0.0, False, None
        end = min(hz_end, len(self.o))
        mfe = 0.0
        for j in range(e, end):
            adv = self.lo[j] if side > 0 else self.h[j] + self.sp[j]
            fav = self.h[j] if side > 0 else self.lo[j] + self.sp[j]
            if (adv - stop) * side <= 0:
                px = stop - side * SLIP
                if (self.o[j] + (self.sp[j] if side < 0 else 0) - stop) * side < 0:
                    px = (self.o[j] + (self.sp[j] if side < 0 else 0)) - side * SLIP  # gapped through
                res = ("stop" if (stop - entry) * side < 0 else "trail", (px - entry) * side, j)
                break
            if tp is not None and (fav - entry) * side >= tp:
                res = ("win", tp, j)
                break
            mfe = max(mfe, (fav - entry) * side)
            # update the stop at the bar's close
            if be is not None and not armed and mfe >= be * risk:
                armed = True
                if (entry - stop) * side > 0:
                    stop = entry
            if trail is not None and mfe >= trail_start:
                cand = entry + side * (mfe - trail)
                if (cand - stop) * side > 0:
                    stop = cand
        if res is None:
            x = end - 1
            px = self.c[x] - (SLIP if side > 0 else -(self.sp[x] + SLIP))
            res = ("time", (px - entry) * side, x)
        return dict(exit=res[0], usd=res[1], mins=res[2] - e + 1, risk=risk, mfe=mfe, entry=entry)

    def kind(self, e: int, side: int, out: dict, tp_ref: float) -> str:
        """The owner's three kinds for a loser stopped at its initial stop; *tp_ref* = the target (or the reference
        target for trailing exits)."""
        if out["exit"] != "stop":
            return ""
        j = e + out["mins"] - 1
        entry = out["entry"]
        later = range(j + 1, min(e + 120, len(self.o)))
        hit = any(((self.h[k] if side > 0 else self.lo[k] + self.sp[k]) - entry) * side >= tp_ref for k in later)
        return "3" if hit else ("2" if out["mfe"] >= 0.5 * tp_ref else "1")


def session_opens(ot: pd.DatetimeIndex, start: str, end: str) -> dict[str, list[pd.Timestamp]]:
    """Each weekday's session opens in UTC: Asia 00:00 UTC, London 08:00 London, New York 08:30 and 09:30 ET."""
    days = pd.bdate_range(start, end, inclusive="left")
    out: dict[str, list[pd.Timestamp]] = {"asia": [], "london": [], "ny830": [], "ny930": []}
    for d in days:
        out["asia"].append(pd.Timestamp(d.date(), tz="UTC"))
        out["london"].append(pd.Timestamp(f"{d.date()} 08:00", tz=LON).tz_convert("UTC"))
        out["ny830"].append(pd.Timestamp(f"{d.date()} 08:30", tz=NY).tz_convert("UTC"))
        out["ny930"].append(pd.Timestamp(f"{d.date()} 09:30", tz=NY).tz_convert("UTC"))
    return out


def half_of(t: pd.Timestamp) -> str:
    for name, a, b in HALVES:
        if pd.Timestamp(a, tz="UTC") <= t < pd.Timestamp(b, tz="UTC"):
            return name
    return "test" if t >= DESIGN_END else "?"
