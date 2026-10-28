"""SW-20 - the three lead streams (ORB 13:00 Thai, RC = reclaim.py, RT_opp = rt_old.py's events the other way) built
from any M1 frame, with their M1 trades (spread only, slippage 0). The event loops are states_events.py's, moved into a
function of the bars; the derived arrays are retest.py's (H1 ATR(14) from M1, M5 bars, server days, PDH / PDL / ASH /
ASL levels). `build(m, start, end)` returns one row per event with entry >= start and < end.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import m1sim

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "precursors"))
import foundation as F  # noqa: E402
import indicators  # noqa: E402

MIN = 60 * 10**9
TH = "Asia/Bangkok"


def in_window(t: pd.Timestamp) -> str:
    th = t.tz_convert(TH)
    mins = th.hour * 60 + th.minute
    if 420 <= mins < 540:
        return "Asia"
    if 780 <= mins < 840:
        return "London"
    ny = t.tz_convert("America/New_York")
    nm = ny.hour * 60 + ny.minute
    if 570 <= nm < 690:
        return "NY"
    return "other"


def build(m: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    spr = m.spread.to_numpy(float) * 0.01 + 0.08
    ti = m.index.asi8
    h1 = indicators.bars(m, "1h")
    atr = F.atr(h1.high.to_numpy(float), h1.low.to_numpy(float), h1.close.to_numpy(float), 14)
    h_av = pd.DatetimeIndex(h1["avail"]).as_unit("ns").asi8
    m5 = indicators.bars(m, "5min")
    m5_av = pd.DatetimeIndex(m5["avail"]).as_unit("ns").asi8
    H5, L5, C5 = (m5[k].to_numpy(float) for k in ("high", "low", "close"))
    sday = m.index.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
    m5_day = pd.DatetimeIndex(m5["last"]).tz_convert("Europe/Athens").tz_localize(None).floor("1D")
    D = pd.DataFrame({"h": h, "l": lo, "d": sday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))

    def H_at(t_ns: int) -> float:
        return float(atr[indicators.at(h_av, np.array([t_ns]))[0]])

    def idx_of_day(d):
        prev = D.index[D.index < d]
        if not len(prev):
            return None
        pdh, pdl = D.loc[prev[-1], "h"], D.loc[prev[-1], "l"]
        idx = np.where(m5_day == d)[0]
        if len(idx) < 50:
            return None
        day_start_ns = m5_av[idx[0]] - 5 * MIN
        asia_s = pd.Timestamp(d.date(), tz="UTC").value
        asia_e = asia_s + 6 * 60 * MIN
        a_bars = idx[(m5_av[idx] > asia_s) & (m5_av[idx] <= asia_e)]
        levels = [("PDH", pdh, 1, day_start_ns), ("PDL", pdl, -1, day_start_ns)]
        if len(a_bars) >= 60:
            levels += [("ASH", H5[a_bars].max(), 1, asia_e), ("ASL", L5[a_bars].min(), -1, asia_e)]
        return idx, levels

    ev = []
    s0, s1 = pd.Timestamp(start), pd.Timestamp(end)
    for d in D.index[(D.index >= s0 - pd.Timedelta(days=20)) & (D.index < s1)]:
        got = idx_of_day(d)
        if got is None:
            continue
        idx, levels = got
        for kind, L, top, known in levels:
            bs = 1 if top == 1 else -1
            cand = idx[m5_av[idx] > known]
            if len(cand) < 3:
                continue
            b = None
            for q in range(1, len(cand)):
                k, kp = cand[q], cand[q - 1]
                Hk = H_at(m5_av[k])
                if (C5[k] - L) * bs > 0.1 * Hk and (C5[kp] - L) * bs <= 0:
                    b = (q, Hk)
                    break
            if b is not None:
                q0, Hk = b
                ext = H5[cand[q0]] if bs > 0 else L5[cand[q0]]
                for q in range(q0 + 1, min(q0 + 25, len(cand))):
                    k = cand[q]
                    if (C5[k] - L) * bs < -0.1 * Hk:
                        side = -bs
                        i_in = int(np.searchsorted(ti, m5_av[k]))
                        if i_in < len(ti):
                            ev.append(dict(stream="RC", t_in=int(ti[i_in]), side=side, stop=ext - side * 0.25 * Hk,
                                           tgt_r=2.0, X=120, opp=False, kind=kind, H=Hk))
                        break
                    ext = max(ext, H5[k]) if bs > 0 else min(ext, L5[k])
            side = bs
            b = None
            for q in range(1, len(cand)):
                k, kp = cand[q], cand[q - 1]
                Hk = H_at(m5_av[k])
                if side < 0 and C5[k] < L - 0.1 * Hk and C5[kp] >= L:
                    b = (q, Hk)
                    break
                if side > 0 and C5[k] > L + 0.1 * Hk and C5[kp] <= L:
                    b = (q, Hk)
                    break
            if b is None:
                continue
            q0, Hk = b
            r = None
            for q in range(q0 + 1, min(q0 + 37, len(cand))):
                k = cand[q]
                if (C5[k] - L) * side < -0.75 * Hk:
                    break
                if (side < 0 and H5[k] >= L - 0.15 * Hk) or (side > 0 and L5[k] <= L + 0.15 * Hk):
                    r = q
                    break
            if r is None:
                continue
            ext = H5[cand[r]] if side < 0 else L5[cand[r]]
            lowest = L5[cand[r]] if side < 0 else H5[cand[r]]
            for q in range(r + 1, min(r + 13, len(cand))):
                k = cand[q]
                if (C5[k] - L) * side < -0.75 * Hk:
                    break
                turned = (C5[k] < lowest) if side < 0 else (C5[k] > lowest)
                if turned and (C5[k] - L) * side > -0.5 * Hk:
                    i_in = int(np.searchsorted(ti, m5_av[k]))
                    if i_in < len(ti):
                        stop = ext + 0.25 * Hk if side < 0 else ext - 0.25 * Hk
                        ev.append(dict(stream="RT_opp", t_in=int(ti[i_in]), side=side, stop=stop, tgt_r=2.0,
                                       X=120, opp=True, kind=kind, H=Hk))
                    break
                ext = max(ext, H5[k]) if side < 0 else min(ext, L5[k])
                lowest = min(lowest, L5[k]) if side < 0 else max(lowest, H5[k])

    for day in pd.bdate_range(s0 - pd.Timedelta(days=3), s1):
        t0 = (day.tz_localize(None) + pd.Timedelta(hours=13)).tz_localize(TH).tz_convert("UTC").value
        i0 = int(np.searchsorted(ti, t0))
        if i0 >= len(ti) or ti[i0] - t0 > 5 * MIN:
            continue
        j = indicators.at(h_av, np.array([t0]))[0]
        if j < 0 or not np.isfinite(atr[j]):
            continue
        H = float(atr[j])
        iL = int(np.searchsorted(ti, t0 + 15 * MIN))
        if iL <= i0 or iL >= len(ti):
            continue
        rh, rl = h[i0:iL].max(), lo[i0:iL].min()
        if rh - rl > 1.5 * H:
            continue
        i_end = int(np.searchsorted(ti, ti[iL] + 60 * MIN))
        for k in range(iL, min(i_end, len(c) - 1)):
            side = 1 if c[k] > rh else (-1 if c[k] < rl else 0)
            if side:
                ev.append(dict(stream="ORB", t_in=int(ti[k] + MIN), side=side, stop=rl if side > 0 else rh,
                               tgt_r=2.0, X=60, opp=False, kind="ORB", H=H))
                break

    E = pd.DataFrame(ev)
    a, z = pd.Timestamp(start, tz="UTC").value, pd.Timestamp(end, tz="UTC").value
    E = E[(E.t_in >= a) & (E.t_in < z)].reset_index(drop=True)
    E["win"] = [in_window(pd.Timestamp(t, tz="UTC")) for t in E.t_in]
    out = []
    for r in E.itertuples():
        i_in = int(np.searchsorted(ti, r.t_in))
        if i_in >= len(ti):
            out.append((np.nan, np.nan, "", -1))
            continue
        i_last = int(np.searchsorted(ti, ti[i_in] + r.X * MIN)) - 1
        s_0 = r.side
        e0 = o[i_in] + spr[i_in] if s_0 > 0 else o[i_in]
        dist = (e0 - r.stop) * s_0
        if not dist > 0:
            out.append((np.nan, np.nan, "", -1))
            continue
        s = -s_0 if r.opp else s_0
        e = o[i_in] + spr[i_in] if s > 0 else o[i_in]
        tg_mult = 1.0 if r.opp else r.tgt_r
        res = m1sim.trade(o, h, lo, c, spr, i_in, s, e - s * dist, e + s * tg_mult * dist, i_last)
        out.append((res[0], res[1], res[2], int(ti[res[3]] + MIN)) if res else (np.nan, np.nan, "", -1))
    E["pnl_m1"], E["risk_m1"], E["exit_m1"], E["t_exit_m1"] = zip(*out, strict=True)
    E["R_m1"] = E.pnl_m1 / E.risk_m1
    return E
