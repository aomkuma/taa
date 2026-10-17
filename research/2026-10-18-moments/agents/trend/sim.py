"""A vectorised version of lab.Bars.trade for many trades at once (same conventions), with an optional break-even
and an optional trailing stop. Paths are taken in the trade's own direction ("signed space"): for a BUY the
adverse price is the bid low, the favourable the bid high, the exit at the bid; for a SELL everything is on the
ask and negated, so one code path serves both sides.

A stop update (break-even or trail) is made at a bar's close and applies from the next bar. A bar that opens
through the stop exits at its open (a gap) - slightly stricter than the brief's bar-low rule."""

from __future__ import annotations

import numpy as np

SLIP = 0.07


def paths(B, e: np.ndarray, side: np.ndarray, width: int) -> dict:
    idx = e[:, None] + np.arange(width)[None, :]
    idx = np.minimum(idx, len(B.o) - 1)
    s = side[:, None].astype(np.float64)
    buy = s > 0
    adv = np.where(buy, B.lo[idx], -(B.h[idx] + B.sp[idx]))
    fav = np.where(buy, B.h[idx], -(B.lo[idx] + B.sp[idx]))
    opn = np.where(buy, B.o[idx], -(B.o[idx] + B.sp[idx]))
    cls = np.where(buy, B.c[idx] - SLIP, -(B.c[idx] + B.sp[idx] + SLIP))
    entry = np.where(side > 0, B.o[e] + B.sp[e] + SLIP, -(B.o[e] - SLIP))  # signed: BUY ask+slip, SELL -(bid-slip)
    return dict(adv=adv, fav=fav, opn=opn, cls=cls, entry=entry, e=e, side=side)


def run(P: dict, risk: np.ndarray, tp: np.ndarray | None, hz: int | np.ndarray, be: float | None = None,
        trail: np.ndarray | None = None, trail_start: np.ndarray | None = None, kind_tp: np.ndarray | None = None) -> dict:
    """*risk*: stop distance (USD) from the fill; *tp*: target distance (np.inf = none); *hz*: bars held at most;
    *be*: R multiple at which the stop moves to the entry; *trail*/*trail_start*: USD distances."""
    adv, fav, opn, cls, entry = P["adv"], P["fav"], P["opn"], P["cls"], P["entry"]
    n, w = adv.shape
    hz = np.broadcast_to(np.asarray(hz), (n,))
    tp = np.full(n, np.inf) if tp is None else tp
    stop0 = entry - risk
    gain = fav - entry[:, None]
    mfe_prev = np.concatenate([np.full((n, 1), -np.inf), np.maximum.accumulate(gain, axis=1)[:, :-1]], axis=1)
    stop = np.repeat(stop0[:, None], w, axis=1)
    if be is not None:
        armed = mfe_prev >= (be * risk)[:, None]
        stop = np.where(armed, np.maximum(stop, entry[:, None]), stop)
    if trail is not None:
        ts = trail_start if trail_start is not None else np.zeros(n)
        tr = np.where(mfe_prev >= ts[:, None], entry[:, None] + mfe_prev - trail[:, None], -np.inf)
        stop = np.maximum(stop, tr)
    col = np.arange(w)[None, :]
    live = col < hz[:, None]
    hit_stop = (adv <= stop) & live
    hit_tp = (gain >= tp[:, None]) & live
    big = w + 1
    js = np.where(hit_stop.any(1), hit_stop.argmax(1), big)
    jt = np.where(hit_tp.any(1), hit_tp.argmax(1), big)
    r = np.arange(n)
    out_usd = np.empty(n)
    exit_ = np.empty(n, dtype=object)
    jx = np.empty(n, dtype=int)
    stop_first = (js <= jt) & (js < big)
    tp_first = (jt < js)
    timed = ~stop_first & ~tp_first
    # stop exits
    jj = np.minimum(js, w - 1)
    st = stop[r, jj]
    px = np.where(opn[r, jj] < st, opn[r, jj], st) - SLIP
    out_usd[stop_first] = (px - entry)[stop_first]
    exit_[stop_first] = np.where(st[stop_first] < entry[stop_first] - 1e-9, "stop", "trail")
    jx[stop_first] = js[stop_first]
    out_usd[tp_first] = tp[tp_first]
    exit_[tp_first] = "win"
    jx[tp_first] = jt[tp_first]
    jl = np.minimum(hz, w) - 1
    out_usd[timed] = (cls[r, jl] - entry)[timed]
    exit_[timed] = "time"
    jx[timed] = jl[timed]
    mfe_exit = mfe_prev[r, np.minimum(jx, w - 1)]
    mfe_exit = np.maximum(mfe_exit, 0)
    kind = np.full(n, "", dtype=object)
    if kind_tp is not None:
        lost = exit_ == "stop"
        after = (col > jx[:, None]) & (col < 120)
        reached = ((gain >= kind_tp[:, None]) & after).any(1)
        kind[lost & reached] = "3"
        kind[lost & ~reached & (mfe_exit >= 0.5 * kind_tp)] = "2"
        kind[lost & ~reached & (mfe_exit < 0.5 * kind_tp)] = "1"
    return dict(usd=out_usd, exit=exit_, mins=jx + 1, R=out_usd / (risk + SLIP), kind=kind)
