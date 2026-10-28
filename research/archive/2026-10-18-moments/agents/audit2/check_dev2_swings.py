"""Audit of the second developer's V3-1 swings (dev2/swings.py, READ ONLY) on the real learning bars.

The bars come from `swings.load_learning()` (2025-08-01 .. 2026-04-17, the reader's filter keeps the exam out).
  A. tf_bars against precursors/indicators.bars on the real bars (OHLC, last, avail), every TF.
  B. Look-ahead by truncation: analyze() on a span, and on the same span cut at a server-day end; every reading of a
     bar complete by the cut (struct, pivots confirmed by then, events, boxes born by then, lines born by then) must
     be equal. Power: the full run must differ after the cut.
  C. The leg-extreme property: is every pivot the extreme of its leg (a trough the lowest low strictly between its two
     neighbouring peaks, a peak the highest high between its troughs)? Counted per TF, with the depth in USD.
  D. The running extreme (rule 4): `running()` (the lowest low / highest high since the last pivot) against the one
     the structure uses (the ZigZag's tracked extreme, from the confirming bar on), at every TF bar after a pivot.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_dev2_swings.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AG / "dev2"))
sys.path.insert(0, str(AG / "precursors"))
import indicators as IND  # noqa: E402
import swings as W  # noqa: E402

LEARN = pd.Timestamp("2025-10-18", tz="UTC")
TFS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def version() -> str:
    f = AG / "dev2" / "swings.py"
    return f"dev2/swings.py sha256 {hashlib.sha256(f.read_bytes()).hexdigest()[:16]}, mtime {pd.Timestamp(f.stat().st_mtime, unit='s', tz='UTC')}"


def part_a(m: pd.DataFrame) -> None:
    print("A. tf_bars against indicators.bars on the real bars")
    for tf in TFS[1:]:
        a, b = W.tf_bars(m, tf), IND.bars(m, W.RULES[tf])
        eq = {k: bool((a[k].to_numpy() == b[k].to_numpy()).all()) for k in ("open", "high", "low", "close", "last", "avail")}
        print(f"   {tf}: {len(a)} / {len(b)} bars, equal: {eq}")


def frames(r: W.TF, cut_bar: int) -> dict[str, pd.DataFrame]:
    """Everything known at the close of TF bar cut_bar."""
    pb, pp, pk, pc = r.piv
    k = pc <= cut_bar
    ev = r.events[r.events.bar <= cut_bar].drop(columns=["avail"], errors="ignore").reset_index(drop=True)
    bx = r.boxes[r.boxes.born <= cut_bar][["id", "born", "first"]].reset_index(drop=True)
    ln = r.lines[r.lines.born <= cut_bar].reset_index(drop=True)
    return {"struct": r.struct.iloc[: cut_bar + 1].reset_index(drop=True),
            "piv": pd.DataFrame({"b": pb[k], "p": pp[k], "k": pk[k], "c": pc[k]}), "events": ev, "boxes": bx, "lines": ln}


def same(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """Equal values (NaN = NaN); an empty frame equals an empty one with the same columns, whatever its dtypes."""
    if a.empty and b.empty:
        return list(a.columns) == list(b.columns)
    try:
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
    except AssertionError:
        return False
    return True


def part_b(m: pd.DataFrame) -> None:
    print("\nB. look-ahead by truncation (span 2025-11-03 .. 2026-01-30; cuts at three server-day ends)")
    span = m[(m.index >= "2025-11-03") & (m.index < "2026-01-31")]
    days = span.index.tz_convert("Europe/Athens").normalize()
    ends = [span.index[days == d][-1] for d in pd.unique(days)]
    cuts = [ends[10], ends[35], ends[50]]
    full = {tf: W.analyze(span, tf, inner=tf in ("M1", "M5")) for tf in TFS}
    for cut in cuts:
        part = span[span.index <= cut]
        line = []
        for tf in TFS:
            rf, rp = full[tf], W.analyze(part, tf, inner=tf in ("M1", "M5"))
            cb = len(rp.bars) - 1
            assert (rf.bars.avail.iloc[: cb + 1].to_numpy() == rp.bars.avail.to_numpy()).all(), tf
            A, B = frames(rf, cb), frames(rp, cb)
            ok = all(same(A[k], B[k]) for k in A)
            if not ok:
                bad = [k for k in A if not same(A[k], B[k])]
                line.append(f"{tf} DIFFERENT {bad}")
                continue
            power = len(rf.piv[0]) > len(B["piv"]) or len(rf.events) > len(B["events"])
            line.append(f"{tf} equal ({cb + 1} bars{', the future adds pivots / events' if power else ''})")
        print(f"   cut {cut:%Y-%m-%d %H:%M} UTC: " + "; ".join(line))


def leg_violations(h: np.ndarray, lo: np.ndarray, piv) -> pd.DataFrame:
    pb, pp, pk, pc = piv
    rows = []
    for k in range(1, len(pb) - 1):
        a, b = int(pb[k - 1]), int(pb[k + 1])
        if pk[k] == -1:
            j = a + 1 + int(np.argmin(lo[a + 1: b]))  # strictly between the neighbours (a wide pivot bar is one turn)
            if lo[j] < pp[k]:
                rows.append(dict(k=k, bar=int(pb[k]), kind=-1, price=pp[k], extreme_bar=j, extreme=lo[j], depth=pp[k] - lo[j],
                                 before_confirm_of_prev=bool(j < pc[k - 1])))
        else:
            j = a + 1 + int(np.argmax(h[a + 1: b]))
            if h[j] > pp[k]:
                rows.append(dict(k=k, bar=int(pb[k]), kind=1, price=pp[k], extreme_bar=j, extreme=h[j], depth=h[j] - pp[k],
                                 before_confirm_of_prev=bool(j < pc[k - 1])))
    return pd.DataFrame(rows, columns=["k", "bar", "kind", "price", "extreme_bar", "extreme", "depth", "before_confirm_of_prev"])


def part_cd(m: pd.DataFrame) -> None:
    print("\nC. is every pivot the extreme of its leg? (the pivots inside the learning parts, from 2025-10-18)")
    print("D. running() against the structure's running extreme (the ZigZag's tracked one), every TF bar after a pivot")
    for tf in ("M1", "M5", "M15", "M30", "H1", "H4"):
        b = W.tf_bars(m, tf)
        h, lo = b.high.to_numpy(float), b.low.to_numpy(float)
        thr = W.tf_threshold(m, b, tf)
        piv, dirs, exts = W.zigzag(h, lo, thr, state=True)
        t = pd.DatetimeIndex(b.t)
        inner = np.asarray(t[piv[0]] >= LEARN)
        V = leg_violations(h, lo, piv)
        V = V[np.asarray(t[V.bar.to_numpy()] >= LEARN)] if len(V) else V
        n = int(inner[1:-1].sum())
        dep = V.depth.describe() if len(V) else None
        print(f"   C {tf}: pivots {n}, not the extreme of their leg {len(V)} ({len(V) / max(n, 1):.1%})"
              + (f"; depth USD median {dep['50%']:.2f}, max {dep['max']:.2f}; the lower / higher bar before the previous "
                 f"pivot's confirmation {int(V.before_confirm_of_prev.sum())}" if len(V) else "")
              + f"; threshold median {np.median(thr[np.asarray(t >= LEARN)]):.2f}")
        if len(V):
            for r in V.head(3).itertuples():
                print(f"       e.g. {'trough' if r.kind == -1 else 'peak'} {t[r.bar]:%Y-%m-%d %H:%M} UTC at {r.price:.2f}; "
                      f"the leg's {'low' if r.kind == -1 else 'high'} {r.extreme:.2f} at {t[r.extreme_bar]:%Y-%m-%d %H:%M} UTC "
                      f"(the previous pivot confirmed {t[int(piv[3][r.k - 1])]:%Y-%m-%d %H:%M} UTC)")
        # D: at every bar j with a confirmed pivot and a tracked extreme
        pb, pp, pk, pc = piv
        diff = tot = 0
        q = -1
        for j in range(len(b)):
            while q + 1 < len(pc) and pc[q + 1] <= j:
                q += 1
            if q < 0 or dirs[j] == 0 or t[j] < LEARN:
                continue
            run = W.running(piv, h, lo, j)
            e = int(exts[j])
            zz = lo[e] if dirs[j] == -1 else h[e]
            tot += 1
            diff += run is not None and run[1] != zz
        print(f"   D {tf}: bars {tot}, running() != the tracked extreme on {diff} ({diff / max(tot, 1):.1%})")


def main() -> None:
    print(version())
    m = W.load_learning()
    print(f"bars {len(m)} {m.index.min()} .. {m.index.max()}")
    part_a(m)
    part_b(m)
    part_cd(m)


if __name__ == "__main__":
    main()
