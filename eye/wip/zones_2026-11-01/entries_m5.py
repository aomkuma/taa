"""Entries on the v7 zones with an M5 structure turn as the trigger - drawn on H1, no outcomes scored.

Claude's form (2026-11-01; the owner: "try it in first; if it doesn't work, take it out"):
  zones   - v7 (entries.py).
  visit   - an H1 bar comes within Z of a line after price was at least S/2 away from it.
  trigger - from the visit on, on M5: BUY when an M5 close passes above the last fixed M5 ZigZag (12/5/3) high
            (the structure turns up); SELL the mirror. Entry at that close. SL S/3 beyond the line, TP the
            opposite edge (one step).
  no turn - price reaches the SL level first (the line did not hold - the stop-limit case) or moves S/2 away, or
            48 hours pass, with no turn.
  fast    - the owner's high volatility: any 1 - 2 closed H1 bars in the 6 hours before the trigger span >= S.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\korap\taa")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from app.indicators.chart_read import zigzag_pivots

D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
OUT = Path(__file__).resolve().parent
S, Z, VOL_LOOK, WAIT_H, MOM_H = 76.0, 10.0, 6, 48, 24
TRIG = sys.argv[1] if len(sys.argv) > 1 else "M5"  # the frame whose structure turn triggers the entry
LATE = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25  # 0 = no late filter
PER_H = {"M5": 12, "M15": 4}[TRIG]
TURN = sys.argv[3] if len(sys.argv) > 3 else "zz"  # zz = past the last fixed ZigZag swing; bar = past the extreme bar
SUFFIX = "" if (TRIG == "M5" and LATE == 0.25 and TURN == "zz") else f"_{TRIG.lower()}_late{LATE:g}" + ("" if TURN == "zz" else f"_{TURN}")
if "ZSTART" in os.environ:
    SUFFIX += "_" + os.environ["ZSTART"][:7]
if os.environ.get("ZADAPT") == "1":
    SUFFIX += "_adapt"
if os.environ.get("ZOWNER") == "1":
    SUFFIX += "_owner"
if os.environ.get("ZKS"):
    SUFFIX += "_k" + os.environ["ZKS"]
TH = "Asia/Bangkok"
import os

START = pd.Timestamp(os.environ.get("ZSTART", "2026-05-01"), tz=TH)
END = pd.Timestamp(os.environ.get("ZEND", "2026-11-01"), tz=TH)
PT = json.load(open(f"{D}/spec.json"))["spec"]["point"]


def load(tf, warm):
    df = pd.read_parquet(f"{D}/{tf}.parquet")
    df["th"] = pd.to_datetime(df.open_time, utc=True).dt.tz_convert(TH)
    df["ct"] = pd.to_datetime(df.close_time, utc=True).dt.tz_convert(TH)
    return df[(df.th >= START - warm) & (df.th < END)].reset_index(drop=True)


h4, h1, m5 = load("H4", pd.Timedelta(days=60)), load("H1", pd.Timedelta(days=2)), load(TRIG, pd.Timedelta(days=5))  # m5 = the trigger frame
zz = zigzag_pivots(h4.high.to_numpy(float), h4.low.to_numpy(float), PT)
z5 = zigzag_pivots(m5.high.to_numpy(float), m5.low.to_numpy(float), PT)
# for each M5 bar: the last fixed swing high / low known at its close
hi_at = np.full(len(m5), np.nan)
lo_at = np.full(len(m5), np.nan)
for s in z5:
    arr = hi_at if s.kind.name == "HIGH" else lo_at
    arr[s.confirm_pos] = s.price
hi_at = pd.Series(hi_at).ffill().to_numpy()
lo_at = pd.Series(lo_at).ffill().to_numpy()


def off(p, a, step=None):
    st = S if step is None else step
    return min((p - a) % st, st - (p - a) % st)


ADAPT = os.environ.get("ZADAPT") == "1"
OWNERGRID = os.environ.get("ZOWNER") == "1"
grids = []  # (known from, anchor, step)
if OWNERGRID:
    # the owner's own lines of 01/11/2026 held fixed over the whole test (the owner: "the zones were drawn wrong")
    S = 76.25
    grids.append((pd.Timestamp("2000-01-01", tz=TH), 4066.41, S))
elif not ADAPT:
    KS = [int(k) for k in os.environ.get("ZKS", "2")]  # whole steps a cluster may span (v7: 2 only)
    for a, b in zip(zz, zz[1:]):
        d = abs(a.price - b.price)
        if not any(abs(d - k * S) <= 0.1 * S * (2 if k == 2 and KS == [2] else 1) for k in KS):
            continue
        lo = min(a.price, b.price)
        if not grids or off(lo, grids[-1][1]) > 0.2 * S:
            grids.append((h4.ct[b.confirm_pos], lo, S))
else:
    # the zone length from the market (the owner, 2026-11-01: "try it"): a cluster = two neighbouring fixed H4 turns
    # and a third that comes back to test the first edge without passing it by more than a third of the step;
    # the step = half the cluster's height (the owner's September and October boxes). Bounds 40 - 120 [Claude].
    for a, b, c in zip(zz, zz[1:], zz[2:]):
        hi_, lo_ = max(a.price, b.price), min(a.price, b.price)
        st = (hi_ - lo_) / 2
        if not (40 <= st <= 120):
            continue
        if not (lo_ - st / 3 <= c.price <= hi_ + st / 3):
            continue
        if (not grids or off(lo_, grids[-1][1], grids[-1][2]) > 0.2 * grids[-1][2]
                or abs(st - grids[-1][2]) > 0.1 * grids[-1][2]):
            grids.append((h4.ct[c.confirm_pos], lo_, st))
    print("grids:", [(g[0].strftime("%d/%m/%y"), round(g[1], 2), round(g[2], 1)) for g in grids if g[0] >= START - pd.Timedelta(days=40)])


def anchor(t):
    gs = [g for g in grids if g[0] <= t]
    return gs[-1][1] if gs else None


def step(t):
    gs = [g for g in grids if g[0] <= t]
    return gs[-1][2] if gs else S


def fast_before(t):
    back = h1[h1.ct <= t].tail(VOL_LOOK)
    span2 = pd.concat([back.high, back.high.shift(1)], axis=1).max(axis=1) - pd.concat([back.low, back.low.shift(1)], axis=1).min(axis=1)
    return bool((span2 >= S).any())


far, marks = {}, []
for i, r in h1.iterrows():
    if r.th < START:
        continue
    A = anchor(r.th)
    if A is None:
        continue
    S = step(r.th)
    Z = 10.0 * S / 76.0
    k0 = int((r.low - A) // S) - 1
    for k in range(k0, k0 + 4):
        L = round(A + k * S, 2)
        down = r.low <= L + Z and r.open > L
        up = r.high >= L - Z and r.open < L
        if (down or up) and far.get(L, True):
            far[L] = False
            side = "BUY" if down else "SELL"
            sl = L - S / 3 if side == "BUY" else L + S / 3
            tp = L + S if side == "BUY" else L - S
            j0 = int(m5.th.searchsorted(r.th))
            res = {"kind": "no turn", "j": None, "entry": np.nan}
            # the owner: no fade against momentum near the zone ("a green candle that big"). Form [Claude]: one of
            # the 3 closed H1 bars before the visit has a body toward the line >= the median H1 range of the
            # 120 bars before
            back = h1.iloc[max(0, i - 3) : i]
            toward = (back.close - back.open) * (1 if side == "SELL" else -1)
            med_rng = (h1.high - h1.low).iloc[max(0, i - 120) : i].median()
            # ... or a steady run: the last 6 H1 bars moved a full step toward the line (the owner's 06/05 trade)
            six = h1.iloc[max(0, i - 6) : i]
            run6 = ((six.close.iloc[-1] - six.open.iloc[0]) * (1 if side == "SELL" else -1)) if len(six) else 0.0
            if len(back) and (toward.max() >= med_rng or run6 >= S):
                marks.append({"t": r.th, "visit": r.th, "side": side, "line": L, "kind": "momentum", "entry": np.nan, "sl": sl, "tp": tp, "S": S})
                continue
            for j in range(j0, min(j0 + WAIT_H * PER_H, len(m5))):
                b = m5.iloc[j]
                if (side == "BUY" and b.low <= sl) or (side == "SELL" and b.high >= sl):
                    res = {"kind": "no turn (line broke)", "j": j, "entry": np.nan}
                    break
                if j > j0 and ((side == "BUY" and b.high >= L + S / 2) or (side == "SELL" and b.low <= L - S / 2)):
                    res = {"kind": "no turn (left)", "j": j, "entry": np.nan}
                    break
                if TURN == "bar":
                    # the smallest turn: a close past the high (BUY) / low (SELL) of the bar that made the zone's extreme
                    seg = m5.iloc[j0:j]
                    if not len(seg):
                        continue
                    k_ext = seg.low.idxmin() if side == "BUY" else seg.high.idxmax()
                    ref = m5.high[k_ext] if side == "BUY" else m5.low[k_ext]
                else:
                    ref = hi_at[j - 1] if side == "BUY" else lo_at[j - 1]
                if np.isnan(ref):
                    continue
                # the turn: a close past the last fixed swing, after price came to the zone
                if (side == "BUY" and b.close > ref and ref < L + S / 2) or (side == "SELL" and b.close < ref and ref > L - S / 2):
                    near_zone = (m5.low.iloc[j0 : j + 1].min() <= L + Z) if side == "BUY" else (m5.high.iloc[j0 : j + 1].max() >= L - Z)
                    if not near_zone:
                        continue
                    past = (b.close - L) if side == "BUY" else (L - b.close)
                    kind = "fast" if fast_before(b.ct) else ("late" if LATE and past > LATE * S else "entry")
                    res = {"kind": kind, "j": j, "entry": float(b.close)}
                    break
            t = m5.ct[res["j"]] if res["j"] is not None else r.th
            marks.append({"t": t, "visit": r.th, "side": side, "line": L, "kind": res["kind"], "entry": res["entry"], "sl": sl, "tp": tp, "S": S})
        elif min(abs(r.high - L), abs(r.low - L)) >= S / 2:
            far[L] = True

m = pd.DataFrame(marks)
m["month"] = m.t.dt.strftime("%Y-%m")
m["R_planned"] = np.where(m.side == "BUY", (m.tp - m.entry) / (m.entry - m.sl), (m.entry - m.tp) / (m.sl - m.entry))
m["from_line"] = np.where(m.side == "BUY", m.entry - m.line, m.line - m.entry)
print(m.groupby(["month", "kind"]).size().unstack(fill_value=0).to_string())
e = m[m.kind == "entry"]
print(f"entries {len(e)}: entry beyond the line by median {e.from_line.median():.1f} (range {e.from_line.min():.1f} .. {e.from_line.max():.1f}); planned R median {e.R_planned.median():.2f}, under 2: {(e.R_planned < 2).sum()}")
m.to_csv(OUT / f"entries_m5{SUFFIX}.csv", index=False)

if ADAPT or OWNERGRID or os.environ.get("ZKS"):
    print("grids:", [(g[0].strftime("%d/%m/%y"), round(g[1], 2)) for g in grids if g[0] >= START - pd.Timedelta(days=40)])
    raise SystemExit
h1s = h1[h1.th >= START]
for month in sorted(m.month.unique()):
    mm = m[m.month == month]
    seg = h1s[h1s.th.dt.strftime("%Y-%m") == month]
    i0, i1 = seg.index[0], seg.index[-1]
    fig, ax = plt.subplots(figsize=(22, 10))
    for k, r in seg.iterrows():
        c = "#26a69a" if r.close >= r.open else "#ef5350"
        ax.vlines(k, r.low, r.high, color=c, lw=0.6)
        ax.add_patch(plt.Rectangle((k - 0.35, min(r.open, r.close)), 0.7, max(abs(r.close - r.open), 0.01), color=c))
    lo, hi = seg.low.min() - 25, seg.high.max() + 25
    cur, xs = None, i0
    for k in list(range(i0, i1 + 1)) + [None]:
        a = anchor(h1.th[k]) if k is not None else None
        if k is None or a != cur:
            if cur is not None:
                n = int((lo - cur) // S)
                while cur + n * S <= hi:
                    y = cur + n * S
                    if y >= lo:
                        ax.hlines(y, xs, (k if k is not None else i1 + 1), color="orange", lw=0.9, alpha=0.8)
                        ax.text(xs + 2, y + 1.5, f"{y:.0f}", fontsize=7, color="#e65100")
                    n += 1
            cur, xs = a, (k if k is not None else xs)

    def xpos(t):
        return int(h1.th.searchsorted(t, side="right")) - 1

    for r in mm.itertuples():
        col = {"BUY": "#1565c0", "SELL": "#c62828"}[r.side]
        x = xpos(r.t)
        if r.kind == "entry":
            ax.plot(x, r.entry, marker="^" if r.side == "BUY" else "v", color=col, ms=11, zorder=5)
            ax.hlines([r.sl, r.tp], x, x + 18, colors=["#000000", "#2e7d32"], lw=1.4, zorder=5)
            ax.text(x + 1, r.entry + (-9 if r.side == "BUY" else 4), f"{r.side} {r.entry:.0f}", fontsize=7, color=col)
        elif r.kind in ("late", "momentum"):
            ax.plot(xpos(r.t), r.entry if r.kind == "late" else r.line, marker="s", mfc="none", mec="#6a1b9a", ms=9, mew=1.5, zorder=5)
        elif r.kind == "fast":
            ax.plot(x, r.entry, marker="D", color="#ff8f00", ms=9, zorder=5)
        else:
            ax.plot(xpos(r.visit), r.line, marker="x", color="#757575", ms=9, mew=2, zorder=5)
    ticks = list(range(i0, i1, 24))
    ax.set_xticks(ticks, [h1.th[i].strftime("%d/%m") for i in ticks], fontsize=8)
    ax.set_xlim(i0 - 3, i1 + 20)
    ax.set_ylim(lo, hi)
    ax.grid(alpha=0.15)
    cnt = mm.kind.value_counts().to_dict()
    nt = sum(v for k, v in cnt.items() if k.startswith("no turn"))
    ax.set_title(
        f"XAUUSD H1 FBS-Demo {month} Thai - entries on the v7 zones on an M5 structure turn: triangle = entry (black dash SL, "
        f"green dash TP), x = zone visited, no M5 turn, orange diamond = high volatility, purple square = momentum / late; {cnt.get('entry', 0)} entries, {cnt.get('momentum', 0)} momentum, {cnt.get('late', 0)} late, {nt} no turn, {cnt.get('fast', 0)} high volatility"
    )
    fig.tight_layout()
    fig.savefig(OUT / f"entries_m5{SUFFIX}_{month}.png", dpi=95)
    plt.close(fig)
