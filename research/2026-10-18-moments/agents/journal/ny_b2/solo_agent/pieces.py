"""Candidate pieces for the solo exam and their gates (PROTOCOL.md):
- gate 1: the entry alone >= +0.10 R a trade in both halves of its test data (2025-10-01 .. the week's end, M1 bars)
- gate 2: the same sign on the old years (2023-09-01 .. 2025-09-30, M1 bars)
Bars: signals from closed bars only; exits on M1 with the stop first when one bar holds both, cost 0.37 USD a trade
(the ticks' mean spread). An adopted piece trades the exam weeks on ticks (`PIECES[name](start, end)`).

One exit for every piece, the journal's realistic shape: half off at +1 R with the rest's stop to the entry, the rest
to +2.5 R or the time limit.

    pieces.py gate nyorb 2026-04-25
"""

from __future__ import annotations

import sys
from functools import lru_cache

import numpy as np
import pandas as pd
import solo_lib as S

COST = 0.37
OLD = (pd.Timestamp("2023-09-01", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC"))
TEST0 = pd.Timestamp("2025-10-01", tz="UTC")
NS_MIN = 60 * 10**9


@lru_cache(maxsize=None)
def m1() -> pd.DataFrame:
    d = pd.read_parquet("data/history/FBS-Demo/XAUUSD/M1.parquet", columns=["open_time", "open", "high", "low", "close"])
    d = d.drop_duplicates("open_time", keep="last").set_index("open_time").sort_index()
    return d.astype("float32")


@lru_cache(maxsize=None)
def bars(tf: str) -> pd.DataFrame:
    """The stored bars; M15 / H1 bars missing from their files (the stored M15 / H1 have a hole from 2026-10-05 08:45 UTC
    while M1 and the ticks go on) are filled from M1 (UTC-aligned, left-labelled, as the stored bars are)."""
    b = S.W.Z.bars(tf)
    if tf not in ("M15", "H1"):
        return b
    m = m1()
    m = m[m.index >= pd.Timestamp("2026-01-01", tz="UTC")]  # the gap is in 2026; older files are complete enough
    r = m.resample("15min" if tf == "M15" else "1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().astype(float)
    r = r[~r.index.isin(b.index)]
    return pd.concat([b, r.assign(tick_volume=np.nan)]).sort_index()


def d1_atr(end: pd.Timestamp) -> pd.Series:
    """D1 ATR(20) known at the open of each server day (of the closed days before it), indexed by the day's open."""
    d = bars("D1")
    d = d[d.index < end]
    pc = d.close.shift(1)
    return pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)


def atr_at(t: pd.Timestamp, a: pd.Series) -> float:
    i = a.index.searchsorted(t, side="right") - 1
    return float(a.iloc[i]) if i >= 0 else np.nan


# --- the signals: (t_entry, side, stop) from closed bars before t_entry, plus the time limit -------------------------

def sig_nyorb(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """The NY cash open range 09:30-09:45 New York (M1); the first M1 close beyond it 09:45-11:00 -> enter at the next
    bar's open in that direction, stop at the range's other side; skipped when the range is under 0.05 or over 0.4 D1
    ATR; out at 12:00 New York. One a day."""
    a = d1_atr(end)
    b = m1()
    b = b[(b.index >= start - pd.Timedelta(days=1)) & (b.index < end)]
    ny = b.index.tz_convert("America/New_York")
    mins = ny.hour * 60 + ny.minute
    keep = (mins >= 570) & (mins < 660)
    b = b[keep].assign(mins=mins[keep], day=ny.date[keep])
    out = []
    for day, g in b.groupby("day"):
        gm = g.mins.values
        rng = g[(gm >= 570) & (gm < 585)]
        if len(rng) < 10:
            continue
        hi, lo = float(rng.high.max()), float(rng.low.min())
        A = atr_at(rng.index[0], a)
        if not np.isfinite(A) or not (0.05 * A <= hi - lo <= 0.4 * A):
            continue
        after = g[(gm >= 585) & (gm < 660)]
        for i, (t, x) in enumerate(after.iterrows()):
            side = 1 if x.close > hi else -1 if x.close < lo else 0
            if side:
                te = t + pd.Timedelta(minutes=1)
                t_end = pd.Timestamp(f"{day} 12:00", tz="America/New_York").tz_convert("UTC")
                out.append(dict(t=te, side=side, stop=lo if side > 0 else hi, t_end=t_end))
                break
    return [o for o in out if start <= o["t"] < end]


def sig_h1mom(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """A strong H1 bar opening 19:00-22:00 Thai: body >= 0.8 x H1 ATR(14) and the close in the last 25 % of its range ->
    enter at the next bar's open in its direction, stop beyond the bar's middle; out 2 hours later. One a day."""
    h = bars("H1")
    h = h[h.index < end]
    atr = S.W._atr14(h).shift(1)
    th = h.index.tz_convert("Asia/Bangkok")
    out, seen = [], set()
    for i in np.flatnonzero((th.hour >= 19) & (th.hour <= 22) & (h.index >= start - pd.Timedelta(hours=1))):
        x, A = h.iloc[i], atr.iloc[i]
        te = h.index[i] + pd.Timedelta(hours=1)
        if not np.isfinite(A) or x.high == x.low or te >= end or th[i].date() in seen:
            continue
        side = 1 if x.close > x.open else -1
        body = (x.close - x.open) * side
        pos = (x.close - x.low) / (x.high - x.low) if side > 0 else (x.high - x.close) / (x.high - x.low)
        if body >= 0.8 * A and pos >= 0.75:
            seen.add(th[i].date())
            out.append(dict(t=te, side=side, stop=(x.high + x.low) / 2, t_end=te + pd.Timedelta(hours=2)))
    return [o for o in out if start <= o["t"] < end]


def sig_dayrun(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """A one-way day: at 20:30 Thai, the server day's move from its open >= 0.6 D1 ATR(20) and the last M15 close in the
    outer 25 % of the day's range -> enter with the move, stop 0.3 D1 ATR; out at 23:00 Thai."""
    a = d1_atr(end)
    m = bars("M15")
    m = m[(m.index < end) & (m.index >= start - pd.Timedelta(days=1))]
    sd = m.index.tz_convert("Europe/Athens").date
    out = []
    for day, g in m.groupby(sd):
        th = g.index.tz_convert("Asia/Bangkok")
        if not len(g):
            continue
        te = pd.Timestamp(pd.Timestamp(th[0].date()).strftime("%Y-%m-%d") + " 20:30", tz="Asia/Bangkok").tz_convert("UTC")
        if th[0].hour >= 20:  # the server day began after 20:30 Thai of that date: the next Thai date
            te += pd.Timedelta(days=1)
        c = g[g.index + pd.Timedelta(minutes=15) <= te]
        if len(c) < 20 or not (te >= start and te < end):
            continue
        A = atr_at(g.index[0], a)
        mv = c.close.iloc[-1] - c.open.iloc[0]
        hi, lo = c.high.max(), c.low.min()
        if not np.isfinite(A) or abs(mv) < 0.6 * A or hi == lo:
            continue
        side = 1 if mv > 0 else -1
        pos = (c.close.iloc[-1] - lo) / (hi - lo) if side > 0 else (hi - c.close.iloc[-1]) / (hi - lo)
        if pos < 0.75:
            continue
        out.append(dict(t=te, side=side, stop=None, stop_atr=0.3 * A, t_end=te + pd.Timedelta(minutes=150)))
    return out


def thai(day, hhmm: str) -> pd.Timestamp:
    """Thai clock time on the server day `day` (a server day runs 04:00/05:00 .. 04:00/05:00 Thai)."""
    return pd.Timestamp(f"{day} {hhmm}", tz="Asia/Bangkok").tz_convert("UTC")


def _m15_days(start: pd.Timestamp, end: pd.Timestamp):
    m = bars("M15")
    m = m[(m.index < end) & (m.index >= start - pd.Timedelta(days=1))]
    return m.groupby(m.index.tz_convert("Europe/Athens").date)


def sig_londonbo(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """The Asia range (the server day's M15 bars before 13:00 Thai) broken in London: the first M15 close beyond it
    13:00-17:00 Thai -> enter at the next bar's open with it, stop at the range's middle; skipped when the range is
    under 0.15 or over 0.8 D1 ATR; out at 19:00 Thai. One a day."""
    a = d1_atr(end)
    out = []
    for day, g in _m15_days(start, end):
        end_ = g.index + pd.Timedelta(minutes=15)
        asia, lon = g[end_ <= thai(day, "13:00")], g[(g.index >= thai(day, "13:00")) & (end_ <= thai(day, "17:00"))]
        if len(asia) < 20 or not len(lon):
            continue
        hi, lo, A = asia.high.max(), asia.low.min(), atr_at(g.index[0], a)
        if not np.isfinite(A) or not (0.15 * A <= hi - lo <= 0.8 * A):
            continue
        for t, x in lon.iterrows():
            side = 1 if x.close > hi else -1 if x.close < lo else 0
            if side:
                te = t + pd.Timedelta(minutes=15)
                t_end = thai(day, "19:00")
                out.append(dict(t=te, side=side, stop=(hi + lo) / 2, t_end=t_end))
                break
    return [o for o in out if start <= o["t"] < end]


def sig_nyfade(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """NY turns an extended day: the server day's move by 20:00 Thai >= 0.6 D1 ATR; from 20:00 to 22:45 Thai an M15 bar
    makes a new day extreme and closes against the day (body >= 25 % of its range: a rejection)
    -> enter against the day's move at the next bar's open, stop 0.05 ATR beyond the new extreme; out 2 hours later."""
    a = d1_atr(end)
    out = []
    for day, g in _m15_days(start, end):
        end_ = g.index + pd.Timedelta(minutes=15)
        pre = g[end_ <= thai(day, "20:00")]
        if len(pre) < 20:
            continue
        A = atr_at(g.index[0], a)
        mv = pre.close.iloc[-1] - pre.open.iloc[0]
        if not np.isfinite(A) or abs(mv) < 0.6 * A:
            continue
        d = 1 if mv > 0 else -1
        ext = pre.high.max() if d > 0 else pre.low.min()
        ny = g[(g.index >= thai(day, "20:00")) & (end_ <= thai(day, "23:00"))]
        for t, x in ny.iterrows():
            new = (x.high > ext) if d > 0 else (x.low < ext)
            ext = max(ext, x.high) if d > 0 else min(ext, x.low)
            if new and ((x.close < x.open) if d > 0 else (x.close > x.open)) and abs(x.close - x.open) >= 0.25 * (x.high - x.low):
                te = t + pd.Timedelta(minutes=15)
                out.append(dict(t=te, side=-d, stop=ext + d * 0.05 * A, t_end=te + pd.Timedelta(hours=2)))
                break
    return [o for o in out if start <= o["t"] < end]


def d1_side(end: pd.Timestamp) -> pd.Series:
    """The D1 side known at each server day's open: +1 when the last close is above its 20-day mean and the last 5
    days rose by at least 0.5 D1 ATR(20); -1 the mirror; 0 otherwise. Indexed by the day's open."""
    d = bars("D1")
    d = d[d.index < end]
    pc = d.close.shift(1)
    atr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean()
    up = (d.close > d.close.rolling(20).mean()) & (d.close - d.close.shift(5) >= 0.5 * atr)
    dn = (d.close < d.close.rolling(20).mean()) & (d.close - d.close.shift(5) <= -0.5 * atr)
    return (up.astype(int) - dn.astype(int)).shift(1)  # known at the next day's open


def sig_d1pull(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """The D1 side's pullback in NY: on a day with a D1 side, price at 20:00 Thai is against the side from the server
    day's open; from 20:00 to 22:30 Thai the first M15 bar closing beyond the previous bar's high (low for a sell)
    -> enter with the side at the next bar's open, stop 0.05 ATR beyond the day's extreme against the side; out 2 h
    later. One a day."""
    a, sd = d1_atr(end), d1_side(end)
    out = []
    for day, g in _m15_days(start, end):
        side = sd.iloc[sd.index.searchsorted(g.index[0], side="right") - 1] if len(sd) else 0
        A = atr_at(g.index[0], a)
        if not side or not np.isfinite(A):
            continue
        end_ = g.index + pd.Timedelta(minutes=15)
        pre = g[end_ <= thai(day, "20:00")]
        if len(pre) < 20 or (pre.close.iloc[-1] - g.open.iloc[0]) * side >= 0:
            continue
        ny = g[(g.index >= thai(day, "20:00")) & (end_ <= thai(day, "22:30"))]
        prev = pre.iloc[-1]
        for t, x in ny.iterrows():
            if (x.close > prev.high) if side > 0 else (x.close < prev.low):
                seen = g[g.index <= t]
                ext = seen.low.min() if side > 0 else seen.high.max()
                te = t + pd.Timedelta(minutes=15)
                out.append(dict(t=te, side=int(side), stop=ext - side * 0.05 * A, t_end=te + pd.Timedelta(hours=2)))
                break
            prev = x
    return [o for o in out if start <= o["t"] < end]


def sig_asiarun(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """A run from the Asia open: the server day's first 3 H1 bars move >= 0.25 D1 ATR one way, at least 2 of them close
    that way and the 3rd closes in the outer 30 % of the 3 bars' range -> enter with it at the 4th bar's open, stop at
    the 3 bars' middle; out at 13:00 Thai (the London open)."""
    a = d1_atr(end)
    h = bars("H1")
    h = h[(h.index < end) & (h.index >= start - pd.Timedelta(days=1))]
    out = []
    for day, g in h.groupby(h.index.tz_convert("Europe/Athens").date):
        if len(g) < 4:
            continue
        x, A = g.iloc[:3], atr_at(g.index[0], a)
        mv = x.close.iloc[-1] - x.open.iloc[0]
        hi, lo = x.high.max(), x.low.min()
        if not np.isfinite(A) or abs(mv) < 0.25 * A or hi == lo:
            continue
        side = 1 if mv > 0 else -1
        if (np.sign(x.close - x.open) == side).sum() < 2:
            continue
        pos = (x.close.iloc[-1] - lo) / (hi - lo) if side > 0 else (hi - x.close.iloc[-1]) / (hi - lo)
        if pos < 0.7:
            continue
        te = g.index[3]
        out.append(dict(t=te, side=side, stop=(hi + lo) / 2, t_end=thai(day, "13:00")))
    return [o for o in out if start <= o["t"] < end]


def sig_rangefade(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """A range's edge rejected: the last 5 closed D1 bars span < 2.5 D1 ATR(20); an H1 bar trades beyond their high
    (low), closes back inside, and its wick beyond the close is >= 50 % of its range (a long wick) on tick volume above
    its 20-bar median -> enter against at the next H1 open, stop 0.05 ATR beyond the wick; out 4 hours later. One a day."""
    a = d1_atr(end)
    d = bars("D1")
    d = d[d.index < end]
    hi5, lo5 = d.high.rolling(5).max(), d.low.rolling(5).min()
    h = bars("H1")
    h = h[(h.index < end) & (h.index >= start - pd.Timedelta(days=2))]
    vmed = bars("H1").tick_volume.rolling(20).median()
    out, seen = [], set()
    for t, x in h.iterrows():
        k = d.index.searchsorted(t, side="right") - 2  # the last D1 bar closed before this H1 bar
        if k < 0 or t + pd.Timedelta(hours=1) >= end:
            continue
        A = atr_at(t, a)
        H, L = hi5.iloc[k], lo5.iloc[k]
        day = t.tz_convert("Europe/Athens").date()
        if not np.isfinite(A) or H - L >= 2.5 * A or day in seen or x.high == x.low or x.tick_volume <= vmed.get(t, np.inf):
            continue
        rng = x.high - x.low
        if x.high > H and x.close < H and (x.high - max(x.open, x.close)) >= 0.5 * rng:
            side, stop = -1, x.high + 0.05 * A
        elif x.low < L and x.close > L and (min(x.open, x.close) - x.low) >= 0.5 * rng:
            side, stop = 1, x.low - 0.05 * A
        else:
            continue
        seen.add(day)
        te = t + pd.Timedelta(hours=1)
        out.append(dict(t=te, side=side, stop=stop, t_end=te + pd.Timedelta(hours=4)))
    return [o for o in out if start <= o["t"] < end]


def sig_nyrev(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """NY reverses a run: the last 2 closed D1 bars closed the same way and the day so far (by the bar's open) has gone
    that way by >= 0.3 D1 ATR; an H1 bar opening 19:00-21:00 Thai with body >= 0.8 H1 ATR(14) against the run and
    the close in its outer 25 % -> enter with the bar at the next H1 open, stop 0.05 D1 ATR beyond the bar's far end;
    out 3 hours later. One a day."""
    a = d1_atr(end)
    d = bars("D1")
    d = d[d.index < end]
    h = bars("H1")
    h = h[h.index < end]
    atr = S.W._atr14(h).shift(1)
    out, seen = [], set()
    for i in np.flatnonzero(h.index >= start - pd.Timedelta(hours=1)):
        t, x, Ah = h.index[i], h.iloc[i], atr.iloc[i]
        hh = t.tz_convert("Asia/Bangkok").hour
        if hh < 19 or hh > 21 or not np.isfinite(Ah) or x.high == x.low:
            continue
        k = d.index.searchsorted(t, side="right") - 1  # today's D1 bar (forming); k-1, k-2 closed
        if k < 2:
            continue
        c1, c2 = d.close.iloc[k - 1] - d.open.iloc[k - 1], d.close.iloc[k - 2] - d.open.iloc[k - 2]
        if np.sign(c1) != np.sign(c2) or c1 == 0:
            continue
        run, A = np.sign(c1), atr_at(t, a)
        if (x.open - d.open.iloc[k]) * run < 0.3 * A:
            continue
        side = -int(run)
        body = (x.close - x.open) * side
        pos = (x.close - x.low) / (x.high - x.low) if side > 0 else (x.high - x.close) / (x.high - x.low)
        day = t.tz_convert("Europe/Athens").date()
        if body >= 0.8 * Ah and pos >= 0.75 and day not in seen:
            seen.add(day)
            te = t + pd.Timedelta(hours=1)
            out.append(dict(t=te, side=side, stop=(x.low if side > 0 else x.high) - side * 0.05 * A, t_end=te + pd.Timedelta(hours=3)))
    return [o for o in out if start <= o["t"] < end]


def sig_newsrun(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """The 08:30 New York data hour runs: the H1 bar opening 08:00 New York (holding 08:30) has body >= 1.5 x H1 ATR(14)
    and closes in its outer 20 % -> enter with it at the next H1 open, stop at the bar's middle; out 3 hours later."""
    h = bars("H1")
    h = h[h.index < end]
    atr = S.W._atr14(h).shift(1)
    ny = h.index.tz_convert("America/New_York")
    out = []
    for i in np.flatnonzero((ny.hour == 8) & (h.index >= start - pd.Timedelta(hours=1))):
        x, A = h.iloc[i], atr.iloc[i]
        te = h.index[i] + pd.Timedelta(hours=1)
        if not np.isfinite(A) or x.high == x.low or te >= end:
            continue
        side = 1 if x.close > x.open else -1
        pos = (x.close - x.low) / (x.high - x.low) if side > 0 else (x.high - x.close) / (x.high - x.low)
        if (x.close - x.open) * side >= 1.5 * A and pos >= 0.8:
            out.append(dict(t=te, side=side, stop=(x.high + x.low) / 2, t_end=te + pd.Timedelta(hours=3)))
    return [o for o in out if start <= o["t"] < end]


def sig_retest(start: pd.Timestamp, end: pd.Timestamp, from_hhmm: str | None = None, fixed: bool = False) -> list[dict]:
    """retest_week.trades()'s entry on M15 bars (a strong D1 bar; the next server day breaks its extreme, comes back
    within 0.1 ATR and an M15 bar closes back on the break side -> with the strong day at the next bar, stop beyond the
    re-test swing + 0.05 ATR, out 23:00 Thai); `from_hhmm`: only re-tests whose bar closes at / after this Thai time."""
    d1 = bars("D1")
    d1 = d1[d1.index < end]
    m15 = bars("M15")
    m15 = m15[(m15.index < end) & (m15.index >= start - pd.Timedelta(days=3))]
    pc = d1.close.shift(1)
    atr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)
    out = []
    for i in range(21, len(d1) - 1):
        nxt = d1.index[i + 1]
        if nxt + pd.Timedelta(days=1) < start or nxt >= end:
            continue
        b, a = d1.iloc[i], atr.iloc[i]
        if not np.isfinite(a) or b.high == b.low:
            continue
        side = 1 if b.close > b.open else -1
        pos = (b.close - b.low) / (b.high - b.low) if side > 0 else (b.high - b.close) / (b.high - b.low)
        if (b.close - b.open) * side / a < 1.0 or pos < 0.7:
            continue
        # retest_week.py adds one day too many here (normalize + 1 day 23 h = the day AFTER the next day, 23:00 Thai,
        # while its docstring says "the next server day, until 23:00 Thai"); `fixed` uses the next server day
        cutoff = (nxt.tz_convert("Asia/Bangkok").normalize() + pd.Timedelta(days=0 if fixed else 1, hours=23)).tz_convert("UTC")
        g = m15[(m15.index >= nxt) & (m15.index + pd.Timedelta(minutes=15) <= cutoff)]
        ext = b.low if side < 0 else b.high
        broke, swing = False, None
        for t, x in g.iterrows():
            if not broke:
                if (x.low < ext) if side < 0 else (x.high > ext):
                    broke, swing = True, (x.high if side < 0 else x.low)
                continue
            swing = max(swing, x.high) if side < 0 else min(swing, x.low)
            if not (((x.high >= ext - 0.1 * a) and x.close < ext) if side < 0 else ((x.low <= ext + 0.1 * a) and x.close > ext)):
                continue
            te = t + pd.Timedelta(minutes=15)
            if from_hhmm and te < thai(nxt.tz_convert("Europe/Athens").date(), from_hhmm):
                continue
            out.append(dict(t=te, side=side, stop=swing + 0.05 * a if side < 0 else swing - 0.05 * a, t_end=cutoff))
            break
    return [o for o in out if start <= o["t"] < end]


def sig_retest13(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """The re-test only from 13:00 Thai (London and NY: the owner's trading windows)."""
    return sig_retest(start, end, "13:00")


def sig_retestfix(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """The re-test as its docstring says: on the next server day only, out at 23:00 Thai of that day."""
    return sig_retest(start, end, fixed=True)


def sig_lonresume(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """London resumes yesterday: the last closed D1 body >= 0.6 D1 ATR one way and today's Asia (the server day's M15
    bars to 13:00 Thai) went against it -> at 13:00 Thai the first M15 bar (13:00-16:00) closing beyond the previous
    bar's extreme in yesterday's direction: enter at the next bar's open, stop 0.05 ATR beyond the Asia extreme against
    it; out at 19:00 Thai. One a day."""
    a = d1_atr(end)
    d = bars("D1")
    d = d[d.index < end]
    out = []
    for day, g in _m15_days(start, end):
        # today's D1 bar opens at / before the day's first M15 bar (21:00 UTC vs 22:00 in summer): the one before it
        k = d.index.searchsorted(g.index[0], side="right") - 2
        if d.index[k] + pd.Timedelta(days=1) > g.index[0]:
            continue
        A = atr_at(g.index[0], a)
        if k < 0 or not np.isfinite(A):
            continue
        body = d.close.iloc[k] - d.open.iloc[k]
        if abs(body) < 0.6 * A:
            continue
        side = 1 if body > 0 else -1
        end_ = g.index + pd.Timedelta(minutes=15)
        asia = g[end_ <= thai(day, "13:00")]
        if len(asia) < 20 or (asia.close.iloc[-1] - asia.open.iloc[0]) * side >= 0:
            continue
        ext = asia.low.min() if side > 0 else asia.high.max()
        lon = g[(g.index >= thai(day, "13:00")) & (end_ <= thai(day, "16:00"))]
        prev = asia.iloc[-1]
        for t, x in lon.iterrows():
            ext = min(ext, x.low) if side > 0 else max(ext, x.high)
            if (x.close > prev.high) if side > 0 else (x.close < prev.low):
                te = t + pd.Timedelta(minutes=15)
                out.append(dict(t=te, side=side, stop=ext - side * 0.05 * A, t_end=thai(day, "19:00")))
                break
            prev = x
    return [o for o in out if start <= o["t"] < end]


def sig_nytrend(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """NY joins a trend day: by 19:00 Thai the server day moved >= 0.5 D1 ATR one way with Asia (to 13:00) and London
    (13:00-19:00) both that way; the first M15 bar 19:00-21:00 Thai closing beyond the previous bar's extreme that way
    -> enter at the next bar, stop 0.05 ATR beyond London's extreme against it; out at 23:00 Thai. One a day."""
    a = d1_atr(end)
    out = []
    for day, g in _m15_days(start, end):
        A = atr_at(g.index[0], a)
        end_ = g.index + pd.Timedelta(minutes=15)
        asia, lon = g[end_ <= thai(day, "13:00")], g[(g.index >= thai(day, "13:00")) & (end_ <= thai(day, "19:00"))]
        if not np.isfinite(A) or len(asia) < 20 or len(lon) < 20:
            continue
        mv = lon.close.iloc[-1] - asia.open.iloc[0]
        side = 1 if mv > 0 else -1
        if abs(mv) < 0.5 * A or (asia.close.iloc[-1] - asia.open.iloc[0]) * side <= 0 or (lon.close.iloc[-1] - lon.open.iloc[0]) * side <= 0:
            continue
        ext = lon.low.min() if side > 0 else lon.high.max()
        ny = g[(g.index >= thai(day, "19:00")) & (end_ <= thai(day, "21:00"))]
        prev = lon.iloc[-1]
        for t, x in ny.iterrows():
            ext = min(ext, x.low) if side > 0 else max(ext, x.high)
            if (x.close > prev.high) if side > 0 else (x.close < prev.low):
                te = t + pd.Timedelta(minutes=15)
                out.append(dict(t=te, side=side, stop=ext - side * 0.05 * A, t_end=thai(day, "23:00")))
                break
            prev = x
    return [o for o in out if start <= o["t"] < end]


def sig_lonrev(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """London reverses Asia: the server day's Asia (to 13:00 Thai) moved >= 0.25 D1 ATR one way; the first M15 bar
    13:00-16:00 Thai closing beyond the previous bar's extreme against it -> enter against Asia at the next bar, stop
    0.05 ATR beyond the Asia extreme; out at 19:00 Thai. One a day. (lonresume without yesterday's bar.)"""
    a = d1_atr(end)
    out = []
    for day, g in _m15_days(start, end):
        A = atr_at(g.index[0], a)
        end_ = g.index + pd.Timedelta(minutes=15)
        asia = g[end_ <= thai(day, "13:00")]
        if not np.isfinite(A) or len(asia) < 20:
            continue
        mv = asia.close.iloc[-1] - asia.open.iloc[0]
        if abs(mv) < 0.25 * A:
            continue
        side = -1 if mv > 0 else 1
        ext = asia.low.min() if side > 0 else asia.high.max()
        lon = g[(g.index >= thai(day, "13:00")) & (end_ <= thai(day, "16:00"))]
        prev = asia.iloc[-1]
        for t, x in lon.iterrows():
            ext = min(ext, x.low) if side > 0 else max(ext, x.high)
            if (x.close > prev.high) if side > 0 else (x.close < prev.low):
                te = t + pd.Timedelta(minutes=15)
                out.append(dict(t=te, side=side, stop=ext - side * 0.05 * A, t_end=thai(day, "19:00")))
                break
            prev = x
    return [o for o in out if start <= o["t"] < end]


def sig_asiafollow(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """Asia follows a strong day: yesterday's D1 body >= 0.6 D1 ATR(20) closing in its outer 30 %; today's first two H1
    bars close beyond yesterday's close in its direction -> enter at the 3rd H1 bar's open with it, stop 0.05 ATR
    beyond the two bars' extreme against it; out at 13:00 Thai."""
    a = d1_atr(end)
    d = bars("D1")
    d = d[d.index < end]
    h = bars("H1")
    h = h[(h.index < end) & (h.index >= start - pd.Timedelta(days=1))]
    out = []
    for day, g in h.groupby(h.index.tz_convert("Europe/Athens").date):
        if len(g) < 3:
            continue
        k = d.index.searchsorted(g.index[0], side="right") - 2
        if k < 0 or d.index[k] + pd.Timedelta(days=1) > g.index[0]:
            continue
        b, A = d.iloc[k], atr_at(g.index[0], a)
        if not np.isfinite(A) or b.high == b.low:
            continue
        side = 1 if b.close > b.open else -1
        pos = (b.close - b.low) / (b.high - b.low) if side > 0 else (b.high - b.close) / (b.high - b.low)
        if abs(b.close - b.open) < 0.6 * A or pos < 0.7:
            continue
        x = g.iloc[:2]
        if not ((x.close - b.close) * side > 0).all():
            continue
        ext = x.low.min() if side > 0 else x.high.max()
        out.append(dict(t=g.index[2], side=side, stop=ext - side * 0.05 * A, t_end=thai(day, "13:00")))
    return [o for o in out if start <= o["t"] < end]


def sig_boxbreak(start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """A D1 box breaks: the last 10 closed D1 bars span < 2.5 D1 ATR(20); the first H1 close beyond their high (low)
    -> enter with it at the next H1 open, stop 0.3 D1 ATR; out 8 hours later. One a day."""
    a = d1_atr(end)
    d = bars("D1")
    d = d[d.index < end]
    hi10, lo10 = d.high.rolling(10).max(), d.low.rolling(10).min()
    h = bars("H1")
    h = h[(h.index < end) & (h.index >= start - pd.Timedelta(days=1))]
    out, seen = [], set()
    for t, x in h.iterrows():
        k = d.index.searchsorted(t, side="right") - 2
        te = t + pd.Timedelta(hours=1)
        day = t.tz_convert("Europe/Athens").date()
        if k < 10 or te >= end or day in seen or d.index[k] + pd.Timedelta(days=1) > t:
            continue
        A, H, L = atr_at(t, a), hi10.iloc[k], lo10.iloc[k]
        if not np.isfinite(A) or H - L >= 2.5 * A:
            continue
        side = 1 if x.close > H else -1 if x.close < L else 0
        if side:
            seen.add(day)
            out.append(dict(t=te, side=side, stop=None, stop_atr=0.3 * A, t_end=te + pd.Timedelta(hours=8)))
    return [o for o in out if start <= o["t"] < end]


SIGNALS = {"retestfix": sig_retestfix, "boxbreak": sig_boxbreak, "asiafollow": sig_asiafollow, "lonrev": sig_lonrev, "nytrend": sig_nytrend, "lonresume": sig_lonresume, "retest": sig_retest, "retest13": sig_retest13, "newsrun": sig_newsrun, "nyrev": sig_nyrev, "rangefade": sig_rangefade, "asiarun": sig_asiarun, "d1pull": sig_d1pull, "nyorb": sig_nyorb, "h1mom": sig_h1mom, "dayrun": sig_dayrun, "londonbo": sig_londonbo, "nyfade": sig_nyfade}


# --- the exits ------------------------------------------------------------------------------------------------------

def bar_trade(s: dict) -> float | None:
    """On M1 bars: entry at the bar open at s.t (+ cost); half at +1 R, the rest to the entry, the rest to +2.5 R."""
    b = m1()
    i = b.index.searchsorted(s["t"])
    if i >= len(b):
        return None
    side = s["side"]
    entry = float(b.open.iloc[i])
    stop = s["stop"] if s.get("stop") is not None else entry - side * s["stop_atr"]
    risk = (entry - stop) * side
    if risk < 1.0:
        return None
    j = b.index.searchsorted(s["t_end"])
    x = b.iloc[i:j]
    if not len(x):
        return None
    hi, lo = x.high.values, x.low.values
    half, st, r = False, stop, 0.0
    for k in range(len(x)):
        adv, fav = (lo[k], hi[k]) if side > 0 else (hi[k], lo[k])
        if (adv - st) * side <= 0:
            return r + (0.5 if half else 1.0) * (st - entry) * side / risk - COST / risk
        if not half and (fav - entry) * side >= risk:
            half, r, st = True, 0.5, entry
            if (fav - entry) * side >= 2.5 * risk:
                return 0.5 + 1.25 - COST / risk
        elif half and (fav - entry) * side >= 2.5 * risk:
            return r + 1.25 - COST / risk
    return r + (0.5 if half else 1.0) * (float(x.close.iloc[-1]) - entry) * side / risk - COST / risk


def tick_trade(s: dict) -> dict | None:
    """On ticks (the exam's adopted pieces): the first tick at / after s.t; the same exit."""
    tk = S.RT.ticks(s["t"].normalize())
    if tk is None:
        return None
    tt, bid, ask = tk
    side = s["side"]
    f = int(np.searchsorted(tt, s["t"].value))
    if f >= len(tt):
        return None
    entry = ask[f] if side > 0 else bid[f]
    stop = s["stop"] if s.get("stop") is not None else entry - side * s["stop_atr"]
    risk = (entry - stop) * side
    if risk < 1.0:
        return None
    t_end = s["t_end"].value
    px1, tx1, k1 = S.RT._manage(tt, bid, ask, f, entry, side, stop, entry + side * risk, t_end)
    if k1 != "target":
        r = (px1 - entry) * side / risk
    else:
        px2, _, _ = S.RT._manage(tt, bid, ask, int(np.searchsorted(tt, tx1)), entry, side, entry, entry + side * 2.5 * risk, t_end)
        r = 0.5 + 0.5 * (px2 - entry) * side / risk
    return dict(t=pd.Timestamp(tt[f], tz="UTC"), side="BUY" if side > 0 else "SELL", entry_price=entry, sl_initial=stop, r_real=r, note=k1)


def make_piece(name: str):
    def run(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        rows = [tick_trade(s) for s in SIGNALS[name](start, end)]
        return pd.DataFrame([r for r in rows if r])
    return run


PIECES = {k: make_piece(k) for k in SIGNALS}


def gate(name: str, end: pd.Timestamp) -> dict:
    """Both gates on data before `end`."""
    res = {}
    for part, a, b in (("old", *OLD), ("test", TEST0, end)):
        sig = SIGNALS[name](a, b)
        r = pd.Series([bar_trade(s) for s in sig], index=[s["t"] for s in sig], dtype=float).dropna()
        res[part] = r
    T = res["test"]
    half = T.index[len(T) // 2] if len(T) else end
    h1, h2 = T[T.index < half], T[T.index >= half]
    out = dict(name=name, old_n=len(res["old"]), old_mean=res["old"].mean(), test_n=len(T), h1_n=len(h1), h1_mean=h1.mean(),
               h2_n=len(h2), h2_mean=h2.mean())
    out["gate1"] = bool(len(h1) and len(h2) and h1.mean() >= 0.10 and h2.mean() >= 0.10)
    out["gate2"] = bool(len(res["old"]) and res["old"].mean() > 0)
    return out, res


if __name__ == "__main__":
    if sys.argv[1] == "gate":
        o, res = gate(sys.argv[2], pd.Timestamp(sys.argv[3], tz="UTC"))
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in o.items()})
        for part, r in res.items():
            if len(r):
                y = r.groupby(r.index.year).agg(["size", "mean", "sum"]).round(3)
                print(part, f"sum {r.sum():+.2f} win {(r > 0).mean() * 100:.0f} %\n", y.to_string())
