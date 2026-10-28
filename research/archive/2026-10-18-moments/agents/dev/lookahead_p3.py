"""The no-look-ahead check for p3_trades.py (Task P3): for a seeded sample of catches, each new setting, on a window of
M1 around the catch, the whole trade (the entry, the stop, the exit's reason / tick / price / USD, the break-even time,
the stop level at the exit) is equal when every M1 bar and tick after the exit is replaced by other prices; power:
replacing everything from the entry decision on changes the exit.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_p3.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_trades as T3  # noqa: E402
import patterns as P  # noqa: E402
from lookahead_p import replaced  # noqa: E402
from lookahead_p2 import tfs_of, ticks_replaced  # noqa: E402

NS_MIN = 60 * 10**9
N_SAMPLE = 100
KEYS = ("entry_t", "entry", "stop", "risk", "exit", "exit_t", "exit_px", "pnl", "t_be")


def same(a: dict, b: dict) -> bool:
    for k in (*KEYS, "stop_exit"):
        x, y = a[k], b[k]
        if not (x == y or (isinstance(x, float) and isinstance(y, float) and np.isnan(x) and np.isnan(y))):
            return False
    return True


def trade(row: pd.DataFrame, w: pd.DataFrame, setting: str, ticks: tuple):
    tfs, pivs = tfs_of(w)
    s = T3.SETTINGS[setting]
    cand = T3.candidates3(row, tfs, s)
    if cand.empty:
        return None, None
    r = cand.iloc[0]
    return r, T3.one_trade3(r, tfs[r.tf], *pivs[r.tf], *ticks, 0.0, s["exit"])


def main() -> None:
    rng = np.random.default_rng(20261019)
    m = P.load_m1()
    idx = m.index.as_unit("ns").asi8
    C = pd.read_parquet(P.HERE / "p_catches.parquet")
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    ticks = T3.P2.Ticks()
    fails = 0
    for setting in ("L", "Xa", "Xb", "Xab", "ST"):
        rows = C.iloc[np.sort(rng.choice(len(C), N_SAMPLE, replace=False))]
        n = eq = changed = 0
        bad = []
        for i in range(len(rows)):
            row = rows.iloc[[i]]
            t_dec = int(row.t_dec.iloc[0])
            w = m.iloc[int(np.searchsorted(idx, t_dec - 7 * 1440 * NS_MIN)):int(np.searchsorted(idx, t_dec + 2 * 1440 * NS_MIN))]
            tk = ticks.span(t_dec)
            r, x = trade(row, w, setting, tk)
            if x is None:
                continue
            n += 1
            _, x2 = trade(row, replaced(w, int(x["exit_t"]) + 1, rng), setting, ticks_replaced(tk, int(x["exit_t"]), rng))
            if x2 is not None and same(x, x2):
                eq += 1
            else:
                bad.append(pd.Timestamp(t_dec, tz="UTC"))
            _, x3 = trade(row, replaced(w, int(r.t_entry), rng), setting, ticks_replaced(tk, int(r.t_entry), rng))
            changed += x3 is None or any(x[k] != x3[k] for k in ("exit", "exit_t", "pnl"))
        fails += n - eq
        print(f"{setting}: trades {n}; equal after the exit was replaced {eq} of {n}; changed when everything from the "
              f"entry decision was replaced {changed} of {n}" + (f"; DIFFERENT {bad[:5]}" if bad else ""), flush=True)
    if fails:
        raise SystemExit("LOOK-AHEAD CHECK FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
