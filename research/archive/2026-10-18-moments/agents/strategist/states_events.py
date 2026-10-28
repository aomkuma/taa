"""Row 45, step 1 - the events of the three leads over O1 .. P2 and their trades, spread only (written before
computing; the pre-registration is at the top of PROPOSALS.md).

- ORB: PLAN-1's London piece (13:00 Thai = 06:00 UTC; the range of the M1 bars 06:00-06:14; skip if wider than 1.5 x
  the H1 ATR(14); the first M1 close beyond it from 06:15 for 60 minutes; the entry at that bar's close; the stop at
  the other side; 2 R; out 60 minutes after the entry).
- RC: reclaim.py's events (the break of PDH / PDL / ASH / ASL by an M5 close 0.1 H past it, then within 24 M5 bars an
  M5 close back inside by 0.1 H -> back into the range; the stop 0.25 H past the break's extreme; 2 R; 120 minutes).
- RT_opp: rt_old.py's events (retest.py's break / retest / turn) taken the other way: the stop at the rule's own stop
  distance from its own fill, the target 1 R, 120 minutes.
- The breaks (for the reading fail20): every break of reclaim.py's definition, with the time its outcome is settled
  (the reclaim bar's close if it failed, else the close of the 24th M5 bar after the break) and whether it failed.

The trades: m1sim (M1 spread only, slippage 0) in every period; tsim.grid (the tick bid / ask, slippage 0) where the
ticks exist (P1 / P2; tsim refuses the exam). Output: states_events.parquet, states_breaks.parquet.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/states_events.py > .../out_states_events.txt
"""

from __future__ import annotations

import os

os.environ["STRAT_START"] = "2023-09-01"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import m1sim  # noqa: E402
import slib  # noqa: E402
import tsim  # noqa: E402
from retest import C5, D, H5, L5, MIN, atr, c, h, h_av, idx_of_day, in_window, indicators, lo, m5_av, o, spr, ti  # noqa: E402

tsim.idle()
PER = [("O1", "2023-10-18", "2024-10-18"), ("O2", "2024-10-18", "2025-10-18"), ("P1", "2025-10-18", "2026-01-16"),
       ("P2", "2026-01-16", "2026-04-18")]
assert ti.max() < slib.EXAM_START.value


def label(t_ns: int) -> str:
    for k, a, b in PER:
        if pd.Timestamp(a, tz="UTC").value <= t_ns < pd.Timestamp(b, tz="UTC").value:
            return k
    return ""


def H_at(t_ns: int) -> float:
    return float(atr[indicators.at(h_av, np.array([t_ns]))[0]])


ev, brk = [], []
days = D.index[(D.index >= pd.Timestamp("2023-10-01")) & (D.index < pd.Timestamp("2026-04-18"))]
for d in days:
    got = idx_of_day(d)
    if got is None:
        continue
    idx, levels = got
    for kind, L, top, known in levels:
        bs = 1 if top == 1 else -1  # the way the level breaks
        cand = idx[m5_av[idx] > known]
        if len(cand) < 3:
            continue
        # --- reclaim.py: the break, then the close back inside ---
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
            failed, settle = False, m5_av[cand[min(q0 + 24, len(cand) - 1)]]
            for q in range(q0 + 1, min(q0 + 25, len(cand))):
                k = cand[q]
                if (C5[k] - L) * bs < -0.1 * Hk:
                    failed, settle = True, m5_av[k]
                    side = -bs
                    i_in = int(np.searchsorted(ti, m5_av[k]))
                    if i_in < len(ti):
                        ev.append(dict(stream="RC", t_in=int(ti[i_in]), side=side, stop=ext - side * 0.25 * Hk,
                                       tgt_r=2.0, X=120, opp=False, kind=kind, H=Hk))
                    break
                ext = max(ext, H5[k]) if bs > 0 else min(ext, L5[k])
            brk.append(dict(t_break=int(m5_av[cand[q0]]), t_settle=int(settle), failed=failed, kind=kind))
        # --- retest.py / rt_old.py: the break, the retest, the turn (side = the break's way) ---
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

# --- ORB 13:00 Thai ---
for day in pd.bdate_range("2023-10-18", "2026-04-17"):
    t0 = (day.tz_localize(None) + pd.Timedelta(hours=13)).tz_localize(slib.TH).tz_convert("UTC").value
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
E["part"] = [label(t) for t in E.t_in]
E = E[E.part != ""].reset_index(drop=True)
E["win"] = [in_window(pd.Timestamp(t, tz="UTC")) for t in E.t_in]

# --- the M1 trades (spread only) ---
out = []
for r in E.itertuples():
    i_in = int(np.searchsorted(ti, r.t_in))  # the bar opening at the decision close
    if i_in >= len(ti):
        out.append((np.nan, np.nan, "", -1))
        continue
    i_last = int(np.searchsorted(ti, ti[i_in] + r.X * MIN)) - 1
    s0 = r.side
    e0 = o[i_in] + spr[i_in] if s0 > 0 else o[i_in]
    dist = (e0 - r.stop) * s0
    if not dist > 0:
        out.append((np.nan, np.nan, "", -1))
        continue
    s = -s0 if r.opp else s0
    e = o[i_in] + spr[i_in] if s > 0 else o[i_in]
    tg_mult = 1.0 if r.opp else r.tgt_r  # RT_opp: x0.5 of the 2 R target = 1 R
    res = m1sim.trade(o, h, lo, c, spr, i_in, s, e - s * dist, e + s * tg_mult * dist, i_last)
    out.append((res[0], res[1], res[2], int(ti[res[3]] + MIN)) if res else (np.nan, np.nan, "", -1))
E["pnl_m1"], E["risk_m1"], E["exit_m1"], E["t_exit_m1"] = zip(*out, strict=True)
E["R_m1"] = E.pnl_m1 / E.risk_m1

# --- the tick trades, P1 / P2 ---
tk = tsim.Ticks()
tr = {}
for r in E[E.part.isin(["P1", "P2"])].sort_values("t_in").itertuples():
    sp = tk.span(int(r.t_in))
    if sp is None:
        continue
    g = tsim.grid(*sp, int(r.t_in), int(r.side), float(r.stop), np.nan, int(r.t_in + r.X * MIN),
                  sides=("opp" if r.opp else "same",), stops=(1.0,), targets=(0.5 if r.opp else "orig",), tgt_r=2.0)
    if g:
        tr[r.Index] = (g[0]["pnl"], g[0]["risk"], g[0]["R"], g[0]["exit"], g[0]["exit_t"])
for k, col in enumerate(("pnl_tk", "risk_tk", "R_tk", "exit_tk", "t_exit_tk")):
    E[col] = [tr[i][k] if i in tr else (np.nan if k != 3 else "") for i in E.index]
# the result each period is judged on: the ticks for P1 / P2, M1 for O1 / O2
tick_part = E.part.isin(["P1", "P2"]).to_numpy()
E["R"] = np.where(tick_part, E.R_tk, E.R_m1)
E["pnl"] = np.where(tick_part, E.pnl_tk, E.pnl_m1)
E["t_exit"] = np.where(tick_part, E.t_exit_tk, E.t_exit_m1)
E.to_parquet(slib.HERE / "states_events.parquet")
B = pd.DataFrame(brk)
B.to_parquet(slib.HERE / "states_breaks.parquet")

print(f"breaks {len(B)} (failed share {B.failed.mean():.2f})")
for st in ("ORB", "RC", "RT_opp"):
    for scope in (["all"] if st != "RC" else ["all", "windows"]):
        g = E[E.stream == st]
        if scope == "windows":
            g = g[g.win != "other"]
        print(f"{st:7s} {scope:7s} " + " | ".join(
            f"{p} n {g[g.part == p].R.notna().sum():3d} R {g[g.part == p].R.mean():+.3f}" for p, _, _ in PER)
            + "   M1 in P1 / P2: " + " / ".join(f"{g[g.part == p].R_m1.mean():+.3f}" for p in ("P1", "P2")))
