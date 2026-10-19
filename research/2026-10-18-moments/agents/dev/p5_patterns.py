"""Task P5: the owner's whole pattern set on the trade's swing scale (DEV_LOG.md "Task P5 - written before computing").
One causal ZigZag on M1 with an inner swing of 0.3 x the H1 ATR; every formation at least one main swing (0.6 x the H1
ATR) tall: double / triple tops and bottoms (with a sweep), H&S, channel breaks, break and retest, the fake first leg at
an open, base / range breaks, A-B-C-D-E triangles; and pictures in formation (two tops / two bottoms) with their two
scenarios. Closed bars only; the sell side by the mirror (highs -> -lows).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p5_patterns.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, LEARN_START, ExamPeriodError  # noqa: E402

NS_MIN = 60 * 10**9
K_MAIN, K_IN, EQ_K, SW_K = 0.6, 0.3, 0.25, 0.5
SPAN5 = 300
CH_MIN_BARS, CH_PAR = 30, 0.5
BASE5_MIN, BASE5_MAX = 20, 240
FO_LEG, FO_WIN = 15, 60  # the fake leg within 15 minutes of the open, the trade within 60
STOP_IN = 0.2  # the scenarios' stops: 0.2 x the inner swing past
NAMES5 = {("double", 1): "double bottom", ("double", -1): "double top", ("triple", 1): "triple bottom",
          ("triple", -1): "triple top", ("ihs", 1): "inverse H&S", ("ihs", -1): "H&S", ("retest", 1): "break up, retest",
          ("retest", -1): "break down, retest", ("channel", 1): "channel break up", ("channel", -1): "channel break down",
          ("triangle", 1): "triangle break up", ("triangle", -1): "triangle break down", ("base", 1): "base break up",
          ("base", -1): "base break down", ("fake_open", 1): "open: fake down, then up", ("fake_open", -1): "open: fake up, then down"}
SELL_LABELS5 = {"L1": "H1", "L2": "H2", "L3": "H3", "P": "T", "P1": "T1", "P2": "T2"}


def map_to_m1(b_avail: np.ndarray, values: np.ndarray, m1_close: np.ndarray) -> np.ndarray:
    """The value of the last bar complete by each M1 bar's close (NaN before the first)."""
    k = np.searchsorted(b_avail, m1_close, side="right") - 1
    out = np.full(len(m1_close), np.nan)
    ok = k >= 0
    out[ok] = values[k[ok]]
    return out


def h1_atr_m1(m: pd.DataFrame) -> np.ndarray:
    """H at each M1 bar: the ATR(14) of the last H1 bar complete by that M1 bar's close (the learning parts)."""
    b = P.tf_bars(m, 60)
    return map_to_m1(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, P.atr14(b),
                     (m.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8)


def day_h1_atr(m: pd.DataFrame) -> np.ndarray:
    """H on the shape-check day (no earlier bars may be read): the mean true range of the day's H1 bars completed so
    far (the first bar's true range = its high - low)."""
    b = P.tf_bars(m, 60)
    h, lo, c = (b[k].to_numpy(float) for k in ("high", "low", "close"))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - lo, np.maximum(h, pc) - np.minimum(lo, pc))
    exp = np.cumsum(tr) / np.arange(1, len(tr) + 1)
    return map_to_m1(pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, exp, (m.index + pd.Timedelta(minutes=1)).as_unit("ns").asi8)


def flat(x: float, a: int, d: int) -> np.ndarray:
    return np.full(d - a + 1, x)


def find5_buy(h: np.ndarray, lo: np.ndarray, c: np.ndarray, seq: list[tuple], d: int, main: float, inn: float) -> list[dict]:
    """The buy-side swing formations breaking out at bar d: double bottom, triple bottom, inverse H&S, break and
    retest. seq = patterns.structure(...) at d on the inner ZigZag."""
    if len(seq) < 3 or not np.isfinite(main):
        return []
    eq, sw = EQ_K * main, SW_K * main
    k3 = len(seq) - 1 if seq[-1][2] == -1 else len(seq) - 2
    if k3 < 2 or seq[k3][2] != -1:
        return []
    t3, p2, t2 = seq[k3], seq[k3 - 1], seq[k3 - 2]
    out = []
    above_p2 = P.first_close_above(c, flat(p2[1], t3[0], d), t3[0], d)
    if above_p2 and t2[1] - sw <= t3[1] <= t2[1] + eq and p2[1] - min(t2[1], t3[1]) >= main and d - t2[0] <= SPAN5:
        out.append(dict(family="double", variant="swept" if t3[1] < t2[1] - eq else "equal", extreme=min(t2[1], t3[1]),
                        trigger=p2[1], height=p2[1] - min(t2[1], t3[1]), start=t2[0],
                        points=[(t2[0], t2[1], "L1"), (p2[0], p2[1], "P"), (t3[0], t3[1], "L2")]))
    if k3 >= 4:
        t1, p1 = seq[k3 - 4], seq[k3 - 3]
        lows = (t1[1], t2[1], t3[1])
        if (above_p2 and t1[1] - sw <= t2[1] <= t1[1] + eq and min(t1[1], t2[1]) - sw <= t3[1] <= max(t1[1], t2[1]) + eq
                and max(p1[1], p2[1]) - min(lows) >= main and d - t1[0] <= SPAN5):
            out.append(dict(family="triple", variant="swept" if t3[1] < min(t1[1], t2[1]) - eq else "equal",
                            extreme=min(lows), trigger=p2[1], height=max(p1[1], p2[1]) - min(lows), start=t1[0],
                            points=[(t1[0], t1[1], "L1"), (p1[0], p1[1], "P1"), (t2[0], t2[1], "L2"), (p2[0], p2[1], "P2"),
                                    (t3[0], t3[1], "L3")]))
        if p2[0] > p1[0] and d - t1[0] <= SPAN5:
            slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
            hgt = p1[1] + slope * (t2[0] - p1[0]) - t2[1]
            line = p1[1] + slope * (np.arange(t3[0], d + 1) - p1[0])
            if (t2[1] < min(t1[1], t3[1]) - eq and abs(t1[1] - t3[1]) <= 0.5 * hgt and abs(p2[1] - p1[1]) <= 0.5 * hgt
                    and hgt >= main and P.first_close_above(c, line, t3[0], d)):
                out.append(dict(family="ihs", variant="inverse H&S", extreme=t2[1], trigger=float(line[-1]), height=hgt,
                                start=t1[0], neck=((p1[0], p1[1]), (p2[0], p2[1])),
                                points=[(t1[0], t1[1], "LS"), (p1[0], p1[1], "N1"), (t2[0], t2[1], "Head"),
                                        (p2[0], p2[1], "N2"), (t3[0], t3[1], "RS")]))
    for j in range(k3 - 1, 0, -1):  # the break and retest: the latest qualifying peak
        pk, before = seq[j], seq[j - 1]
        if pk[2] != 1 or pk[3] or before[2] != -1 or pk[1] - before[1] < main:
            continue
        brk = np.nonzero(c[pk[0] + 1:t3[0]] > pk[1])[0]
        if not len(brk) or not (pk[1] - eq <= t3[1] <= pk[1] + eq) or d - pk[0] > SPAN5:
            continue
        b1 = pk[0] + 1 + int(brk[0])
        top = float(h[b1:t3[0] + 1].max())
        if top - t3[1] >= inn and P.first_close_above(c, flat(top, t3[0], d), t3[0], d):
            out.append(dict(family="retest", variant="held", extreme=t3[1], trigger=top, height=top - t3[1], start=pk[0],
                            points=[(pk[0], pk[1], "level"), (b1, float(c[b1]), "break"), (t3[0], t3[1], "retest")]))
        break
    return out


def unmirror5(p: dict) -> dict:
    q = dict(p, side=-1, extreme=-p["extreme"], trigger=-p["trigger"])
    q["points"] = [(b, -x, SELL_LABELS5.get(lab, lab)) for b, x, lab in p["points"]]
    if "neck" in p:
        q["neck"] = tuple((b, -x) for b, x in p["neck"])
    return q


def confirmed(seq: list[tuple], n: int) -> list[tuple]:
    return [x for x in seq if not x[3]][-n:]


def find_channel(c: np.ndarray, seq: list[tuple], d: int, inn: float) -> list[dict]:
    """A channel break at bar d: the last four confirmed pivots (two peaks, two troughs), the upper line through the
    peaks and the lower through the troughs parallel (|su - sl| <= CH_PAR x the larger |slope|), the width at the last
    pivot >= inn, >= CH_MIN_BARS and <= SPAN5 bars from the first pivot; every close from the last pivot to d - 1 inside
    the lines and close[d] beyond one: above -> buy, below -> sell."""
    q = confirmed(seq, 4)
    if len(q) < 4 or not np.isfinite(inn):
        return []
    pk = [x for x in q if x[2] == 1]
    tr = [x for x in q if x[2] == -1]
    if len(pk) != 2 or len(tr) != 2:
        return []
    su = (pk[1][1] - pk[0][1]) / (pk[1][0] - pk[0][0])
    sl = (tr[1][1] - tr[0][1]) / (tr[1][0] - tr[0][0])
    if abs(su - sl) > CH_PAR * max(abs(su), abs(sl)):
        return []
    last, first = q[-1][0], q[0][0]
    up = lambda b: pk[0][1] + su * (b - pk[0][0])  # noqa: E731
    dn = lambda b: tr[0][1] + sl * (b - tr[0][0])  # noqa: E731
    if up(last) - dn(last) < inn or not (CH_MIN_BARS <= d - first <= SPAN5):
        return []
    bars = np.arange(last, d)
    if len(bars) and (np.any(c[last:d] > up(bars)) or np.any(c[last:d] < dn(bars))):
        return []
    side = 1 if c[d] > up(d) else -1 if c[d] < dn(d) else 0
    if not side:
        return []
    return [dict(family="channel", variant="descending" if su < 0 else "ascending" if su > 0 else "flat", side=side,
                 extreme=tr[1][1] if side > 0 else pk[1][1], trigger=float(up(d) if side > 0 else dn(d)),
                 height=float(up(last) - dn(last)), start=first,
                 lines=((pk[0][0], pk[0][1], d, float(up(d))), (tr[0][0], tr[0][1], d, float(dn(d)))),
                 points=[(x[0], x[1], "H" if x[2] == 1 else "L") for x in q])]


def find_triangle(c: np.ndarray, seq: list[tuple], d: int, main: float) -> list[dict]:
    """An A-B-C-D-E triangle break at bar d: the last five confirmed pivots alternate; A, C, E peaks descending and B,
    D troughs ascending (or A, C, E troughs ascending and B, D peaks descending); the lines A-C and B-D converge; |A - B|
    >= main; every close from E to d - 1 inside the lines, close[d] beyond one - the side by the break."""
    q = confirmed(seq, 5)
    if len(q) < 5 or not np.isfinite(main):
        return []
    a, b, cc, dd, e = q
    s = a[2]  # +1: A, C, E peaks
    if not (s * (a[1] - cc[1]) > 0 and s * (cc[1] - e[1]) > 0 and s * (dd[1] - b[1]) > 0) or abs(a[1] - b[1]) < main:
        return []
    if d - a[0] > SPAN5:
        return []
    l1 = lambda x: a[1] + (cc[1] - a[1]) / (cc[0] - a[0]) * (x - a[0])  # noqa: E731
    l2 = lambda x: b[1] + (dd[1] - b[1]) / (dd[0] - b[0]) * (x - b[0])  # noqa: E731
    up, dn = (l1, l2) if s > 0 else (l2, l1)
    bars = np.arange(e[0], d)
    if len(bars) and (np.any(c[e[0]:d] > up(bars)) or np.any(c[e[0]:d] < dn(bars))):
        return []
    side = 1 if c[d] > up(d) else -1 if c[d] < dn(d) else 0
    if not side or up(d) <= dn(d):
        return []
    lows = [x for x in q if x[2] == -1]
    highs = [x for x in q if x[2] == 1]
    return [dict(family="triangle", variant="A-B-C-D-E", side=side, extreme=lows[-1][1] if side > 0 else highs[-1][1],
                 trigger=float(up(d) if side > 0 else dn(d)), height=abs(a[1] - b[1]), start=a[0],
                 lines=((a[0], a[1], d, float(l1(d))), (b[0], b[1], d, float(l2(d)))),
                 points=[(x[0], x[1], lab) for x, lab in zip(q, "ABCDE", strict=True)])]


def find_base5(h: np.ndarray, lo: np.ndarray, c: np.ndarray, main: np.ndarray, d: int, r20: np.ndarray) -> list[dict]:
    """A base / range break at bar d: the longest run of BASE5_MIN .. BASE5_MAX bars ending at d - 1 within the main
    swing at d - 1 (r20[d - 1] = the range of the 20 bars ending at d - 1, a fast first test); close[d] beyond it."""
    if d - BASE5_MIN < 0 or not np.isfinite(main[d - 1]) or not r20[d - 1] <= main[d - 1]:
        return []
    w = main[d - 1]
    hi, low, best = -np.inf, np.inf, None
    for n in range(1, min(BASE5_MAX, d) + 1):
        hi, low = max(hi, h[d - n]), min(low, lo[d - n])
        if hi - low > w:
            break
        if n >= BASE5_MIN:
            best = (n, hi, low)
    if best is None:
        return []
    n, hi, low = best
    side = 1 if c[d] > hi else -1 if c[d] < low else 0
    if not side:
        return []
    return [dict(family="base", variant=f"{n} bars", side=side, extreme=low if side > 0 else hi, trigger=hi if side > 0 else low,
                 height=hi - low, start=d - n, box=(d - n, d - 1, low, hi), points=[])]


def window_opens(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[int, str]]:
    """The owner's window opens in [start, end), UTC ns: 07:00 Thai (Asia), 13:00 Thai (London), 09:30 New York (NY),
    weekdays (Mon - Fri of the opening clock's date)."""
    out = []
    for day in pd.date_range(start.tz_convert("UTC").normalize() - pd.Timedelta(days=1), end, freq="D"):
        for zone, hh, mm, name in (("Asia/Bangkok", 7, 0, "Asia"), ("Asia/Bangkok", 13, 0, "London"),
                                   ("America/New_York", 9, 30, "NY")):
            t = pd.Timestamp(year=day.year, month=day.month, day=day.day, hour=hh, minute=mm, tz=zone)
            if t.weekday() < 5 and start <= t.tz_convert("UTC") < end:
                out.append((t.tz_convert("UTC").value, name))
    return sorted(set(out))


def fake_opens(t_open: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray, inn: np.ndarray,
               opens: list[tuple[int, str]]) -> list[dict]:
    """The fake first leg at each open: p0 = the close before the open's bar; the first bar within FO_LEG minutes that
    moves an inner swing from p0 sets the fake side (both ways in one bar: the larger); the trade = the first close
    beyond p0 the other way within FO_WIN minutes of the open; extreme = the fake leg's extreme up to that bar."""
    out = []
    for o, name in opens:
        j0 = int(np.searchsorted(t_open, o))
        if j0 < 1 or j0 >= len(c) or t_open[j0] - o > 5 * NS_MIN or not np.isfinite(inn[j0 - 1]):
            continue
        p0 = c[j0 - 1]
        j_leg = s1 = None
        for j in range(j0, len(c)):
            if t_open[j] >= o + FO_LEG * NS_MIN:
                break
            up, dn = h[j] - p0, p0 - lo[j]
            if max(up, dn) >= inn[j0 - 1]:
                j_leg, s1 = j, (1 if up >= dn else -1)
                break
        if j_leg is None:
            continue
        for k in range(j_leg, len(c)):
            if t_open[k] >= o + FO_WIN * NS_MIN:
                break
            if s1 * (c[k] - p0) < 0:
                ext = float(h[j0:k + 1].max() if s1 > 0 else lo[j0:k + 1].min())
                out.append(dict(family="fake_open", variant=name, side=-s1, d=k, extreme=ext, trigger=float(p0),
                                height=abs(ext - p0), start=j0, points=[(j0 - 1, float(p0), "open"),
                                                                       (int(np.argmax(h[j0:k + 1]) if s1 > 0 else np.argmin(lo[j0:k + 1])) + j0, ext, "fake")]))
                break
    return out


def forming_tops(h: np.ndarray, lo: np.ndarray, c: np.ndarray, seq: list[tuple], d: int, main: float, inn: float) -> dict | None:
    """Two tops in formation at bar d (two bottoms by the mirror): the last confirmed peak P_a, the confirmed trough T
    after it, the next peak P_b (confirmed, or the running one) within [P_a - EQ, P_a + SW]; max(P) - T >= main; the
    close below P_b by >= EQ and above T; no close above max(P) since P_b. With scenario A (sell below the lowest low
    since P_b; the stop above the top + 0.2 inn; the target minus the height) and B (buy above the top; the stop below
    that low - 0.2 inn; the target plus the height)."""
    if len(seq) < 3 or not np.isfinite(main):
        return None
    eq, sw = EQ_K * main, SW_K * main
    if seq[-1][2] == 1:  # the running peak is P_b
        pa, t, pb = seq[-3], seq[-2], seq[-1]
    else:  # P_b confirmed, the running extreme a pullback trough
        if len(seq) < 4:
            return None
        pa, t, pb = seq[-4], seq[-3], seq[-2]
    if not (pa[2] == 1 and t[2] == -1 and pb[2] == 1 and not pa[3] and not t[3]):
        return None
    top = max(pa[1], pb[1])
    if not (pa[1] - eq <= pb[1] <= pa[1] + sw) or top - t[1] < main or d <= pb[0]:
        return None
    if not (c[d] <= pb[1] - eq and c[d] > t[1]) or np.any(c[pb[0] + 1:d + 1] > top):
        return None
    low = float(lo[pb[0] + 1:d + 1].min())
    hgt = top - t[1]
    return dict(kind="two tops", pa=pa, t=t, pb=pb, top=top, low=low, height=hgt,
                a=dict(side=-1, trigger=low, stop=top + STOP_IN * inn, target=low - hgt),
                b=dict(side=1, trigger=top, stop=low - STOP_IN * inn, target=top + hgt))


def patterns5_at(h, lo, c, H, piv, mir, d, r20) -> list[dict]:
    """Every completed formation breaking out at bar d (all families but the fake open leg, found per open)."""
    main, inn = K_MAIN * H[d], K_IN * H[d]
    seq = P.structure(piv, h, lo, d, keep=10)
    out = [dict(p, side=1) for p in find5_buy(h, lo, c, seq, d, main, inn)]
    mh, ml, mc, mp = mir
    out += [unmirror5(p) for p in find5_buy(mh, ml, mc, P.structure(mp, mh, ml, d, keep=10), d, main, inn)]
    out += find_channel(c, seq, d, inn) + find_triangle(c, seq, d, main)
    out += find_base5(h, lo, c, K_MAIN * H, d, r20)
    for p in out:
        p["d"] = d
    return out


def forming_at(h, lo, c, H, piv, mir, d) -> list[dict]:
    """The pictures in formation at bar d: two tops, and two bottoms by the mirror."""
    main, inn = K_MAIN * H[d], K_IN * H[d]
    out = []
    x = forming_tops(h, lo, c, P.structure(piv, h, lo, d, keep=10), d, main, inn)
    if x:
        out.append(x)
    mh, ml, mc, mp = mir
    y = forming_tops(mh, ml, mc, P.structure(mp, mh, ml, d, keep=10), d, main, inn)
    if y:
        out.append(dict(kind="two bottoms", pa=(y["pa"][0], -y["pa"][1], -1, y["pa"][3]), t=(y["t"][0], -y["t"][1], 1, y["t"][3]),
                        pb=(y["pb"][0], -y["pb"][1], -1, y["pb"][3]), top=-y["top"], low=-y["low"], height=y["height"],
                        a=dict(side=1, trigger=-y["a"]["trigger"], stop=-y["a"]["stop"], target=-y["a"]["target"]),
                        b=dict(side=-1, trigger=-y["b"]["trigger"], stop=-y["b"]["stop"], target=-y["b"]["target"])))
    return out


class Chart:
    """M1 bars with H, the inner ZigZag and the mirror, ready to scan."""

    def __init__(self, m: pd.DataFrame, H: np.ndarray):
        self.m = m
        self.t_open = m.index.as_unit("ns").asi8
        self.avail = self.t_open + NS_MIN
        self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("high", "low", "close"))
        self.H = H
        self.piv = P.zigzag(self.h, self.lo, H, K_IN)
        self.mir = (-self.lo, -self.h, -self.c, P.mirror_piv(self.piv))
        self.r20 = (pd.Series(self.h).rolling(BASE5_MIN).max() - pd.Series(self.lo).rolling(BASE5_MIN).min()).to_numpy()

    def scan(self, a: int, b: int, opens: list[tuple[int, str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
        cats, forms, seen = [], [], set()
        for d in range(max(a, 1), b):
            if not np.isfinite(self.H[d]):
                continue
            cats += patterns5_at(self.h, self.lo, self.c, self.H, self.piv, self.mir, d, self.r20)
            for f in forming_at(self.h, self.lo, self.c, self.H, self.piv, self.mir, d):
                key = (f["kind"], f["pb"][0])
                if key not in seen:
                    seen.add(key)
                    forms.append(dict(f, d=d))
        cats += [x for x in fake_opens(self.t_open, self.h, self.lo, self.c, K_IN * self.H, opens) if a <= x["d"] < b]
        C = pd.DataFrame(cats)
        if len(C):
            C["name"] = [NAMES5[(f, s)] for f, s in zip(C.family, C.side, strict=True)]
            C["t_dec"] = self.avail[C.d.to_numpy(int)]
        F = pd.DataFrame(forms)
        if len(F):
            F["t_dec"] = self.avail[F.d.to_numpy(int)]
        return C, F


def main() -> None:
    from p4_trades import window_of  # noqa: PLC0415

    m = P.load_m1()
    ch = Chart(m, h1_atr_m1(m))
    a = int(np.searchsorted(ch.avail, LEARN_START.value))
    C, F = ch.scan(a, len(ch.c), window_opens(LEARN_START, EXAM_START))
    if (C.t_dec >= EXAM_START.value).any() or (F.t_dec >= EXAM_START.value).any():
        raise ExamPeriodError("an exam decision")
    C["window"] = [window_of(t) for t in C.t_dec]
    F["window"] = [window_of(t) for t in F.t_dec]
    keep = ["family", "variant", "side", "name", "d", "t_dec", "trigger", "extreme", "height", "start", "window"]
    pts = lambda df: df.assign(pts_t=[[int(ch.t_open[b]) for b, _, _ in p] for p in df.points],  # noqa: E731
                               pts_p=[[float(x) for _, x, _ in p] for p in df.points],
                               pts_lab=[[lab for _, _, lab in p] for p in df.points])
    C2 = pts(C)[keep + ["pts_t", "pts_p", "pts_lab"]]
    C2.to_parquet(HERE / "p5_catches.parquet")
    pd.to_pickle(dict(C=C, F=F), HERE / "p5_scan.pkl")
    pd.set_option("display.width", 200)
    days = pd.DatetimeIndex(pd.to_datetime(C.t_dec, utc=True)).normalize().nunique()
    print(f"catches {len(C)} on {days} days; inside the owner's windows {int(C.window.notna().sum())}")
    print(C.groupby(["name"]).size().to_string())
    print(f"pictures in formation {len(F)} (two tops {int((F.kind == 'two tops').sum())}, two bottoms {int((F.kind == 'two bottoms').sum())})")


if __name__ == "__main__":
    main()
