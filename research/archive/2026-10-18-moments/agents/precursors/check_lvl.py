"""A second, independent derivation of LV's decisions (pandas resampling of the raw M1, its own loops) checked against
the trades lvl.scan produced - trade by trade - and a sample of decision minutes where the conditions hold but no trade
was taken (missed signals).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_lvl.py \
        lvl_design_stall_0.5_T1.parquet stall 0.5 T1
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import jlib  # noqa: E402
from fingerprint import zigzag  # noqa: E402

M1 = jlib.m1_frame("XAUUSD")
SP = M1.spread.to_numpy(float) * 0.01 + 0.08
TFMIN = {"M1": 1, "M5": 5, "M15": 15, "M30": 30}


def buckets(rule: str) -> pd.DataFrame:
    """Complete-able bars of a timeframe with their clock end (UTC)."""
    if rule == "4h":
        loc = M1.index.tz_convert("Europe/Athens").tz_localize(None)
        key = loc.floor("4h")
        start = pd.DatetimeIndex(key).tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="shift_forward")
        start = start.tz_convert("UTC")
    else:
        start = M1.index.floor(rule)
    g = M1.assign(k=start, _t=M1.index).groupby("k")
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "last": g._t.max()})
    b["done"] = b["last"] + pd.Timedelta(minutes=1)  # complete once its last minute in the data has closed
    return b


BK = {r: buckets(r) for r in ("5min", "15min", "30min", "1h", "4h")}
for r, b in BK.items():
    e20 = b.close.ewm(span=20, adjust=False).mean()
    e50 = b.close.ewm(span=50, adjust=False).mean()
    b["trend"] = np.where((e20 > e50) & (e50 > e50.shift(3)), 1, np.where((e20 < e50) & (e50 < e50.shift(3)), -1, 0))
    tr = pd.concat([b.high - b.low, (b.high - b.close.shift()).abs(), (b.low - b.close.shift()).abs()], axis=1).max(axis=1)
    b["atr"] = tr.rolling(14).mean()
TR1 = pd.concat([M1.high - M1.low, (M1.high - M1.close.shift()).abs(), (M1.low - M1.close.shift()).abs()], axis=1)
ATR1 = TR1.max(axis=1).rolling(14).mean()
B5 = BK["5min"].reset_index()
PB, PP, PT, PC = zigzag(B5.high.to_numpy(float), B5.low.to_numpy(float), B5.atr.to_numpy(float), 2.0)
PIV = pd.DataFrame({"start": B5.k.to_numpy()[PB], "px": PP, "typ": PT, "known": B5.done.to_numpy()[PC]})


DONE = {r: pd.DatetimeIndex(b.done) for r, b in BK.items()}


def last_done(rule: str, t_dec: pd.Timestamp) -> pd.Series:
    """The last bar of the timeframe complete at t_dec (its last minute closed)."""
    return BK[rule].iloc[int(DONE[rule].searchsorted(t_dec, side="right")) - 1]


def derive(t: pd.Timestamp, k: float):
    """Everything LV decides at the close of the M1 bar opening at t, from scratch."""
    t_dec = t + pd.Timedelta(minutes=1)
    side = {last_done(r, t_dec).trend for r in ("15min", "1h", "4h")}
    side = side.pop() if len(side) == 1 else 0
    if side == 0:
        return dict(ok=False, why="trend")
    atrs = {"M1": ATR1.loc[t], "M5": last_done("5min", t_dec).atr, "M15": last_done("15min", t_dec).atr,
            "M30": last_done("30min", t_dec).atr}
    etf = next((x for x in ("M1", "M5", "M15", "M30") if np.isfinite(atrs[x]) and atrs[x] >= 5), "M30")
    a = atrs[etf]
    m5_last = last_done("5min", t_dec)
    i5 = int(np.searchsorted(B5.k.to_numpy(), m5_last.name))
    from_start = B5.k.iloc[max(i5 - 95, 0)]
    pv = PIV[(PIV.known <= t_dec) & (PIV.start >= from_start)].sort_values("start")
    price = M1.close.loc[t]
    if len(pv) < 2 or pv.typ.iloc[-1] != (-1 if side < 0 else 1):
        return dict(ok=False, why="no bounce", side=side)
    T = pv.iloc[-1]
    if (price - T.px) * -side < a:
        return dict(ok=False, why="bounce small", side=side)
    earlier = pv[pv.start < T.start]
    beyond = earlier[(earlier.px - price) * -side > 0]
    if beyond.empty:
        return dict(ok=False, why="no level", side=side)
    L = beyond.iloc[(beyond.px - price).abs().argmin()]
    closes = M1.close.iloc[int(M1.index.searchsorted(T.start)):int(M1.index.searchsorted(t, side="right"))]
    void = bool(((closes - L.px) * -side > 0.25 * a).any())
    out = dict(ok=True, side=side, etf=etf, a=a, T=T.px, L=L.px, kind="A" if L.typ == -(-1 if side < 0 else 1) else "B",
               void=void, price=price)
    if etf == "M1":
        bar = M1.loc[t]
        boundary = True
    else:
        bb = last_done({"M5": "5min", "M15": "15min", "M30": "30min"}[etf], t_dec)
        boundary = bb.done == t_dec
        bar = bb
    near = k * a
    if side < 0:
        out["stall"] = boundary and bar.high >= L.px - near and bar.close < bar.open and bar.close < L.px
    else:
        out["stall"] = boundary and bar.low <= L.px + near and bar.close > bar.open and bar.close > L.px
    return out


def exit_of(j0: int, side: int, entry: float, sl: float, tp: float, etf: str, ss: float, at_open: bool):
    o, h, lo, c = (M1[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    ot = M1.index
    stop = entry - side * sl
    armed, best = False, 0.0
    end = ot[j0] + pd.Timedelta(minutes=12 * TFMIN[etf])
    j = j0
    while j < len(o) and ot[j] < end:
        ask_h, ask_l = h[j] + SP[j], lo[j] + SP[j]
        bad = lo[j] <= stop if side > 0 else ask_h >= stop
        if bad:
            return ("be" if armed else "stop"), (stop - side * ss - entry) * side, j
        good_px = h[j] if side > 0 else ask_l
        if (j > j0 or at_open) and (good_px - entry) * side >= tp:
            return "win", tp, j
        if j > j0 or at_open:
            best = max(best, (good_px - entry) * side)
        if not armed and best >= 0.6 * tp:
            armed, stop = True, entry
        j += 1
    x = j - 1
    px = c[x] - 0.07 if side > 0 else c[x] + SP[x] + 0.07
    return "time", (px - entry) * side, x


def main() -> None:
    f, form, k, target = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    T = pd.read_parquet(HERE / f)
    rng = np.random.default_rng(3)
    sample = T.sample(min(40, len(T)), random_state=5).sort_values("t")
    bad = 0
    for r in sample.itertuples():
        d = derive(r.t, k)
        probs = []
        if not d["ok"]:
            probs.append(f"independent: no setup ({d['why']})")
        else:
            if d["side"] != r.side:
                probs.append(f"side {d['side']} vs {r.side}")
            if d["etf"] != r.etf:
                probs.append(f"etf {d['etf']} vs {r.etf}")
            if abs(d["a"] - r.atr) > 1e-6:
                probs.append(f"atr {d['a']:.4f} vs {r.atr:.4f}")
            if abs(d["T"] - r.start) > 1e-6 or abs(d["L"] - r.level) > 1e-6 or d["kind"] != r.lkind:
                probs.append(f"T/L {d['T']}/{d['L']}{d['kind']} vs {r.start}/{r.level}{r.lkind}")
            if d["void"]:
                probs.append("independent: the level was voided")
            if form == "stall" and not d["stall"]:
                probs.append("independent: no stall bar")
        j0 = int(r.j0)
        if form == "stall":
            exp_entry = M1.open.iloc[j0] - 0.07 if r.side < 0 else M1.open.iloc[j0] + SP[j0] + 0.07
            if M1.index[j0] <= r.t or (j0 > 0 and M1.index[j0 - 1] != r.t):
                probs.append("entry bar is not the next bar")
            at_open = True
        else:
            # the limit from scratch: L -/+ k x ATR, live 60 minutes from the decision, cancelled by the start
            exp_entry, exp_j = np.nan, -1
            if d["ok"]:
                lim = d["L"] + d["side"] * k * d["a"]
                end = r.t + pd.Timedelta(minutes=61)
                for j in range(int(np.searchsorted(M1.index, r.t)) + 1, len(M1)):
                    if M1.index[j] >= end:
                        break
                    if d["side"] < 0:
                        if M1.low.iloc[j] < d["T"]:
                            break
                        if M1.high.iloc[j] >= lim:
                            exp_entry, exp_j = max(lim, M1.open.iloc[j]), j
                            break
                    else:
                        if M1.high.iloc[j] + SP[j] > d["T"]:
                            break
                        if M1.low.iloc[j] + SP[j] <= lim:
                            exp_entry, exp_j = min(lim, M1.open.iloc[j] + SP[j]), j
                            break
            if exp_j != j0:
                probs.append(f"fill bar {exp_j} vs {j0}")
            at_open = r.entry == (M1.open.iloc[j0] if r.side < 0 else M1.open.iloc[j0] + SP[j0])
        if abs(exp_entry - r.entry) > 1e-6:
            probs.append(f"entry {exp_entry} vs {r.entry}")
        ss = 0.15 if abs(r.pnl / (r.sl + 0.15) - r.R) < 1e-9 else 0.20
        ex, pnl, xj = exit_of(j0, int(r.side), r.entry, r.sl, r.tp, r.etf, ss, at_open)
        if ex != r.exit or abs(pnl - r.pnl) > 1e-6 or xj != r.xj:
            probs.append(f"exit {ex} {pnl:.3f} @{xj} vs {r.exit} {r.pnl:.3f} @{r.xj}")
        if probs:
            bad += 1
            print(f"MISMATCH {r.t} side {r.side}: " + "; ".join(probs))
    print(f"\nchecked {len(sample)} trades of {len(T)}: {bad} with a mismatch")
    # missed or extra signals (stall form): every decision minute of 30 random days, in time order, the independent
    # rule with its own "level used once per bounce" bookkeeping; minutes inside a trade of T are skipped as LV does
    if form == "stall":
        import plib  # noqa: PLC0415

        W = plib.window_mask(M1.index)
        inwin = W.any(axis=1).to_numpy() & (M1.index >= T.t.min()) & (M1.index <= T.t.max())
        days = pd.Series(M1.index[inwin].normalize()).unique()
        pick = rng.choice(days, size=min(30, len(days)), replace=False)
        busy = np.zeros(len(M1), bool)
        for r in T.itertuples():
            busy[int(np.searchsorted(M1.index, r.t)) + 1:int(r.xj) + 1] = True
        taken = set(T.t)
        used: set = set()
        exp_n = got_n = miss = extra = 0
        for day in sorted(pick):
            idx = np.nonzero(inwin & (M1.index.normalize() == day))[0]
            for i in idx:
                t = M1.index[i]
                if busy[i]:
                    continue
                d = derive(t, k)
                fire = False
                if d["ok"]:
                    key = (d["T"], round(d["L"], 2), d["side"])
                    if key not in used:
                        if d["void"]:
                            used.add(key)
                        elif d["stall"]:
                            used.add(key)
                            fire = True
                exp_n += fire
                got_n += t in taken
                if fire and t not in taken:
                    miss += 1
                    print(f"MISSED {t} side {d['side']} T {d['T']} L {d['L']}", flush=True)
                if t in taken and not fire:
                    extra += 1
                    print(f"EXTRA {t}: LV traded, the independent rule did not ({d.get('why', '')})", flush=True)
        print(f"30 days, every decision minute: independent signals {exp_n}, LV trades {got_n}, missed {miss}, extra {extra}")


if __name__ == "__main__":
    main()
