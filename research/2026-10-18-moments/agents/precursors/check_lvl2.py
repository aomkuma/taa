"""Layer 4 for LV2: an independent re-derivation of each sampled trade from the raw M1 with pandas (its own resampling,
its own fractals and zones, its own walk through the trade), checked field by field against lvl2's output.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_lvl2.py \
        lvl2_design_k0.5_all_T1_p80.parquet lvl2_signals_k0.5_all.parquet 0.5 all T1 80
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
if len(sys.argv) > 1 and sys.argv[1] in ("verify", "verify3"):  # the same short slice lvl2 is given (identical EMA / ATR history)
    M1 = M1[(M1.index >= pd.Timestamp(sys.argv[2], tz="UTC")) & (M1.index < pd.Timestamp(sys.argv[3], tz="UTC"))]
SP = M1.spread.to_numpy(float) * 0.01 + 0.08
LAD = ["M1", "M5", "M15", "M30", "H1", "H4"]
RULE = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
MINS = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}


def bars(tf: str) -> pd.DataFrame:
    if tf == "M1":
        b = M1[["open", "high", "low", "close"]].copy()
        b["start"] = M1.index
        b["done"] = M1.index + pd.Timedelta(minutes=1)
        return b.reset_index(drop=True)
    if tf == "H4":
        loc = M1.index.tz_convert("Europe/Athens").tz_localize(None).floor("4h")
        key = pd.DatetimeIndex(loc).tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
    else:
        key = M1.index.floor(RULE[tf])
    g = M1.assign(k=key, _t=M1.index).groupby("k")
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                      "done": g._t.max() + pd.Timedelta(minutes=1)})
    b["start"] = b.index
    return b.reset_index(drop=True)


B = {tf: bars(tf) for tf in LAD}
for tf, b in B.items():
    e20 = b.close.ewm(span=20, adjust=False).mean()
    e50 = b.close.ewm(span=50, adjust=False).mean()
    b["trend"] = np.where((e20 > e50) & (e50 > e50.shift(3)), 1, np.where((e20 < e50) & (e50 < e50.shift(3)), -1, 0))
    tr = pd.concat([b.high - b.low, (b.high - b.close.shift()).abs(), (b.low - b.close.shift()).abs()], axis=1).max(axis=1)
    b["atr"] = tr.rolling(14).mean()
ZZ = {}
for tf in ("M1", "M5", "M15", "M30"):
    b = B[tf]
    pb, pp, pt, pc = zigzag(b.high.to_numpy(float), b.low.to_numpy(float), b.atr.to_numpy(float), 2.0)
    ZZ[tf] = pd.DataFrame({"start": b.start.to_numpy()[pb], "px": pp, "typ": pt, "known": b.done.to_numpy()[pc]})
FR = {}
for tf in ("M15", "M30", "H1"):
    b = B[tf]
    hi, lo = b.high, b.low
    is_ph = (hi == hi.rolling(5, center=True).max())  # a 5-bar fractal high (2 bars each side)
    is_pl = (lo == lo.rolling(5, center=True).min())
    rows = []
    for i in np.nonzero(is_ph.to_numpy())[0]:
        if i + 2 < len(b):
            rows.append((b.start.iloc[i], hi.iloc[i], 1, b.done.iloc[i + 2], i))
    for i in np.nonzero(is_pl.to_numpy())[0]:
        if i + 2 < len(b):
            rows.append((b.start.iloc[i], lo.iloc[i], -1, b.done.iloc[i + 2], i))
    FR[tf] = pd.DataFrame(rows, columns=["start", "px", "typ", "known", "bar"])


def last(tf: str, t_dec: pd.Timestamp) -> pd.Series:
    b = B[tf]
    return b.iloc[int(b.done.searchsorted(t_dec, side="right")) - 1]


def derive(t: pd.Timestamp, k: float, important: bool) -> dict:
    t_dec = t + pd.Timedelta(minutes=1)
    atrs = {tf: last(tf, t_dec).atr for tf in ("M1", "M5", "M15", "M30")}
    etf = next((x for x in ("M1", "M5", "M15", "M30") if np.isfinite(atrs[x]) and atrs[x] >= 5), "M30")
    a = atrs[etf]
    signs = {last(tf, t_dec).trend for tf in LAD[LAD.index(etf) + 1:]}
    if len(signs) != 1 or 0 in signs:
        return dict(ok=False, why="trend")
    side = signs.pop()
    zz = ZZ[etf][ZZ[etf].known <= t_dec]
    if zz.empty or zz.typ.iloc[-1] != (-1 if side < 0 else 1):
        return dict(ok=False, why="no bounce")
    T = zz.iloc[-1]
    price = M1.close.loc[t]
    if (price - T.px) * -side < a:
        return dict(ok=False, why="small bounce")
    lt = [x for x in ("M15", "M30", "H1") if LAD.index(x) > LAD.index(etf)]
    parts = []
    for tf in lt:
        f = FR[tf]
        i_last = int(B[tf].done.searchsorted(t_dec, side="right")) - 1
        f = f[(f.known <= t_dec) & (f.bar >= i_last - 119) & (f.start < T.start)]
        parts.append(f.assign(tf=tf))
    P = pd.concat(parts).sort_values("px")
    tol = 0.25 * last(lt[-1], t_dec).atr
    zones, cur = [], []
    for r in P.itertuples():
        if cur and r.px - cur[0].px > tol:
            zones.append(cur)
            cur = []
        cur.append(r)
    if cur:
        zones.append(cur)
    Z = [(np.mean([r.px for r in z]), max(sum(r.tf == lt[0] for r in z), 1), any(r.tf == "H1" for r in z)) for z in zones]
    cand = [z for z in Z if (z[0] - price) * -side > 0 and (not important or z[1] >= 2 or z[2])]
    if not cand:
        return dict(ok=False, why="no level")
    L = min(cand, key=lambda z: abs(z[0] - price))
    return dict(ok=True, side=side, etf=etf, a=a, T=T.px, L=L[0], swings=L[1], h1=L[2])


def walk(j0: int, side: int, entry: float, sl: float, tp: float, level: float, etf: str, ss: float) -> tuple:
    o, h, lo, c = (M1[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    ot = M1.index
    E = B[etf]
    closes = dict(zip(E.done, E.close))
    stop, armed, best = entry - side * sl, False, 0.0
    end = ot[j0] + pd.Timedelta(minutes=12 * MINS[etf])
    j = j0
    while j < len(o) and ot[j] < end:
        if (lo[j] <= stop) if side > 0 else (h[j] + SP[j] >= stop):
            return ("be" if armed else "stop"), (stop - side * ss - entry) * side, j
        g = h[j] if side > 0 else lo[j] + SP[j]
        if (g - entry) * side >= tp:
            return "win", tp, j
        best = max(best, (g - entry) * side)
        if not armed and best >= 0.6 * tp:
            armed, stop = True, entry
        cl = closes.get(ot[j] + pd.Timedelta(minutes=1))
        if cl is not None and (cl - level) * -side > 0 and j + 1 < len(o):
            px = o[j + 1] + SP[j + 1] + 0.07 if side < 0 else o[j + 1] - 0.07
            return "close", (px - entry) * side, j + 1
        j += 1
    x = j - 1
    px = c[x] - 0.07 if side > 0 else c[x] + SP[x] + 0.07
    return "time", (px - entry) * side, x


def verify() -> None:
    """lvl2 and this file on the same slice: every signal of every decision minute, and every trade, must agree."""
    import plib  # noqa: PLC0415

    import lvl2  # noqa: PLC0415

    sig_from = pd.Timestamp(sys.argv[4], tz="UTC")
    k, imp, target, p = 0.5, sys.argv[5] == "important", sys.argv[6], float(sys.argv[7])
    M = lvl2.Market(M1, SP)
    win = plib.window_mask(M1.index).any(axis=1).to_numpy()
    dec = np.nonzero(win & np.asarray(M1.index >= sig_from))[0]
    S = lvl2.signals(M, dec, lvl2.Params(k=k, important=imp))
    T = lvl2.trades(M, S, lvl2.Params(k=k, important=imp, target=target, p=p), np.zeros(len(M1), bool))
    print(f"lvl2 on the slice: {len(S)} signals, {len(T)} trades", flush=True)
    # 1. every decision minute, independently, in time order with "once per (ETF, start, level, side)"
    used, fired = set(), []
    for i in dec:
        t = M1.index[i]
        if i + 1 >= len(M1):
            continue
        d = derive(t, k, imp)
        if not d["ok"]:
            continue
        zz = ZZ[d["etf"]][ZZ[d["etf"]].known <= t + pd.Timedelta(minutes=1)]
        key = (d["etf"], zz.start.iloc[-1], round(d["L"], 2), d["side"])
        if key in used:
            continue
        bar = last(d["etf"], t + pd.Timedelta(minutes=1))
        if bar.done != t + pd.Timedelta(minutes=1):
            continue
        near = k * d["a"]
        if d["side"] < 0:
            ok = bar.high >= d["L"] - near and bar.close < bar.open and bar.close < d["L"]
        else:
            ok = bar.low <= d["L"] + near and bar.close > bar.open and bar.close > d["L"]
        if ok:
            used.add(key)
            fired.append(i)
    mine, theirs = set(fired), set(S.t.astype(int))
    print(f"signals: independent {len(mine)}, lvl2 {len(theirs)}, only independent {len(mine - theirs)}, only lvl2 {len(theirs - mine)}")
    for i in sorted(mine ^ theirs)[:10]:
        print("  differs at", M1.index[i])
    # 2. every trade
    bad = 0
    for r in T.itertuples():
        d = derive(r.t, k, imp)
        probs = []
        if not d["ok"] or d["side"] != r.side or d["etf"] != r.etf or abs(d["T"] - r.start) > 1e-9                 or abs(d["L"] - r.level) > 1e-9 or abs(d["a"] - r.atr) > 1e-9:
            probs.append(f"setup {d}")
        s = S[S.j0 == r.j0].iloc[0]
        earlier = S[(S.resolved <= s.t_ns) & S.won]
        if abs(np.percentile(earlier.over_A, p) - r.b) > 1e-9:
            probs.append("learned buffer")
        ex, pnl, xj = walk(int(r.j0), int(r.side), r.entry, r.sl, r.tp, r.level, r.etf, 0.15)
        if ex != r.exit or abs(pnl - r.pnl) > 1e-6 or xj != r.xj:
            probs.append(f"exit {ex} {pnl:.3f} @{xj} vs {r.exit} {r.pnl:.3f} @{r.xj}")
        if probs:
            bad += 1
            print(f"MISMATCH {r.t}: " + "; ".join(probs))
    print(f"trades: {len(T)} checked, {bad} with a mismatch")


def verify3() -> None:
    """LV3 on a slice: the legs entry re-derived independently (own M1 swings at s x ATR, own pause count) at every
    decision minute, against lvl3.signals; then every trade."""
    import plib  # noqa: PLC0415

    import lvl2  # noqa: PLC0415
    import lvl3  # noqa: PLC0415

    sig_from = pd.Timestamp(sys.argv[4], tz="UTC")
    s_, n_, target, p = float(sys.argv[5]), int(sys.argv[6]), sys.argv[7], float(sys.argv[8])
    # a code test on a short slice may lower the learned stop's history (both sides alike), so trades exist
    mh = int(sys.argv[9]) if len(sys.argv) > 9 else 30
    M = lvl3.Market(M1, SP)
    win = plib.window_mask(M1.index).any(axis=1).to_numpy()
    dec = np.nonzero(win & np.asarray(M1.index >= sig_from))[0]
    S = lvl3.signals(M, dec, lvl3.Params(k=0.5, s=s_, n=n_, min_history=mh))
    T = lvl2.trades(M, S, lvl3.Params(k=0.5, s=s_, n=n_, target=target, p=p, min_history=mh), np.zeros(len(M1), bool))
    print(f"lvl3 on the slice: {len(S)} signals, {len(T)} trades; legs {S.legs.value_counts().to_dict() if len(S) else {}}")
    b = B["M1"]
    zb, zp, zt, zc = zigzag(b.high.to_numpy(float), b.low.to_numpy(float), b.atr.to_numpy(float), s_)
    conf = {int(c): i for i, c in enumerate(zc)}
    used, fired = set(), []
    for i in dec:
        if i + 1 >= len(M1) or i not in conf:
            continue
        q = conf[i]
        t = M1.index[i]
        d = derive(t, 0.5, False)
        if not d["ok"]:
            continue
        zz = ZZ[d["etf"]][ZZ[d["etf"]].known <= t + pd.Timedelta(minutes=1)]
        t_start = zz.start.iloc[-1]
        want = 1 if d["side"] < 0 else -1
        if zt[q] != want:
            continue
        key = (d["etf"], t_start, round(d["L"], 2), d["side"])
        if key in used:
            continue
        # the minute of the start's extreme inside its entry-TF bar, found independently from the raw M1
        seg = M1[(M1.index >= t_start) & (M1.index < t_start + pd.Timedelta(minutes=MINS[d["etf"]]))]
        col = seg.high if d["side"] > 0 else seg.low
        t_ext = col.index[np.isclose(col.to_numpy(), d["T"])][0] if np.isclose(col.to_numpy(), d["T"]).any() else t_start
        px = [zp[j] for j in range(q + 1) if zt[j] == want and b.start.iloc[zb[j]] >= t_ext]
        if not px:
            continue
        ext = max(px) if d["side"] < 0 else min(px)
        last_ext = max(j for j, v in enumerate(px) if v == ext)
        legs = px[last_ext:]
        if n_ > 0:
            need = n_
        else:
            E = ZZ[d["etf"]]
            k_ = int(E.known.searchsorted(t + pd.Timedelta(minutes=1), side="right")) - 1
            move = abs(E.px.iloc[k_] - E.px.iloc[k_ - 1]) / d["a"] if k_ >= 1 else 0.0
            need = 3 if move < 5 else 5
        near = 0.5 * d["a"]
        newest = legs[-1]
        ok = len(legs) >= max(need, 2) and ((newest < ext and ext >= d["L"] - near) if d["side"] < 0
                                            else (newest > ext and ext <= d["L"] + near))
        if ok:
            used.add(key)
            fired.append(i)
    mine, theirs = set(fired), set(S.t.astype(int))
    print(f"signals: independent {len(mine)}, lvl3 {len(theirs)}, only independent {len(mine - theirs)}, only lvl3 {len(theirs - mine)}")
    for i in sorted(mine ^ theirs)[:10]:
        print("  differs at", M1.index[i])
    bad = 0
    for r in T.itertuples():
        ex, pnl, xj = walk(int(r.j0), int(r.side), r.entry, r.sl, r.tp, r.level, r.etf, 0.15)
        s = S[S.j0 == r.j0].iloc[0]
        earlier = S[(S.resolved <= s.t_ns) & S.won]
        probs = []
        if len(earlier) < mh:
            probs.append(f"traded with {len(earlier)} earlier winners (< {mh})")
        elif abs(np.percentile(earlier.over_A, p) - r.b) > 1e-9:
            probs.append("learned buffer")
        if ex != r.exit or abs(pnl - r.pnl) > 1e-6 or xj != r.xj:
            probs.append(f"exit {ex} {pnl:.3f} @{xj} vs {r.exit} {r.pnl:.3f} @{r.xj}")
        if probs:
            bad += 1
            print(f"MISMATCH {r.t}: " + "; ".join(probs))
    print(f"trades: {len(T)} checked, {bad} with a mismatch")


def main() -> None:
    if sys.argv[1] == "verify":
        verify()
        return
    if sys.argv[1] == "verify3":
        verify3()
        return
    tf_, sf, k, lev, _target, p = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5], float(sys.argv[6])
    T = pd.read_parquet(HERE / tf_)
    S = pd.read_parquet(HERE / sf)
    sample = T.sample(min(40, len(T)), random_state=9).sort_values("t")
    bad = 0
    for r in sample.itertuples():
        d = derive(r.t, k, lev == "important")
        probs = []
        if not d["ok"]:
            probs.append(f"no setup independently ({d['why']})")
        else:
            for name, mine, theirs in (("side", d["side"], r.side), ("etf", d["etf"], r.etf)):
                if mine != theirs:
                    probs.append(f"{name} {mine} vs {theirs}")
            for name, mine, theirs in (("atr", d["a"], r.atr), ("start", d["T"], r.start), ("level", d["L"], r.level)):
                if abs(mine - theirs) > 1e-6:
                    probs.append(f"{name} {mine:.4f} vs {theirs:.4f}")
            if d["swings"] != r.swings or d["h1"] != r.has_h1:
                probs.append(f"importance {d['swings']}/{d['h1']} vs {r.swings}/{r.has_h1}")
        # the learned buffer from the signal table, recomputed
        s = S[S.j0 == r.j0].iloc[0]
        earlier = S[(S.resolved <= s.t_ns) & S.won]
        if abs(np.percentile(earlier.over_A, p) - r.b) > 1e-9:
            probs.append("learned buffer differs")
        exp_entry = M1.open.iloc[r.j0] - 0.07 if r.side < 0 else M1.open.iloc[r.j0] + SP[r.j0] + 0.07
        if abs(exp_entry - r.entry) > 1e-9:
            probs.append(f"entry {exp_entry} vs {r.entry}")
        ss = 0.15 if abs(r.pnl / (r.sl + 0.15) - r.R) < 1e-9 else 0.20
        ex, pnl, xj = walk(int(r.j0), int(r.side), r.entry, r.sl, r.tp, r.level, r.etf, ss)
        if ex != r.exit or abs(pnl - r.pnl) > 1e-6 or xj != r.xj:
            probs.append(f"exit {ex} {pnl:.3f} @{xj} vs {r.exit} {r.pnl:.3f} @{r.xj}")
        if probs:
            bad += 1
            print(f"MISMATCH {r.t}: " + "; ".join(probs), flush=True)
    print(f"checked {len(sample)} of {len(T)} trades: {bad} with a mismatch")


if __name__ == "__main__":
    main()
