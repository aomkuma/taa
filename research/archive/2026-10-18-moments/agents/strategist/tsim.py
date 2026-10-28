"""The strategist's tick simulator for the transformations of the FAIL rows (CHECKLIST row 39; owner, 2026-10-20: "before
discarding a method, try the opposite side, a wider stop, a nearer target"). One trade's entry is re-simulated on the
real ticks in a grid of variants:

- the side: the rule's own ('same') or the opposite ('opp': the other way at the same moment);
- the stop: the rule's stop distance x 1 / 1.5 / 2 (the distance d_s0 measured from the rule-side fill);
- the target: the rule's own ('orig'; none stays none), its distance x 0.75 / x 0.5 (trades without a target keep none),
  or '1R0' = a target at 1 x the rule's own stop distance d_s0 (whatever the stop cell);
- the rule's other exits kept: the time (the first tick at / after t_out), the surrender (no tick Y USD our way before
  K minutes after the fill -> out at the first tick at / after it; side-free, so kept for 'opp' too), and a
  structure exit time (the rule's own close-based exit for its side; 'same' only - for the other side it would be a
  confirmation, not an exit);
- a gap of more than 30 minutes in the ticks (the daily break / the weekend): out at the last tick before it; ticks that
  end before t_out: out at the last tick ('end').

Costs: the tick bid / ask spread only (owner, 2026-10-20). A buy fills at the ask + slip, a sell at the bid - slip;
market exits at the bid (buy) / ask (sell) -/+ slip_exit; both default to 0. The target is a limit filled at its level.
One tick reaching the stop and the target: the stop. Order on one tick: stop, target, structure, surrender, time.
R = pnl / the variant's own risk (m x d_s0).

The ticks: `span(t_ns)` joins a UTC day's file to the next day's and refuses any day at / after the exam start
(2026-04-18); a learning day is never joined to an exam day.
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TICKS = Path(__file__).resolve().parents[4] / "data/ticks/XAUUSD"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
NS_MIN = 60 * 10**9
GAP_NS = 30 * NS_MIN
MAX_LAG_NS = 5 * NS_MIN
STOPS = (1.0, 1.5, 2.0)
TARGETS = ("orig", 0.75, 0.5, "1R0")
ORDER = {"stop": 0, "target": 1, "structure": 2, "surrender": 3, "time": 4, "break": 4, "end": 4}


def idle() -> None:
    """Run at idle priority (the team's rule for heavy runs)."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)


def day_ticks(day: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    d = pd.Timestamp(day)
    d = (d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")).normalize()
    if d >= EXAM_START:
        raise RuntimeError(f"{d:%Y-%m-%d} is in the exam period")
    f = TICKS / f"{d:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f, columns=["time_utc", "bid", "ask"])
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


class Ticks:
    """Cached day + next-day spans (never an exam day)."""

    def __init__(self) -> None:
        self.days: dict = {}
        self.spans: dict = {}

    def day(self, d: pd.Timestamp):
        if d not in self.days:
            self.days[d] = day_ticks(d) if d < EXAM_START else None
            if len(self.days) > 6:  # keep memory small: drop the oldest days
                for k in sorted(self.days)[:-4]:
                    del self.days[k]
        return self.days[d]

    def span(self, t_ns: int):
        d = pd.Timestamp(int(t_ns), tz="UTC").normalize()
        if d not in self.spans:
            a = self.day(d)
            if a is None:
                self.spans[d] = None
            else:
                b = self.day(d + pd.Timedelta(days=1))
                self.spans[d] = a if b is None else tuple(np.concatenate([x, y]) for x, y in zip(a, b, strict=True))
            if len(self.spans) > 3:
                for k in sorted(self.spans)[:-2]:
                    del self.spans[k]
        return self.spans[d]


def grid(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t_in: int, side0: int, stop_px: float, tgt_px: float,
         t_out: int, t_struct: int | None = None, surr: tuple[float, float] | None = None, slip: float = 0.0,
         slip_exit: float = 0.0, sides: tuple[str, ...] = ("same", "opp"), stops: tuple[float, ...] = STOPS,
         targets: tuple = TARGETS, stop_d: float = np.nan, tgt_r: float = np.nan) -> list[dict] | None:
    """Every variant of one trade. None when there is no tick within 5 minutes of t_in, the fill is past the rule's
    stop, or no tick follows the fill before the exit. A rule whose stop is a distance from its fill passes stop_d
    (then stop_px is ignored); a rule whose target is a multiple of its risk passes tgt_r (then tgt_px is ignored)."""
    f = int(np.searchsorted(t, t_in, side="left"))
    if f >= len(t) or t[f] - t_in > MAX_LAG_NS:
        return None
    e0 = ask[f] + slip if side0 > 0 else bid[f] - slip
    if np.isfinite(stop_d):
        stop_px = e0 - side0 * stop_d
    d_s0 = side0 * (e0 - stop_px)
    if np.isfinite(tgt_r) and d_s0 > 0:
        tgt_px = e0 + side0 * tgt_r * d_s0
    if not d_s0 > 0:
        return None
    d_t0 = side0 * (tgt_px - e0) if np.isfinite(tgt_px) else np.nan
    if np.isfinite(d_t0) and d_t0 <= 0:
        d_t0 = np.nan
    end = int(np.searchsorted(t, t_out, side="left"))
    end_kind = "time"
    if end >= len(t):
        end, end_kind = len(t) - 1, "end"
    gaps = np.nonzero(np.diff(t[f:end + 1]) > GAP_NS)[0]
    if len(gaps):
        end, end_kind = f + int(gaps[0]), "break"
    if end <= f:
        return None
    n = end - f  # ticks f+1 .. end -> relative 0 .. n-1
    k_struct = None
    if t_struct is not None:
        k = int(np.searchsorted(t, t_struct, side="left"))
        if f < k <= end:
            k_struct = k - f - 1
    rows = []
    for sname in sides:
        s = side0 if sname == "same" else -side0
        e = ask[f] + slip if s > 0 else bid[f] - slip
        mkt = (bid[f + 1:end + 1] - slip_exit) if s > 0 else (ask[f + 1:end + 1] + slip_exit)
        fav = s * (mkt - e)
        cmin = np.minimum.accumulate(fav)
        cmax = np.maximum.accumulate(fav)
        base_ev = [(n - 1, end_kind)]
        if k_struct is not None and sname == "same":
            base_ev.append((k_struct, "structure"))
        if surr is not None:
            kk = int(np.searchsorted(t, t[f] + int(surr[0] * NS_MIN), side="left"))
            if kk <= end:
                r = kk - f - 1  # the tick at / after K minutes (relative)
                ran = r > 0 and cmax[r - 1] >= surr[1]
                if not ran:
                    base_ev.append((r, "surrender"))
        for m in stops:
            d_s = m * d_s0
            i_s = int(np.searchsorted(-cmin, d_s, side="left"))
            for tg in targets:
                if tg == "orig":
                    d_t = d_t0
                elif tg == "1R0":
                    d_t = d_s0
                else:
                    d_t = float(tg) * d_t0
                ev = list(base_ev)
                if i_s < n:
                    ev.append((i_s, "stop"))
                if np.isfinite(d_t):
                    i_t = int(np.searchsorted(cmax, d_t, side="left"))
                    if i_t < n:
                        ev.append((i_t, "target"))
                i, why = min(ev, key=lambda x: (x[0], ORDER[x[1]]))
                pnl = d_t if why == "target" else float(fav[i])
                rows.append(dict(side_v=sname, side=s, stop_m=m, tgt=str(tg), entry=float(e), risk=float(d_s),
                                 exit=why, exit_t=int(t[f + 1 + i]), pnl=float(pnl), R=float(pnl / d_s),
                                 has_tgt=bool(np.isfinite(d_t0)), entry_t=int(t[f])))
    return rows


def run(specs: pd.DataFrame, slip: float = 0.0, slip_exit: float = 0.0, **kw) -> pd.DataFrame:
    """specs: one row per rule trade with t_in, side, stop_px, tgt_px, t_out, t_struct (or NaN), surr_min, surr_usd
    (or NaN) and any label columns (kept). Returns one row per trade x variant."""
    tk = Ticks()
    out = []
    specs = specs.sort_values("t_in").reset_index(drop=True)
    for r in specs.itertuples(index=False):
        sp = tk.span(int(r.t_in))
        if sp is None:
            continue
        ts = getattr(r, "t_struct", np.nan)
        ts = None if ts is None or pd.isna(ts) else int(ts)
        su = getattr(r, "surr_min", np.nan)
        su = None if su is None or pd.isna(su) else (float(su), float(r.surr_usd))
        sd, tr = float(getattr(r, "stop_d", np.nan)), float(getattr(r, "tgt_r", np.nan))
        rows = grid(*sp, int(r.t_in), int(r.side), float(getattr(r, "stop_px", np.nan)), float(getattr(r, "tgt_px", np.nan)),
                    int(r.t_out), ts, su, slip, slip_exit, stop_d=sd, tgt_r=tr, **kw)
        if rows is None:
            continue
        lab = {k: v for k, v in r._asdict().items() if k not in ("side",)}
        out.extend({**lab, **x} for x in rows)
    return pd.DataFrame(out)


def one_at_a_time(T: pd.DataFrame) -> pd.DataFrame:
    """From the same entries, a trade entering before the previous kept trade's exit is dropped (per variant)."""
    T = T.sort_values("entry_t")
    keep, busy = [], -1
    for i, a, b in zip(T.index, T.entry_t.to_numpy(), T.exit_t.to_numpy(), strict=True):
        if a < busy:
            continue
        keep.append(i)
        busy = b
    return T.loc[keep]
