"""V3-1's shape check on 2026-10-19 (after the data end: shape only, no outcome, nothing fitted). The owner's reading and
the tolerances are in DEV_LOG.md ("The acceptance tolerances"), written before this ran.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/shape_v31.py > research/2026-10-18-moments/agents/dev2/out_shape_v31.txt
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402

TH = "Asia/Bangkok"
DAY = "2026-10-19"
TURNS = [("07:02", 1, 4187.63), ("08:26", -1, 4165.61), ("09:10", 1, 4184.49), ("09:32", -1, 4169.13),
         ("11:57", 1, 4184.68), ("12:29", -1, 4174.00), ("12:57", 1, 4186.18), ("13:32", -1, 4171.09),
         ("14:33", 1, 4190.25), ("17:46", -1, 4162.21), ("18:16", 1, 4177.06), ("19:03", -1, 4158.69),
         ("19:09", 1, 4170.00), ("20:47", -1, 4143.37), ("21:00", 1, 4155.32)]
TFS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def th(x) -> pd.Timestamp:
    return pd.Timestamp(f"{DAY} {x}", tz=TH)


def fmt(t) -> str:
    return pd.Timestamp(t).tz_convert(TH).strftime("%H:%M") if pd.notna(t) else "-"


def ns(t) -> int:
    return int(pd.Timestamp(t).tz_convert("UTC").as_unit("ns").value)


def piv_table(r: W.TF) -> pd.DataFrame:
    pb, pp, pk, pc = r.piv
    b = r.bars
    # the M1 minute holding the extreme inside the TF bar (for the TF bars), for the times
    return pd.DataFrame({"bar": pb, "price": pp, "kind": pk, "conf": pc, "t": b.t.to_numpy()[pb],
                         "known": b.avail.to_numpy()[pc]})


def m1_minute(m: pd.DataFrame, r: W.TF, bar: int, kind: int) -> pd.Timestamp:
    b = r.bars.iloc[bar]
    seg = m[(m.index >= b.t) & (m.index <= b["last"])]
    return seg.high.idxmax() if kind == 1 else seg.low.idxmin()


def main() -> None:
    m = W.load_live()
    print(f"bars: {len(m)} M1 from {fmt(m.index.min())} Thai {m.index.min().tz_convert(TH):%Y-%m-%d} to {fmt(m.index.max())} Thai"
          f" ({m.index.min()} .. {m.index.max()} UTC); the rows before 2026-10-18 00:00 UTC are filtered by the reader")
    R = W.analyze_all(m, TFS)
    s = W.swing_size(m)
    a = W.h1_atr(m)
    day = (m.index >= th("05:00")) & (m.index < th("23:00"))
    print(f"S on the day: min {s[day].min():.2f}, max {s[day].max():.2f}; the H1 ATR behind it: {np.nanmin(a[day]):.2f} .. {np.nanmax(a[day]):.2f}"
          f" (14 H1 bars exist from {fmt(R['H1'].bars.avail.iloc[14])} Thai; before that the warm-up mean)")

    # ---- 1. the 15 turns
    print("\n== 1. The 15 turns (M1 pivots; found = same kind, within 10 minutes and 1.00 USD)")
    P = piv_table(R["M1"])
    P = P[(P.t >= th("05:00")) & (P.t < th("23:00"))].copy()
    P["tt"] = P.t.map(fmt)
    used = set()
    found = 0
    for hm, k, px in TURNS:
        c = P[(P.kind == k) & ((P.t - th(hm)).abs() <= pd.Timedelta(minutes=10)) & ((P.price - px).abs() <= 1.0)]
        if len(c):
            row = c.iloc[0]
            used.add(int(row.bar))
            found += 1
            print(f"  FOUND  {hm} {'H' if k == 1 else 'L'} {px:.2f}: pivot {row.tt} {row.price:.2f}, known (confirmed) at {fmt(row.known)}")
        else:
            print(f"  MISSED {hm} {'H' if k == 1 else 'L'} {px:.2f}")
    extra = P[~P.bar.isin(used)]
    print(f"  found {found} of {len(TURNS)}; extra pivots on the day: {len(extra)}")
    for _, row in extra.iterrows():
        print(f"  EXTRA  {row.tt} {'H' if row.kind == 1 else 'L'} {row.price:.2f} (known {fmt(row.known)})")
    print("  all M1 pivots of the day: " + ", ".join(f"{r_.tt} {'H' if r_.kind == 1 else 'L'} {r_.price:.2f}" for _, r_ in P.iterrows()))

    # ---- 2. the structure per TF
    print("\n== 2. The structure per TF (label: up = HH+HL, down = LH+LL, mixed; bias = the last close beyond the last confirmed pivot)")
    times = pd.date_range(th("13:00"), th("22:00"), freq="5min")
    t_ns = np.array([ns(t) for t in times])
    lab = {}
    for tf in TFS:
        r = R[tf]
        j = r.at(t_ns)
        L = np.where(j >= 0, r.struct.label.to_numpy()[np.maximum(j, 0)], np.nan)
        B = np.where(j >= 0, r.struct.bias.to_numpy()[np.maximum(j, 0)], np.nan)
        lab[tf] = (L, B, j)
    code = {1.0: "U", -1.0: "D", 0.0: "x"}
    print("  time  " + " ".join(f"{tf:>5}" for tf in TFS) + "   (label/bias)")
    for i, t in enumerate(times):
        if t.minute % 15:
            continue
        print(f"  {fmt(t)}  " + " ".join(f"  {code.get(lab[tf][0][i], '?')}/{code.get(lab[tf][1][i], '?')}" for tf in TFS))
    after = times >= th("14:33")
    verdicts = {}
    for tf in TFS:
        L, B, _ = lab[tf]
        dn = np.where(after & (L == -1))[0]
        first = times[dn[0]] if len(dn) else None
        stays = None
        if first is not None:
            k0 = dn[0]
            stays = bool(np.all(L[k0:] == -1))
        bd = np.where(after & (B == -1))[0]
        bfirst = times[bd[0]] if len(bd) else None
        # the tolerance (DEV_LOG): label down by 18:55 and stays to 22:00; or bias down by 18:55 and label down by
        # 20:47, staying to 22:00
        ok_a = first is not None and first <= th("18:55") and stays
        ok_b = (bfirst is not None and bfirst <= th("18:55") and first is not None and first <= th("20:47") and stays)
        verdicts[tf] = ok_a or ok_b
        # the first M1 minute the label reads down after 14:33 (the 5-minute grid above rounds it)
        t1 = pd.date_range(th("14:33"), th("22:00"), freq="1min")
        j1 = R[tf].at(np.array([ns(t) for t in t1]))
        L1 = np.where(j1 >= 0, R[tf].struct.label.to_numpy()[np.maximum(j1, 0)], np.nan)
        B1 = np.where(j1 >= 0, R[tf].struct.bias.to_numpy()[np.maximum(j1, 0)], np.nan)
        f1 = t1[np.argmax(L1 == -1)] if (L1 == -1).any() else None
        b1 = t1[np.argmax(B1 == -1)] if (B1 == -1).any() else None
        print(f"  {tf}: to the minute: label down from {fmt(f1) if f1 is not None else '-'}, bias down from {fmt(b1) if b1 is not None else '-'}")
        print(f"  {tf}: label first down after 14:33 at {fmt(first) if first is not None else '-'}"
              f" (stays down to 22:00: {stays}); bias first down at {fmt(bfirst) if bfirst is not None else '-'}")
    for tf in ("M1", "M5", "M15", "M30", "H1"):
        r = R[tf]
        Q = piv_table(r)
        Q = Q[(Q.t >= th("11:00")) & (Q.t < th("23:00"))]
        txt = ", ".join(f"{fmt(m1_minute(m, r, int(q.bar), int(q.kind)))} {'H' if q.kind == 1 else 'L'} {q.price:.2f}"
                        f" [known {fmt(q.known)}]" for _, q in Q.iterrows())
        print(f"  {tf} pivots 11:00-23:00: {txt}")

    # ---- 3. the range box, its break, the tests of its top
    print("\n== 3. The range box")
    for tf in ("M5", "M1"):
        r = R[tf]
        bx = r.boxes
        for _, b in bx.iterrows():
            t_first, t_born = r.bars.t.iloc[b["first"]], r.bars.avail.iloc[b.born]
            t_end = r.bars.avail.iloc[b.end] if b.end >= 0 else None
            if t_born < th("05:00") or t_born > th("23:00"):
                continue
            tests_t = W.edge_tests(r, b, int(b.end if b.end >= 0 else len(r.bars) - 1), 1)
            tests_b = W.edge_tests(r, b, int(b.end if b.end >= 0 else len(r.bars) - 1), -1)
            print(f"  {tf} box {int(b.id)}: {b.bot:.2f} - {b.top:.2f} (height {b.top - b.bot:.2f}), first member {fmt(t_first)},"
                  f" born (4th pivot known) {fmt(t_born)}, members {b.n}, end {fmt(t_end) if t_end is not None else 'live'} ({b.why or 'live'});"
                  f" top tests {len(tests_t)} [{', '.join(f'{fmt(r.bars.t.iloc[x])} {p:.2f}' for x, p in tests_t)}];"
                  f" bottom tests {len(tests_b)}")
            ev = r.events[(r.events.tag.str.startswith("box")) & (r.events.obj == b.id)]
            for _, e in ev.iterrows():
                print(f"      {fmt(r.bars.t.iloc[e.bar])} bar ({tf}) {e.tag} {e.kind} level {e.level:.2f} price {e.price:.2f} (known {fmt(e.avail)})")

    # ---- 4. the lines and the retest
    print("\n== 4. The lines (support = rising lows, resistance = falling highs) and their breaks / retests")
    for tf in ("M1", "M5", "M15"):
        r = R[tf]
        Lr = r.lines
        if not len(Lr):
            continue
        pb, pp, pk, pc = r.piv
        for _, L in Lr.iterrows():
            born = r.bars.avail.iloc[int(L.born)]
            if born < th("05:00") or born > th("23:00"):
                continue
            la, lb = int(L.a), int(L.b)
            ta, tb = r.bars.t.iloc[pb[la]], r.bars.t.iloc[pb[lb]]
            v = lambda t: L.pa + L.slope * ((ns(t) // W.NS_MIN) - L.ta)  # noqa: E731
            print(f"  {tf} {'support' if L.kind == -1 else 'resistance'} {int(L.id)}: through {fmt(ta)} {pp[la]:.2f} and {fmt(tb)} {pp[lb]:.2f},"
                  f" {L.slope * 60:+.2f} USD/h, touches {L.touches}, born {fmt(born)}; at 17:20 {v(th('17:20')):.2f}, at 18:15 {v(th('18:15')):.2f}")
            ev = r.events[(r.events.tag.isin(["sup", "res"])) & (r.events.obj == L.id)]
            for _, e in ev.iterrows():
                print(f"      {fmt(r.bars.t.iloc[e.bar])} bar ({tf}) {e.kind} level {e.level:.2f} price {e.price:.2f} (known {fmt(e.avail)})")

    # ---- 5. the Fibonacci
    print("\n== 5. The Fibonacci of the last big swing (rule 8: the last completed H1 leg; beside it H4)")
    for tf in ("H1", "H4"):
        r = R[tf]
        for hm in ("14:40", "18:30", "20:47", "22:00"):
            j = int(r.at(np.array([ns(th(hm))]))[0])
            f = W.fib_at(r, j) if j >= 0 else None
            if f is None:
                print(f"  {tf} at {hm}: no completed leg yet")
                continue
            lv = ", ".join(f"{k * 100:.1f} % {x:.2f}" for k, x in f["levels"].items())
            print(f"  {tf} at {hm}: leg {fmt(r.bars.t.iloc[f['start_bar']])} {f['start']:.2f} -> {fmt(r.bars.t.iloc[f['end_bar']])} {f['end']:.2f}: {lv}")

    # ---- 6. the readout (rule 16): the D1 bias and the M15 / M30 / H1 trend, each as known then
    print("\n== 6. The readout (rule 16; label / bias, U up, D down, x mixed, ? unknown)")
    hm = ("07:00", "09:00", "13:00", "14:33", "15:00", "16:00", "17:20", "18:15", "18:30", "18:55", "19:00", "20:30", "20:47", "22:00")
    rd = W.readings_at(R, np.array([ns(th(x)) for x in hm]), tfs=("D1", "H4", "H1", "M30", "M15", "M5", "M1"))
    cols = ("D1", "H4", "H1", "M30", "M15", "M5", "M1")
    print("  (rule 17: side and trend, each from the labels / from the biases)")
    print("  time   " + " ".join(f"{c:>5}" for c in cols) + "   side  trend")
    for x, (_, row) in zip(hm, rd.iterrows()):
        print(f"  {x}  " + " ".join(f"  {code.get(row[c + '_label'], '?')}/{code.get(row[c + '_bias'], '?')}" for c in cols)
              + f"    {code.get(row.side, '?')}/{code.get(row.side_bias, '?')}   {code.get(row.trend, '?')}/{code.get(row.trend_bias, '?')}")
    print(f"  D1 bars on the day's data: {len(R['D1'].bars)}, the first complete at {fmt(R['D1'].bars.avail.iloc[0])} Thai"
          f" {R['D1'].bars.avail.iloc[0].tz_convert(TH):%Y-%m-%d} (after the data end) - so D1 reads unknown all day")

    with open(HERE / "v31_shape.pkl", "wb") as fh:
        pickle.dump(dict(m=m, R=R, s=s, verdicts=verdicts), fh)
    print("\nstructure verdicts (tolerance in DEV_LOG): " + ", ".join(f"{k} {'FOUND' if v else 'MISSED'}" for k, v in verdicts.items()))


if __name__ == "__main__":
    main()
