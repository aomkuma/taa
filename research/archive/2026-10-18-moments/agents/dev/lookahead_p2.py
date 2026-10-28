"""The no-look-ahead check for p2_trades.py (Task P2), on the real M1 and ticks of the learning parts. For a seeded
sample of catches, each variant (A, B1, B2), on a window of M1 around the catch:

1. the B confirmation (the bar, the frozen high, the pullback low) is equal when every M1 bar from the confirmation's
   close on is replaced by other prices;
2. the whole trade (the entry tick and price, the stop, the target, the exit reason, tick, price and USD) is equal
   when every M1 bar and every tick after the exit is replaced by other prices;
3. power: replacing everything from the entry decision on changes the exit of many trades.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/lookahead_p2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p2_trades as T  # noqa: E402
import patterns as P  # noqa: E402
from lookahead_p import replaced  # noqa: E402

NS_MIN = 60 * 10**9
N_SAMPLE = 150
KEYS = ("entry_t", "entry", "stop", "risk", "exit", "exit_t", "exit_px", "pnl")


def tfs_of(w: pd.DataFrame) -> tuple[dict, dict]:
    tfs = {"M1": P.TF(w, 1), "M5": P.TF(w, 5)}
    return tfs, {k: T.last_pivot_prices(tf.piv, len(tf.c)) for k, tf in tfs.items()}


def trade(row: pd.DataFrame, w: pd.DataFrame, variant: str, ticks: tuple) -> tuple[pd.Series | None, dict | None]:
    tfs, pivs = tfs_of(w)
    cand = T.candidates(row, tfs, variant)
    if cand.empty:
        return None, None
    r = cand.iloc[0]
    rr = r.copy()
    x = T.one_trade(rr, tfs[r.tf], *pivs[r.tf], *ticks, 0.0)
    return r, x


def ticks_replaced(ticks: tuple, t_cut: int, rng: np.random.Generator) -> tuple:
    """Every tick after t_cut replaced by a random walk (other bids and asks, the same times)."""
    t, bid, ask = (np.array(a) for a in ticks)
    k = int(np.searchsorted(t, t_cut, side="right"))
    n = len(t) - k
    if n > 0:
        p = bid[k - 1] + np.cumsum(rng.normal(0, 0.6, n)) + 30 * np.sin(np.arange(n) / 500)
        bid[k:], ask[k:] = p, p + 0.3
    return t, bid, ask


def main() -> None:
    rng = np.random.default_rng(20261019)
    m = P.load_m1()
    idx = m.index.as_unit("ns").asi8
    C = pd.read_parquet(P.HERE / "p_catches.parquet")
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    ticks = T.Ticks()
    out = {}
    for variant in ("A", "B1", "B2"):
        rows = C.iloc[np.sort(rng.choice(len(C), N_SAMPLE, replace=False))]
        n = conf_eq = conf_n = eq = changed = 0
        bad = []
        for i in range(len(rows)):
            row = rows.iloc[[i]]
            t_dec = int(row.t_dec.iloc[0])
            a = int(np.searchsorted(idx, t_dec - 7 * 1440 * NS_MIN))
            b = int(np.searchsorted(idx, t_dec + 2 * 1440 * NS_MIN))
            w = m.iloc[a:b]
            tk = ticks.span(t_dec)
            r, x = trade(row, w, variant, tk)
            if variant != "A":  # 1. the confirmation with the bars from its close on replaced
                tfs, _ = tfs_of(w)
                tf = tfs[row.tf.iloc[0]]
                d = int(np.searchsorted(tf.avail, t_dec))
                c0 = T.confirm_b(tf.h, tf.lo, tf.c, d, float(row.extreme.iloc[0]), float(row.atr.iloc[0]), int(row.side.iloc[0]))
                if c0 is not None:
                    w2 = replaced(w, int(tf.avail[c0["k"]]), rng)
                    tf2 = tfs_of(w2)[0][row.tf.iloc[0]]
                    c1 = T.confirm_b(tf2.h, tf2.lo, tf2.c, d, float(row.extreme.iloc[0]), float(row.atr.iloc[0]),
                                     int(row.side.iloc[0]))
                    conf_n += 1
                    conf_eq += c0 == c1
            if x is None:
                continue
            n += 1
            # 2. everything after the exit replaced: the bars opening after the exit and the ticks after it
            w2 = replaced(w, int(x["exit_t"]) + 1, rng)
            _, x2 = trade(row, w2, variant, ticks_replaced(tk, int(x["exit_t"]), rng))
            if x2 is not None and all(x[k] == x2[k] for k in KEYS):
                eq += 1
            else:
                bad.append((pd.Timestamp(t_dec, tz="UTC"), variant))
            # 3. power: everything from the entry decision on replaced
            w3 = replaced(w, int(r.t_entry), rng)
            _, x3 = trade(row, w3, variant, ticks_replaced(tk, int(r.t_entry), rng))
            changed += x3 is None or any(x[k] != x3[k] for k in ("exit", "exit_t", "pnl"))
        out[variant] = (n, eq, changed, conf_n, conf_eq, bad)
        print(f"{variant}: trades {n}; equal after the exit was replaced {eq} of {n}; changed when everything from the "
              f"entry decision was replaced {changed} of {n}" + (f"; B confirmations equal after their close was replaced "
              f"{conf_eq} of {conf_n}" if variant != "A" else "") + (f"; DIFFERENT {bad[:5]}" if bad else ""), flush=True)
    if any(v[0] != v[1] or v[3] != v[4] for v in out.values()):
        raise SystemExit("LOOK-AHEAD CHECK FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
