"""An independent re-derivation of transform.py's results: a plain tick-by-tick loop (no cumulative arrays, no
searchsorted on the excursions), written separately from tsim.grid, on a fixed random sample of trade x cell rows of
transform_trades.parquet; every row must agree on the exit kind, the exit time and the pnl (1e-6).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/recheck_transform.py > .../out_recheck_transform.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import slib
import tsim

NS_MIN = 60 * 10**9


def loop(t, bid, ask, r) -> tuple[str, int, float]:
    f = 0
    while t[f] < r.t_in:
        f += 1
    s = int(r.side)
    e = ask[f] if s > 0 else bid[f]
    assert abs(e - r.entry) < 1e-9
    risk, d_t = r.risk, None
    # the target distance as the row was built: recompute from the rule's definitions
    side0 = s if r.side_v == "same" else -s
    e0 = ask[f] if side0 > 0 else bid[f]
    stop_px = e0 - side0 * r.stop_d if np.isfinite(r.stop_d) else r.stop_px
    d_s0 = side0 * (e0 - stop_px)
    tgt_px = e0 + side0 * r.tgt_r * d_s0 if np.isfinite(r.tgt_r) else r.tgt_px
    d_t0 = side0 * (tgt_px - e0) if np.isfinite(tgt_px) else np.nan
    if np.isfinite(d_t0) and d_t0 <= 0:
        d_t0 = np.nan
    d_t = {"orig": d_t0, "1R0": d_s0, "0.75": 0.75 * d_t0, "0.5": 0.5 * d_t0}[r.tgt]
    assert abs(risk - r.stop_m * d_s0) < 1e-6
    best = -np.inf
    k_surr = None
    if np.isfinite(r.surr_min):
        k_surr = r.surr_min * NS_MIN
    struct = None if (r.side_v != "same" or pd.isna(r.t_struct)) else int(r.t_struct)
    for k in range(f + 1, len(t)):
        if t[k] - t[k - 1] > 30 * NS_MIN:
            px = bid[k - 1] if s > 0 else ask[k - 1]
            return "break", int(t[k - 1]), s * (px - e)
        px = bid[k] if s > 0 else ask[k]
        fav = s * (px - e)
        if fav <= -risk:
            return "stop", int(t[k]), fav
        if np.isfinite(d_t) and fav >= d_t:
            return "target", int(t[k]), d_t
        if struct is not None and t[k] >= struct:
            return "structure", int(t[k]), fav
        if k_surr is not None and t[k] - t[f] >= k_surr and best < r.surr_usd:
            return "surrender", int(t[k]), fav
        if t[k] >= r.t_out:
            return "time", int(t[k]), fav
        best = max(best, fav)
    return "end", int(t[-1]), s * ((bid[-1] if s > 0 else ask[-1]) - e)


def main() -> None:
    A = pd.read_parquet(slib.HERE / "transform_trades.parquet")
    for c in ("stop_d", "tgt_r", "surr_min", "surr_usd", "t_struct", "stop_px", "tgt_px"):
        if c not in A:
            A[c] = np.nan
    S = A.sample(400, random_state=11)
    tk = tsim.Ticks()
    bad = 0
    for r in S.sort_values("t_in").itertuples():
        t, bid, ask = tk.span(int(r.t_in))
        k, xt, pnl = loop(t, bid, ask, r)
        ok = k == r.exit and xt == r.exit_t and abs(pnl - r.pnl) < 1e-6
        if not ok:
            bad += 1
            print(f"DIFF {r.family} {r.side_v} x{r.stop_m} {r.tgt} t_in {pd.Timestamp(int(r.t_in), tz='UTC')}: loop {k} {xt} {pnl:+.3f}"
                  f" | grid {r.exit} {r.exit_t} {r.pnl:+.3f}")
    print(f"{len(S) - bad} of {len(S)} rows agree; families {S.family.value_counts().to_dict()}; exits {S.exit.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
