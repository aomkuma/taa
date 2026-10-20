"""LV (notes.md "LV"): with the trend of H4, H1 and M15, take the bounce into an earlier level the trend's way.

The pieces are small pure functions (tested in test_lvl.py with prices whose answer is known); `scan` puts them
together over gold M1 and `main` reads the design period.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/lvl.py design
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

TREND_TFS = ("H4", "H1", "M15")
RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
ETF_MIN = {"M1": 1, "M5": 5, "M15": 15, "M30": 30}
ETFS = ("M1", "M5", "M15", "M30")  # the owner's adaptive entry timeframes (H1 stays the largest, for analysis)


@dataclass(frozen=True)
class Params:
    form: str = "stall"  # "stall" or "limit"
    k: float = 0.5  # how near the level counts as reaching it, in entry-TF ATRs
    target: str = "T1"  # T1 = 1 x stop, T15 = 1.5 x stop, T2 = back to the bounce's start
    zz_k: float = 2.0  # the M5 ZigZag reversal in M5 ATRs
    hours: float = 8.0  # how far back the levels go
    min_bounce: float = 1.0  # the bounce from its start, in entry-TF ATRs
    stop_buf: float = 0.25  # the stop beyond the level, in entry-TF ATRs
    void_buf: float = 0.25  # a close this far beyond the level voids it
    min_stop: float = 3.0  # USD
    min_stop_atr: float = 0.5
    min_target: float = 5.0  # USD (the owner's floor)
    be_share: float = 0.6
    time_bars: int = 12  # of the entry timeframe
    limit_live_min: int = 60
    placebo: bool = False  # shift the level by a random 1-3 ATR (does the level itself matter?)


# ---------------------------------------------------------------- pieces
def ema(x: np.ndarray, span: int) -> np.ndarray:
    """MT5's EMA (foundation.ema)."""
    import foundation as F  # noqa: PLC0415

    return F.ema(x, span)


def atr14(h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> np.ndarray:
    """MT5's ATR(14) (foundation.atr)."""
    import foundation as F  # noqa: PLC0415

    return F.atr(np.asarray(h, float), np.asarray(lo, float), np.asarray(c, float), 14)


def trend_sign(close: np.ndarray) -> np.ndarray:
    """Per bar: +1 when EMA20 > EMA50 and EMA50 rose over 3 bars, -1 when both point down, else 0."""
    e20, e50 = ema(close, 20), ema(close, 50)
    back = np.r_[np.full(3, np.nan), e50[:-3]]
    return np.where((e20 > e50) & (e50 > back), 1, np.where((e20 < e50) & (e50 < back), -1, 0))


def all_agree(signs: list[int]) -> int:
    """The side every trend timeframe agrees on, else 0."""
    s = set(signs)
    return signs[0] if len(s) == 1 and signs[0] != 0 else 0


def entry_tf(atrs: dict[str, float], floor: float = 5.0) -> tuple[str, float]:
    """The owner's adaptive rule: the smallest of M1 / M5 / M15 / M30 whose ATR(14) covers the 5 USD target (else M30;
    H1 stays the largest timeframe and is not an entry timeframe)."""
    for tf in ETFS:
        a = atrs[tf]
        if np.isfinite(a) and a >= floor:
            return tf, a
    return "M30", atrs["M30"]


def find_setup(piv_bar: np.ndarray, piv_px: np.ndarray, piv_typ: np.ndarray, known: np.ndarray, from_bar: int,
               price: float, side: int, min_bounce_px: float) -> tuple[int, float, float, str] | None:
    """The bounce and the level in front. Pivots are M5 swings (+1 peak / -1 trough) usable when `known` (the
    pivot's confirming state at the decision) is True and the pivot bar >= from_bar (the lookback). For a sell
    (side -1): the latest usable pivot is a trough T, price is >= min_bounce_px above it, and L is the nearest earlier
    pivot (a peak = A, or a trough price has since broken = B) above the price. Mirrored for a buy.
    Returns (T's bar, T's price, L, "A" / "B") or None."""
    use = known & (piv_bar >= from_bar)
    idx = np.nonzero(use)[0]
    if len(idx) < 2:
        return None
    last = idx[np.argmax(piv_bar[idx])]
    start_typ = -1 if side < 0 else 1  # a sell bounces up from a trough; a buy dips from a peak
    if piv_typ[last] != start_typ:
        return None
    t_bar, t_px = int(piv_bar[last]), float(piv_px[last])
    if (price - t_px) * -side < min_bounce_px:  # sell: price - T >= ...; buy: T - price >= ...
        return None
    earlier = idx[piv_bar[idx] < t_bar]
    px = piv_px[earlier]
    beyond = earlier[(px - price) * -side > 0]  # sell: above the price; buy: below it
    if len(beyond) == 0:
        return None
    j = beyond[np.argmin(np.abs(piv_px[beyond] - price))]
    lv = float(piv_px[j])
    kind = "A" if piv_typ[j] == -start_typ else "B"  # sell: a peak = A, a broken trough = B
    return t_bar, t_px, lv, kind


def voided(closes_since_start: np.ndarray, level: float, buf_px: float, side: int) -> bool:
    """A close beyond the level by buf_px since the bounce began breaks it (sell: above it)."""
    if len(closes_since_start) == 0:
        return False
    return bool(((closes_since_start - level) * -side > buf_px).any())


def stall(bar_o: float, bar_h: float, bar_l: float, bar_c: float, level: float, near_px: float, side: int) -> bool:
    """An entry-TF bar that reached within near_px of the level and closed back the trend's way, inside the level."""
    if side < 0:
        return bar_h >= level - near_px and bar_c < bar_o and bar_c < level
    return bar_l <= level + near_px and bar_c > bar_o and bar_c > level


def limit_fill(o: np.ndarray, h: np.ndarray, lo: np.ndarray, sp: np.ndarray, ot, j_from: int, t_end, limit: float,
               side: int, cancel_px: float) -> tuple[int, float] | None:
    """A sell limit (bid reaches it) or a buy limit (ask reaches it) on the bars from j_from that open before t_end;
    cancelled when price first trades through cancel_px (the bounce's start). A gap through the limit fills at the
    open."""
    j = j_from
    while j < len(o) and ot[j] < t_end:
        if side < 0:
            if lo[j] < cancel_px:  # the bounce's start broken (in the same bar as a touch: unknown order, cancel)
                return None
            if h[j] >= limit:
                return j, max(limit, o[j])
        else:
            if h[j] + sp[j] > cancel_px:
                return None
            if lo[j] + sp[j] <= limit:
                return j, min(limit, o[j] + sp[j])
        j += 1
    return None


def plan(entry: float, level: float, start_px: float, a: float, side: int, p: Params) -> tuple[float, float]:
    """(stop distance, target distance) in price from the entry."""
    stop_px = level - side * p.stop_buf * a  # sell: above the level
    dist = max((stop_px - entry) * -side, p.min_stop, p.min_stop_atr * a)
    if p.target == "T1":
        tgt = dist
    elif p.target == "T15":
        tgt = 1.5 * dist
    else:
        tgt = (entry - start_px) * -side
    return dist, max(tgt, p.min_target)


def manage(o, h, lo, c, sp, ot, j0: int, side: int, entry: float, sl: float, tp: float, be_share: float,
           t_end: pd.Timestamp, slip: float, stop_slip: float, check_target_in_fill_bar: bool) -> dict:
    """Bars from j0 (the fill bar). A buy's stop / target on the bid, a sell's on the ask (bid + spread). In the
    fill bar only the stop is checked unless check_target_in_fill_bar (a fill at the bar's open). Both in one bar =
    the stop."""
    stop, armed, mfe = entry - side * sl, False, 0.0
    j = j0
    while j < len(o) and ot[j] < t_end:
        adv = lo[j] if side > 0 else h[j] + sp[j]
        fav = h[j] if side > 0 else lo[j] + sp[j]
        if (adv - stop) * side <= 0:
            return dict(exit="stop" if not armed else "be", pnl=(stop - side * stop_slip - entry) * side, xj=j, mfe=mfe)
        if (j > j0 or check_target_in_fill_bar) and (fav - entry) * side >= tp:
            return dict(exit="win", pnl=tp, xj=j, mfe=max(mfe, tp))
        if j > j0 or check_target_in_fill_bar:
            mfe = max(mfe, (fav - entry) * side)
        if not armed and mfe >= be_share * tp:
            armed, stop = True, entry
        j += 1
    x = max(j - 1, j0)
    px = c[x] - (slip if side > 0 else -(sp[x] + slip))
    return dict(exit="time", pnl=(px - entry) * side, xj=x, mfe=mfe)


# ---------------------------------------------------------------- the market's arrays
class Market:
    """Gold M1 with real costs (jlib) and the timeframe series LV reads, all from closed bars."""

    def __init__(self, m: pd.DataFrame | None = None, sp: np.ndarray | None = None, slip: float = 0.07,
                 stop_slip: float = 0.15, stop_slip_ny: float = 0.20, zz_k: float = 2.0) -> None:
        """m: M1 bars (open / high / low / close / tick_volume, indexed by the UTC open time); sp: the spread per bar
        in price. Without m: gold with the auditor's real costs (jlib)."""
        import plib  # noqa: PLC0415
        from fingerprint import zigzag  # noqa: PLC0415

        if m is None:
            import jlib  # noqa: PLC0415

            P = jlib.Instr("XAUUSD")
            m, sp, slip, stop_slip, stop_slip_ny = P.m, P.sp, P.slip, P.stop_slip, P.stop_slip_ny
        self.m = m
        self.ot = m.index
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = np.zeros(len(m)) if sp is None else np.asarray(sp, float)
        # times as int64 UTC nanoseconds for the searches (one representation everywhere)
        self.avail1 = (self.ot + pd.Timedelta(minutes=1)).tz_convert("UTC").asi8
        self.tf = {}
        for tf in ("M5", "M15", "M30", "H1", "H4"):
            b = plib.tf_bars(m, RULE[tf])
            h, lo, c = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
            avail = pd.DatetimeIndex(b["avail"]).tz_convert("UTC").asi8
            assert (np.diff(avail) > 0).all(), f"{tf} bars out of order"
            self.tf[tf] = dict(b=b, avail=avail, trend=trend_sign(c), atr=atr14(h, lo, c))
        self.atr1 = atr14(self.h, self.lo, self.c)
        b5 = self.tf["M5"]["b"]
        pb, pp, pt, pc = zigzag(b5.high.to_numpy(float), b5.low.to_numpy(float), self.tf["M5"]["atr"], zz_k)
        self.piv_bar, self.piv_px, self.piv_typ, self.piv_conf = pb, pp, pt, pc
        # the M1 index of each M5 bar's first minute (to look at closes since a swing)
        first = b5["last"].dt.floor("5min")
        self.m5_first_m1 = np.searchsorted(self.ot.to_numpy(), first.to_numpy())
        self.slip, self.stop_slip, self.stop_slip_ny = slip, stop_slip, stop_slip_ny

    def last_closed(self, tf: str, t_dec: int) -> int:
        """The last bar of tf complete at t_dec (int64 UTC ns)."""
        return int(np.searchsorted(self.tf[tf]["avail"], t_dec, side="right") - 1)


def scan(M: Market, dec: np.ndarray, p: Params, ny: np.ndarray, seed: int = 1) -> pd.DataFrame:
    """Walk the decision minutes in time order, one position at a time; every taken or voided level is used once."""
    rng = np.random.default_rng(seed)
    o, h, lo, c, sp, ot = M.o, M.h, M.lo, M.c, M.sp, M.ot
    rows, busy, used, shifts = [], -1, set(), {}
    for t in dec:
        if t <= busy or t + 1 >= len(o):
            continue
        t_dec = M.avail1[t]
        side = all_agree([int(M.tf[tf]["trend"][M.last_closed(tf, t_dec)]) for tf in TREND_TFS])
        if side == 0:
            continue
        atrs = {"M1": M.atr1[t]}
        for tf in ("M5", "M15", "M30"):
            atrs[tf] = M.tf[tf]["atr"][M.last_closed(tf, t_dec)]
        etf, a = entry_tf(atrs)
        if not np.isfinite(a) or a <= 0:
            continue
        i5 = M.last_closed("M5", t_dec)
        from_bar = i5 - int(p.hours * 12) + 1
        a0 = int(np.searchsorted(M.piv_bar, from_bar))
        a1 = int(np.searchsorted(M.piv_conf, i5, side="right"))  # swings confirmed by the last closed M5 bar
        if a1 - a0 < 2:
            continue
        sl_ = slice(a0, a1)
        setup = find_setup(M.piv_bar[sl_], M.piv_px[sl_], M.piv_typ[sl_], np.ones(a1 - a0, bool), from_bar, c[t],
                           side, p.min_bounce * a)
        if setup is None:
            continue
        t_bar, t_px, lv, kind = setup
        lv_real = lv
        key = (int(t_bar), round(lv, 2), side)  # the real pair (bounce start, level): used once, placebo or not
        if key in used:
            continue
        if p.placebo:
            # the placebo level is drawn once per pair and kept for every later minute of that bounce
            if key not in shifts:
                shifts[key] = rng.uniform(1, 3) * a * rng.choice([-1, 1])
            lv = lv + shifts[key]
            if (lv - c[t]) * -side <= p.k * a:
                continue
        j_start = int(M.m5_first_m1[t_bar])
        if voided(c[j_start:t + 1], lv, p.void_buf * a, side):
            used.add(key)
            continue
        near = p.k * a
        if p.form == "limit":
            limit = lv + side * near  # sell: below the level
            if (c[t] - limit) * -side >= 0:  # already at / beyond the limit: no resting order to place
                continue
            fill = limit_fill(o, h, lo, sp, ot, t + 1, ot[t] + pd.Timedelta(minutes=1 + p.limit_live_min), limit, side,
                              t_px)
            used.add(key)
            if fill is None:
                continue
            j0, entry = fill
            at_open = entry == (o[j0] if side < 0 else o[j0] + sp[j0])
        else:
            ib = M.last_closed(etf, t_dec) if etf != "M1" else -1
            if etf == "M1":
                bo, bh, bl, bc = o[t], h[t], lo[t], c[t]
            else:
                if M.tf[etf]["avail"][ib] != t_dec:  # only when an entry-TF bar has just closed
                    continue
                bb = M.tf[etf]["b"].iloc[ib]
                bo, bh, bl, bc = bb.open, bb.high, bb.low, bb.close
            if not stall(bo, bh, bl, bc, lv, near, side):
                continue
            used.add(key)
            j0 = t + 1
            entry = o[j0] - M.slip if side < 0 else o[j0] + sp[j0] + M.slip
            at_open = True
        dist, tgt = plan(entry, lv, t_px, a, side, p)
        ss = M.stop_slip_ny if ny[t] else M.stop_slip
        t_end = ot[j0] + pd.Timedelta(minutes=p.time_bars * ETF_MIN[etf])
        r = manage(o, h, lo, c, sp, ot, j0, side, entry, dist, tgt, p.be_share, t_end, M.slip, ss, at_open)
        later = range(r["xj"] + 1, min(j0 + 120, len(o)))
        kind_l = ""
        if r["exit"] == "stop":
            hit = any(((h[q] if side > 0 else lo[q] + sp[q]) - entry) * side >= tgt for q in later)
            kind_l = "3" if hit else ("2" if r["mfe"] >= 0.5 * tgt else "1")
        rows.append(dict(t=ot[t], j0=j0, side=side, etf=etf, atr=a, level=lv, level_real=lv_real, lkind=kind, start=t_px,
                         entry=entry,
                         sl=dist, tp=tgt, R=r["pnl"] / (dist + ss), kind=kind_l, **r))
        busy = r["xj"]
    return pd.DataFrame(rows)


def main() -> None:
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    mode = sys.argv[1] if len(sys.argv) > 1 else "design"
    M = Market()
    W = plib.window_mask(M.ot)
    inwin = W.any(axis=1).to_numpy()
    ny = W[[c for c in W.columns if c.startswith("NY")]].any(axis=1).to_numpy()
    # the test window = the latest six months from the current day (owner, 2026-10-18): 2026-04-18 .. the data end
    start, split = pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-04-18", tz="UTC")
    part = (M.ot >= start) & (M.ot < split) if mode == "design" else (M.ot >= split)
    dec = np.nonzero(inwin & np.asarray(part))[0]
    halves = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01",
                             "2026-04-18", "2026-10-17"], utc=True)
    days = pd.Series(M.ot[dec].normalize()).nunique()
    rows = []
    cells = [(f, k, tg, pl) for f in ("stall", "limit") for k in (0.25, 0.5) for tg in ("T1", "T15", "T2")
             for pl in (False, True)] if mode == "design" else [tuple(sys.argv[2:6])]
    for f, k, tg, pl in cells:
        p = Params(form=f, k=float(k), target=tg, placebo=pl in (True, "True"))
        t = scan(M, dec, p, ny)
        if t.empty:
            rows.append(dict(form=f, k=k, target=tg, placebo=p.placebo, trades=0))
            continue
        t["half"] = pd.cut(t.t, halves, labels=["H1", "H2", "H3", "H4", "H5", "H6", "W"], right=False)
        hr = t.groupby("half", observed=True).R.mean()
        eq = t.pnl.cumsum()
        rows.append(dict(form=f, k=k, target=tg, placebo=p.placebo, trades=len(t), per_day=round(len(t) / days, 2),
                         win=round((t.pnl > 0).mean(), 3), R=round(t.R.mean(), 3), usd=round(t.pnl.sum(), 1),
                         halves=" ".join(f"{v:+.2f}" for v in hr), maxdd=round((eq.cummax().clip(lower=0) - eq).max(), 1),
                         kinds="/".join(f"{(t[t.exit == 'stop'].kind == q).mean():.0%}" for q in "123"),
                         typeA=round((t.lkind == "A").mean(), 2)))
        t.to_parquet(HERE / f"lvl_{mode}_{f}_{k}_{tg}{'_placebo' if p.placebo else ''}.parquet")
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(HERE / f"lvl_{mode}.csv", index=False)


if __name__ == "__main__":
    main()
