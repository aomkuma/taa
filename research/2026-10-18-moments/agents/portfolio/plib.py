"""The portfolio agent's library: the journal's wide candidate tables (every minute of Asia 00-02, London 07-12, New
York 12-17 UTC x both sides, features at the decision bar's close), the six entry families (notes.md), the
protective menu, a trade loop with a per-row exit (target / break-even / horizon / optional trailing stop), and the
step / account tables. Real costs via the journal's ``jlib.Instr`` (the auditor's).

Design rows end before 2026-03-01 (``jlib.cands`` asserts it); the test table is read only by ``load('wtest')``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "journal"))
import jlib  # noqa: E402
import rules  # noqa: E402

ET = ZoneInfo("America/New_York")
HALVES = jlib.HALVES
TP_U, BE, HZ, RMIN, RMAX = 8.0, 0.6, 60, 3.0, 10.0


def rmax(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).max().to_numpy()


def rmin(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n).min().to_numpy()


def load(part: str) -> tuple[jlib.Instr, pd.DataFrame]:
    P = jlib.Instr("XAUUSD")
    D = jlib.cands("XAUUSD", part)
    if part.endswith("test"):
        D = D[(D.t >= jlib.TEST_START) & (D.t < jlib.TEST_END)]
    D = D.reset_index(drop=True)
    D["e"] = P.e_of(D.t)
    D = rules.augment(D, P)
    D["unit"] = rules.unit(D, P)
    p = D.e.to_numpy() - 1
    et = pd.DatetimeIndex(D.t).tz_convert(ET)
    D["et_min"] = (et.hour * 60 + et.minute).to_numpy()
    D["m15_tide"] = (D.m15_e20_slope > 0) & (D.m15_c_e50 > 0)
    D["m5_with"] = rules.m5_with(D)
    D["c_dec"] = P.c[p]
    return P, D.set_index(["t", "side"], drop=False).sort_index()


# ---------------------------------------------------------------------------------------------- protective menu

def late(D: pd.DataFrame) -> pd.Series:
    asia = (D.session == 0) & (pd.DatetimeIndex(D.t).hour * 60 + pd.DatetimeIndex(D.t).minute >= 100)
    ny = (D.session == 2) & (D.et_min >= 10 * 60 + 15)
    return asia | ny


MENU = {
    "C1 H1 leg not against": lambda D: D.cr_H1_leg_dir >= 0,
    "C2 H1 not flat": lambda D: D.h1_c_e50.abs() >= 0.85,
    "C3 pos240 >= .5": lambda D: D.pos240 >= 0.5,
    "C4 72-h extreme near/behind": lambda D: (D.front72 - D.c_dec) * D.side < 0.5 * TP_U * D.unit,
    "C5 not a fast tape": lambda D: D.atr_ratio < 2,
    "C6 not late": lambda D: ~late(D),
    "C7 no release +-15m": lambda D: (D.since_rel > 15) & (D.until_rel > 15),
    "C8 H1 tide with": lambda D: D.tide.astype(bool),
    # added after the first design run (notes.md): the journal's J1, the one lesson above the coin in 3 of 5 halves
    "C9 M5 with the trade": lambda D: rules.m5_with(D),
}


# ---------------------------------------------------------------------------------------------- families

def _stop(D: pd.DataFrame, P: jlib.Instr, stop_px: np.ndarray, widen: bool = True) -> pd.DataFrame:
    side = D.side.to_numpy()
    sl = (P.fill(D.e.to_numpy(), side) - stop_px) * side
    u = D.unit.to_numpy()
    if widen:
        sl = np.maximum(sl, RMIN * u)
        ok = sl <= RMAX * u
    else:
        ok = (sl >= RMIN * u) & (sl <= RMAX * u)
    return D.assign(sl=sl, stop_px=stop_px)[ok]


def _exit(S: pd.DataFrame, tp_u=TP_U, be=BE, hz=HZ, trail=False) -> pd.DataFrame:
    return S.assign(tp=tp_u * S.unit if np.isfinite(tp_u) else np.inf, be=be if be is not None else np.nan, hz=hz, trail=trail)


def f_conf(D, P):
    S = rules.signals(D.reset_index(drop=True), rules.RULES["B0"], P)
    return _exit(S)


def _rows_at(D: pd.DataFrame, P: jlib.Instr, e: np.ndarray, side: np.ndarray) -> pd.DataFrame:
    """The candidate rows for entry bar e and side (dropped when outside the windows)."""
    t = P.ot[e]
    key = pd.MultiIndex.from_arrays([t, side])
    ok = key.isin(D.index)
    return D.loc[key[ok]].reset_index(drop=True), ok


def _ny_events(P: jlib.Instr):
    et = P.ot.tz_convert(ET)
    mins = et.hour * 60 + et.minute
    day = pd.Series(et.date)
    rng = (mins >= 510) & (mins < 570)
    g = pd.DataFrame({"d": day[rng].to_numpy(), "h": P.h[rng], "l": P.lo[rng]}).groupby("d").agg(hi=("h", "max"), lo=("l", "min"), n=("h", "size"))
    trig = np.flatnonzero((mins >= 570) & (mins < 600))
    T = pd.DataFrame({"p": trig, "d": day.to_numpy()[trig]}).merge(g[g.n >= 50], left_on="d", right_index=True)
    c = P.c[T.p.to_numpy()]
    T["sd"] = np.where(c > T.hi, 1, np.where(c < T.lo, -1, 0))
    T = T[T.sd != 0].groupby("d").head(1)
    T = T[T.p + 1 < len(P.o)]
    T = T[(P.ot[T.p.to_numpy() + 1] - P.ot[T.p.to_numpy()]) == pd.Timedelta(minutes=1)]
    return T


def f_nyb(D, P, exit_="b"):
    T = _ny_events(P)
    R, ok = _rows_at(D, P, T.p.to_numpy() + 1, T.sd.to_numpy())
    T = T[ok].reset_index(drop=True)
    R = R.assign(rng_hi=T.hi.to_numpy(), rng_lo=T.lo.to_numpy())
    R = R[R.tide.astype(bool)]
    s = R.side.to_numpy()
    if exit_ == "a":
        S = _stop(R, P, np.where(s > 0, R.rng_lo, R.rng_hi))
        return _exit(S, tp_u=np.inf, be=None, hz=180, trail=True)
    edge = np.where(s > 0, R.rng_hi, R.rng_lo)
    return _exit(_stop(R, P, edge - s * R.atr1.to_numpy()))


OPENS = [("UTC", "00:00"), ("UTC", "01:00"), ("Europe/London", "08:00"), ("America/New_York", "08:30"), ("America/New_York", "09:30")]


def _opens(D, P):
    days = sorted({t.normalize() for t in D.t.drop_duplicates()})
    out = []
    for d in days:
        if d.weekday() > 4:
            continue
        for z, clock in OPENS:
            T = pd.Timestamp(f"{d.date()} {clock}").tz_localize(ZoneInfo(z)).tz_convert("UTC")
            if (T, 1) not in D.index or (T, -1) not in D.index:
                continue
            up_r, dn_r = D.loc[(T, 1)], D.loc[(T, -1)]
            x = float(up_r.c_dec)
            up = x + float(up_r.room) if np.isfinite(up_r.room) else np.nan
            dn = x - float(dn_r.room) if np.isfinite(dn_r.room) else np.nan
            out.append((T, int(up_r.e), up, dn))
    return out


def f_open(D, P):
    c = P.c
    ev = []
    for T, e0, up, dn in _opens(D, P):
        for j in range(e0, e0 + 30):
            sd = 1 if c[j] > up else -1 if c[j] < dn else 0
            if sd == 0:
                continue
            lvl = up if sd > 0 else dn
            if (c[j + 1] - lvl) * sd > 0:
                ev.append((j + 2, sd, lvl))
            break
    ev = np.array(ev) if ev else np.zeros((0, 3))
    R, ok = _rows_at(D, P, ev[:, 0].astype(int), ev[:, 1].astype(int))
    lvl = ev[ok, 2]
    s = R.side.to_numpy()
    return _exit(_stop(R, P, lvl - s * R.atr1.to_numpy()))


def f_sweep(D, P):
    c, h, lo = P.c, P.h, P.lo
    ev = []
    for T, e0, up, dn in _opens(D, P):
        for j in range(e0, e0 + 30):
            sd = -1 if h[j] > up else 1 if lo[j] < dn else 0
            if sd == 0:
                continue
            lvl = up if sd < 0 else dn
            for k in range(j, j + 5):
                if (c[k] - lvl) * sd > 0:
                    ext = h[j : k + 1].max() if sd < 0 else lo[j : k + 1].min()
                    ev.append((k + 1, sd, ext))
                    break
            break
    ev = np.array(ev) if ev else np.zeros((0, 3))
    R, ok = _rows_at(D, P, ev[:, 0].astype(int), ev[:, 1].astype(int))
    ext = ev[ok, 2]
    s = R.side.to_numpy()
    return _exit(_stop(R, P, ext - s * 0.5 * R.atr1.to_numpy()))


def f_fade(D, P):
    p = D.e.to_numpy() - 1
    s = D.side.to_numpy()
    hi20, lo20 = rmax(P.h, 20), rmin(P.lo, 20)
    c = P.c
    brk = np.where(s > 0, (c[p] < lo20[p - 1]) & (c[p - 1] >= lo20[p - 2]), (c[p] > hi20[p - 1]) & (c[p - 1] <= hi20[p - 2]))
    ny_skip = (D.et_min >= 480) & (D.et_min < 720)
    m = brk & D.tide.astype(bool) & D.m15_tide & ~ny_skip
    R = D[m.to_numpy()].reset_index(drop=True)
    p = R.e.to_numpy() - 1
    s = R.side.to_numpy()
    ext3 = np.where(s > 0, rmin(P.lo, 3)[p], rmax(P.h, 3)[p])
    return _exit(_stop(R, P, ext3 - s * 0.5 * R.atr1.to_numpy()))


def f_sqz(D, P):
    p = D.e.to_numpy() - 1
    s = D.side.to_numpy()
    hi15, lo15 = rmax(P.h, 15), rmin(P.lo, 15)
    c = P.c
    bh, bl = hi15[p - 1], lo15[p - 1]
    width = (bh - bl) / D.atr1.to_numpy()
    brk = np.where(s > 0, (c[p] > bh) & (c[p - 1] <= hi15[p - 2]), (c[p] < bl) & (c[p - 1] >= lo15[p - 2]))
    m = brk & (width <= 3) & D.tide.astype(bool) & D.m5_with & (D.m5_rsi > 50)
    R = D[m.to_numpy()].reset_index(drop=True)
    p = R.e.to_numpy() - 1
    s = R.side.to_numpy()
    far = np.where(s > 0, lo15[p - 1], hi15[p - 1])
    return _exit(_stop(R, P, far - s * 0.5 * R.atr1.to_numpy()))


def f_pull(D, P):
    """F7 PULL: B0's confirmation without the level - H1 tide, price action (M1 / M5 hammer or M1 engulfing), 2 of
    3 M5 indicators; stop beyond the last 15 minutes' extreme by 0.5 ATR."""
    pa = D.pa_m1 | D.pa_m5 | D.engulf
    ind = (D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2
    R = D[(D.tide.astype(bool) & pa & ind).to_numpy()].reset_index(drop=True)
    s = R.side.to_numpy()
    return _exit(_stop(R, P, R.ext15.to_numpy() - s * 0.5 * R.atr1.to_numpy()))


FAMILIES = {"F1 CONF": f_conf, "F2 NYB": f_nyb, "F3 OPEN": f_open, "F4 SWEEP": f_sweep, "F5 FADE": f_fade, "F6 SQZ": f_sqz, "F7 PULL": f_pull}


# ---------------------------------------------------------------------------------------------- trades

def trade(P: jlib.Instr, e: int, side: int, tp: float, sl: float, be: float, hz: int, ss: float, trail: bool) -> dict:
    """jlib.Instr.trade plus an optional 1 R trailing stop from +1 R (updated at a bar's close, used from the next
    bar). be NaN = none, tp inf = none. Stopped losers in the owner's three kinds (reference target: tp, or 2 R)."""
    SLIP = P.slip
    entry = P.o[e] + (P.sp[e] + SLIP if side > 0 else -SLIP)
    stop, armed, moved, mfe = entry - side * sl, False, False, 0.0
    end = min(e + hz, len(P.o) - 1)
    res = None
    for j in range(e, end):
        adv = P.lo[j] if side > 0 else P.h[j] + P.sp[j]
        fav = P.h[j] if side > 0 else P.lo[j] + P.sp[j]
        if (adv - stop) * side <= 0:
            px = stop - side * ss
            res = ("trail" if moved else "be" if armed else "stop", (px - entry) * side, j)
            break
        if (fav - entry) * side >= tp:
            res = ("win", tp, j)
            break
        mfe = max(mfe, (fav - entry) * side)
        if np.isfinite(be) and not armed and mfe >= be * tp:
            armed, stop = True, entry
        if trail and mfe >= sl:
            ns = entry + side * (mfe - sl)
            if (ns - stop) * side > 0:
                stop, moved = ns, True
    if res is None:
        x = end - 1
        px = P.c[x] - (SLIP if side > 0 else -(P.sp[x] + SLIP))
        res = ("time", (px - entry) * side, x)
    kind = ""
    if res[0] == "stop":
        ref = tp if np.isfinite(tp) else 2 * sl
        later = range(res[2] + 1, min(e + 120, len(P.o)))
        hit = any(((P.h[k] if side > 0 else P.lo[k] + P.sp[k]) - entry) * side >= ref for k in later)
        kind = "3" if hit else ("2" if mfe >= 0.5 * ref else "1")
    return dict(exit=res[0], pnl=res[1], mins=res[2] - e + 1, kind=kind, mfe=mfe)


def run(sig: pd.DataFrame, P: jlib.Instr, coin: np.random.Generator | None = None, per_sess: int = 2,
        per_sess_all: int | None = None, prio: str | None = None) -> pd.DataFrame:
    """One position at a time. *per_sess*: cap per (day, session, family); *per_sess_all*: cap per (day, session)
    across families; *prio*: a column sorted ascending among signals on the same minute."""
    x = sig.reset_index(drop=True)
    x = x.sort_values(["t"] + ([prio] if prio else [])).drop_duplicates("t")
    rows, free, cnt, cnt_all = [], pd.Timestamp(0, tz="UTC"), {}, {}
    fam = x["fam"].to_numpy() if "fam" in x else np.full(len(x), "")
    for i, r in enumerate(x.itertuples()):
        day = r.t.normalize()
        k1, k2 = (day, r.session, fam[i]), (day, r.session)
        if r.t < free or cnt.get(k1, 0) >= per_sess or (per_sess_all and cnt_all.get(k2, 0) >= per_sess_all):
            continue
        s = int(r.side) if coin is None else int(coin.choice([-1, 1]))
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        out = trade(P, int(r.e), s, float(r.tp), float(r.sl), float(r.be), int(r.hz), ss, bool(r.trail))
        out |= {"t": r.t, "session": int(r.session), "side": s, "sl": float(r.sl), "tp": float(r.tp), "e": int(r.e),
                "R": out["pnl"] / (float(r.sl) + ss), "u": float(r.unit), "pnl_u": out["pnl"] / float(r.unit), "fam": fam[i],
                "row": i}
        rows.append(out)
        free = r.t + pd.Timedelta(minutes=int(out["mins"]))
        cnt[k1] = cnt.get(k1, 0) + 1
        cnt_all[k2] = cnt_all.get(k2, 0) + 1
    z = pd.DataFrame(rows)
    if len(z):
        z = z.rename(columns={"row": "sig_idx"})  # positions in x
        z.attrs["x"] = x
    return z


def with_features(z: pd.DataFrame) -> pd.DataFrame:
    x = z.attrs["x"]
    f = x.iloc[z.sig_idx.to_numpy()].reset_index(drop=True)
    z = z.reset_index(drop=True)
    for col in f.columns:
        if col not in z.columns:
            z[col] = f[col].to_numpy()
    return z


def half_of(t: pd.Series) -> pd.Series:
    out = pd.Series("", index=t.index)
    for hn, a, b in HALVES:
        out[(t >= pd.Timestamp(a, tz="UTC")) & (t < pd.Timestamp(b, tz="UTC"))] = hn
    return out


def account(z: pd.DataFrame) -> dict:
    usd = z.pnl.to_numpy()
    eq = np.cumsum(usd)
    dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    u = z.pnl_u.to_numpy()
    equ = np.cumsum(u)
    ddu = float((np.maximum.accumulate(np.r_[0, equ]) - np.r_[0, equ]).max())
    st = mx = 0
    for v in usd:
        st = st + 1 if v < 0 else 0
        mx = max(mx, st)
    stops = usd[(z.exit == "stop").to_numpy()]
    avg = float(-stops.mean()) if len(stops) else 0.0
    return dict(worst=float(usd.min()), streak=mx, dd=dd, dd_u=ddu, avg_loss=avg, six=6 * avg, worst_u=float(u.min()))


def summary(z: pd.DataFrame, days: int, label: str = "") -> str:
    if not len(z):
        return f"  {label:34} 0 trades"
    a = account(z)
    return (f"  {label:34} {len(z):4} {len(z) / days:4.2f}/d win {100 * (z.exit == 'win').mean():3.0f}% "
            f"R {z.R.mean():+.3f}  USD {z.pnl.sum():+7.1f}  worst {a['worst']:6.2f} streak {a['streak']:2} "
            f"DD {a['dd']:5.1f} (at 4100: {a['dd_u']:5.1f})  6 losses {a['six']:4.1f}")


def by_half(z: pd.DataFrame) -> str:
    h = half_of(z.t)
    g = z.R.groupby(h).mean().reindex([x[0] for x in HALVES])
    n = z.R.groupby(h).size().reindex([x[0] for x in HALVES]).fillna(0).astype(int)
    return f"halves+ {(g > 0).sum()}/{g.notna().sum()}: " + " ".join(f"{v:+.2f}({k})" for v, k in zip(g.to_numpy(), n.to_numpy()))


def kinds(z: pd.DataFrame) -> str:
    v = z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    return f"{100 * v['1']:.0f}/{100 * v['2']:.0f}/{100 * v['3']:.0f}"


def coin(sig: pd.DataFrame, P: jlib.Instr, seeds: int = 10, **kw) -> dict:
    rs, ks, ws = [], [], []
    for s in range(seeds):
        z = run(sig, P, coin=np.random.default_rng(100 + s), **kw)
        if len(z):
            rs.append(z.R.mean())
            ws.append((z.exit == "win").mean())
            ks.append(z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0).to_numpy())
    k = np.mean(ks, 0) if ks else np.zeros(3)
    return dict(R=float(np.mean(rs)) if rs else np.nan, win=float(np.mean(ws)) if ws else np.nan,
                kinds=f"{100 * k[0]:.0f}/{100 * k[1]:.0f}/{100 * k[2]:.0f}")
