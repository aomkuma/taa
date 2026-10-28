"""Setup OWN V3 - the shared trade-size swings and the structure per TF (V3-1). The rules are written in DEV_LOG.md
("Written before computing (V3-1)", rules 1-14) and coded here one for one. Every reading at a TF bar uses that bar
and the bars before it only; a reading at a moment t uses the last TF bar complete by t (`at`).

Public interface (read-only for the other roles; changed only through the measurer):
- `load_learning()`, `load_live()`: M1 bars (UTC open-time index; open, high, low, close).
- `swing_size(m)`: S in USD at every M1 bar (known at its close) - rule 1; `h1_atr(m)` the H1 ATR behind it.
- `zigzag(h, lo, thr)`: (pivot bar, price, kind +1 peak / -1 trough, confirming bar) - rule 2, the shape of
  `dev/patterns.py::zigzag`.
- `m1_pivots(m, share=1.0)`: the M1 pivots with threshold share x S (1.0 the trade-size swings, 0.3 the inner).
- `known_at(piv, d)`: the pivots confirmed by bar d, and `running(piv, h, lo, d)`: the running leg's extreme.
- `analyze(m, tf)`: one TF's pivots, structure, box, lines, Fibonacci and events (a `TF` object); `TF.at(t_ns)`.
- `analyze_all(m)`: M1, M5, M15, M30, H1, H4, D1; `readings_at(R, t_ns)`: the D1 bias and the M15 / M30 / H1 trend
  (label and bias of each), each as known at each moment (rules 15-16).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PRE = HERE.parent / "precursors"
ROOT = HERE.parents[3]
sys.path.insert(0, str(PRE))
import foundation as F  # noqa: E402

# ---- the rules' constants (DEV_LOG.md, V3-1)
S_FLOOR = 10.0  # rule 1: the owner's trade size, USD
S_ATR = 0.6  # rule 1: x the H1 ATR14
TF_ATR = 1.0  # rule 3: x the TF's own ATR14
INNER = 0.3  # rule 12: the inner swings, x S
BOX_MIN = 4  # rule 5: pivots in a box
BOX_MAX = 3.0  # rule 5: the band, x S
ACCEPT = 2  # rules 5-6: consecutive closes beyond = an accepted break
RT = 0.25  # rule 7: the retest distance, x S
LINE_BACK = 5  # rule 6: earlier pivots tried for a line's first anchor
TOUCH = 0.2  # rule 6: a third touch, x S
TOP_Q = 0.25  # rule 12: the top / bottom quarter of a box
FIB = (0.236, 0.382, 0.5, 0.618)  # rule 8
BOX_COLS = ["id", "born", "first", "n", "members", "top", "bot", "end", "why"]
LINE_COLS = ["id", "kind", "born", "a", "b", "ta", "pa", "slope", "touches"]
NS_MIN = 60_000_000_000
RULES = {"M1": None, "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h", "D1": "1D"}
LEARN_FROM = pd.Timestamp("2025-08-01", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
LIVE_FROM = pd.Timestamp("2026-10-18", tz="UTC")
HIST = ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
LIVE = HIST  # the repo store (the measurer, 2026-10-20); the reader keeps open_time >= LIVE_FROM only
COLS = ["open", "high", "low", "close"]


# ------------------------------------------------------------------ data
def _clean(d: pd.DataFrame) -> pd.DataFrame:
    """The open time (a column, or the index pandas restored from the file's metadata) as a UTC index."""
    t = d.pop("open_time") if "open_time" in d.columns else d.index
    d.index = pd.DatetimeIndex(pd.to_datetime(t, utc=True))
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d[COLS].astype(float)


def load_learning() -> pd.DataFrame:
    """M1 from 2025-08-01 to 2026-04-18 (exclusive). The filter is applied by the reader: no exam row reaches the
    code."""
    import pyarrow.dataset as ds  # noqa: PLC0415

    f = (ds.field("open_time") >= LEARN_FROM.to_pydatetime()) & (ds.field("open_time") < EXAM_START.to_pydatetime())
    d = ds.dataset(str(HIST)).to_table(filter=f, columns=["open_time", *COLS]).to_pandas()
    out = _clean(d)
    assert out.index.max() < EXAM_START
    return out


def load_live(path: Path = LIVE) -> pd.DataFrame:
    """The shape days' bars (the repo store), from 2026-10-18 00:00 UTC only: the earlier rows are the exam's and are
    filtered by the reader."""
    import pyarrow.dataset as ds  # noqa: PLC0415

    d = ds.dataset(str(path)).to_table(filter=ds.field("open_time") >= LIVE_FROM.to_pydatetime(),
                                       columns=["open_time", *COLS]).to_pandas()
    out = _clean(d)
    assert out.index.min() >= LIVE_FROM
    return out


# ------------------------------------------------------------------ bars, ATR, the swing size
def tf_bars(m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """The TF's bars from M1 as `precursors/indicators.bars` builds them (clock bars; H4 / D1 on the server day), plus
    `t` = the bar's open time (the clock key; for H4 the first M1 inside). M1 itself: the bars, avail = open + 1 min."""
    if tf == "M1":
        b = m[COLS].copy()
        b["t"] = m.index
        b["last"] = m.index
        b["avail"] = m.index + pd.Timedelta(minutes=1)
        return b.reset_index(drop=True)
    rule = RULES[tf]
    if rule in ("4h", "1D"):
        key = m.index.tz_convert("Europe/Athens").tz_localize(None).floor(rule)
    else:
        key = m.index.floor(rule)
    g = m.assign(_k=key, _t=m.index).groupby("_k", sort=True)
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "first": g._t.min(), "last": g._t.max()})
    b["avail"] = b["last"] + pd.Timedelta(minutes=1)
    b["t"] = b["first"] if rule in ("4h", "1D") else b.index
    b = b.reset_index(drop=True)
    return b[["open", "high", "low", "close", "t", "last", "avail"]]


def atr_warm(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int = 14) -> np.ndarray:
    """MetaTrader's ATR(n) (`foundation.atr`); before it is defined, the mean true range of the bars so far, the first
    bar's true range = its high - low (rule 1's warm-up)."""
    a = F.atr(h, lo, c, n)
    tr = F.true_range(h, lo, c)
    if len(tr):
        tr[0] = h[0] - lo[0]
    warm = np.cumsum(tr) / np.arange(1, len(tr) + 1)
    return np.where(np.isfinite(a), a, warm)


def _ns(x) -> np.ndarray:
    return pd.DatetimeIndex(x).as_unit("ns").asi8


def size_at(m_h1: pd.DataFrame, t_ns: np.ndarray) -> np.ndarray:
    """S at moments t: max(10, 0.6 x ATR14 of the last H1 bar complete by t); 10 before any complete H1 bar."""
    a = atr_warm(*(m_h1[k].to_numpy(float) for k in ("high", "low", "close")))
    k = np.searchsorted(_ns(m_h1["avail"]), t_ns, side="right") - 1
    out = np.full(len(t_ns), S_FLOOR)
    ok = k >= 0
    out[ok] = np.maximum(S_FLOOR, S_ATR * a[k[ok]])
    return out


def h1_atr(m: pd.DataFrame) -> np.ndarray:
    """The H1 ATR behind S at every M1 bar's close (NaN before the first complete H1 bar)."""
    h1 = tf_bars(m, "H1")
    a = atr_warm(*(h1[k].to_numpy(float) for k in ("high", "low", "close")))
    k = np.searchsorted(_ns(h1["avail"]), _ns(m.index + pd.Timedelta(minutes=1)), side="right") - 1
    out = np.full(len(m), np.nan)
    out[k >= 0] = a[k[k >= 0]]
    return out


def swing_size(m: pd.DataFrame) -> np.ndarray:
    """Rule 1: S in USD at every M1 bar, known at that bar's close."""
    return size_at(tf_bars(m, "H1"), _ns(m.index + pd.Timedelta(minutes=1)))


# ------------------------------------------------------------------ the swing detector
def zigzag(h: np.ndarray, lo: np.ndarray, thr: np.ndarray, state: bool = False):
    """Rule 2: the causal ZigZag. Returns (pivot bar, price, kind +1 / -1, confirming bar); with state=True also the
    per-bar state after each bar: (direction 0 / +1 tracking a peak / -1 tracking a trough, the tracked extreme's bar)."""
    n = len(h)
    piv: list[tuple[int, float, int, int]] = []
    dirs = np.zeros(n, np.int8)
    exts = np.full(n, -1, np.int64)
    hi_i = lo_i = ext = 0
    direction = 0
    for i in range(n):
        if direction == 0:
            if h[i] > h[hi_i]:
                hi_i = i
            if lo[i] < lo[lo_i]:
                lo_i = i
            if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr[i]:
                if lo_i < hi_i:
                    piv.append((lo_i, float(lo[lo_i]), -1, i))
                    direction, ext = 1, hi_i
                else:
                    piv.append((hi_i, float(h[hi_i]), 1, i))
                    direction, ext = -1, lo_i
        elif direction == 1:
            if h[i] > h[ext]:
                ext = i
            elif h[ext] - lo[i] >= thr[i]:
                piv.append((ext, float(h[ext]), 1, i))
                direction, ext = -1, i
        else:
            if lo[i] < lo[ext]:
                ext = i
            elif h[i] - lo[ext] >= thr[i]:
                piv.append((ext, float(lo[ext]), -1, i))
                direction, ext = 1, i
        dirs[i] = direction
        exts[i] = ext if direction else -1
    p = np.array(piv, dtype=float).reshape(-1, 4)
    out = (p[:, 0].astype(np.int64), p[:, 1], p[:, 2].astype(np.int64), p[:, 3].astype(np.int64))
    return (out, dirs, exts) if state else out


def m1_pivots(m: pd.DataFrame, share: float = 1.0):
    """The M1 pivots with threshold share x S (rule 3 on M1: max(S, ATR14 of M1); share applies to both)."""
    b = tf_bars(m, "M1")
    return zigzag(*_hl(b), share * tf_threshold(m, b, "M1"))


def known_at(piv, d: int):
    """The pivots confirmed by bar d (confirming bar <= d)."""
    n = int(np.searchsorted(piv[3], d, side="right"))
    return tuple(a[:n] for a in piv)


def running(piv, h: np.ndarray, lo: np.ndarray, d: int):
    """The running leg's extreme at bar d: after a confirmed peak the lowest low since it, after a trough the highest
    high (the first bar keeps a tie). Returns (bar, price, kind) or None before the first pivot."""
    pb, _, pk, _ = known_at(piv, d)
    if not len(pb):
        return None
    s = slice(int(pb[-1]) + 1, d + 1)
    if pk[-1] == 1:
        j = s.start + int(np.argmin(lo[s]))
        return j, float(lo[j]), -1
    j = s.start + int(np.argmax(h[s]))
    return j, float(h[j]), 1


def _hl(b: pd.DataFrame):
    return b["high"].to_numpy(float), b["low"].to_numpy(float)


def s_default(m: pd.DataFrame):
    """S at moments t (ns) from m's H1 bars (rule 1)."""
    h1 = tf_bars(m, "H1")
    return lambda t_ns: size_at(h1, t_ns)


def tf_threshold(m: pd.DataFrame, b: pd.DataFrame, tf: str, s_fn=None) -> np.ndarray:
    """Rule 3: at TF bar j, max(S at the bar's close, 1.0 x the TF's ATR14 at j). s_fn: S at moments (tests inject a
    constant; default rule 1)."""
    s = (s_fn or s_default(m))(_ns(b["avail"]))
    a = atr_warm(*(b[k].to_numpy(float) for k in ("high", "low", "close")))
    return np.maximum(s, TF_ATR * a)


# ------------------------------------------------------------------ breaks and retests of one level
class Edge:
    """Rules 5-7 / 11 for one level: side -1 = a bottom / support broken downward, +1 = a top / resistance broken
    upward. Mirrored internally so that the code reads as the down case."""

    def __init__(self, side: int, tag: str, obj: int):
        self.side, self.tag, self.obj = side, tag, obj
        self.n = 0
        self.accepted = False
        self.state = ""
        self.away_bar = -1
        self.ext = np.nan
        self.rc = 0
        self.done = False

    def step(self, j: int, c: float, h: float, lo: float, level: float, rt: float, ev: list) -> str:
        s = self.side
        # the down view: X = price for s = -1, X = -price for s = +1 (then "high" is the mirrored low)
        cx, hx, lx, lv = (c, h, lo, level) if s < 0 else (-c, -lo, -h, -level)
        if not self.accepted:
            if cx < lv:
                self.n += 1
                if self.n == 1:
                    ev.append((j, self.tag, "break", s, level, c, self.obj))
                if self.n == ACCEPT:
                    self.accepted = True
                    self.state = "wait_away"
                    ev.append((j, self.tag, "accepted", s, level, c, self.obj))
                    if lx <= lv - rt:
                        self.state, self.away_bar = "away", j
                    return "accepted"
            else:
                if self.n == 1:
                    ev.append((j, self.tag, "sweep", s, level, c, self.obj))
                self.n = 0
            return ""
        if self.done:
            return ""
        if self.state == "wait_away":
            if lx <= lv - rt:
                self.state, self.away_bar = "away", j
        elif self.state == "away" and j > self.away_bar and hx >= lv - rt:
            self.state, self.ext = "retest", hx
            ev.append((j, self.tag, "retest", s, level, h if s < 0 else lo, self.obj))
        if self.state == "retest":
            self.ext = max(self.ext, hx)
            if cx < lv - rt:
                ev.append((j, self.tag, "retest_fail", s, level, self.ext if s < 0 else -self.ext, self.obj))
                self.state, self.away_bar = "away", j
        self.rc = self.rc + 1 if cx > lv else 0
        if self.rc == ACCEPT:
            self.done = True
            ev.append((j, self.tag, "reclaim", s, level, c, self.obj))
        return ""


# ------------------------------------------------------------------ one TF: pivots, structure, box, lines, Fibonacci
@dataclass
class TF:
    tf: str
    bars: pd.DataFrame
    thr: np.ndarray
    s: np.ndarray  # S at each TF bar's close
    piv: tuple
    struct: pd.DataFrame  # per TF bar
    boxes: pd.DataFrame  # one row per box
    lines: pd.DataFrame  # one row per line
    events: pd.DataFrame
    inner: tuple = field(default_factory=tuple)

    def at(self, t_ns: np.ndarray) -> np.ndarray:
        """The last TF bar complete by each moment (-1 when none)."""
        return np.searchsorted(_ns(self.bars["avail"]), np.asarray(t_ns, np.int64), side="right") - 1


def _cmp(new: float, old: float) -> float:
    if not (np.isfinite(new) and np.isfinite(old)):
        return np.nan
    return 1.0 if new > old else -1.0 if new < old else 0.0


def _box_ok(prices: list[float], kinds: list[int], cap: float) -> bool:
    top, bot = max(prices), min(prices)
    if top - bot > cap:
        return False
    mid = (top + bot) / 2.0
    return all((p >= mid) if k == 1 else (p <= mid) for p, k in zip(prices, kinds))


def _structure(h: np.ndarray, lo: np.ndarray, c: np.ndarray, piv, dirs: np.ndarray, exts: np.ndarray) -> pd.DataFrame:
    """Rules 4 + 13 (D5-D8) at every bar of the path h / lo / c, from its pivots and the ZigZag state."""
    pb, pp, pk, pc = piv
    n = len(h)
    st = {k: np.full(n, np.nan) for k in ("highs", "lows", "label", "bias", "bias_bar", "hi_old", "hi_new", "lo_old", "lo_new")}
    peaks: list[int] = []
    troughs: list[int] = []
    q = 0
    pk_broken = tr_broken = True
    bias = np.nan
    bias_bar = np.nan
    for j in range(n):
        while q < len(pb) and pc[q] <= j:
            if pk[q] == 1:
                peaks.append(q)
                pk_broken = False
            else:
                troughs.append(q)
                tr_broken = False
            q += 1
        e = exts[j]
        hi_pair = (pp[peaks[-2]] if len(peaks) > 1 else np.nan, pp[peaks[-1]] if peaks else np.nan)
        lo_pair = (pp[troughs[-2]] if len(troughs) > 1 else np.nan, pp[troughs[-1]] if troughs else np.nan)
        if dirs[j] == 1 and peaks and h[e] > pp[peaks[-1]]:
            hi_pair = (pp[peaks[-1]], h[e])
        if dirs[j] == -1 and troughs and lo[e] < pp[troughs[-1]]:
            lo_pair = (pp[troughs[-1]], lo[e])
        hs, ls = _cmp(hi_pair[1], hi_pair[0]), _cmp(lo_pair[1], lo_pair[0])
        st["highs"][j], st["lows"][j] = hs, ls
        st["hi_old"][j], st["hi_new"][j], st["lo_old"][j], st["lo_new"][j] = (*hi_pair, *lo_pair)
        if np.isfinite(hs) and np.isfinite(ls):
            st["label"][j] = 1.0 if hs == 1 and ls == 1 else -1.0 if hs == -1 and ls == -1 else 0.0
        if peaks and not pk_broken and c[j] > pp[peaks[-1]]:
            pk_broken, bias, bias_bar = True, 1.0, j
        if troughs and not tr_broken and c[j] < pp[troughs[-1]]:
            tr_broken, bias, bias_bar = True, -1.0, j
        st["bias"][j], st["bias_bar"][j] = bias, bias_bar
    return pd.DataFrame(st)


def analyze(m: pd.DataFrame, tf: str, inner: bool = False, s_fn=None) -> TF:
    """Rules 3-8 and 11-13 on one TF. s_fn: S at moments (default rule 1; tests inject a constant)."""
    s_fn = s_fn or s_default(m)
    b = tf_bars(m, tf)
    h, lo = _hl(b)
    c = b["close"].to_numpy(float)
    t_min = _ns(b["t"]) // NS_MIN  # minutes, for the lines
    thr = tf_threshold(m, b, tf, s_fn)
    s_bar = s_fn(_ns(b["avail"]))
    piv, dirs, exts = zigzag(h, lo, thr, state=True)
    pb, pp, pk, pc = piv
    n = len(b)
    # ---- rule 4 + 13: the structure and the last break
    struct = _structure(h, lo, c, piv, dirs, exts)
    struct.insert(0, "avail", b["avail"].to_numpy())

    # ---- rules 5-7, 11: the box, the lines, their breaks and retests
    ev: list[tuple] = []
    box_rows: list[dict] = []
    line_rows: list[dict] = []
    per = {k: np.full(n, np.nan) for k in ("box", "box_live", "box_top", "box_bot", "sup", "sup_val", "res", "res_val")}
    live = None  # the live box: dict(members=[pivot index], ...)
    ref = None  # the reference box (live or frozen)
    edges: list[Edge] = []
    last_accept = -1
    sup = res = None
    sup_edge = res_edge = None
    q = 0
    for j in range(n):
        new = []
        while q < len(pb) and pc[q] <= j:
            new.append(q)
            q += 1
        cap = BOX_MAX * s_bar[j]
        for p in new:
            # the box
            if live is not None:
                pr = [pp[x] for x in live["members"]] + [pp[p]]
                kd = [pk[x] for x in live["members"]] + [pk[p]]
                if _box_ok(pr, kd, cap):
                    live["members"].append(p)
                    live["top"], live["bot"] = max(pr), min(pr)
                else:
                    live["end"], live["why"] = j, "outgrown"
                    live = None
            if live is None:
                run: list[int] = []
                for x in range(p, -1, -1):
                    if pb[x] <= last_accept:
                        break
                    cand = [x, *run]
                    if not _box_ok([pp[y] for y in cand], [pk[y] for y in cand], cap):
                        break
                    run = cand
                if len(run) >= BOX_MIN:
                    pr = [pp[y] for y in run]
                    live = dict(id=len(box_rows), born=j, members=run, top=max(pr), bot=min(pr), end=-1, why="")
                    box_rows.append(live)
                    ref = live
                    edges = [Edge(1, "box_top", live["id"]), Edge(-1, "box_bot", live["id"])]
            # the lines (rule 6)
            kind = pk[p]
            prev = list(range(p - 2, max(p - 2 * LINE_BACK, 0) - 1, -2))  # pivots alternate: same kind every 2nd
            if prev:
                slopes = [(pp[p] - pp[x]) / max(t_min[pb[p]] - t_min[pb[x]], 1) for x in prev]
                k = int(np.argmax(slopes)) if kind == -1 else int(np.argmin(slopes))
                a, sl = prev[k], slopes[k]
                ta = t_min[pb[a]]
                between = slice(pb[a] + 1, pb[p])
                vals = pp[a] + sl * (t_min[between] - ta)
                ok = (sl > 0 and not np.any(c[between] < vals)) if kind == -1 else (sl < 0 and not np.any(c[between] > vals))
                if ok:
                    tol = TOUCH * s_bar[j]
                    mid = [x for x in range(a + 1, p) if pk[x] == kind]
                    touches = 2 + sum(abs(pp[x] - (pp[a] + sl * (t_min[pb[x]] - ta))) <= tol for x in mid)
                    row = dict(id=len(line_rows), kind=kind, born=j, a=a, b=p, ta=int(ta), pa=float(pp[a]),
                               slope=float(sl), touches=int(touches))
                    line_rows.append(row)
                    if kind == -1:
                        sup, sup_edge = row, Edge(-1, "sup", row["id"])
                    else:
                        res, res_edge = row, Edge(1, "res", row["id"])
        rt = RT * s_bar[j]
        if ref is not None:
            for e in edges:
                lvl = ref["top"] if e.side == 1 else ref["bot"]
                if e.step(j, c[j], h[j], lo[j], lvl, rt, ev) == "accepted" and live is ref:
                    live["end"], live["why"] = j, "broken"
                    live = None
                    last_accept = j
            per["box"][j], per["box_live"][j] = ref["id"], float(live is ref)
            per["box_top"][j], per["box_bot"][j] = ref["top"], ref["bot"]
        for row, e, key in ((sup, sup_edge, "sup"), (res, res_edge, "res")):
            if row is None:
                continue
            v = row["pa"] + row["slope"] * (t_min[j] - row["ta"])
            per[key][j], per[f"{key}_val"][j] = row["id"], v
            if j > row["born"]:
                e.step(j, c[j], h[j], lo[j], v, rt, ev)
    for k, v in per.items():
        struct[k] = v
    boxes = pd.DataFrame([dict(id=r["id"], born=r["born"], first=int(pb[r["members"][0]]), n=len(r["members"]),
                               members=list(r["members"]), top=r["top"], bot=r["bot"], end=r["end"], why=r["why"])
                          for r in box_rows], columns=BOX_COLS)
    lines = pd.DataFrame(line_rows, columns=LINE_COLS)  # the columns kept when empty
    events = pd.DataFrame(ev, columns=["bar", "tag", "kind", "side", "level", "price", "obj"])
    if len(events):
        events["avail"] = b["avail"].to_numpy()[events["bar"].to_numpy()]
    inn: tuple = ()
    if inner:
        inn = zigzag(h, lo, INNER * s_bar)
    return TF(tf, b, thr, s_bar, piv, struct, boxes, lines, events, inn)


# ------------------------------------------------------------------ rule 8: the Fibonacci of the last big swing
def fib_at(r: TF, j: int):
    """The last completed leg of r's swings known at TF bar j (from the second-last to the last confirmed pivot) and its
    levels end - f x (end - start). None before two pivots."""
    pb, pp, pk, _ = known_at(r.piv, j)
    if len(pb) < 2:
        return None
    start, end = float(pp[-2]), float(pp[-1])
    return dict(start=start, end=end, start_bar=int(pb[-2]), end_bar=int(pb[-1]), kind=int(pk[-1]),
                levels={f: end - f * (end - start) for f in FIB})


# ------------------------------------------------------------------ rule 12: the tests of a box edge
def edge_tests(r: TF, box: pd.Series, upto: int, side: int) -> list[tuple[int, float]]:
    """The inner-swing peaks (side +1) / troughs (-1) confirmed by bar `upto`, from the box's first member's bar to
    `upto`, inside the box's top / bottom quarter (the box as given)."""
    pb, pp, pk, _ = known_at(r.inner, upto)
    hgt = box["top"] - box["bot"]
    out = []
    for b_, p_, k_ in zip(pb, pp, pk):
        if k_ != side or b_ < box["first"] or b_ > upto:
            continue
        if (side == 1 and p_ >= box["top"] - TOP_Q * hgt) or (side == -1 and p_ <= box["bot"] + TOP_Q * hgt):
            out.append((int(b_), float(p_)))
    return out


SIDE_TFS = ("D1", "H4", "H1")
TREND_TFS = ("M15", "M30", "H1")


def side_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Rule 17 on per-TF columns `<TF>_label` / `<TF>_bias`: side, side_bias, trend, trend_bias (+1 / -1 / 0, NaN when
    an input is unknown)."""
    out = {}
    for what, sfx in (("label", ""), ("bias", "_bias")):
        d1, h4, h1 = (df[f"{tf}_{what}"].to_numpy(float) for tf in SIDE_TFS)
        known = np.isfinite(d1) & np.isfinite(h4) & np.isfinite(h1)
        buy = (d1 == 1) & (h4 == 1) & (h1 != -1)
        sell = (d1 == -1) & (h4 == -1) & (h1 != 1)
        out[f"side{sfx}"] = np.where(known, np.where(buy, 1.0, np.where(sell, -1.0, 0.0)), np.nan)
        a, b, c = (df[f"{tf}_{what}"].to_numpy(float) for tf in TREND_TFS)
        known = np.isfinite(a) & np.isfinite(b) & np.isfinite(c)
        up = (a == 1) & (b == 1) & (c == 1)
        dn = (a == -1) & (b == -1) & (c == -1)
        out[f"trend{sfx}"] = np.where(known, np.where(up, 1.0, np.where(dn, -1.0, 0.0)), np.nan)
    return pd.DataFrame(out, index=df.index)


def readings_at(R: dict[str, TF], t_ns, tfs=("D1", "H4", "H1", "M30", "M15"), mode: str = "bar") -> pd.DataFrame:
    """Rules 16-17: one row per moment; for each TF its label and bias from its last bar complete by the moment (NaN
    when none), and - when D1, H4, H1, M30 and M15 are all given - the side and the trend columns (rule 17), each as
    known then. mode "path" reads rule 18's reading (`R["<TF>@M1"]`, the TF's swing size on the M1 path; M1 itself is
    the same in both modes), "bar" the TF's own bars."""
    t_ns = np.asarray(t_ns, np.int64)
    out = {}
    for tf in tfs:
        r = R[f"{tf}@M1"] if mode == "path" and tf != "M1" else R[tf]
        j = r.at(t_ns)
        for what in ("label", "bias"):
            v = r.struct[what].to_numpy(float)
            out[f"{tf}_{what}"] = np.where(j >= 0, v[np.maximum(j, 0)], np.nan)
    df = pd.DataFrame(out, index=pd.DatetimeIndex(t_ns, tz="UTC"))
    if all(tf in tfs for tf in (*SIDE_TFS, *TREND_TFS)):
        df = pd.concat([df, side_trend(df)], axis=1)
    return df


def analyze_all(m: pd.DataFrame, tfs=("M1", "M5", "M15", "M30", "H1", "H4", "D1"), s_fn=None,
                path: bool = False) -> dict[str, TF]:
    """Every TF on its own bars; with path=True also rule 18's reading of each TF above M1 as `R["<TF>@M1"]`."""
    s_fn = s_fn or s_default(m)
    R = {tf: analyze(m, tf, inner=tf in ("M1", "M5"), s_fn=s_fn) for tf in tfs}
    if path:
        for tf in tfs:
            if tf != "M1":
                R[f"{tf}@M1"] = analyze_path(m, tf, s_fn=s_fn)
    return R


# ------------------------------------------------------------------ rule 18: a TF's structure read on the M1 path
def path_threshold(m: pd.DataFrame, tf: str, s_fn=None) -> np.ndarray:
    """At every M1 bar d: max(S at d's close, 1.0 x the TF's ATR14 at its last bar complete by d's close); before the
    TF's first complete bar, S alone."""
    b1 = tf_bars(m, "M1")
    t = _ns(b1["avail"])
    s = (s_fn or s_default(m))(t)
    b = tf_bars(m, tf)
    a = atr_warm(*(b[k].to_numpy(float) for k in ("high", "low", "close")))
    j = np.searchsorted(_ns(b["avail"]), t, side="right") - 1
    return np.maximum(s, np.where(j >= 0, TF_ATR * a[np.maximum(j, 0)], 0.0))


def analyze_path(m: pd.DataFrame, tf: str, s_fn=None) -> TF:
    """Rule 18: the TF's swing size on the M1 path - the ZigZag on the M1 highs / lows with `path_threshold`, and the
    structure (D5-D8, the bias on the M1 closes) at every M1 close. Bars = the M1 bars; no box / lines / events."""
    b1 = tf_bars(m, "M1")
    h, lo = _hl(b1)
    c = b1["close"].to_numpy(float)
    thr = path_threshold(m, tf, s_fn)
    piv, dirs, exts = zigzag(h, lo, thr, state=True)
    struct = _structure(h, lo, c, piv, dirs, exts)
    struct.insert(0, "avail", b1["avail"].to_numpy())
    s1 = (s_fn or s_default(m))(_ns(b1["avail"]))
    e = pd.DataFrame()
    return TF(f"{tf}@M1", b1, thr, s1, piv, struct, e, e, e)


# ------------------------------------------------------------------ rule 19: the tests of a box edge on the M1 bars
def edge_visits(h: np.ndarray, lo: np.ndarray, s: np.ndarray, top: float, bot: float, side: int = 1) -> list[int]:
    """Rule 19 on the M1 bars given (from the box's first member on): a bar whose high reaches the top quarter
    (>= top - 0.25 x height) is a test when it is the first such bar or price has left the quarter by at least S since
    the previous test (a low <= top - 0.25 x height - S at that bar). Returns the bars of the tests. side -1: the
    bottom, mirrored."""
    hgt = top - bot
    if side == 1:
        q = top - TOP_Q * hgt
        reach, left = h >= q, lo <= q - s
    else:
        q = bot + TOP_Q * hgt
        reach, left = lo <= q, h >= q + s
    out: list[int] = []
    armed = True
    for i in range(len(h)):
        if not armed and left[i]:
            armed = True
        if armed and reach[i]:
            out.append(i)
            armed = False
    return out
