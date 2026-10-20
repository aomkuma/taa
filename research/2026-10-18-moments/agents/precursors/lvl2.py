"""LV2 (notes.md "LV2"): LV made to match the owner's rules - the entry timeframe from M1 .. M30, the trend from every
larger timeframe, the bounce on the entry timeframe, the levels from the larger timeframes (M15 / M30 / H1) merged into
zones with their importance, an exit on an entry-TF close through the level, and a stop learned walk-forward from the
overshoot of earlier signals that reached their target.

Two passes: `signals` walks the decision minutes in time order and records every stall (with its outcome, used only
once it is known); `trades` takes them one position at a time with the stop learned from the signals resolved before.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/lvl2.py design
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
from lvl import atr14, entry_tf, stall, trend_sign  # noqa: E402

LADDER = ("M1", "M5", "M15", "M30", "H1", "H4")
LEVEL_TFS = ("M15", "M30", "H1")
RULE = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
MINS = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}
NS_MIN = 60_000_000_000


@dataclass(frozen=True)
class Params:
    k: float = 0.5  # the stall bar reaches within k x A of the level
    target: str = "T2"  # T2 = back to the bounce's start, T1 = the stop distance
    p: float = 80.0  # the percentile of the winners' overshoot that sets the stop
    important: bool = False  # only levels with >= 2 swings or an H1 swing
    zz_k: float = 2.0
    screen: int = 120  # bars of each level timeframe looked at
    min_bounce: float = 1.0
    zone_tol: float = 0.25  # of the largest level timeframe's ATR
    min_stop_atr: float = 0.5
    min_target: float = 5.0
    be_share: float = 0.6
    time_bars: int = 12
    min_history: int = 30  # resolved winners needed before the learned stop exists


# ---------------------------------------------------------------- pure pieces
def trend_tfs(etf: str) -> tuple[str, ...]:
    """Every timeframe above the entry timeframe, up to H4."""
    return LADDER[LADDER.index(etf) + 1:]


def level_tfs(etf: str) -> tuple[str, ...]:
    """The level timeframes (M15 / M30 / H1) larger than the entry timeframe."""
    return tuple(t for t in LEVEL_TFS if LADDER.index(t) > LADDER.index(etf))


def merge_zones(px: np.ndarray, is_h1: np.ndarray, tol: float, finest: np.ndarray | None = None) -> list[tuple[float, int, bool]]:
    """Swings sorted by price form zones no wider than tol (a swing joins while it is within tol of the zone's first
    price - no chaining into wide bands): (mean price, importance, any H1 swing). Importance = how many swings of the
    finest level timeframe are in the zone (one swing on H1 is also one on M30 and M15 - counted once), at least 1."""
    if len(px) == 0:
        return []
    finest = np.ones(len(px), bool) if finest is None else finest
    order = np.argsort(px, kind="stable")
    v, h1, fn = px[order], is_h1[order], finest[order]
    zones = []
    a = 0
    for b in range(1, len(v) + 1):
        if b == len(v) or v[b] - v[a] > tol:
            zones.append((float(np.mean(v[a:b])), max(int(fn[a:b].sum()), 1), bool(h1[a:b].any())))
            a = b
    return zones


def level_in_front(zones: list[tuple[float, int, bool]], price: float, side: int, important: bool):
    """The nearest zone beyond the price the trend's way (a sell: above it). important: >= 2 swings or an H1 swing."""
    cand = [z for z in zones if (z[0] - price) * -side > 0 and (not important or z[1] >= 2 or z[2])]
    if not cand:
        return None
    return min(cand, key=lambda z: abs(z[0] - price))


def learned_buffer(over: np.ndarray, resolved_at: np.ndarray, won: np.ndarray, t_now: int, p: float,
                   min_n: int) -> float | None:
    """The p-th percentile of the overshoot (in ATRs) of the earlier signals that reached their target and whose
    outcome was known at t_now (int64 ns). None until min_n such winners exist."""
    ok = won & (resolved_at <= t_now)
    if ok.sum() < min_n:
        return None
    return float(np.percentile(over[ok], p))


def outcome(o, h, lo, sp, ot_ns, j0: int, side: int, entry: float, level: float, tgt: float, t_end: int) -> tuple:
    """Without a stop: did price reach the target before t_end; the overshoot beyond the level before that (price);
    the time the outcome was known (int64 ns: the target bar's close, or t_end)."""
    over = 0.0
    j = j0
    while j < len(o) and ot_ns[j] < t_end:
        adv = h[j] + sp[j] if side < 0 else lo[j]  # a sell is hurt on the ask, a buy on the bid
        over = max(over, (adv - level) * -side)
        fav = lo[j] + sp[j] if side < 0 else h[j]
        if (fav - entry) * side >= tgt:
            return True, over, int(ot_ns[j] + NS_MIN)
        j += 1
    return False, over, int(t_end)


def manage(o, h, lo, c, sp, ot_ns, j0: int, side: int, entry: float, sl: float, tp: float, level: float,
           etf_done: np.ndarray, etf_close: np.ndarray, be_share: float, t_end: int, slip: float,
           stop_slip: float) -> dict:
    """The stall entry fills at the M1 open of j0. Per M1 bar: the stop first (a sell's on the ask), then the target,
    then break-even at be_share of the target; when an entry-TF bar closes beyond the level (a sell: above it), out at
    the next M1 open; else out at t_end at the last close."""
    stop, armed, mfe = entry - side * sl, False, 0.0
    j = j0
    while j < len(o) and ot_ns[j] < t_end:
        adv = lo[j] if side > 0 else h[j] + sp[j]
        fav = h[j] if side > 0 else lo[j] + sp[j]
        if (adv - stop) * side <= 0:
            return dict(exit="stop" if not armed else "be", pnl=(stop - side * stop_slip - entry) * side, xj=j, mfe=mfe)
        if (fav - entry) * side >= tp:
            return dict(exit="win", pnl=tp, xj=j, mfe=max(mfe, tp))
        mfe = max(mfe, (fav - entry) * side)
        if not armed and mfe >= be_share * tp:
            armed, stop = True, entry
        done = ot_ns[j] + NS_MIN  # this M1 bar's close: an entry-TF bar may close with it
        k = int(np.searchsorted(etf_done, done))
        if k < len(etf_done) and etf_done[k] == done and (etf_close[k] - level) * -side > 0 and j + 1 < len(o):
            px = o[j + 1] + (sp[j + 1] + slip if side < 0 else -slip)  # out at the next open (a sell buys at the ask)
            return dict(exit="close", pnl=(px - entry) * side, xj=j + 1, mfe=mfe)
        j += 1
    x = max(j - 1, j0)
    px = c[x] - (slip if side > 0 else -(sp[x] + slip))
    return dict(exit="time", pnl=(px - entry) * side, xj=x, mfe=mfe)


# ---------------------------------------------------------------- the market
class Market:
    def __init__(self, m: pd.DataFrame | None = None, sp: np.ndarray | None = None, slip: float = 0.07,
                 stop_slip: float = 0.15, stop_slip_ny: float = 0.20, zz_k: float = 2.0) -> None:
        import plib  # noqa: PLC0415
        from fingerprint import zigzag  # noqa: PLC0415

        if m is None:
            import jlib  # noqa: PLC0415

            P = jlib.Instr("XAUUSD")
            m, sp, slip, stop_slip, stop_slip_ny = P.m, P.sp, P.slip, P.stop_slip, P.stop_slip_ny
        self.m = m
        self.ot = m.index
        self.ot_ns = self.ot.tz_convert("UTC").as_unit("ns").asi8  # nanoseconds everywhere (pandas may keep us / ms)
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = np.zeros(len(m)) if sp is None else np.asarray(sp, float)
        self.slip, self.stop_slip, self.stop_slip_ny = slip, stop_slip, stop_slip_ny
        self.tf = {}
        for tf in LADDER:
            if tf == "M1":
                start = self.ot
                done = self.ot + pd.Timedelta(minutes=1)
                b = m
            else:
                b = plib.tf_bars(m, RULE[tf])
                done = pd.DatetimeIndex(b["avail"])
                if tf == "H4":
                    loc = pd.DatetimeIndex(b["last"]).tz_convert("Europe/Athens").tz_localize(None).floor("4h")
                    start = loc.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
                else:
                    start = pd.DatetimeIndex(b["last"]).floor(RULE[tf])
            h, lo, c = b["high"].to_numpy(float), b["low"].to_numpy(float), b["close"].to_numpy(float)
            o = b["open"].to_numpy(float)
            atr = atr14(h, lo, c)
            done_ns = pd.DatetimeIndex(done).tz_convert("UTC").as_unit("ns").asi8
            assert (np.diff(done_ns) > 0).all(), tf
            entry = dict(o=o, h=h, lo=lo, c=c, done=done_ns, start=pd.DatetimeIndex(start).tz_convert("UTC").as_unit("ns").asi8,
                         trend=trend_sign(c), atr=atr)
            if tf in ("M1", "M5", "M15", "M30"):  # an entry timeframe: its 2-ATR ZigZag gives the bounce's start
                pb, pp, pt, pc = zigzag(h, lo, atr, zz_k)
                entry.update(zz_b=pb, zz_p=pp, zz_t=pt, zz_known=done_ns[pc] if len(pc) else np.zeros(0, np.int64))
            if tf in LEVEL_TFS:  # a level timeframe: the swings a trader sees on that chart, 5-bar fractals
                ph, pl = plib.pivots(h, lo, 2)
                pb = np.r_[ph, pl]
                pp = np.r_[h[ph], lo[pl]]
                pt = np.r_[np.ones(len(ph), int), -np.ones(len(pl), int)]
                ok = pb + 2 < len(h)
                pb, pp, pt = pb[ok], pp[ok], pt[ok]
                order = np.argsort(pb + 2, kind="stable")
                pb, pp, pt = pb[order], pp[order], pt[order]
                entry.update(fr_b=pb, fr_p=pp, fr_t=pt, fr_known=done_ns[pb + 2])
            self.tf[tf] = entry

    def last(self, tf: str, t_ns: int) -> int:
        return int(np.searchsorted(self.tf[tf]["done"], t_ns, side="right") - 1)


def bounce_at(M: Market, t: int, p: Params):
    """The first part of LV2's setup at the close of M1 bar t, without a level (2026-10-19: so each component can be
    measured alone): the entry TF, every larger timeframe's trend agreeing, the bounce's start on the entry TF's
    ZigZag and a bounce of at least min_bounce x A. None, or (side, etf, A, T, its times, the price, the time)."""
    t_ns = int(M.ot_ns[t] + NS_MIN)
    atrs = {tf: M.tf[tf]["atr"][M.last(tf, t_ns)] for tf in ("M1", "M5", "M15", "M30")}
    etf, a = entry_tf(atrs)
    if not np.isfinite(a) or a <= 0:
        return None
    signs = [int(M.tf[tf]["trend"][M.last(tf, t_ns)]) for tf in trend_tfs(etf)]
    side = signs[0] if len(set(signs)) == 1 and signs[0] != 0 else 0
    if side == 0:
        return None
    E = M.tf[etf]
    known = np.searchsorted(E["zz_known"], t_ns, side="right")  # the entry TF's ZigZag swings, in time order
    if known < 1:
        return None
    last = known - 1
    start_typ = -1 if side < 0 else 1
    if E["zz_t"][last] != start_typ:
        return None
    t_px = float(E["zz_p"][last])
    t_start = int(E["start"][E["zz_b"][last]])
    # the minute the start's extreme happened inside its entry-TF bar (the first M1 bar there reaching it)
    j_a = int(np.searchsorted(M.ot_ns, t_start))
    j_b = int(np.searchsorted(M.ot_ns, t_start + MINS[etf] * NS_MIN))
    seg = M.h[j_a:j_b] if side > 0 else M.lo[j_a:j_b]  # a buy dips from a peak, a sell bounces from a trough
    hit = np.nonzero(np.isclose(seg, t_px))[0]
    t_ext = int(M.ot_ns[j_a + hit[0]]) if len(hit) else t_start
    price = M.c[t]
    if (price - t_px) * -side < p.min_bounce * a:
        return None
    return dict(side=side, etf=etf, a=float(a), t_px=t_px, t_start=t_start, t_ext=t_ext, price=price, t_ns=t_ns)


def setup_at(M: Market, t: int, p: Params):
    """What LV2 sees at the close of M1 bar t: None, or the setup (side, etf, A, T, L, zone, the ETF bar index)."""
    b = bounce_at(M, t, p)
    if b is None:
        return None
    side, etf, t_ns, t_start, price = b["side"], b["etf"], b["t_ns"], b["t_start"], b["price"]
    pxs, h1, fine = [], [], []
    lt = level_tfs(etf)
    for tf in lt:
        L_ = M.tf[tf]
        i = M.last(tf, t_ns)
        kk = np.searchsorted(L_["fr_known"], t_ns, side="right")  # the level TF's fractal swings, in time order
        sel = np.arange(kk)
        sel = sel[(L_["fr_b"][sel] >= i - p.screen + 1) & (L_["start"][L_["fr_b"][sel]] < t_start)]
        pxs.append(L_["fr_p"][sel])
        h1.append(np.full(len(sel), tf == "H1"))
        fine.append(np.full(len(sel), tf == lt[0]))
    if not pxs:
        return None
    big = lt[-1]
    tol = p.zone_tol * M.tf[big]["atr"][M.last(big, t_ns)]
    zones = merge_zones(np.concatenate(pxs), np.concatenate(h1), tol, np.concatenate(fine))
    lv = level_in_front(zones, price, side, p.important)
    if lv is None:
        return None
    return dict(side=side, etf=etf, a=b["a"], t_px=b["t_px"], t_start=t_start, t_ext=b["t_ext"], level=lv[0],
                swings=lv[1], has_h1=lv[2], ib=M.last(etf, t_ns), t_ns=t_ns)


def signals(M: Market, dec: np.ndarray, p: Params) -> pd.DataFrame:
    """Every stall in time order (each (ETF, T, L) pair once), with its outcome without a stop (known at
    `resolved`), and the learned buffer for each percentile from the signals resolved before it."""
    rows, used = [], set()
    over_l, res_l, won_l = [], [], []
    for t in dec:
        if t + 1 >= len(M.o):
            continue
        s = setup_at(M, t, p)
        if s is None:
            continue
        key = (s["etf"], s["t_start"], round(s["level"], 2), s["side"])
        if key in used:
            continue
        E = M.tf[s["etf"]]
        if E["done"][s["ib"]] != s["t_ns"]:  # only when an ETF bar has just closed
            continue
        side, lv, a = s["side"], s["level"], s["a"]
        if not stall(E["o"][s["ib"]], E["h"][s["ib"]], E["lo"][s["ib"]], E["c"][s["ib"]], lv, p.k * a, side):
            continue
        used.add(key)
        j0 = t + 1
        entry = M.o[j0] - M.slip if side < 0 else M.o[j0] + M.sp[j0] + M.slip
        t_end = int(M.ot_ns[j0] + p.time_bars * MINS[s["etf"]] * NS_MIN)
        tgt2 = max((entry - s["t_px"]) * -side, p.min_target)
        won, over, resolved = outcome(M.o, M.h, M.lo, M.sp, M.ot_ns, j0, side, entry, lv, tgt2, t_end)
        # the buffer as known at this decision (from the signals resolved before it), for each percentile
        arr_o, arr_r, arr_w = np.array(over_l), np.array(res_l, dtype=np.int64), np.array(won_l, bool)
        bufs = {q: learned_buffer(arr_o, arr_r, arr_w, s["t_ns"], q, p.min_history) for q in (70.0, 80.0, 90.0)}
        closes = M.c[int(np.searchsorted(M.ot_ns, s["t_start"])):t + 1]
        rows.append(dict(t=t, j0=j0, entry=entry, tgt2=tgt2, won=won, over_A=over / a, resolved=resolved,
                         closes_max_beyond=float(((closes - lv) * -side).max()) / a if len(closes) else -np.inf,
                         **{f"b{int(q)}": bufs[q] for q in bufs}, **s))
        over_l.append(over / a)
        res_l.append(resolved)
        won_l.append(won)
    return pd.DataFrame(rows)


def trades(M: Market, S: pd.DataFrame, p: Params, ny: np.ndarray) -> pd.DataFrame:
    rows, busy = [], -1
    bcol = f"b{int(p.p)}"
    for s in S.itertuples():
        b = getattr(s, bcol)
        if s.t <= busy or b is None or not np.isfinite(b):
            continue
        if s.closes_max_beyond > b:  # a close beyond the learned buffer since the bounce began: the level broke
            continue
        side, a, lv = int(s.side), float(s.a), float(s.level)
        stop_px = lv - side * b * a
        sl = max((stop_px - s.entry) * -side, p.min_stop_atr * a)
        tp = max(s.tgt2 if p.target == "T2" else sl, p.min_target)
        E = M.tf[s.etf]
        ss = M.stop_slip_ny if ny[s.t] else M.stop_slip
        t_end = int(M.ot_ns[s.j0] + p.time_bars * MINS[s.etf] * NS_MIN)
        r = manage(M.o, M.h, M.lo, M.c, M.sp, M.ot_ns, int(s.j0), side, float(s.entry), sl, tp, lv, E["done"], E["c"],
                   p.be_share, t_end, M.slip, ss)
        rows.append(dict(t=M.ot[s.t], j0=int(s.j0), side=side, etf=s.etf, atr=a, level=lv, swings=s.swings,
                         has_h1=s.has_h1, start=s.t_px, entry=float(s.entry), b=b, sl=sl, tp=tp, R=r["pnl"] / (sl + ss), **r))
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
    split = pd.Timestamp("2026-04-18", tz="UTC")
    # signals walk the whole history from 2023-08 so the learned stop has its earlier signals; trades are cut per part
    dec = np.nonzero(inwin & np.asarray(M.ot >= pd.Timestamp("2023-08-15", tz="UTC")))[0]
    rows = []
    grid = [(k, imp, tg, q) for k in (0.25, 0.5) for imp in (False, True) for tg in ("T2", "T1") for q in (70.0, 80.0, 90.0)]
    if mode == "window":  # only the cell chosen on design: k, all|important, target, p
        grid = [(float(sys.argv[2]), sys.argv[3] == "important", sys.argv[4], float(sys.argv[5]))]
    for k, imp in sorted({(g[0], g[1]) for g in grid}):
        if True:
            S = signals(M, dec, Params(k=k, important=imp))
            S.to_parquet(HERE / f"lvl2_signals_k{k}_{'imp' if imp else 'all'}.parquet")
            for tg, q in [(g[2], g[3]) for g in grid if (g[0], g[1]) == (k, imp)]:
                if True:
                    pp = Params(k=k, important=imp, target=tg, p=q)
                    T = trades(M, S, pp, ny)
                    if T.empty:
                        continue
                    part = (T.t >= pd.Timestamp("2023-11-01", tz="UTC")) & (T.t < split) if mode == "design" else (T.t >= split)
                    T = T[part]
                    T.to_parquet(HERE / f"lvl2_{mode}_k{k}_{'imp' if imp else 'all'}_{tg}_p{int(q)}.parquet")
                    eq = T.pnl.cumsum()
                    days = (np.busday_count("2023-11-01", "2026-04-18") if mode == "design"
                            else np.busday_count("2026-04-18", "2026-10-17"))
                    rows.append(dict(k=k, levels="important" if imp else "all", target=tg, p=q, trades=len(T),
                                     per_wd=round(len(T) / max(days, 1), 2), win=round((T.pnl > 0).mean(), 3),
                                     R=round(T.R.mean(), 3), usd=round(T.pnl.sum(), 1), maxdd=round((eq.cummax().clip(lower=0) - eq).max(), 1),
                                     sl_med=round(T.sl.median(), 2), b_med=round(T.b.median(), 2),
                                     exits=" ".join(f"{e} {v:.0%}" for e, v in T.exit.value_counts(normalize=True).items())))
                    print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(HERE / f"lvl2_{mode}.csv", index=False)


if __name__ == "__main__":
    main()
