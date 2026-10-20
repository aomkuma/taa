"""V3-1's no-look-ahead check (DEV_PROMPT section 2): at decision moments spread over P1 and P2, every M1 bar after the
decision is replaced by another path; every reading at the decision must be unchanged. With power: two planted
look-aheads must be caught.

Decisions (a rule written before running): every 1999th M1 bar of P1 and P2, from the 1000th. The data window of each
decision: the 20 calendar days before it and the 2 days after (the analysis runs on that window in both versions).
The two replacements of everything after the decision bar d: (a) the mirror of the real path about d's close
(x -> 2 x close_d - x, high and low swapped), (b) a flat line at d's close.

The readings compared at the decision (the close of bar d): S at d; for M1, M5, M15, M30, H1, H4, D1: the last complete TF
bar's index and its OHLC, the pivots known then (and the inner pivots), every per-bar structure column up to that bar
(labels, pairs, bias, box state, line ids and values), the events up to that bar, the lines born by then, and the
Fibonacci (H1, H4, D1), and the readout (rules 16-17: D1, H4, H1, M30, M15 label / bias, the side and the trend).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/lookahead_v31.py > research/2026-10-18-moments/agents/dev2/out_lookahead_v31.txt
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402

PARTS = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}
TFS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def readings(m: pd.DataFrame, d: int) -> dict:
    t_ns = np.array([W._ns([m.index[d] + pd.Timedelta(minutes=1)])[0]])
    out = {"S": float(W.swing_size(m)[d])}
    R = W.analyze_all(m, TFS)
    out["readout"] = W.readings_at(R, t_ns).to_csv()  # every TF of rule 16 + the side and trend (rule 17)
    for tf, r in R.items():
        j = int(r.at(t_ns)[0])
        out[f"{tf}.j"] = j
        if j < 0:
            continue
        out[f"{tf}.bars"] = r.bars.iloc[: j + 1][["open", "high", "low", "close"]].to_numpy().tobytes()
        out[f"{tf}.piv"] = tuple(a.tobytes() for a in W.known_at(r.piv, j))
        if r.inner:
            out[f"{tf}.inner"] = tuple(a.tobytes() for a in W.known_at(r.inner, j))
        st = r.struct.iloc[: j + 1].drop(columns=["avail"]).to_numpy(float)
        out[f"{tf}.struct"] = np.nan_to_num(st, nan=-999.0).tobytes()
        ev = r.events[r.events.bar <= j] if len(r.events) else r.events
        out[f"{tf}.events"] = ev.drop(columns=["avail"], errors="ignore").to_csv(index=False)
        ln = r.lines[r.lines.born <= j] if len(r.lines) else r.lines
        out[f"{tf}.lines"] = ln.to_csv(index=False)
        if tf in ("H1", "H4", "D1"):
            out[f"{tf}.fib"] = repr(W.fib_at(r, j))
    return out


def replaced(m: pd.DataFrame, d: int, how: str) -> pd.DataFrame:
    x = m.copy()
    c = float(m.close.iloc[d])
    fut = slice(d + 1, None)
    if how == "mirror":
        o, h, lo, cl = (m[k].to_numpy()[d + 1:] for k in ("open", "high", "low", "close"))
        x.iloc[fut, x.columns.get_loc("open")] = 2 * c - o
        x.iloc[fut, x.columns.get_loc("high")] = 2 * c - lo
        x.iloc[fut, x.columns.get_loc("low")] = 2 * c - h
        x.iloc[fut, x.columns.get_loc("close")] = 2 * c - cl
    else:
        for k in ("open", "high", "low", "close"):
            x.iloc[fut, x.columns.get_loc(k)] = c
    return x


def decisions(m: pd.DataFrame) -> list[int]:
    out = []
    for a, b in PARTS.values():
        idx = np.where((m.index >= pd.Timestamp(a, tz="UTC")) & (m.index < pd.Timestamp(b, tz="UTC")))[0]
        out += idx[1000::1999].tolist()
    return out


def window(m: pd.DataFrame, i: int) -> tuple[pd.DataFrame, int]:
    t = m.index[i]
    w = m[(m.index >= t - pd.Timedelta(days=20)) & (m.index <= t + pd.Timedelta(days=2))]
    return w, int(np.searchsorted(w.index, t))


def check(m: pd.DataFrame, D: list[int], label: str) -> tuple[int, int, dict]:
    eq = tot = 0
    diff: dict[str, int] = {}
    for i in D:
        w, d = window(m, i)
        base = readings(w, d)
        for how in ("mirror", "flat"):
            other = readings(replaced(w, d, how), d)
            for k, v in base.items():
                tot += 1
                if other.get(k) == v:
                    eq += 1
                else:
                    diff[k] = diff.get(k, 0) + 1
    print(f"{label}: {eq} of {tot} readings equal; differing keys: {diff if diff else 'none'}", flush=True)
    return eq, tot, diff


def main() -> None:
    t0 = time.time()
    m = W.load_learning()
    D = decisions(m)
    print(f"{len(D)} decisions: {sum(m.index[D] < pd.Timestamp('2026-01-16', tz='UTC'))} in P1, the rest in P2;"
          f" first {m.index[D[0]]}, last {m.index[D[-1]]}", flush=True)
    eq, tot, diff = check(m, D, "the code as it is")
    print("PASSED" if eq == tot else "FAILED", flush=True)

    # power: two planted look-aheads, on the first 15 decisions
    sub = D[:15]
    orig_size_at, orig_at = W.size_at, W.TF.at

    def size_at_peek(m_h1, t_ns):  # reads the H1 bar still forming (complete within the next 59 minutes)
        return orig_size_at(m_h1, np.asarray(t_ns) + 59 * W.NS_MIN)

    W.size_at = size_at_peek
    _, tot1, d1 = check(m, sub, "power 1 - S from the H1 bar still forming")
    W.size_at = orig_size_at

    def at_peek(self, t_ns):  # the next TF bar, before it is complete
        return np.minimum(orig_at(self, t_ns) + 1, len(self.bars) - 1)

    W.TF.at = at_peek
    _, tot2, d2 = check(m, sub, "power 2 - the TF bar after the last complete one")
    W.TF.at = orig_at
    print(f"power: planted look-ahead 1 caught: {bool(d1)}; planted look-ahead 2 caught: {bool(d2)}")
    print(f"done in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
