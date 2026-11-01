"""REFERENCE for eye/ZONE_RULES.md - the prototype the run-zone measurements of 2026-11-01 came from (copied from
eye/wip/zones_2026-11-01/system_long.py). A build of eye/zone_bot.py must reproduce its trades; where this file and
ZONE_RULES.md differ, ZONE_RULES.md wins and the difference is reported.

The run-zone system end to end, for long tests - a simulation on stored bars, no orders.

All of it as decided on 2026-11-01 (METHOD 2e "The run zones"; eye/BOT_RESEARCH.md for every form):
  step S     - fixed (ZS=76) or the median D1 range of the 60 trading days before each month (ZS=range); a grid keeps the
               step it was made with and is remade at a month start when the month's step differs by more than 20 %.
  zones      - v8: two neighbouring fixed H4 ZigZag (12/5/3) turns 1, 2 or 3 steps apart (+-0.1 S) -> anchor = the
               lower turn, lines A + k*S; a new grid when the anchor is more than S/5 off the current lines.
  visit      - an H1 bar comes within Z = S*10/76 of a line after price was at least S/2 away from it.
  momentum   - skip: one of the 3 closed H1 bars before has a body toward the line >= the median H1 range (120 bars),
               or the last 6 H1 bars ran S toward the line.
  state gate - trade only when the weighted share of D1 / H4 / H1 / M15 that are sideways (last two ZigZag highs and
               lows do not agree) is over 0.25 (weights .4 / .3 / .2 / .1).
  setup (C)  - P1 limit S*10/76 before the line, P2 limit S*15/76 into the fake break, SL S/2 past the line for both, TP
               one step (the opposite edge); before the first fill the orders are cancelled when price ran S/3 toward
               the line over the last hour (closed bars, and up to the fill price). Fills / exits on the EXEC frame,
               bid bars + spread, SL first in a bar holding both, one setup at a time.
Usage: ZSTART ZEND ZS (76 | range) ZEXEC (M5 | M15) ZTAG.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "C:/Users/korap/taa")
from app.indicators.chart_read import zigzag_pivots  # noqa: E402

HERE = Path(__file__).resolve().parent
D = "C:/Users/korap/taa/data/history/FBS-Demo/XAUUSD"
TH = "Asia/Bangkok"
PT = json.load(open(f"{D}/spec.json"))["spec"]["point"]
START = pd.Timestamp(os.environ.get("ZSTART", "2025-11-01"), tz=TH)
END = pd.Timestamp(os.environ.get("ZEND", "2026-11-01"), tz=TH)
SMODE = os.environ.get("ZS", "76")
EXEC = os.environ.get("ZEXEC", "M5")
TAG = os.environ.get("ZTAG", f"{EXEC}_{SMODE}_{START:%Y%m}")
PER_H = {"M5": 12, "M15": 4}[EXEC]
W = {"D1": 0.4, "H4": 0.3, "H1": 0.2, "M15": 0.1}
FIX = os.environ.get("ZFIX", "1") == "1"  # 1 = v2 (Sol's review, 2026-11-01); 0 = the behaviour every number before it came from


def load(tf):
    df = pd.read_parquet(f"{D}/{tf}.parquet")
    df["th"] = pd.to_datetime(df.open_time, utc=True).dt.tz_convert(TH)
    df["ct"] = pd.to_datetime(df.close_time, utc=True).dt.tz_convert(TH)
    return df.sort_values("th").reset_index(drop=True)


d1, h4, h1, m15 = load("D1"), load("H4"), load("H1"), load("M15")
ex = load(EXEC) if EXEC != "M15" else m15
d1["r"] = d1.high - d1.low

# the step by month
_m0 = (h4.th.iloc[0].tz_localize(None) if FIX else START.tz_localize(None)) - pd.offsets.MonthBegin(1)
months = pd.date_range(_m0, END.tz_localize(None), freq="MS").tz_localize(TH)
# weekly ATR(14) (MT5's: a simple mean of the true range), weeks built from D1 in broker time - matches the owner's
# screen (195.99 on the week of 25/10/2026)
_d = d1.copy()
_d["ts"] = pd.to_datetime(_d.time_server, unit="s")
wk = _d.set_index("ts").resample("W-SUN", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
wk["tr"] = pd.concat([wk.high - wk.low, (wk.high - wk.close.shift()).abs(), (wk.low - wk.close.shift()).abs()], axis=1).max(axis=1)
wk["atr"] = wk.tr.rolling(14).mean()
wk["done"] = (wk.index + pd.Timedelta(days=7)).tz_localize("UTC").tz_convert(TH)  # about when the week has closed


def watr(t):
    w = wk[(wk.done <= t) & wk.atr.notna()]
    return float(w.atr.iloc[-1])


S_OF = {}
for mstart in months:
    if SMODE.startswith("watr"):
        S_OF[mstart.strftime("%Y-%m")] = float(SMODE[4:]) * watr(mstart)
        continue
    S_OF[mstart.strftime("%Y-%m")] = float(d1[d1.ct <= mstart].tail(60).r.median()) if SMODE == "range" else float(SMODE)


def s_at(t):
    return S_OF.get(t.strftime("%Y-%m"), 76.0)


# zones
zz4 = zigzag_pivots(h4.high.to_numpy(float), h4.low.to_numpy(float), PT)


def off(p, a, st):
    return min((p - a) % st, st - (p - a) % st)


grids = []  # (from, anchor, step)
events = [(h4.ct[b.confirm_pos], "pair", (a, b)) for a, b in zip(zz4, zz4[1:])] + [(m, "month", None) for m in months]
events.sort(key=lambda e: e[0])
for t, kind, pr in events:
    if t >= END:
        break
    st = s_at(t)
    if kind == "pair":
        a, b = pr
        dd = abs(a.price - b.price)
        if not any(abs(dd - k * st) <= 0.1 * st for k in (1, 2, 3)):
            continue
        lo = min(a.price, b.price)
        if not grids or off(lo, grids[-1][1], grids[-1][2]) > 0.2 * grids[-1][2] or abs(st - grids[-1][2]) > 0.2 * grids[-1][2]:
            grids.append((t, lo, st))
    elif grids and abs(st - grids[-1][2]) > 0.2 * grids[-1][2]:
        grids.append((t, grids[-1][1], st))
gt = np.array([g[0].value for g in grids])


def grid_at(t):
    k = int(np.searchsorted(gt, t.value, side="right")) - 1
    return grids[k] if k >= 0 else None


# the state gate
PIV = {}
for tf, df in (("D1", d1), ("H4", h4), ("H1", h1), ("M15", m15)):
    z = zigzag_pivots(df.high.to_numpy(float), df.low.to_numpy(float), PT)
    PIV[tf] = (np.array([df.ct[p.confirm_pos].value for p in z]), np.array([p.kind.name for p in z]), np.array([p.price for p in z]))


def side_share(t):
    tot = 0.0
    for tf, w in W.items():
        ct, kd, pr = PIV[tf]
        m = ct <= t.value
        hs, ls = pr[m & (kd == "HIGH")][-2:], pr[m & (kd == "LOW")][-2:]
        trend = len(hs) == 2 and len(ls) == 2 and ((hs[1] > hs[0] and ls[1] > ls[0]) or (hs[1] < hs[0] and ls[1] < ls[0]))
        tot += 0 if trend else w
    return tot


ER_MAX = float(os.environ.get("ZER", "1"))
# the owner: "the day frame is too slow - use a smaller frame and measure volatility, or price far away, much more
# than normal; it should tell at once that this is not a state for a zone setup". On H1, against the 60 days before:
#   A - the high-low of the last 24 H1 bars / its median;   B - |close - EMA50| / its median.   Skip at >= ABN.
ABN = float(os.environ.get("ZABN", "0"))
ABN_KIND = os.environ.get("ZABNK", "A")
_rng24 = (h1.high.rolling(24).max() - h1.low.rolling(24).min()).to_numpy()
_ema = h1.close.ewm(span=50, adjust=False).mean()
_dist = (h1.close - _ema).abs().to_numpy()
_N60 = 60 * 23


_tr = pd.concat([h1.high - h1.low, (h1.high - h1.close.shift()).abs(), (h1.low - h1.close.shift()).abs()], axis=1).max(axis=1)
_atr = _tr.rolling(14).mean().to_numpy()


def abnormal(i):
    out = False
    if "C" in ABN_KIND:
        # C - |close - EMA50| in H1 ATR(14) units (the owner: "maybe 2.5 - 3 ATR")
        out |= _dist[i - 1] >= ABN * _atr[i - 1]
    if "A" in ABN_KIND:
        base = np.nanmedian(_rng24[max(0, i - 1 - _N60) : i - 1])
        out |= _rng24[i - 1] >= ABN * base
    if "B" in ABN_KIND:
        base = np.nanmedian(_dist[max(0, i - 1 - _N60) : i - 1])
        out |= _dist[i - 1] >= ABN * base
    return bool(out)


def d1_er(t, n=20):
    x = d1[d1.ct <= t].tail(n + 1)
    return abs(x.close.iloc[-1] - x.close.iloc[0]) / x.close.diff().abs().sum()


# visits on H1
h1r = (h1.high - h1.low).to_numpy()
visits, far = [], {}
i0 = int(h1.th.searchsorted(START))
for i in range(max(i0, 130), len(h1)):
    r = h1.iloc[i]
    if r.th >= END:
        break
    g = grid_at(r.th)
    if g is None:
        continue
    _, A, S = g
    Z = S * 10 / 76
    if FIX:
        # re-arm: every disarmed key of this grid whose line the whole bar stays away from (by S/2)
        for key in [kk for kk, armed in far.items() if not armed and kk[0] == round(A, 2) and kk[1] == round(S, 2)]:
            if r.low >= key[2] + S / 2 or r.high <= key[2] - S / 2:
                far[key] = True
        ks = range(int(np.ceil((r.low - Z - A) / S)) - 1, int(np.floor((r.high + Z - A) / S)) + 2)
    else:
        k0 = int((r.low - A) // S) - 1
        ks = range(k0, k0 + 4)
    for k in ks:
        L = round(A + k * S, 2)
        key = (round(A, 2), round(S, 2), L)
        down = r.low <= L + Z and r.open > L
        up = r.high >= L - Z and r.open < L
        if (down or up) and far.get(key, True):
            far[key] = False
            side = "BUY" if down else "SELL"
            back = h1.iloc[i - 3 : i]
            toward = (back.close - back.open) * (1 if side == "SELL" else -1)
            med = float(np.median(h1r[i - 120 : i]))
            six = h1.iloc[i - 6 : i]
            run6 = (six.close.iloc[-1] - six.open.iloc[0]) * (1 if side == "SELL" else -1)
            mom = toward.max() >= med or run6 >= S
            visits.append({"visit": r.th, "side": side, "line": L, "S": S, "momentum": bool(mom), "abn": abnormal(i) if ABN > 0 else False,
                           "h1_open": float(r.open), "Z": Z})
        elif not FIX and min(abs(r.high - L), abs(r.low - L)) >= S / 2:
            far[key] = True
v = pd.DataFrame(visits)
if FIX and len(v):
    # several visits in one H1 hour: the first reached (on exec_tf, the bid within Z) goes first - not the lower line
    _tt = []
    for r in v.itertuples():
        j0 = int(ex.th.searchsorted(r.visit))
        jt = j0
        while jt < min(j0 + PER_H, len(ex)):
            b = ex.iloc[jt]
            if (r.side == "BUY" and b.low <= r.line + r.Z) or (r.side == "SELL" and b.high >= r.line - r.Z):
                break
            jt += 1
        _tt.append((jt, abs(r.h1_open - r.line)))
    v["touch_j"] = [x[0] for x in _tt]
    v["from_open"] = [x[1] for x in _tt]
    v = v.sort_values(["visit", "touch_j", "from_open", "line"], kind="stable").reset_index(drop=True)
if os.environ.get("ZVISITS") and len(v):
    (HERE / "zone_reference_out").mkdir(exist_ok=True)
    v.to_csv(HERE / "zone_reference_out" / f"visits_{TAG}.csv", index=False, float_format="%.6f")
    pd.DataFrame([(g[0], g[1], g[2]) for g in grids], columns=["start", "anchor", "step"]).to_csv(
        HERE / "zone_reference_out" / f"grids_{TAG}.csv", index=False, float_format="%.6f")

# the setups
rows, busy, skip = [], None, {"momentum": 0, "trend gate": 0, "busy": 0, "cancel": 0, "no fill": 0}
for r in v.itertuples():
    if r.momentum:
        skip["momentum"] += 1
        continue
    if busy is not None and r.visit <= busy:
        skip["busy"] += 1
        continue
    if r.abn:
        skip["abnormal"] = skip.get("abnormal", 0) + 1
        continue
    if side_share(r.visit) <= 0.25:
        skip["trend gate"] += 1
        continue
    if ER_MAX < 1 and d1_er(r.visit) >= ER_MAX:
        # the owner: "a clear bull or bear market - we don't use this setup"; the D1 ZigZag lags a fast trend, the
        # 20-day D1 efficiency ratio does not
        skip["clear trend"] = skip.get("clear trend", 0) + 1
        continue
    S, L, sgn = r.S, r.line, (1 if r.side == "BUY" else -1)
    p1, p2 = L + sgn * S * 10 / 76, L - sgn * S * 15 / 76
    sl, tp = L - sgn * S / 2, L + sgn * S
    j0 = int(ex.th.searchsorted(r.visit))
    if FIX and j0 < PER_H:
        raise SystemExit(f"{EXEC} has no hour of history before the visit {r.visit} - start the run at {ex.th.iloc[PER_H]} or later")
    end = min(j0 + 48 * PER_H, len(ex))
    fills, out, cancelled, j = {}, None, False, j0
    while j < len(ex):
        b = ex.iloc[j]
        sp = b.spread * PT
        if not fills:
            if j >= end or (j > j0 and sgn * ((b.high if sgn > 0 else b.low) - L) >= S / 2):
                break
            w = ex.iloc[j - PER_H : j]
            if (w.close.iloc[-1] - w.open.iloc[0]) * -sgn >= S / 3:
                cancelled = True
                break
        lo_px = b.low + sp if sgn > 0 else b.low
        hi_px = b.high  # a SELL limit fills when the bid reaches it (fixed 2026-11-01: was high + spread, the ask)
        for name, px in (("P1", p1), ("P2", p2)):
            if name in fills:
                continue
            hit = (lo_px <= px) if sgn > 0 else (hi_px >= px)
            if hit and not fills and (px - ex.open.iloc[j - PER_H]) * -sgn >= S / 3:
                cancelled = True
                break
            if hit and (fills or j < end):
                fills[name] = (j, px)
        if cancelled:
            break
        if fills:
            stop_hit = (b.low <= sl) if sgn > 0 else (b.high + sp >= sl)
            tp_hit = (b.high >= tp) if sgn > 0 else (b.low + sp <= tp)
            if stop_hit:
                out = (j, sl, "SL")
            elif tp_hit and all(f[0] < j for f in fills.values()):
                out = (j, tp, "TP")
            if out:
                break
        j += 1
    if cancelled:
        skip["cancel"] += 1
        if FIX:
            busy = ex.ct[j]
        continue
    if not fills:
        if FIX and j >= len(ex):
            skip["pending at the end"] = skip.get("pending at the end", 0) + 1
            busy = ex.ct.iloc[-1]
            continue
        skip["no fill"] += 1
        if FIX:
            busy = ex.ct[j]
        continue
    q, px_out, how = out if out else (len(ex) - 1, ex.close.iloc[-1], "open")
    for name, (jf, px_in) in fills.items():
        pnl = sgn * (px_out - px_in)
        risk = sgn * (px_in - sl)
        if how == "SL":
            assert pnl < 0
        rows.append({"visit": r.visit, "pos": name, "entry_t": ex.ct[jf], "exit_t": ex.ct[q], "side": r.side, "line": L, "S": round(S, 2),
                     "entry": px_in, "sl": sl, "tp": tp, "how": how, "risk": risk, "pnl": pnl})
    busy = ex.ct[q]

t = pd.DataFrame(rows)
(HERE / "zone_reference_out").mkdir(exist_ok=True)
t.to_csv(HERE / "zone_reference_out" / f"long_{TAG}.csv", index=False, float_format="%.6f")
if FIX:
    print("open at the end (not a result):", t[t.how == "open"].visit.nunique())
    t = t[t.how != "open"]
s = t.groupby("visit").agg(usd=("pnl", "sum"), risk=("risk", "sum"), S=("S", "first"), how=("how", "first")).reset_index()
s["R"] = s.usd / s.risk
s["cum"] = s.usd.cumsum()
print("grids:", len(grids), "| visits:", len(v), "| skipped:", skip)
if os.environ.get("ZGRIDS"):
    print("grid list:", [(g[0].strftime("%d/%m/%y %H:%M"), round(g[1], 2), round(g[2], 2)) for g in grids if g[0] >= pd.Timestamp(os.environ["ZGRIDS"], tz=TH)])
print(f"setups {len(s)}: {s.R.mean():+.3f} R a setup, TP {(s.how == 'TP').mean():.0%}, USD at 0.01 lot each {s.usd.sum():+.1f}")
y = s.groupby(s.visit.dt.year).agg(n=("R", "size"), R=("R", "mean"), usd=("usd", "sum"), S=("S", "median"))
print(y.round(3).to_string())
pk = s.cum.cummax()
dd = s.cum - pk
k = int(dd.idxmin()) if len(dd) else 0
print(f"deepest drawdown {dd.min():.1f} USD (to {s.visit[k]:%d/%m/%y}); losing months {(s.groupby(s.visit.dt.strftime('%Y-%m')).usd.sum() < 0).sum()} of {s.visit.dt.strftime('%Y-%m').nunique()}")
