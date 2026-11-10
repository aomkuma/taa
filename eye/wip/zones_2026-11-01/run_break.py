"""The line that does not hold - a stop limit the way of the break (METHOD 2e, the owner's formula, 2026-11-01).
Simulated on M5, no orders; a book of its own beside variant C (run_two.py).

For every zone visit in the entries file (any kind - also those skipped for momentum): price came down to a lower
line L (a BUY visit; SELL mirrored). If price then trades S/3 below L (the stop price - past the fake break) within
48 h, before it goes S/2 back above L, a SELL limit is armed at L (the retest): SL L + S/3 + b, TP L - S. The limit
is cancelled if price reaches the TP first or 48 h pass. SELL fills when the bid reaches L, exits on ask. SL first
if a bar holds both. One position at a time. b = S/15 (the owner's "a little, against the whip").
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
TH, PT = "Asia/Bangkok", 0.01
SRC = os.environ.get("ZSRC", "entries_m5")
MODE = os.environ.get("ZBREAK", "line")  # line = stop S/3, limit at the line; liq = stop past the liquidation zone
TPM = os.environ.get("ZTP", "line")  # liq mode: TP at the next line, or one step from the limit

m5 = pd.read_parquet(f"{D}/M5.parquet")
m5["th"] = pd.to_datetime(m5.open_time, utc=True).dt.tz_convert(TH)
m5["ct"] = pd.to_datetime(m5.close_time, utc=True).dt.tz_convert(TH)
m5 = m5.reset_index(drop=True)
v = pd.read_csv(HERE / f"{SRC}.csv", parse_dates=["t", "visit"]).sort_values("visit").drop_duplicates(["visit", "line", "side"])

rows, busy, stat = [], None, {"no break": 0, "no retest": 0, "busy": 0}
for r in v.itertuples():
    S = float(r.S) if hasattr(r, "S") and not pd.isna(r.S) else 76.0
    b_ = S / 15
    sgn = -1 if r.side == "BUY" else 1  # the trade goes the way of the break: a BUY visit breaks down -> SELL
    L = r.line
    if MODE == "liq":
        # the owner: "the stop limit triggers when price is past the liquidation zone" - the stop at S/2 past the
        # line (variant C's SL), the limit back at the fake-break edge S/3 past it, SL S/3 + b from the limit
        stop_px, lim = L + sgn * S / 2, L + sgn * S / 3
        sl = lim - sgn * (S / 3 + b_)
        tp = (L + sgn * S) if TPM == "line" else (lim + sgn * S)
    else:
        stop_px, lim = L + sgn * S / 3, L
        sl, tp = L - sgn * (S / 3 + b_), L + sgn * S
    j0 = int(m5.th.searchsorted(r.visit))
    # 1. the break
    jb = None
    for j in range(j0, min(j0 + 48 * 12, len(m5))):
        b = m5.iloc[j]
        if (sgn < 0 and b.low <= stop_px) or (sgn > 0 and b.high + b.spread * PT >= stop_px):
            jb = j
            break
        if (sgn < 0 and b.high >= L + S / 2) or (sgn > 0 and b.low <= L - S / 2):
            break
    if jb is None:
        stat["no break"] += 1
        continue
    if busy is not None and m5.ct[jb] <= busy:
        stat["busy"] += 1
        continue
    # 2. the retest fill at L, after the break bar
    jf = None
    for j in range(jb + 1, min(jb + 1 + 48 * 12, len(m5))):
        b = m5.iloc[j]
        sp = b.spread * PT
        if (sgn < 0 and b.low + sp <= tp) or (sgn > 0 and b.high >= tp):
            break  # ran to the target without a retest
        if (sgn < 0 and b.high >= lim) or (sgn > 0 and b.low + sp <= lim):
            jf = j
            break
    if jf is None:
        stat["no retest"] += 1
        continue
    out = None
    fb = m5.iloc[jf]
    if (sgn < 0 and fb.high + fb.spread * PT >= sl) or (sgn > 0 and fb.low <= sl):
        out = (jf, sl, "SL")
    q = jf + 1
    while out is None and q < len(m5):
        b = m5.iloc[q]
        sp = b.spread * PT
        if sgn < 0:
            if b.high + sp >= sl:
                out = (q, sl, "SL")
            elif b.low + sp <= tp:
                out = (q, tp, "TP")
        else:
            if b.low <= sl:
                out = (q, sl, "SL")
            elif b.high >= tp:
                out = (q, tp, "TP")
        q += 1
    q, px, how = out if out else (len(m5) - 1, m5.close.iloc[-1], "open")
    pnl = sgn * (px - lim)
    risk = S / 3 + b_
    if how == "SL":
        assert pnl < 0
    rows.append({"visit": r.visit, "visit_kind": r.kind, "side": "SELL" if sgn < 0 else "BUY", "line": L,
                 "break_t": m5.ct[jb], "entry_t": m5.ct[jf], "exit_t": m5.ct[q], "entry": round(lim, 2), "sl": round(sl, 2), "tp": tp,
                 "how": how, "risk": round(risk, 2), "pnl": round(pnl, 2), "R": round(pnl / risk, 3)})
    busy = m5.ct[q]

t = pd.DataFrame(rows)
t.to_csv(HERE / f"trades_break{SRC.replace('entries_m5', '')}_{MODE}_{TPM}.csv", index=False)
print("stat:", stat)
print(f"{len(t)} trades, TP {(t.how == 'TP').sum()} ({(t.how == 'TP').mean():.0%}), {t.R.mean():+.3f} R a trade, USD at 0.01 lot {t.pnl.sum():+.2f}")
print("from momentum visits:", (t.visit_kind == "momentum").sum())
print(t.groupby(t.entry_t.dt.strftime("%Y-%m")).pnl.agg(["count", "sum"]).round(1).to_string())
