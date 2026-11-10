"""Where the bot would enter on the v7 zones - drawn on H1, one month an image, no outcomes scored.

Claude's form (2026-11-01; METHOD 2e "The run zones", the formulas the owner took to try):
  zones   - v7: a pair of neighbouring fixed H4 ZigZag (12/5/3) turns 2S apart (+-10 %); lines A + k*S; a shift when
            a new pair's low is more than S/5 off the lines.
  a visit - an H1 bar reaches within Z of a line after price was at least S/2 away from it.
  entry   - a limit at the line: BUY when price comes down to it, SELL when it comes up; SL S/3 beyond the line,
            TP the opposite edge (one step).
  skipped - a trend run: in the 12 H1 bars before, price ran at least S toward the line with no pullback over S/4.
  near    - price came within Z of the line and turned without touching it (no fill).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\korap\taa")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.indicators.chart_read import zigzag_pivots

D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
OUT = Path(__file__).resolve().parent
S, Z, RUN_BARS, VOL_LOOK = 76.0, 10.0, 12, 6
TH = "Asia/Bangkok"
START, END = pd.Timestamp("2026-05-01", tz=TH), pd.Timestamp("2026-11-01", tz=TH)
PT = json.load(open(f"{D}/spec.json"))["spec"]["point"]


def load(tf, warm):
    df = pd.read_parquet(f"{D}/{tf}.parquet")
    df["th"] = pd.to_datetime(df.open_time, utc=True).dt.tz_convert(TH)
    df["ct"] = pd.to_datetime(df.close_time, utc=True).dt.tz_convert(TH)
    return df[(df.th >= START - warm) & (df.th < END)].reset_index(drop=True)


h4, h1 = load("H4", pd.Timedelta(days=60)), load("H1", pd.Timedelta(days=2))
zz = zigzag_pivots(h4.high.to_numpy(float), h4.low.to_numpy(float), PT)


def off(p, a):
    return min((p - a) % S, S - (p - a) % S)


grids = []
for a, b in zip(zz, zz[1:]):
    if abs(abs(a.price - b.price) - 2 * S) > 0.1 * 2 * S:
        continue
    lo = min(a.price, b.price)
    if not grids or off(lo, grids[-1][1]) > 0.2 * S:
        grids.append((h4.ct[b.confirm_pos], lo))


def anchor(t):
    gs = [g for g in grids if g[0] <= t]
    return gs[-1][1] if gs else None


def trend_run(i, L, side):
    """The leg into the line with no pullback over S/4, walked back from bar i; a trend run when it covers >= S."""
    best = None
    for j in range(i, max(-1, i - 48), -1):
        seg = h1.loc[j:i]
        if side == "BUY":
            bounce = (seg.high - seg.low.cummin().shift(1)).max()  # a later bar's high over an earlier low
        else:
            bounce = (seg.high.cummax().shift(1) - seg.low).max()
        if pd.notna(bounce) and bounce >= S / 4:
            break
        best = j
    if best is None:
        return False, 0.0
    seg = h1.loc[best:i]
    run = (seg.high.max() - L) if side == "BUY" else (L - seg.low.min())
    return run >= S, run


far, marks = {}, []
for i, r in h1.iterrows():
    if r.th < START:
        continue
    A = anchor(r.th)
    if A is None:
        continue
    k0 = int((r.low - A) // S) - 1
    for k in range(k0, k0 + 4):
        L = round(A + k * S, 2)
        reach_down = r.low <= L + Z and r.open > L  # coming down to it
        reach_up = r.high >= L - Z and r.open < L
        if (reach_down or reach_up) and far.get(L, True):
            far[L] = False
            side = "BUY" if reach_down else "SELL"
            # the limit rests until the line is touched or price moves S/2 back away from it
            fill = None
            for q in range(i, min(i + 120, len(h1))):
                b = h1.iloc[q]
                if (side == "BUY" and b.low <= L) or (side == "SELL" and b.high >= L):
                    fill = q
                    break
                if q > i and ((side == "BUY" and b.high >= L + S / 2) or (side == "SELL" and b.low <= L - S / 2)):
                    break
            trend, run = trend_run(fill if fill is not None else i, L, side)
            # the owner: "beware high volatility - sometimes it runs the full distance within 1 - 2 H1 bars".
            # Form [Claude]: any 1 - 2 closed H1 bars in the VOL_LOOK hours before the fill spanning >= S
            x0 = fill if fill is not None else i
            back = h1.iloc[max(0, x0 - VOL_LOOK) : x0]
            span2 = pd.concat([back.high, back.high.shift(1)], axis=1).max(axis=1) - pd.concat([back.low, back.low.shift(1)], axis=1).min(axis=1)
            fast = bool((span2 >= S).any())
            kind = "skip" if trend else ("fast" if fast else ("entry" if fill is not None else "near"))
            x = fill if fill is not None else i
            sl = L - S / 3 if side == "BUY" else L + S / 3
            tp = L + S if side == "BUY" else L - S
            marks.append({"t": h1.th[x], "i": x, "side": side, "line": L, "kind": kind, "run": round(run, 1), "sl": sl, "tp": tp})
        elif min(abs(r.high - L), abs(r.low - L)) >= S / 2:
            far[L] = True

m = pd.DataFrame(marks)
m["month"] = m.t.dt.strftime("%Y-%m")
print(m.groupby(["month", "kind"]).size().unstack(fill_value=0).to_string())
m.to_csv(OUT / "entries.csv", index=False)

h1s = h1[h1.th >= START]
for month, mm in m.groupby("month"):
    seg = h1s[h1s.th.dt.strftime("%Y-%m") == month]
    i0, i1 = seg.index[0], seg.index[-1]
    fig, ax = plt.subplots(figsize=(22, 10))
    for k, r in seg.iterrows():
        c = "#26a69a" if r.close >= r.open else "#ef5350"
        ax.vlines(k, r.low, r.high, color=c, lw=0.6)
        ax.add_patch(plt.Rectangle((k - 0.35, min(r.open, r.close)), 0.7, max(abs(r.close - r.open), 0.01), color=c))
    lo, hi = seg.low.min() - 25, seg.high.max() + 25
    # zone lines over time
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
    for r in mm.itertuples():
        col = {"BUY": "#1565c0", "SELL": "#c62828"}[r.side]
        if r.kind == "entry":
            ax.plot(r.i, r.line, marker="^" if r.side == "BUY" else "v", color=col, ms=11, zorder=5)
            ax.hlines([r.sl, r.tp], r.i, r.i + 18, colors=["#000000", "#2e7d32"], lw=1.4, zorder=5)
            ax.text(r.i + 1, r.line + (-9 if r.side == "BUY" else 4), f"{r.side} {r.line:.0f}", fontsize=7, color=col)
        elif r.kind == "fast":
            ax.plot(r.i, r.line, marker="D", color="#ff8f00", ms=9, zorder=5)
        elif r.kind == "skip":
            ax.plot(r.i, r.line, marker="x", color="#757575", ms=10, mew=2, zorder=5)
        else:
            ax.plot(r.i, r.line, marker="o", mfc="none", mec=col, ms=10, mew=1.5, zorder=5)
    ticks = list(range(i0, i1, 24))
    ax.set_xticks(ticks, [h1.th[i].strftime("%d/%m") for i in ticks], fontsize=8)
    ax.set_xlim(i0 - 3, i1 + 20)
    ax.set_ylim(lo, hi)
    ax.grid(alpha=0.15)
    cnt = mm.kind.value_counts().to_dict()
    ax.set_title(
        f"XAUUSD H1 FBS-Demo {month} Thai - entries on the v7 zones (S {S:.0f}): triangle = limit filled at the line "
        f"(black dash SL, green dash TP), x = skipped (trend run), circle = turned within {Z:.0f} before the line, orange diamond = high volatility; "
        f"{cnt.get('entry', 0)} entries, {cnt.get('skip', 0)} skipped, {cnt.get('near', 0)} turned before, {cnt.get('fast', 0)} high volatility"
    )
    fig.tight_layout()
    fig.savefig(OUT / f"entries_{month}.png", dpi=95)
    plt.close(fig)
