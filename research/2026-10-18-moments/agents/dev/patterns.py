"""Task P: the chart pattern at the level (DEV_PROMPT.md section 5; owner 2026-10-19 11:15 Thai: "at least M1 must show a
chart pattern, and so must every TF used to enter"; "at least it must show an inverted H&S - something like this
around the price level"). The rules are in DEV_LOG.md "Task P - written before computing"; in short:

- swings: a causal ATR ZigZag per TF (ZZ_K x ATR(14)); at a decision bar d the structure is the pivots confirmed by d
  plus the running extreme since the last one;
- the patterns from the last swings (buy side; sells are the mirror): inverse head and shoulders, W (and W whose second
  low swept the first), the sweep then the higher low (at a level), a base then its break; each breaks out at the
  first close beyond its trigger;
- where they count: at the owner's H1 levels (precursors/zones.levels_at), the extreme in the level's zone or past it
  by a sweep; after a news first-minute leg (sweep_detector.first_minute), at the release bar's extreme;
- the TFs: M1 and M5 (M5 agreement for an M1 entry; an M1 pattern for an M5 entry).

Closed bars only; nothing from 2026-04-18 on is read (`load_m1` filters the parquet).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/patterns.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENTS = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(AGENTS / "precursors"))
sys.path.insert(0, str(AGENTS / "journal"))
sys.path.insert(0, str(AGENTS.parent))
ROOT = HERE.parents[3]
M1_FILE = ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet"

from sweep_detector import EXAM_START, LEARN_START, ExamPeriodError  # noqa: E402

WARM_START = pd.Timestamp("2025-09-01", tz="UTC")
NS_MIN = 60 * 10**9
ZZ_K = 2.0  # a swing = ZZ_K x the TF's ATR(14)
HEAD_ATR = 0.5  # the head below both shoulders by at least this x ATR
SHOULDER_H = 0.5  # the shoulders within this x the height of each other
NECK_H = 0.5  # the neckline's two points within this x the height of each other
EQ_ATR, EQ_H = 0.5, 0.15  # "equal lows": within max(EQ_ATR x ATR, EQ_H x height)
SWEEP_W_H = 0.35  # a W's second low may sweep the first by up to this x the height
SPAN = {"ihs": 60, "w": 40, "st": 40}  # bars from the pattern's first point to the breakout
BASE_MIN, BASE_MAX, BASE_W = 8, 40, 1.5  # a base: 8 .. 40 bars within 1.5 x ATR
STOP_ATR = 0.2  # the stop beyond the extreme
ZONE_H1 = 0.1  # the level's zone: +- this x H1 ATR (zones.TOUCH_ATR)
SWEEP_H1 = 0.5  # a sweep past the zone: at most this x H1 ATR
HEIGHT_ATR = 4.0  # a pattern's height (extreme to trigger) at most this x its TF's ATR = two swing sizes (amendment)
SELL_NAMES = {"W": "M", "W, the 2nd low swept the 1st": "M, the 2nd high swept the 1st", "inverse H&S": "H&S",
              "sweep, higher low": "sweep, lower high"}
SELL_LABELS = {"L1": "H1", "L2": "H2", "P": "T", "HL": "LH"}  # a sell's points: the tops H1 / H2, the trough T, LH
AGREE_MIN = 30  # the other TF's pattern within the last 30 minutes
NEWS_MIN = 15  # a news leg's level lives from the release + 1 min to + 15 min
NAMES = {("ihs", 1): "inverse H&S", ("ihs", -1): "H&S", ("w", 1): "W", ("w", -1): "M",
         ("st", 1): "sweep, higher low", ("st", -1): "sweep, lower high", ("base", 1): "base, break up",
         ("base", -1): "base, break down"}


def load_m1(start: pd.Timestamp = WARM_START, end: pd.Timestamp = EXAM_START) -> pd.DataFrame:
    """The M1 bars in [start, end) straight from the parquet with a row filter (the exam rows are never read), UTC
    index = the bar's open, duplicates keep the last (as plib.load)."""
    import pyarrow.parquet as pq  # noqa: PLC0415

    if end > EXAM_START:
        raise ExamPeriodError("M1 may not be read into the exam period")
    cols = ["open_time", "open", "high", "low", "close", "tick_volume", "spread"]
    t = pq.read_table(M1_FILE, columns=cols, filters=[("open_time", ">=", start), ("open_time", "<", end)])
    m = t.to_pandas().drop_duplicates("open_time", keep="last").set_index("open_time").sort_index()
    m.index = pd.DatetimeIndex(m.index).tz_convert("UTC")
    m.index.name = None
    if len(m) and m.index.max() >= EXAM_START:
        raise ExamPeriodError("an exam row was read")
    return m.astype(float)


def tf_bars(m: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Bars of `minutes` from M1 on the clock: open / high / low / close, indexed by the bar's open; avail = open +
    minutes (known only when the whole period is over, even if its last minutes have no M1 bar)."""
    if minutes == 1:
        b = m[["open", "high", "low", "close"]].copy()
    else:
        g = m.groupby(m.index.floor(f"{minutes}min"), sort=True)
        b = pd.DataFrame(dict(open=g.open.first(), high=g.high.max(), low=g.low.min(), close=g.close.last()))
    b["avail"] = b.index + pd.Timedelta(minutes=minutes)
    return b


def atr14(b: pd.DataFrame) -> np.ndarray:
    import foundation as F  # noqa: PLC0415

    return F.atr(b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float), 14)


def zigzag(h: np.ndarray, lo: np.ndarray, atr: np.ndarray, k: float = ZZ_K) -> tuple[np.ndarray, ...]:
    """The causal ATR ZigZag: arrays (pivot bar, price, kind +1 peak / -1 trough, the bar that confirmed it). Each bar
    i reads bars <= i only. Before the first pivot: the highest high and lowest low since the first ATR; when they are
    the threshold apart, the earlier one is the first pivot. Then, tracking a peak: a bar with a high >= the peak's
    extends it; else a low the threshold below the peak confirms the peak at that bar and the trough is tracked from
    it. Troughs mirrored."""
    piv: list[tuple[int, float, int, int]] = []
    n = len(h)
    fin = np.isfinite(atr)
    if not fin.any():
        return (np.empty(0, int), np.empty(0), np.empty(0, int), np.empty(0, int))
    i0 = int(np.argmax(fin))
    hi_i = lo_i = ext = i0
    direction = 0
    for i in range(i0, n):
        thr = k * atr[i]
        if not np.isfinite(thr):
            continue
        if direction == 0:
            if h[i] > h[hi_i]:
                hi_i = i
            if lo[i] < lo[lo_i]:
                lo_i = i
            if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr:  # one bar holding both extremes is never two turns (auditor)
                if lo_i < hi_i:
                    piv.append((lo_i, float(lo[lo_i]), -1, i))
                    direction, ext = 1, hi_i
                else:
                    piv.append((hi_i, float(h[hi_i]), 1, i))
                    direction, ext = -1, lo_i
        elif direction == 1:
            if h[i] >= h[ext]:
                ext = i
            elif h[ext] - lo[i] >= thr:
                piv.append((ext, float(h[ext]), 1, i))
                direction, ext = -1, i
        else:
            if lo[i] <= lo[ext]:
                ext = i
            elif h[i] - lo[ext] >= thr:
                piv.append((ext, float(lo[ext]), -1, i))
                direction, ext = 1, i
    p = np.array(piv, dtype=float).reshape(-1, 4)
    return p[:, 0].astype(int), p[:, 1], p[:, 2].astype(int), p[:, 3].astype(int)


def structure(piv: tuple[np.ndarray, ...], h: np.ndarray, lo: np.ndarray, d: int, keep: int = 6) -> list[tuple]:
    """The swings known at the close of bar d: the last `keep` pivots confirmed by d, then the running extreme since
    the last of them (the lowest low after a peak, the highest high after a trough; the earliest bar on a tie) as a
    provisional pivot. Items: (bar, price, kind, provisional)."""
    pb, pp, pk, pc = piv
    n = int(np.searchsorted(pc, d, side="right"))
    out = [(int(pb[j]), float(pp[j]), int(pk[j]), False) for j in range(max(n - keep, 0), n)]
    if n:
        last_b, last_k = int(pb[n - 1]), int(pk[n - 1])
        if last_b < d:
            seg = slice(last_b + 1, d + 1)
            if last_k == 1:
                j = last_b + 1 + int(np.argmin(lo[seg]))
                out.append((j, float(lo[j]), -1, True))
            else:
                j = last_b + 1 + int(np.argmax(h[seg]))
                out.append((j, float(h[j]), 1, True))
    return out


def first_close_above(c: np.ndarray, line: np.ndarray, a: int, d: int) -> bool:
    """line = the trigger's values at bars a .. d (length d - a + 1): close[d] above line's last value and every close
    of bars a .. d - 1 at or below its value."""
    return bool(c[d] > line[-1] and np.all(c[a:d] <= line[:-1]))


def find_buy(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: float, seq: list[tuple], d: int) -> list[dict]:
    """The buy-side swing patterns breaking out at bar d (inverse H&S, W, and the higher-low turn - a sweep candidate
    whose level is checked later). seq = structure(...) at d. Points: (bar, price, label)."""
    if len(seq) < 3 or not np.isfinite(atr):
        return []
    k3 = len(seq) - 1 if seq[-1][2] == -1 else len(seq) - 2
    if k3 < 2 or seq[k3][2] != -1:
        return []
    t3, p2, t2 = seq[k3], seq[k3 - 1], seq[k3 - 2]
    out = []
    if first_close_above(c, np.full(d - t3[0] + 1, p2[1]), t3[0], d):
        hgt = p2[1] - min(t2[1], t3[1])
        eq = max(EQ_ATR * atr, EQ_H * hgt)
        base = dict(trigger=p2[1], height=hgt, start=t2[0])
        if d - t2[0] <= SPAN["w"]:
            if abs(t3[1] - t2[1]) <= eq:
                out.append(dict(family="w", variant="W", extreme=min(t2[1], t3[1]), higher_low=t3[1],
                                points=[(t2[0], t2[1], "L1"), (p2[0], p2[1], "P"), (t3[0], t3[1], "L2")], **base))
            elif t2[1] - SWEEP_W_H * hgt <= t3[1] < t2[1] - eq:
                out.append(dict(family="w", variant="W, the 2nd low swept the 1st", extreme=t3[1], higher_low=t3[1],
                                points=[(t2[0], t2[1], "L1"), (p2[0], p2[1], "P"), (t3[0], t3[1], "L2")], **base))
        if d - t2[0] <= SPAN["st"] and t3[1] > t2[1] + eq:
            out.append(dict(family="st", variant="sweep, higher low", extreme=t2[1], higher_low=t3[1],
                            points=[(t2[0], t2[1], "S"), (p2[0], p2[1], "P"), (t3[0], t3[1], "HL")], **base))
    if k3 >= 4:
        t1, p1 = seq[k3 - 4], seq[k3 - 3]
        if d - t1[0] <= SPAN["ihs"] and p2[0] > p1[0]:
            slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
            line = p1[1] + slope * (np.arange(t3[0], d + 1) - p1[0])
            hgt = p1[1] + slope * (t2[0] - p1[0]) - t2[1]
            if (t2[1] < min(t1[1], t3[1]) - HEAD_ATR * atr and abs(t1[1] - t3[1]) <= SHOULDER_H * hgt
                    and abs(p2[1] - p1[1]) <= NECK_H * hgt and first_close_above(c, line, t3[0], d)):
                out.append(dict(family="ihs", variant="inverse H&S", extreme=t2[1], higher_low=t3[1], trigger=float(line[-1]),
                                height=hgt, start=t1[0], neck=((p1[0], p1[1]), (p2[0], p2[1])),
                                points=[(t1[0], t1[1], "LS"), (p1[0], p1[1], "N1"), (t2[0], t2[1], "Head"),
                                        (p2[0], p2[1], "N2"), (t3[0], t3[1], "RS")]))
    return out


def find_base(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: np.ndarray, d: int) -> list[dict]:
    """A base then its break at bar d: the longest run of BASE_MIN .. BASE_MAX bars ending at d - 1 within BASE_W x the
    ATR at d - 1; close[d] above its high (side +1) or below its low (side -1)."""
    if d - BASE_MIN < 0 or not np.isfinite(atr[d - 1]):
        return []
    w = BASE_W * atr[d - 1]
    best = None
    hi, low = -np.inf, np.inf
    for n in range(1, min(BASE_MAX, d) + 1):
        hi, low = max(hi, h[d - n]), min(low, lo[d - n])
        if hi - low > w:
            break
        if n >= BASE_MIN:
            best = (n, hi, low)
    if best is None:
        return []
    n, hi, low = best
    side = 1 if c[d] > hi else -1 if c[d] < low else 0
    if not side:
        return []
    return [dict(family="base", variant="base", side=side, extreme=low if side > 0 else hi, trigger=hi if side > 0 else low,
                 height=hi - low, start=d - n, box=(d - n, d - 1, low, hi), higher_low=np.nan,
                 points=[(d - n, low if side > 0 else hi, "base")])]


def mirror_piv(piv: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    pb, pp, pk, pc = piv
    return pb, -pp, -pk, pc


def unmirror(p: dict) -> dict:
    """A pattern found on the mirrored prices, back in prices, side -1."""
    q = dict(p)
    for key in ("extreme", "trigger", "higher_low"):
        q[key] = -p[key]
    q["points"] = [(b, -x, SELL_LABELS.get(lab, lab)) for b, x, lab in p["points"]]
    if "neck" in p:
        q["neck"] = tuple((b, -x) for b, x in p["neck"])
    q["side"] = -1
    q["variant"] = SELL_NAMES[p["variant"]]
    return q


def patterns_at(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: np.ndarray, piv: tuple[np.ndarray, ...], d: int,
                mir: tuple | None = None) -> list[dict]:
    """Every pattern breaking out at bar d, both sides: the swing patterns (sells by the mirror: highs -> -lows) and
    the base, each no taller than HEIGHT_ATR x the ATR at d. mir = (-lo, -h, -c, mirror_piv(piv)) precomputed, or None
    to build it here."""
    out = [dict(p, side=1) for p in find_buy(h, lo, c, atr[d], structure(piv, h, lo, d), d)]
    mh, ml, mc, mp = mir if mir is not None else (-lo, -h, -c, mirror_piv(piv))
    out += [unmirror(p) for p in find_buy(mh, ml, mc, atr[d], structure(mp, mh, ml, d), d)]
    out += find_base(h, lo, c, atr, d)
    out = [p for p in out if p["height"] <= HEIGHT_ATR * atr[d]]
    for p in out:
        p["stop"] = p["extreme"] - p["side"] * STOP_ATR * atr[d]
        p["d"] = d
        p["atr"] = float(atr[d])
    return out


def at_level(p: dict, close: float, levels: pd.DataFrame, z: float, sweep: float) -> dict | None:
    """Where pattern p counts against these levels: 'at' (the extreme within the zone), 'swept' (past it by at most
    `sweep`, the breakout close back on the near side of the zone's far edge), 'base' (the base overlaps the zone). The
    sweep-turn needs 'swept' and its higher low back at / inside the zone. The nearest level to the extreme wins."""
    s, ext = p["side"], p["extreme"]
    best = None
    for L in levels.itertuples(index=False):
        lv = float(L.price)
        if p["family"] == "base":
            lo_b, hi_b = p["box"][2], p["box"][3]
            how = "base" if (lo_b <= lv + z and hi_b >= lv - z) else None
        else:
            past = s * (lv - ext) - z  # > 0: past the zone's far edge in the pattern's extreme direction
            if abs(ext - lv) <= z:
                how = "at"
            elif 0 < past <= sweep and s * (close - (lv - s * z)) > 0:
                how = "swept"
            else:
                how = None
            if p["family"] == "st" and (how != "swept" or s * (p["higher_low"] - (lv - s * z)) < 0):
                how = None
        if how is not None:
            dist = abs(ext - lv)
            if best is None or dist < best["dist"]:
                best = dict(level=lv, level_kind=str(L.kind), how=how, dist=dist)
    return best


def next_level(levels: np.ndarray, entry: float, side: int, z: float, own: float) -> float:
    """The nearest level beyond the entry in the trade's way (more than one zone away, not the pattern's own)."""
    v = levels[(np.abs(levels - own) > z) & (side * (levels - entry) > z)]
    if not len(v):
        return np.nan
    return float(v.min() if side > 0 else v.max())


def m_structure(piv: tuple[np.ndarray, ...], d: int) -> str:
    """The TF's structure as it stands at bar d from its last two confirmed troughs and peaks: up (both higher), down
    (both lower), else mixed ('none' with fewer than two of each)."""
    pb, pp, pk, pc = piv
    n = int(np.searchsorted(pc, d, side="right"))
    tr = pp[:n][pk[:n] == -1][-2:]
    pk_ = pp[:n][pk[:n] == 1][-2:]
    if len(tr) < 2 or len(pk_) < 2:
        return "none"
    if tr[1] > tr[0] and pk_[1] > pk_[0]:
        return "up"
    if tr[1] < tr[0] and pk_[1] < pk_[0]:
        return "down"
    return "mixed"


class TF:
    """One timeframe's bars, ATR and swings."""

    def __init__(self, m: pd.DataFrame, minutes: int):
        self.minutes = minutes
        self.b = tf_bars(m, minutes)
        self.h, self.lo, self.c, self.o = (self.b[k].to_numpy(float) for k in ("high", "low", "close", "open"))
        self.atr = atr14(self.b)
        self.piv = zigzag(self.h, self.lo, self.atr)
        self.t_open = self.b.index.as_unit("ns").asi8
        self.avail = pd.DatetimeIndex(self.b["avail"]).as_unit("ns").asi8
        self.mir = (-self.lo, -self.h, -self.c, mirror_piv(self.piv))

    def scan(self, a: int, b: int) -> list[dict]:
        out = []
        for d in range(a, b):
            if np.isfinite(self.atr[d]):
                out += patterns_at(self.h, self.lo, self.c, self.atr, self.piv, d, self.mir)
        return out

    def last_complete(self, t_ns: int) -> int:
        return int(np.searchsorted(self.avail, t_ns, side="right")) - 1


def level_inputs(m: pd.DataFrame) -> dict:
    """The inputs of zones.levels_at from M1, the way precursors/touches.py builds them."""
    import foundation as F  # noqa: PLC0415

    from indicators import bars  # noqa: PLC0415
    from zones import swings  # noqa: PLC0415

    b1, d1 = bars(m, "1h"), bars(m, "1D")
    return dict(S=swings(b1), avail=pd.DatetimeIndex(b1["avail"]).as_unit("ns").asi8,
                atr=F.atr(b1.high.to_numpy(), b1.low.to_numpy(), b1.close.to_numpy(), 14), h=b1.high.to_numpy(float),
                lo=b1.low.to_numpy(float), d_avail=pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8,
                d_high=d1.high.to_numpy(float), d_low=d1.low.to_numpy(float))


def news_levels(m1: TF) -> pd.DataFrame:
    """At each 08:30 / 10:00 NY minute whose first minute moved 3+ USD on the tick mid (sweep_detector.first_minute,
    the larger side - known at the release + 60 s; what came after is not read): the release bar's M1 low (a down first
    leg) or high (up) as a level for the other side, live for decisions from the release + 1 min to + NEWS_MIN."""
    from sweep_detector import fixed_events, first_minute, learning_ticks  # noqa: PLC0415

    ev = fixed_events()
    rows = []
    for day, D in ev.groupby(pd.DatetimeIndex(ev.t).normalize(), sort=True):
        tk = learning_ticks(day)
        if tk is None:
            continue
        t, bid, ask = tk
        mid = (bid + ask) / 2
        for r in D.itertuples(index=False):
            rel = pd.Timestamp(r.t).value
            fm = first_minute(t, mid, rel)
            if fm is None or fm["first"] == 0:
                continue
            j = int(np.searchsorted(m1.t_open, rel))
            if j >= len(m1.t_open) or m1.t_open[j] != rel:
                continue
            lv = m1.lo[j] if fm["first"] < 0 else m1.h[j]
            rows.append(dict(t_rel=rel, ny=r.ny, first=fm["first"], leg1=fm["leg1"], level=float(lv)))
    return pd.DataFrame(rows)


def locate(P: list[dict], tf: TF, Y: dict, news: pd.DataFrame) -> pd.DataFrame:
    """Each pattern at the owner's H1 levels and / or after a news leg; the ones at neither are dropped."""
    from zones import levels_at  # noqa: PLC0415

    rows = []
    for p in P:
        d = p["d"]
        t_dec = int(tf.avail[d])
        if not (LEARN_START.value <= t_dec < EXAM_START.value):
            continue
        close = float(tf.c[d])
        L, a1 = levels_at(Y, t_dec, close)
        if not np.isfinite(a1):
            continue
        hit = None
        if not L.empty and np.isfinite(a1):
            hit = at_level(p, close, L, ZONE_H1 * a1, SWEEP_H1 * a1)
        nw = news[(news.t_rel + NS_MIN < t_dec) & (t_dec <= news.t_rel + NEWS_MIN * NS_MIN) & (news["first"] == -p["side"])]
        nhit = None
        if len(nw) and np.isfinite(a1):
            r = nw.iloc[-1]
            nhit = at_level(p, close, pd.DataFrame(dict(price=[r.level], kind=["news leg"])), ZONE_H1 * a1, SWEEP_H1 * a1)
            if nhit:
                nhit.update(t_rel=int(r.t_rel), ny=r.ny)
        if not hit and not nhit:
            continue
        use = hit or nhit
        entry_t = t_dec
        e_i = int(np.searchsorted(tf.t_open, entry_t))
        entry = float(tf.o[e_i]) if e_i < len(tf.o) and tf.t_open[e_i] == entry_t else np.nan
        lv_prices = L.price.to_numpy(float) if not L.empty else np.empty(0)
        rows.append(dict(
            tf=f"M{tf.minutes}", family=p["family"], side=p["side"], name=NAMES[(p["family"], p["side"])],
            variant=p["variant"], d=d, t_dec=t_dec, close=close, trigger=p["trigger"], extreme=p["extreme"],
            stop=p["stop"], atr=p["atr"], height=p["height"], start_t=int(tf.t_open[p["start"]]),
            pts_t=[int(tf.t_open[b]) for b, _, _ in p["points"]], pts_p=[float(x) for _, x, _ in p["points"]],
            pts_lab=[lab for _, _, lab in p["points"]],
            neck_t=[int(tf.t_open[p["neck"][0][0]]), int(tf.t_open[p["neck"][1][0]])] if "neck" in p else None,
            neck_p=[float(p["neck"][0][1]), float(p["neck"][1][1])] if "neck" in p else None,
            box_t=[int(tf.t_open[p["box"][0]]), int(tf.t_open[p["box"][1]])] if "box" in p else None,
            box_p=[float(p["box"][2]), float(p["box"][3])] if "box" in p else None,
            at_h1=bool(hit), at_news=bool(nhit), level=use["level"], level_kind=use["level_kind"], how=use["how"],
            news_t=nhit["t_rel"] if nhit else None, news_ny=nhit["ny"] if nhit else None, h1_atr=a1,
            zone=ZONE_H1 * a1, entry_t=entry_t, entry=entry,
            next_level=next_level(lv_prices, entry if np.isfinite(entry) else close, p["side"], ZONE_H1 * a1, use["level"])))
    return pd.DataFrame(rows)


def agree(A: pd.DataFrame, B: pd.DataFrame, other: TF) -> pd.DataFrame:
    """For each located pattern of A (one TF): the other TF's same-side pattern at the same level (within one zone)
    decided within the last AGREE_MIN minutes, and the other TF's structure as it stands (its last complete bar)."""
    A = A.copy()
    pat, struct = [], []
    for r in A.itertuples(index=False):
        if len(B):
            q = B[(B.side == r.side) & ((B.level - r.level).abs() <= r.zone) & (B.t_dec <= r.t_dec)
                  & (B.t_dec >= r.t_dec - AGREE_MIN * NS_MIN)]
        else:
            q = B
        pat.append(", ".join(sorted(set(q["name"]))) if len(q) else "")
        struct.append(m_structure(other.piv, other.last_complete(r.t_dec)))
    A["other_pattern"], A["other_structure"] = pat, struct
    return A


def main() -> None:
    from m15_trades import part_of  # noqa: PLC0415

    m = load_m1()
    Y = level_inputs(m)
    m1, m5 = TF(m, 1), TF(m, 5)
    news = news_levels(m1)
    out = {}
    for tf in (m1, m5):
        a = int(np.searchsorted(tf.avail, LEARN_START.value))
        out[tf.minutes] = locate(tf.scan(a, len(tf.c)), tf, Y, news)
    A1 = agree(out[1], out[5], m5)
    A5 = agree(out[5], out[1], m1)
    C = pd.concat([A1, A5], ignore_index=True)
    C["part"] = part_of(pd.to_datetime(C.t_dec, utc=True))
    if (C.t_dec >= EXAM_START.value).any():
        raise ExamPeriodError("an exam decision in the catches")
    C.to_parquet(HERE / "p_catches.parquet")
    news.to_parquet(HERE / "p_news_levels.parquet")
    print(f"located patterns written: {len(C)} rows (M1 {len(A1)}, M5 {len(A5)}); news legs {len(news)}")


if __name__ == "__main__":
    main()
