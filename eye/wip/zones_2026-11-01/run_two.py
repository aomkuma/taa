"""Variant C - two positions at a zone line (the owner, 2026-11-01: "one before price [reaches the line] and one on
the fake break, SL beyond the liquidation zone"). Simulated on M5, no orders.

Form [Claude]: per visit not skipped for momentum (entries_m5.csv), BUY at a lower line L (SELL mirrored):
  P1 - a limit BEFORE the line at L + BEFORE;  P2 - a limit in the fake break at L - INTO;
  SL for both L - SLX (beyond the liquidation zone); TP for both L + S (the opposite edge).
Orders rest from the visit until price moves S/2 away from L or 48 h; before the first fill they are cancelled when
the last 12 closed M5 bars ran S/3 toward the line. BUY fills when the ask reaches the price; exits on bid (SELL the
mirror). SL first if a bar holds both. One visit at a time.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
TH, PT, S = "Asia/Bangkok", 0.01, 76.0
B0 = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
I0 = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
BEFORE, INTO, SLX = B0, I0, S / 2

m5 = pd.read_parquet(f"{D}/M5.parquet")
m5["th"] = pd.to_datetime(m5.open_time, utc=True).dt.tz_convert(TH)
m5["ct"] = pd.to_datetime(m5.close_time, utc=True).dt.tz_convert(TH)
m5 = m5.reset_index(drop=True)
import os

SRC = os.environ.get("ZSRC", "entries_m5")
v = pd.read_csv(HERE / f"{SRC}.csv", parse_dates=["t", "visit"]).sort_values("visit")
v = v.drop_duplicates(["visit", "line", "side"])

# the market-state gate (the owner, 2026-11-01: "if that period is a trend, no trade - the bot should know whether
# the market in front of it favours this setup"): each of D1 / H4 / H1 / M15 is sideways when its last two fixed
# ZigZag (12/5/3) highs and lows do not agree; the share of weight sideways must be over GATE.
GATE = float(os.environ.get("ZGATE", "-1"))
WTS = dict(zip(["D1", "H4", "H1", "M15"], [float(x) for x in os.environ.get("ZW", "0.4,0.3,0.2,0.1").split(",")]))
if GATE >= 0:
    sys.path.insert(0, "C:/Users/korap/taa")
    from app.indicators.chart_read import zigzag_pivots
    PIV = {}
    for tf in WTS:
        h = pd.read_parquet(f"{D}/{tf}.parquet")
        h["ct"] = pd.to_datetime(h.close_time, utc=True).dt.tz_convert(TH)
        if tf == "M15":
            h = h[h.ct >= "2025-09-01"].reset_index(drop=True)
        zz = zigzag_pivots(h.high.to_numpy(float), h.low.to_numpy(float), PT)
        PIV[tf] = (np.array([h.ct[z.confirm_pos].value for z in zz]), np.array([z.kind.name for z in zz]), np.array([z.price for z in zz]))


def side_share(t):
    tot = 0.0
    for tf, w in WTS.items():
        ct, kd, pr = PIV[tf]
        m = ct <= t.value
        hs, ls = pr[m & (kd == "HIGH")][-2:], pr[m & (kd == "LOW")][-2:]
        trend = len(hs) == 2 and len(ls) == 2 and ((hs[1] > hs[0] and ls[1] > ls[0]) or (hs[1] < hs[0] and ls[1] < ls[0]))
        tot += 0 if trend else w
    return tot / sum(WTS.values())


rows, busy, skip = [], None, {"momentum": 0, "cancel": 0, "no fill": 0, "busy": 0, "trend gate": 0}
for r in v.itertuples():
    if r.kind == "momentum":
        skip["momentum"] += 1
        continue
    if busy is not None and r.visit <= busy:
        skip["busy"] += 1
        continue
    if GATE >= 0 and side_share(r.visit) <= GATE:
        skip["trend gate"] += 1
        continue
    sgn = 1 if r.side == "BUY" else -1
    L = r.line
    S = float(getattr(r, "S", 76.0)) if not pd.isna(getattr(r, "S", np.nan)) else 76.0
    BEFORE, INTO, SLX = B0 * S / 76.0, I0 * S / 76.0, S / 2  # scale-free: the same fractions of the step
    p1, p2 = L + sgn * BEFORE, L - sgn * INTO
    sl, tp = L - sgn * SLX, L + sgn * S
    j0 = int(m5.th.searchsorted(r.visit))
    fills, out, cancelled = {}, None, False
    end = min(j0 + 48 * 12, len(m5))
    j = j0
    while j < len(m5):
        b = m5.iloc[j]
        sp = b.spread * PT
        if not fills:
            if j >= end or (j > j0 and sgn * ((b.high if sgn > 0 else b.low) - L) >= S / 2):
                break
            if j >= 12:
                w = m5.iloc[j - 12 : j]
                if (w.close.iloc[-1] - w.open.iloc[0]) * -sgn >= S / 3:
                    cancelled = True
                    break
        # fills on this bar (BUY: ask = bid + spread reaches the price)
        lo_px = b.low + sp if sgn > 0 else b.low
        hi_px = b.high if sgn > 0 else b.high + sp
        for name, px in (("P1", p1), ("P2", p2)):
            if name in fills or out:
                continue
            hit = (lo_px <= px) if sgn > 0 else (hi_px >= px)
            if hit and not fills and j >= 12:
                # momentum up to the fill itself, known at that moment: from the open 12 bars back to the fill price
                # (the 07/05 SELL 4738 was filled by a spike inside one bar, past the closed-bar check)
                if (px - m5.open.iloc[j - 12]) * -sgn >= S / 3:
                    cancelled = True
                    break
            if hit and (fills or j < end):
                fills[name] = (j, px)
        if cancelled:
            break
        if fills:
            # exits: the stop first (also on a fill bar); TP only on a later bar than the fill
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
        continue
    if not fills:
        skip["no fill"] += 1
        continue
    q, px_out, how = out if out else (len(m5) - 1, m5.close.iloc[-1], "open")
    for name, (jf, px_in) in fills.items():
        pnl = sgn * (px_out - px_in)
        risk = sgn * (px_in - sl)
        if how == "SL":
            assert pnl < 0
        rows.append({"visit": r.visit, "pos": name, "entry_t": m5.ct[jf], "exit_t": m5.ct[q], "side": r.side, "line": L,
                     "entry": round(px_in, 2), "sl": round(sl, 2), "tp": tp, "how": how, "risk": round(risk, 2),
                     "pnl": round(pnl, 2), "R": round(pnl / risk, 3)})
    busy = m5.ct[q]

t = pd.DataFrame(rows)
TAG = "" if GATE < 0 else f"_gate{GATE:g}_w{os.environ.get('ZW', '0.4,0.3,0.2,0.1').replace(',', '-')}"
t.to_csv(HERE / f"trades_two_{B0:g}_{I0:g}_38{SRC.replace('entries_m5', '')}{TAG}.csv", index=False)
print("skipped:", skip)
for pos, g in t.groupby("pos"):
    print(f"{pos}: {len(g)} fills, TP {(g.how == 'TP').sum()} ({(g.how == 'TP').mean():.0%}), {g.R.mean():+.3f} R a fill, USD at 0.01 lot {g.pnl.sum():+.2f}")
setups = t.groupby("visit").agg(pnl=("pnl", "sum"), risk=("risk", "sum"), n=("pos", "count"), how=("how", "first"))
print(f"setups {len(setups)} (both filled {(setups.n == 2).sum()}): {(setups.pnl / setups.risk).mean():+.3f} R a setup (on the setup's total risk), USD at 0.01 lot each {setups.pnl.sum():+.2f}")
print(setups.groupby(setups.index.strftime("%Y-%m")).pnl.agg(["count", "sum"]).round(1).to_string())
