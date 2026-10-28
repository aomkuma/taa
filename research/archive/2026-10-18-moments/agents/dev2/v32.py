"""Setup OWN V3-2 - the four entries of the owner's playbook as rules (DEV_LOG.md, "Written before computing (V3-2)",
rules R0-R11), built on V3-1's swings (`swings.py`). This module turns the bars into trade specifications; `v32_run.py`
simulates them on the ticks (`tsim32.py`) and reports.

Every reading at a decision uses the bars complete by the decision (`avail`), the swings / pivots confirmed by then
(rule D4) and the levels known by then. The trail steps of exit (a) are each dated at their own confirming bar's
`avail`, so the simulator applies each only from its own moment.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402

NS_MIN = W.NS_MIN
ENTRY_TFS = ("M1", "M5", "M15")
UP_TFS = ("M1", "M5", "M15", "M30", "H1")  # "every TF from the entry TF up to H1"
BUF = 0.25  # x S: "a few USD past" the extreme (trade 4: 4177.06 -> 4180)
BUF_H = 0.25  # x H: entry 3's break-extreme stop (PROPOSALS proposal 2)
BASE_N = 6  # R5: the base's bars
BASE_ATR = 2.0  # R5: the base's span, x the TF's ATR14
FAKE_A = 0.3  # R8: the fake leg, x S
FAKE_MIN = 60  # R8: the decision by T0 + 60 minutes
HOLD = 120  # R7: minutes
HOLD_NY = 240  # R7: minutes for an NY-open entry
PIV_N = 6  # R7: the last confirmed pivots of M15 / H1 as target candidates
PARTS = {"P1": (pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-01-16", tz="UTC")),
         "P2": (pd.Timestamp("2026-01-16", tz="UTC"), pd.Timestamp("2026-04-18", tz="UTC"))}
WINDOWS = ("Asia", "London", "NY0830", "NYopen")


# ------------------------------------------------------------------ R1: the windows
def window_of(t_ns) -> np.ndarray:
    """The window of each decision moment: Asia 00:00-02:00 UTC, London 06:00-07:00 UTC, NY0830 08:30-09:30 and
    NYopen 09:30-13:30 New York time; else 'other'."""
    t = pd.DatetimeIndex(np.asarray(t_ns, np.int64), tz="UTC")
    u = np.asarray(t.hour * 60 + t.minute)
    ny = t.tz_convert("America/New_York")
    n = np.asarray(ny.hour * 60 + ny.minute)
    out = np.full(len(t), "other", dtype=object)
    out[(u >= 0) & (u < 120)] = "Asia"
    out[(u >= 360) & (u < 420)] = "London"
    out[(n >= 510) & (n < 570)] = "NY0830"
    out[(n >= 570) & (n < 810)] = "NYopen"
    return out


def ny_bucket(t_ns) -> np.ndarray:
    """The NY-open 30-minute bucket ('09:30' .. '13:00'), '' outside the NY-open window."""
    t = pd.DatetimeIndex(np.asarray(t_ns, np.int64), tz="UTC").tz_convert("America/New_York")
    n = np.asarray(t.hour * 60 + t.minute)
    b = (n - 570) // 30
    lab = np.array([f"{(570 + 30 * k) // 60:02d}:{(570 + 30 * k) % 60:02d}" for k in range(8)], dtype=object)
    return np.where((n >= 570) & (n < 810), lab[np.clip(b, 0, 7)], "")


def part_of(t_ns) -> np.ndarray:
    t = pd.DatetimeIndex(np.asarray(t_ns, np.int64), tz="UTC")
    out = np.full(len(t), "", dtype=object)
    for k, (a, b) in PARTS.items():
        out[(t >= a) & (t < b)] = k
    return out


# ------------------------------------------------------------------ R2: the entry TF
def choose_tf(h_atr: np.ndarray, q1: float, q2: float) -> np.ndarray:
    """Low tercile (H < q1) -> M1, middle (q1 <= H < q2) -> M5, high (H >= q2) -> M15; NaN H -> ''."""
    h = np.asarray(h_atr, float)
    out = np.where(h < q1, "M1", np.where(h < q2, "M5", "M15")).astype(object)
    out[~np.isfinite(h)] = ""
    return out


# ------------------------------------------------------------------ the market: bars, swings, S, H
@dataclass
class Mkt:
    m: pd.DataFrame
    R: dict
    t1: np.ndarray  # M1 bar close moments (ns) = open + 1 min
    S: np.ndarray  # S at each M1 close
    H: np.ndarray  # the H1 ATR at each M1 close
    m15_inner: tuple
    av: dict  # the TFs' bar-complete moments (ns), cached

    def k1(self, t_ns) -> np.ndarray:
        """The last M1 bar complete by each moment."""
        return np.searchsorted(self.t1, np.asarray(t_ns, np.int64), side="right") - 1

    def s_at(self, t_ns) -> np.ndarray:
        k = self.k1(t_ns)
        return np.where(k >= 0, self.S[np.maximum(k, 0)], W.S_FLOOR)

    def h_at(self, t_ns) -> np.ndarray:
        k = self.k1(t_ns)
        return np.where(k >= 0, self.H[np.maximum(k, 0)], np.nan)


def market(m: pd.DataFrame, R: dict | None = None) -> Mkt:
    R = R or W.analyze_all(m, path=True)
    r15 = R["M15"]
    inner15 = W.zigzag(r15.bars.high.to_numpy(float), r15.bars.low.to_numpy(float), W.INNER * r15.s)
    av = {k: W._ns(r.bars.avail) for k, r in R.items() if "@" not in k}
    return Mkt(m, R, W._ns(m.index + pd.Timedelta(minutes=1)), W.swing_size(m), W.h1_atr(m), inner15, av)


def inner_of(mk: Mkt, tf: str) -> tuple:
    return mk.m15_inner if tf == "M15" else mk.R[tf].inner


def reading(mk: Mkt, tf: str, what: str, t_ns, mode: str = "path") -> np.ndarray:
    """A TF's label / bias at each moment (its last complete bar); NaN when none. mode 'path' = rule 18 (the TF's
    swing size on the M1 path, the primary), 'bar' = the TF's own bars."""
    r = mk.R[f"{tf}@M1"] if mode == "path" and tf != "M1" else mk.R[tf]
    j = r.at(np.asarray(t_ns, np.int64))
    v = r.struct[what].to_numpy(float)
    return np.where(j >= 0, v[np.maximum(j, 0)], np.nan)


def aligned(mk: Mkt, tf: str, what: str, t_ns, side, mode: str = "path") -> np.ndarray:
    """Every TF from `tf` up to H1 reads `side` (label or bias) at each moment."""
    side = np.asarray(side, float)
    ok = np.ones(len(side), bool)
    for x in UP_TFS[UP_TFS.index(tf):]:
        ok &= reading(mk, x, what, t_ns, mode) == side
    return ok


# ------------------------------------------------------------------ R3: the levels everyone sees (strategist/retest.py)
def everyone(mk: Mkt, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None):
    """The levels everyone sees per server day and their events on M5, as `strategist/retest.py` / `reclaim.py` define
    them (re-implemented). Returns (levels: list of (kind, price, top +1 / low -1, known ns, server day)),
    reclaims (#23), turns (#25) as DataFrames."""
    m = mk.m
    b5 = mk.R["M5"].bars
    av5 = W._ns(b5.avail)
    H5, L5, C5 = (b5[k].to_numpy(float) for k in ("high", "low", "close"))
    day5 = pd.DatetimeIndex(b5["last"]).tz_convert("Europe/Athens").tz_localize(None).floor("1D")
    sday = m.index.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
    D = pd.DataFrame({"h": m.high.to_numpy(), "l": m.low.to_numpy(), "d": sday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
    Hm = mk.h_at(av5)  # the H1 ATR at each M5 bar's close
    levels, rec, tur = [], [], []
    for d in D.index:
        if start is not None and d < start.tz_convert(None).floor("1D") - pd.Timedelta(days=1):
            continue
        if end is not None and d >= end.tz_convert(None):
            continue
        prev = D.index[D.index < d]
        idx = np.where(day5 == d)[0]
        if len(idx) < 50:
            continue
        day_start = av5[idx[0]] - 5 * NS_MIN
        lv = []
        if len(prev):
            lv += [("PDH", D.loc[prev[-1], "h"], 1, day_start), ("PDL", D.loc[prev[-1], "l"], -1, day_start)]
        a_s = pd.Timestamp(d.date(), tz="UTC").value
        a_e = a_s + 360 * NS_MIN
        ab = idx[(av5[idx] > a_s) & (av5[idx] <= a_e)]
        if len(ab) >= 60:
            lv += [("ASH", H5[ab].max(), 1, a_e), ("ASL", L5[ab].min(), -1, a_e)]
        for kind, L, top, known in lv:
            levels.append((kind, float(L), top, int(known), d))
            cand = idx[av5[idx] > known]
            if len(cand) < 3:
                continue
            bs = top  # the way the level breaks
            # the break (the same test in both scripts): the first M5 close beyond by 0.1 H from the other side
            q0 = None
            for q in range(1, len(cand)):
                k, kp = cand[q], cand[q - 1]
                Hk = Hm[k]
                if (C5[k] - L) * bs > 0.1 * Hk and (C5[kp] - L) * bs <= 0:
                    q0 = q
                    break
            if q0 is None:
                continue
            Hk = Hm[cand[q0]]
            # #23 the reclaim: within 24 M5 bars a close back inside by 0.1 H
            for q in range(q0 + 1, min(q0 + 25, len(cand))):
                k = cand[q]
                if (C5[k] - L) * bs < -0.1 * Hk:
                    seg = cand[q0:q + 1]
                    ext = H5[seg].max() if bs > 0 else L5[seg].min()
                    rec.append(dict(t_dec=int(av5[k]), brk=bs, kind=kind, L=L, H=Hk, ext=float(ext), bar=int(k)))
                    break
            # #25 the retest and its turn (retest.py)
            r = None
            for q in range(q0 + 1, min(q0 + 37, len(cand))):
                k = cand[q]
                if (C5[k] - L) * bs < -0.75 * Hk:
                    break
                if (bs < 0 and H5[k] >= L - 0.15 * Hk) or (bs > 0 and L5[k] <= L + 0.15 * Hk):
                    r = q
                    break
            if r is None:
                continue
            ext = H5[cand[r]] if bs < 0 else L5[cand[r]]
            lowest = L5[cand[r]] if bs < 0 else H5[cand[r]]
            for q in range(r + 1, min(r + 13, len(cand))):
                k = cand[q]
                if (C5[k] - L) * bs < -0.75 * Hk:
                    break
                turned = (C5[k] < lowest) if bs < 0 else (C5[k] > lowest)
                if turned and (C5[k] - L) * bs > -0.5 * Hk:
                    seg = cand[q0:q + 1]
                    bext = L5[seg].min() if bs < 0 else H5[seg].max()  # the break's extreme to the decision
                    tur.append(dict(t_dec=int(av5[k]), brk=bs, kind=kind, L=L, H=Hk, rext=float(ext), ext=float(bext), bar=int(k)))
                    break
                ext = max(ext, H5[k]) if bs < 0 else min(ext, L5[k])
                lowest = min(lowest, L5[k]) if bs < 0 else max(lowest, H5[k])
    cols_r = ["t_dec", "brk", "kind", "L", "H", "ext", "bar"]
    return levels, pd.DataFrame(rec, columns=cols_r), pd.DataFrame(tur, columns=[*cols_r[:5], "rext", "ext", "bar"])


def levels_known(levels, t_ns: int) -> list[float]:
    """PDH / PDL / ASH / ASL known at t (the same server day's, and known by t)."""
    d = pd.Timestamp(int(t_ns), tz="UTC").tz_convert("Europe/Athens").tz_localize(None).floor("1D")
    return [p for (_, p, _, known, day) in levels if day == d and known <= t_ns]


# ------------------------------------------------------------------ R7: the target candidates and the trail
def candidates(mk: Mkt, tf: str, t_ns, levels) -> list[list[float]]:
    """R7: the target candidates known at each moment (a list per moment)."""
    t_ns = np.asarray(t_ns, np.int64)
    out: list[list[float]] = [[] for _ in t_ns]
    for x in ("H1", "H4"):
        r = mk.R[x]
        for i, j in enumerate(r.at(t_ns)):
            if j >= 0:
                fb = W.fib_at(r, int(j))
                if fb is not None:
                    out[i] += list(fb["levels"].values())
    for x in ("M15", "H1"):
        r = mk.R[x]
        for i, j in enumerate(r.at(t_ns)):
            if j >= 0:
                out[i] += [float(p) for p in W.known_at(r.piv, int(j))[1][-PIV_N:]]
    r = mk.R[tf]
    top, bot = r.struct.box_top.to_numpy(float), r.struct.box_bot.to_numpy(float)
    for i, j in enumerate(r.at(t_ns)):
        if j >= 0:
            out[i] += [top[j], bot[j]]
    for i, t in enumerate(t_ns):
        out[i] += levels_known(levels, int(t))
    return [[x for x in o if np.isfinite(x)] for o in out]


def trail_steps(mk: Mkt, tf: str, j_dec: int, side: int, s: float, t_out: int) -> list[tuple[int, float]]:
    """R7 (a): the inner pivots of `tf` against the trade (peaks for a sell) whose bar is >= j_dec, confirmed after
    j_dec, each as (its confirming bar's avail, price + 0.25 S for a sell / - for a buy), up to t_out."""
    pb, pp, pk, pc = inner_of(mk, tf)
    av = mk.av[tf]
    want = 1 if side < 0 else -1
    sel = (pk == want) & (pb >= j_dec) & (pc > j_dec)
    out = []
    for p, c in zip(pp[sel], pc[sel]):
        if av[c] <= t_out:
            out.append((int(av[c]), float(p - side * BUF * s)))
    return out


# ------------------------------------------------------------------ the entries
def _base_cols(mk: Mkt, df: pd.DataFrame) -> pd.DataFrame:
    """The columns every entry carries: S, H, the window, the bucket, the part, the hold end."""
    t = df.t_dec.to_numpy(np.int64)
    df["S"] = mk.s_at(t)
    df["H"] = mk.h_at(t)
    df["window"] = window_of(t)
    df["bucket"] = ny_bucket(t)
    df["part"] = part_of(t)
    return df


def entry1(mk: Mkt, tf: str) -> pd.DataFrame:
    """R4: a retest_fail on the TF's box edge / line, traded with the break; stop = the extreme + 0.25 S."""
    ev = mk.R[tf].events
    e = ev[ev.tag.isin(["box_top", "box_bot", "sup", "res"])].copy()
    rf = e[e.kind == "retest_fail"].copy()
    if not len(rf):
        return pd.DataFrame()
    rf["first"] = rf.groupby(["tag", "obj"]).cumcount() == 0
    df = pd.DataFrame({"t_dec": W._ns(rf.avail), "side": rf.side.to_numpy(int), "ext": rf.price.to_numpy(float),
                       "level": rf.level.to_numpy(float), "tag": rf.tag.to_numpy(), "obj": rf.obj.to_numpy(int),
                       "j_dec": rf.bar.to_numpy(int), "first": rf["first"].to_numpy()})
    df = _base_cols(mk, df)
    df["stop"] = df.ext - df.side * BUF * df.S
    df["line"] = df.tag.isin(["sup", "res"])
    t = df.t_dec.to_numpy(np.int64)
    for mode, sfx in (("path", ""), ("bar", "_bar")):
        df[f"al_label{sfx}"] = aligned(mk, tf, "label", t, df.side, mode)
        df[f"al_bias{sfx}"] = aligned(mk, tf, "bias", t, df.side, mode)
    df["etype"], df["tf"], df["src"] = 1, tf, "box_line"
    return df


def base_triggers(mk: Mkt, tf: str, what: str, mode: str = "path") -> pd.DataFrame:
    """R5: the bars of `tf` where an aligned base starts, per side."""
    r = mk.R[tf]
    b = r.bars
    h, lo = b.high.to_numpy(float), b.low.to_numpy(float)
    n = len(b)
    atr = W.atr_warm(h, lo, b.close.to_numpy(float))
    hi6 = pd.Series(h).rolling(BASE_N).max().to_numpy()
    lo6 = pd.Series(lo).rolling(BASE_N).min().to_numpy()
    atr_prev = np.r_[np.full(BASE_N, np.nan), atr[:-BASE_N]] if n > BASE_N else np.full(n, np.nan)
    width = (hi6 - lo6) <= BASE_ATR * atr_prev
    j = np.arange(n)
    av = W._ns(b.avail)
    pb, pp, pk, pc = r.piv
    out = []
    for side in (-1, 1):
        want = 1 if side < 0 else -1  # a sell needs the last confirmed peak above the base
        sel = pk == want
        cb, bb, pr = pc[sel], pb[sel], pp[sel]
        q = np.searchsorted(cb, j, side="right") - 1
        has = q >= 0
        pbar = np.where(has, bb[np.maximum(q, 0)], 10**12)
        pprice = np.where(has, pr[np.maximum(q, 0)], np.nan)
        after = has & (j - (BASE_N - 1) > pbar)
        beyond = (hi6 < pprice) if side < 0 else (lo6 > pprice)
        al = aligned(mk, tf, what, av, np.full(n, side), mode)
        cond = width & after & beyond & al
        trig = cond & ~np.r_[False, cond[:-1]]
        for x in np.nonzero(trig)[0]:
            out.append(dict(t_dec=int(av[x]), side=side, j_dec=int(x), piv=float(pprice[x]), top=float(hi6[x]),
                            bot=float(lo6[x])))
    return pd.DataFrame(out, columns=["t_dec", "side", "j_dec", "piv", "top", "bot"])


def entry2(mk: Mkt, tf: str, what: str = "bias", mode: str = "path") -> pd.DataFrame:
    df = base_triggers(mk, tf, what, mode)
    if not len(df):
        return df
    df = _base_cols(mk, df.sort_values("t_dec").reset_index(drop=True))
    df["stop"] = df.piv - df.side * BUF * df.S
    near = []
    r = mk.R["H1"]
    for t, top, bot, s in zip(df.t_dec, df.top, df.bot, df.S):
        j = int(r.at(np.array([t]))[0])
        fb = W.fib_at(r, j) if j >= 0 else None
        near.append(bool(fb) and any(bot - BUF * s <= v <= top + BUF * s for v in fb["levels"].values()))
    df["fib"] = near
    df["etype"], df["tf"], df["src"], df["align"], df["mode"] = 2, tf, "base", what, mode
    return df


def _last_break_bar(ev: pd.DataFrame) -> np.ndarray:
    """For each event row, the bar of the latest 'break' of the same (tag, obj) at / before it (-1 when none)."""
    out = np.full(len(ev), -1)
    last: dict = {}
    for i, (tag, obj, kind, bar) in enumerate(zip(ev.tag, ev.obj, ev.kind, ev.bar)):
        if kind == "break":
            last[(tag, obj)] = bar
        out[i] = last.get((tag, obj), -1)
    return out


def entry3_box(mk: Mkt, tf: str) -> pd.DataFrame:
    """R6 on the TF's box edges: (i) sweep / reclaim, (ii) retest_fail, traded back inside."""
    r = mk.R[tf]
    ev = r.events[r.events.tag.isin(["box_top", "box_bot"])].reset_index(drop=True)
    if not len(ev):
        return pd.DataFrame()
    bb = _last_break_bar(ev)
    h, lo, c = (r.bars[k].to_numpy(float) for k in ("high", "low", "close"))
    rows = []
    for i, e in enumerate(ev.itertuples(index=False)):
        if e.kind not in ("sweep", "reclaim", "retest_fail") or bb[i] < 0:
            continue
        seg = slice(int(bb[i]), int(e.bar) + 1)
        ext = h[seg].max() if e.side > 0 else lo[seg].min()
        rows.append(dict(t_dec=int(W._ns(pd.DatetimeIndex([e.avail]))[0]), brk=int(e.side), kind3="ii" if e.kind == "retest_fail" else "i",
                         ev=e.kind, ext=float(ext), rext=float(e.price) if e.kind == "retest_fail" else np.nan,
                         close=float(c[e.bar]), j_dec=int(e.bar), lvl=e.tag))
    df = pd.DataFrame(rows)
    if not len(df):
        return df
    df["src"] = "box"
    return _base_cols(mk, df)


def entry3_everyone(mk: Mkt, rec: pd.DataFrame, tur: pd.DataFrame) -> pd.DataFrame:
    a = rec.assign(kind3="i", ev="reclaim23", rext=np.nan, lvl=rec.kind) if len(rec) else pd.DataFrame()
    b = tur.assign(kind3="ii", ev="turn25", lvl=tur.kind) if len(tur) else pd.DataFrame()
    df = pd.concat([a, b], ignore_index=True)
    if not len(df):
        return df
    c5 = mk.R["M5"].bars.close.to_numpy(float)
    df["close"] = c5[df.bar.to_numpy(int)]
    df["j_dec"] = df.bar.astype(int)
    df["src"] = "everyone"
    return _base_cols(mk, df.drop(columns=["kind", "L", "bar"]))


def entry3(mk: Mkt, tf: str, rec: pd.DataFrame, tur: pd.DataFrame) -> pd.DataFrame:
    """R6: the union; side = back inside (-brk); stop settings 'mirror' (mirror_of) and 'ext' (stop)."""
    parts = [x for x in (entry3_box(mk, tf), entry3_everyone(mk, rec, tur)) if len(x)]
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    df["side"] = -df.brk
    hb = BUF_H * df.H
    df["stop_ext"] = df.ext - df.side * hb
    # mirror: (i) the same distance as the ext stop from the decision close; (ii) the same-side rule's stop.
    # The same-side rule (with the break) has its stop past the retest's extreme, against the break side:
    # brk = -1 (sell) -> rext + buf; brk = +1 (buy) -> rext - buf
    buf = np.where(df.src == "box", BUF * df.S, BUF_H * df.H)
    same_stop = df.rext.to_numpy(float) - df.brk.to_numpy(float) * buf
    df["mirror_of"] = np.where(df.kind3 == "ii", same_stop, np.nan)
    df["mirror_dist"] = np.where(df.kind3 == "i", (df.close - df.stop_ext).abs(), np.nan)
    df["etype"], df["tf"] = 3, tf
    df["prio"] = np.select([(df.src == "box") & (df.kind3 == "i"), (df.src == "everyone") & (df.kind3 == "i"),
                            (df.src == "box") & (df.kind3 == "ii")], [0, 1, 2], 3)
    df = df.sort_values(["t_dec", "side", "prio"]).drop_duplicates(["t_dec", "side"], keep="first")
    return df.reset_index(drop=True)


def opens(mk: Mkt) -> pd.DataFrame:
    """R8: the opens T0 of every weekday in the bars: Asia 00:00 UTC, London 06:00 UTC, NY 08:30 / 09:30 NY time."""
    days = pd.DatetimeIndex(mk.m.index.normalize().unique())
    rows = []
    for d in days:
        for name, t0 in (("Asia", d), ("London", d + pd.Timedelta(hours=6))):
            if t0.dayofweek < 5:
                rows.append((name, t0))
        nyd = pd.Timestamp(d.date()).tz_localize("America/New_York")
        if nyd.dayofweek < 5:
            rows.append(("NY0830", (nyd + pd.Timedelta(hours=8, minutes=30)).tz_convert("UTC")))
            rows.append(("NYopen", (nyd + pd.Timedelta(hours=9, minutes=30)).tz_convert("UTC")))
    df = pd.DataFrame(rows, columns=["open", "T0"]).drop_duplicates("T0").sort_values("T0").reset_index(drop=True)
    return df


def entry4(mk: Mkt, tf: str, what: str = "bias", mode: str = "path") -> pd.DataFrame:
    O = opens(mk)
    t0 = W._ns(pd.DatetimeIndex(O.T0))
    col = "trend_bias" if what == "bias" else "trend"
    rd = W.readings_at(mk.R, t0, mode=mode)
    d = rd[col].to_numpy(float)
    m = mk.m
    mo, mh, ml = (m[k].to_numpy(float) for k in ("open", "high", "low"))
    mt = W._ns(m.index)
    r = mk.R[tf]
    bt, bav, bc = W._ns(r.bars.t), W._ns(r.bars.avail), r.bars.close.to_numpy(float)
    rows = []
    for k in range(len(O)):
        side = d[k]
        if not np.isfinite(side) or side == 0:
            continue
        side = int(side)
        T0 = int(t0[k])
        i0 = int(np.searchsorted(mt, T0, side="left"))
        if i0 >= len(mt) or mt[i0] - T0 >= 5 * NS_MIN:
            continue
        p0 = mo[i0]
        A = FAKE_A * float(mk.s_at(np.array([T0]))[0])
        i1 = int(np.searchsorted(mt, T0 + FAKE_MIN * NS_MIN, side="left"))
        fake = np.nonzero((mh[i0:i1] >= p0 + A) if side < 0 else (ml[i0:i1] <= p0 - A))[0]
        if not len(fake):
            continue
        f_av = mt[i0 + fake[0]] + NS_MIN  # the fake bar's close
        cand = np.nonzero((bt >= T0) & (bav >= f_av) & (bav <= T0 + FAKE_MIN * NS_MIN)
                          & ((bc < p0) if side < 0 else (bc > p0)))[0]
        if not len(cand):
            continue
        jd = int(cand[0])
        t_dec = int(bav[jd])
        seg = slice(i0, int(np.searchsorted(mt, t_dec, side="left")))  # M1 bars opened in [T0, t_dec)
        ext = mh[seg].max() if side < 0 else ml[seg].min()
        rows.append(dict(t_dec=t_dec, side=side, j_dec=jd, T0=T0, open=O.open[k], p0=float(p0), ext=float(ext)))
    df = pd.DataFrame(rows, columns=["t_dec", "side", "j_dec", "T0", "open", "p0", "ext"])
    if not len(df):
        return df
    df = _base_cols(mk, df)
    df["stop"] = df.ext - df.side * BUF * df.S
    df["etype"], df["tf"], df["src"], df["align"], df["mode"] = 4, tf, "open", what, mode
    return df


# ------------------------------------------------------------------ the side source, the specs for the simulator
def side_source(mk: Mkt, t_ns, side) -> pd.DataFrame:
    out = {}
    for mode, sfx in (("path", ""), ("bar", "_bar")):
        rd = W.readings_at(mk.R, np.asarray(t_ns, np.int64), mode=mode)
        for col in ("side", "side_bias", "trend", "trend_bias"):
            v = rd[col].to_numpy(float)
            s = np.asarray(side, float)
            out[f"src_{col}{sfx}"] = np.where(~np.isfinite(v), "unknown", np.where(v == 0, "none", np.where(v == s, "with", "against")))
    return pd.DataFrame(out)


def finish(mk: Mkt, df: pd.DataFrame, levels, learning: bool = True) -> pd.DataFrame:
    """Adds the hold end, the side source and (entries 1 / 2 / 4) the target candidates and the trail steps."""
    if not len(df):
        return df
    if learning:
        df = df[df.part != ""]  # the warm-up months carry no trade
    df = df.reset_index(drop=True)
    if not len(df):
        return df
    hold = np.where((df.window == "NYopen") & df.etype.isin([1, 2, 4]), HOLD_NY, HOLD)
    df["t_out"] = df.t_dec.to_numpy(np.int64) + hold * NS_MIN
    df = pd.concat([df, side_source(mk, df.t_dec, df.side)], axis=1)
    if int(df.etype.iat[0]) in (1, 2, 4):
        df["cands"] = candidates(mk, str(df.tf.iat[0]), df.t_dec.to_numpy(np.int64), levels)
        df["trail"] = [trail_steps(mk, tf, int(j), int(s), float(S), int(to))
                       for tf, j, s, S, to in zip(df.tf, df.j_dec, df.side, df.S, df.t_out)]
    return df


def build(mk: Mkt, tfs=ENTRY_TFS, learning: bool = True) -> dict[str, pd.DataFrame]:
    """Every entry's specs on each entry TF (all hours; the windows and the 'vol' choice are applied in the report)."""
    levels, rec, tur = everyone(mk)
    out = {"rec": rec, "tur": tur}
    for tf in tfs:
        out[f"e1_{tf}"] = finish(mk, entry1(mk, tf), levels, learning)
        for what in ("bias", "label"):
            for mode in ("path", "bar"):
                out[f"e2_{tf}_{what}_{mode}"] = finish(mk, entry2(mk, tf, what, mode), levels, learning)
                out[f"e4_{tf}_{what}_{mode}"] = finish(mk, entry4(mk, tf, what, mode), levels, learning)
        out[f"e3_{tf}"] = finish(mk, entry3(mk, tf, rec, tur), levels, learning)
    out["base25"] = finish(mk, _base25(mk, tur), levels, learning)
    out["levels"] = pd.DataFrame(levels, columns=["kind", "price", "top", "known", "day"])
    return out


def _base25(mk: Mkt, tur: pd.DataFrame) -> pd.DataFrame:
    """The base rate (#25) in my simulator: the turn with the break, stop = the retest's extreme + 0.25 H, 2 R."""
    if not len(tur):
        return pd.DataFrame()
    df = pd.DataFrame({"t_dec": tur.t_dec, "side": tur.brk, "j_dec": tur.bar, "lvl": tur.kind})
    df = _base_cols(mk, df)
    df["stop"] = tur.rext.to_numpy() - df.side * BUF_H * tur.H.to_numpy()
    df["etype"], df["tf"], df["src"] = 25, "M5", "everyone"
    return df
