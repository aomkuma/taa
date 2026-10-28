"""Vectorised M1 trade simulator: market or limit entries, stop / target / time exit, the losers' three kinds.

Conventions (BRIEF.md): decide at bar i's close, act from bar i + 1. Bars are bid OHLC; ask = bid + the bar's spread.
- Market entry: BUY at open_{i+1} + spread + 0.07; SELL at open_{i+1} - 0.07.
- Limit entry (no slippage): a BUY limit at ask level L fills on the first bar j in i+1 .. i+V with
  low_j + spread_j <= L - 0.01, at min(L, open_j + spread_j); a SELL limit at bid level L fills when
  high_j >= L + 0.01, at max(L, open_j). No fill = no trade.
- After the fill: stop on the adverse bid (buy) / ask (sell) extreme, exit at the stop - 0.07; target as a limit
  (no slippage); both in one bar = the stop. In a limit's fill bar only the stop is checked (the target is not
  credited: the order of the bar's high and low is unknown). Time exit at the close of the H-th bar after the
  fill (bid for a buy, ask for a sell) with 0.07 slippage, or at the last bar before a break (> 5 minutes without
  a bar, e.g. the daily break or the weekend) if that comes first; a break right after the decision = no order. Optional break-even: at be x target of favourable
  excursion the stop moves to the fill price.
- Losers' kinds for stopped trades (not break-even exits): 3 if the target (from the fill) is reached within 120
  minutes of the fill after the stop; else 2 if the excursion before the stop reached half the target; else 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

from common import SLIP, Bars

AFTER = 120
# costs (BRIEF.md "Real costs", the auditor 2026-10-17): the M1 spread column is the minute's minimum, + XSP for
# the real ask; stop fills slip STOP_SLIP (New York 08:00-12:00 ET: STOP_SLIP_NY). REAL is the default from round 2
# on; LEGACY (xsp 0, stop slippage 0.07) reproduces the earlier rounds' convention.
REAL = dict(xsp=0.08, stop_slip=0.15, stop_slip_ny=0.20)
LEGACY = dict(xsp=0.0, stop_slip=SLIP, stop_slip_ny=SLIP)
COST = dict(REAL)


def simulate(B: Bars, i: np.ndarray, side: np.ndarray, sl: np.ndarray, tp: np.ndarray, hold: int,
             limit_off: np.ndarray | None = None, valid: int = 0, be: float | None = None,
             chunk: int = 4000, stop_entry: bool = False) -> pd.DataFrame:
    """stop_entry: the pending order is a stop order *limit_off* beyond the market instead (a BUY stop at ask
    level L = ask + off fills when the ask high trades 0.01 through L, at max(L, ask open) + the stop slippage; a
    SELL stop at bid level L = close - off when the low trades through, at min(L, open) - the stop slippage).
    i: decision bars; side +1/-1; sl/tp: USD distances from the fill; limit_off: USD distance of the limit
    from the decision bar's close (ask for a buy, bid for a sell; positive = a better price); None = market."""
    i = np.asarray(i, np.int64)
    n = len(i)
    out = {k: np.zeros(n) for k in ("filled", "f", "x", "usd", "fill_px", "code", "kind")}
    W = max(valid, 1) + hold + AFTER + 2
    lo_p = np.r_[B.lo, np.full(W, np.nan)]
    hi_p = np.r_[B.h, np.full(W, np.nan)]
    xsp = COST["xsp"]
    sp_p = np.r_[B.sp + xsp, np.full(W, np.nan)]
    ny = (B.ny_min >= 480) & (B.ny_min < 720)
    op_p = np.r_[B.o, np.full(W, np.nan)]
    cl_p = np.r_[B.c, np.full(W, np.nan)]
    gap_p = np.r_[B.gap, np.full(W, 999)]
    LO, HI, SP, OP, CL, GP = (swv(a, W) for a in (lo_p, hi_p, sp_p, op_p, cl_p, gap_p))
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        ii, s = i[a:b], side[a:b].astype(float)
        st = ii + 1
        lo, hi, sp, op, cl = LO[st], HI[st], SP[st], OP[st], CL[st]
        m = len(ii)
        rows = np.arange(m)
        gp = GP[st]
        kk = np.arange(W)[None, :]
        # the first break (> 5 minutes without a bar) after the first bar: positions are closed before it;
        # a break right after the decision bar = no order
        brk = (gp > 5) & (kk >= 1)
        g0 = np.where(brk.any(1), brk.argmax(1), W)
        no_start = gp[:, 0] > 5
        # adverse / favourable extremes in the trade's own price (bid for buy exits, ask for sell exits)
        adv = np.where(s[:, None] > 0, lo, hi + sp)
        fav = np.where(s[:, None] > 0, hi, lo + sp)
        if limit_off is None:
            f = np.zeros(m, np.int64)
            fill = np.where(s > 0, op[:, 0] + sp[:, 0] + COST.get("slip", SLIP), op[:, 0] - COST.get("slip", SLIP))
            filled = np.isfinite(fill)
        elif stop_entry:
            L = np.where(s > 0, B.c[ii] + B.sp[ii] + xsp + limit_off[a:b], B.c[ii] - limit_off[a:b])
            V = valid
            ask_hi = hi[:, :V] + sp[:, :V]
            hit = np.where(s[:, None] > 0, ask_hi >= (L + COST.get("tick", 0.01))[:, None], lo[:, :V] <= (L - COST.get("tick", 0.01))[:, None])
            hit &= np.isfinite(lo[:, :V]) & (np.arange(V)[None, :] < g0[:, None])
            filled = hit.any(1)
            f = np.where(filled, hit.argmax(1), 0)
            o_f = np.where(s > 0, op[rows, f] + sp[rows, f], op[rows, f])
            es = np.where(ny[ii], COST["stop_slip_ny"], COST["stop_slip"])
            fill = np.where(s > 0, np.maximum(L, o_f) + es, np.minimum(L, o_f) - es)
        else:
            L = np.where(s > 0, B.c[ii] + B.sp[ii] + xsp - limit_off[a:b], B.c[ii] + limit_off[a:b])
            V = valid
            ask_lo = lo[:, :V] + sp[:, :V]
            hit = np.where(s[:, None] > 0, ask_lo <= (L - COST.get("tick", 0.01))[:, None], hi[:, :V] >= (L + COST.get("tick", 0.01))[:, None])
            hit &= np.isfinite(lo[:, :V]) & (np.arange(V)[None, :] < g0[:, None])
            filled = hit.any(1)
            f = np.where(filled, hit.argmax(1), 0)
            o_f = np.where(s > 0, op[rows, f] + sp[rows, f], op[rows, f])
            fill = np.where(s > 0, np.minimum(L, o_f), np.maximum(L, o_f))
        stop = fill - s * sl[a:b]
        tgt = fill + s * tp[a:b]
        k = np.arange(W)[None, :]
        end_k = np.minimum(f + hold, g0)
        live = (k >= f[:, None]) & (k < end_k[:, None])
        stop_hit = live & ((adv - stop[:, None]) * s[:, None] <= 0)
        tgt_hit = live & (k > (f[:, None] if limit_off is not None else -1)) & ((fav - tgt[:, None]) * s[:, None] >= 0)
        BIG = W + 5
        j_stop = np.where(stop_hit.any(1), stop_hit.argmax(1), BIG)
        j_tgt = np.where(tgt_hit.any(1), tgt_hit.argmax(1), BIG)
        if be is not None:
            # favourable excursion running max (after the fill bar for limits; the fill bar itself for market)
            fe = np.where(live & (k > (f[:, None] if limit_off is not None else -1)), (fav - fill[:, None]) * s[:, None], -np.inf)
            run = np.maximum.accumulate(fe, axis=1)
            arm = live & (run >= be * tp[a:b][:, None])
            j_arm = np.where(arm.any(1), arm.argmax(1), BIG)
            # after arming (from the next bar) the stop is the fill price
            be_hit = live & (k > j_arm[:, None]) & ((adv - fill[:, None]) * s[:, None] <= 0)
            j_be = np.where(be_hit.any(1), be_hit.argmax(1), BIG)
            j_stop_eff = np.minimum(j_stop, j_be)
            is_be = (j_be < j_stop)
        else:
            j_stop_eff, is_be = j_stop, np.zeros(m, bool)
        j_end = end_k - 1
        stop_first = j_stop_eff <= j_tgt
        code = np.where(stop_first & (j_stop_eff < BIG), np.where(is_be, 3, 1), np.where(j_tgt < BIG, 2, 4))
        x = np.where(code == 2, j_tgt, np.where(code == 4, j_end, j_stop_eff))
        x = np.minimum(x, W - 1)
        sslip = np.where(ny[ii], COST["stop_slip_ny"], COST["stop_slip"])
        px_stop = np.where(is_be, fill, stop) - s * sslip
        px_time = np.where(s > 0, cl[rows, x] - COST.get("slip", SLIP), cl[rows, x] + sp[rows, x] + COST.get("slip", SLIP))
        px = np.where(code == 2, tgt, np.where(code == 4, px_time, px_stop))
        usd = (px - fill) * s
        # losers' kinds (stops only)
        fe0 = np.where((k >= f[:, None]) & (k < j_stop[:, None]), (fav - fill[:, None]) * s[:, None], -np.inf).max(1)
        later = (k > j_stop[:, None]) & (k < f[:, None] + AFTER) & ((fav - tgt[:, None]) * s[:, None] >= 0)
        kind = np.where(code == 1, np.where(later.any(1), 3, np.where(fe0 >= 0.5 * tp[a:b], 2, 1)), 0)
        # a gap (weekend / break) inside the trade: drop (rare)
        gapped = no_start | (f >= g0)
        filled = filled & ~gapped & np.isfinite(usd)
        out["filled"][a:b] = filled
        out["f"][a:b] = ii + 1 + f
        out["x"][a:b] = ii + 1 + x
        out["usd"][a:b] = np.where(filled, usd, 0.0)
        out["fill_px"][a:b] = fill
        out["code"][a:b] = code
        out["kind"][a:b] = kind
        # unfilled: the order is pending until it expires
        out["x"][a:b] = np.where(filled, out["x"][a:b], ii + max(valid, 1))
    d = pd.DataFrame(out)
    d["i"], d["side"], d["sl"], d["tp"] = i, side, sl, tp
    d["exit"] = d.code.map({1: "stop", 2: "win", 3: "be", 4: "time"})
    for c in ("f", "x", "code", "kind"):
        d[c] = d[c].astype(np.int64)
    d["filled"] = d.filled.astype(bool)
    return d


def one_at_a_time(d: pd.DataFrame, per_day: int | None = None, B: Bars | None = None,
                  day_key: np.ndarray | None = None) -> pd.DataFrame:
    """Greedy: take a signal only when no position or pending order is open (a pending order blocks until it
    fills or expires); optional cap of *per_day* filled trades per key (e.g. day x session)."""
    d = d.sort_values("i")
    keep, free, cnt = [], -1, {}
    for r in d.itertuples():
        if r.i < free:
            continue
        if per_day is not None:
            key = day_key[r.i]
            if cnt.get(key, 0) >= per_day:
                continue
        keep.append(r.Index)
        free = r.x + 1 if r.filled else r.x
        if r.filled and per_day is not None:
            cnt[key] = cnt.get(key, 0) + 1
    return d.loc[keep]


def summary(t: pd.DataFrame, B: Bars, days: int) -> dict:
    f = t[t.filled]
    if not len(f):
        return dict(n=0)
    r = f.usd / (f.sl + SLIP)
    kinds = f.kind[f.kind > 0].value_counts(normalize=True).reindex([1, 2, 3]).fillna(0)
    return dict(n=len(f), per_day=len(f) / days, fill=len(f) / max(len(t), 1), win=(f.exit == "win").mean(),
                usd=f.usd.sum(), usd_tr=f.usd.mean(), R=r.mean(),
                k1=kinds[1], k2=kinds[2], k3=kinds[3])
