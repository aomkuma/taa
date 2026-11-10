"""Variant B: a limit at the line, no M5 turn - the momentum filter keeps it off trend legs. Simulated on M5, no orders.

Visits and the momentum flag come from entries_m5.csv (kind "momentum" = skipped). For every other visit: a limit at
the line L from the visit's H1 bar on, until filled, price moves S/2 away, or 48 h. BUY: SL L - S/3, TP L + S (SELL
the mirror) - the owner's formula, 1:3. High volatility (1 - 2 H1 bars spanning S in the 6 h before the fill) skips.
BUY fills when the ask reaches L (bid low + spread <= L) at L, exits on bid; SELL fills when the bid high >= L, exits on
ask. SL first if a bar holds both. One position at a time. Cost = the spread.
"""

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
TH, PT, S = "Asia/Bangkok", 0.01, 76.0


def load(tf):
    df = pd.read_parquet(f"{D}/{tf}.parquet")
    df["th"] = pd.to_datetime(df.open_time, utc=True).dt.tz_convert(TH)
    df["ct"] = pd.to_datetime(df.close_time, utc=True).dt.tz_convert(TH)
    return df.reset_index(drop=True)


m5, h1 = load("M5"), load("H1")
v = pd.read_csv(HERE / "entries_m5.csv", parse_dates=["t", "visit"]).sort_values("visit")


def fast_before(t):
    back = h1[h1.ct <= t].tail(6)
    span2 = pd.concat([back.high, back.high.shift(1)], axis=1).max(axis=1) - pd.concat([back.low, back.low.shift(1)], axis=1).min(axis=1)
    return bool((span2 >= S).any())


rows, busy, skipped = [], None, {"momentum": 0, "no fill": 0, "fast": 0, "busy": 0}
for r in v.itertuples():
    if r.kind == "momentum":
        skipped["momentum"] += 1
        continue
    L = r.line
    sl = L - S / 3 if r.side == "BUY" else L + S / 3
    tp = L + S if r.side == "BUY" else L - S
    j0 = int(m5.th.searchsorted(r.visit))
    fill = None
    cancelled = False
    for j in range(j0, min(j0 + 48 * 12, len(m5))):
        b = m5.iloc[j]
        sp = b.spread * PT
        # the resting limit is cancelled when momentum builds: the last 12 closed M5 bars ran S/3 toward the line
        # (the owner, 07/05 SELL 4738 filled by a spike: "it shouldn't - so how did it trade?")
        if j >= 12:
            w = m5.iloc[j - 12 : j]
            ran = (w.close.iloc[-1] - w.open.iloc[0]) * (1 if r.side == "SELL" else -1)
            if ran >= S / 3:
                cancelled = True
                break
        if (r.side == "BUY" and b.low + sp <= L) or (r.side == "SELL" and b.high >= L):
            fill = j
            break
        if j > j0 and ((r.side == "BUY" and b.high >= L + S / 2) or (r.side == "SELL" and b.low <= L - S / 2)):
            break
    if cancelled:
        skipped["m5 momentum"] = skipped.get("m5 momentum", 0) + 1
        continue
    if fill is None:
        skipped["no fill"] += 1
        continue
    if busy is not None and m5.ct[fill] <= busy:
        skipped["busy"] += 1
        continue
    if fast_before(m5.th[fill]):
        skipped["fast"] += 1
        continue
    out = None
    fb = m5.iloc[fill]
    # on the fill bar itself only the stop can be judged honestly (order inside the bar unknown)
    if (r.side == "BUY" and fb.low <= sl) or (r.side == "SELL" and fb.high + fb.spread * PT >= sl):
        out = (fill, sl, "SL")
    for q in range(fill + 1, len(m5)):
        if out:
            break
        b = m5.iloc[q]
        sp = b.spread * PT
        if r.side == "BUY":
            if b.low <= sl:
                out = (q, sl, "SL")
            elif b.high >= tp:
                out = (q, tp, "TP")
        else:
            if b.high + sp >= sl:
                out = (q, sl, "SL")
            elif b.low + sp <= tp:
                out = (q, tp, "TP")
    q, px, how = out if out else (len(m5) - 1, m5.close.iloc[-1], "open")
    pnl = (px - L) if r.side == "BUY" else (L - px)
    R = pnl / (S / 3)
    if how == "SL":
        assert R < 0
    rows.append({"entry_t": m5.ct[fill], "exit_t": m5.ct[q], "side": r.side, "line": L, "entry": L, "sl": round(sl, 2),
                 "tp": tp, "exit": round(px, 2), "how": how, "risk": round(S / 3, 2), "R": round(R, 3), "usd_001": round(pnl, 2),
                 "hours": round((m5.ct[q] - m5.ct[fill]).total_seconds() / 3600, 1)})
    busy = m5.ct[q]

t = pd.DataFrame(rows)
t.to_csv(HERE / "trades_limit.csv", index=False)
print("skipped:", skipped)
print(t[["entry_t", "side", "line", "how", "R", "hours"]].to_string())
print(f"{len(t)} trades, TP {(t.how == 'TP').sum()} ({(t.how == 'TP').mean():.0%}), sum R {t.R.sum():+.2f}, {t.R.mean():+.3f} R a trade, USD at 0.01 lot {t.usd_001.sum():+.2f}")
print(t.groupby(t.entry_t.dt.strftime("%Y-%m")).R.agg(["count", "sum"]).round(2).to_string())
