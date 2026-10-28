"""SW-20 - the own-result switch on the years no switch study has seen (pre-registered by the measurer in
precursors/notes.md "SW-20"; the build note is at the top of PROPOSALS.md).

The rule: a stream's event is traded for real only when at least 20 of the stream's earlier paper trades exited
strictly before its entry and the mean R of the last 20 of them (by exit time) is > 0. Every event is a paper trade
(the record is warmed from the store's first bar). N = 20 is fixed.

Modes:
    .venv/Scripts/python research/.../strategist/sw20.py check   # streams.build on the main store == states_events O1
    .venv/Scripts/python research/.../strategist/sw20.py run     # Y1 / Y2 / Y3, read once -> out_sw20.txt
Run from the repo root (gold.py reads relative paths).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # research/2026-10-18-moments (gold.py)

N = 20
YEARS = [("Y1", "2020-10-18", "2021-10-18"), ("Y2", "2021-10-18", "2022-10-18"), ("Y3", "2022-10-18", "2023-10-18")]
STREAMS = ("ORB", "RC_win", "RT_opp")


def switch_ok(t_exit: np.ndarray, R: np.ndarray, t_in: np.ndarray, n: int = N) -> np.ndarray:
    """For each entry time, True when >= n paper trades exited strictly before it and the mean R of the last n of them
    (ordered by exit time) is > 0. Trades without a result (R NaN, or t_exit <= 0) are not in the record."""
    ok = np.isfinite(R) & (t_exit > 0)
    te, rr = t_exit[ok], R[ok]
    o = np.argsort(te, kind="stable")
    te, rr = te[o], rr[o]
    out = np.zeros(len(t_in), dtype=bool)
    for i, t in enumerate(t_in):
        k = int(np.searchsorted(te, t, side="left"))  # exits < t
        if k >= n:
            out[i] = rr[k - n:k].mean() > 0
    return out


def streams_of(E: pd.DataFrame) -> pd.DataFrame:
    E = E[E.R_m1.notna()].copy()
    rc = E[E.stream == "RC"]
    return pd.concat([E[E.stream == "ORB"], rc[rc.win != "other"].assign(stream="RC_win"), E[E.stream == "RT_opp"]],
                     ignore_index=True)


def main() -> None:
    import gold
    import slib
    import streams

    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "check":
        m = gold.bars("M1", before=pd.Timestamp("2024-10-25", tz="UTC"))
        m = m[m.index >= pd.Timestamp("2023-09-01", tz="UTC")]
        m = m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)
        m = m[~m.index.duplicated(keep="last")].sort_index()
        m.index = pd.DatetimeIndex(m.index).as_unit("ns")
        E = streams.build(m, "2023-10-18", "2024-10-18")
        S = pd.read_parquet(slib.HERE / "states_events.parquet")
        S = S[S.part == "O1"]
        for st in ("ORB", "RC", "RT_opp"):
            a = E[E.stream == st].sort_values(["t_in", "kind"]).reset_index(drop=True)
            b = S[S.stream == st].sort_values(["t_in", "kind"]).reset_index(drop=True)
            same_t = len(a) == len(b) and bool((a.t_in.to_numpy() == b.t_in.to_numpy()).all())
            dR = float(np.nanmax(np.abs(a.R_m1.to_numpy() - b.R_m1.to_numpy()))) if same_t else np.nan
            print(f"check {st:7s} events {len(a)} vs states_events O1 {len(b)}; same entries {same_t}; "
                  f"max |dR| {dR:.2e}; R {a.R_m1.mean():+.4f} vs {b.R_m1.mean():+.4f}")
        return

    m = gold.bars("M1", before=pd.Timestamp("2023-10-21", tz="UTC"))
    m = m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)
    m = m[~m.index.duplicated(keep="last")].sort_index()
    m.index = pd.DatetimeIndex(m.index).as_unit("ns")
    print(f"M1 bars {len(m)}: {m.index.min()} .. {m.index.max()}")
    first = m.index.min().strftime("%Y-%m-%d")
    E = streams_of(streams.build(m, first, "2023-10-18"))

    def year(t: int) -> str:
        for k, a, b in YEARS:
            if pd.Timestamp(a, tz="UTC").value <= t < pd.Timestamp(b, tz="UTC").value:
                return k
        return ""

    E["year"] = [year(int(t)) for t in E.t_in]
    E["real"] = False
    for st in STREAMS:
        g = E[E.stream == st]
        E.loc[g.index, "real"] = switch_ok(g.t_exit_m1.to_numpy(np.int64), g.R_m1.to_numpy(float), g.t_in.to_numpy(np.int64))
    E.to_parquet(slib.HERE / "sw20_trades.parquet")
    print(f"paper events from {pd.Timestamp(E.t_in.min(), tz='UTC')} (the store's start)\n")
    print("per stream and year: always-on trades / R / summed R | switched: real trades / share / R per traded / summed R")
    for st in STREAMS + ("ALL3",):
        g = E if st == "ALL3" else E[E.stream == st]
        for y, _, _ in YEARS:
            x = g[g.year == y]
            k = x[x.real]
            print(f"{st:7s} {y}: always {len(x):4d} {x.R_m1.mean() if len(x) else np.nan:+.3f} {x.R_m1.sum():+7.1f} | "
                  f"real {len(k):4d} {len(k) / max(len(x), 1):4.0%} {k.R_m1.mean() if len(k) else np.nan:+.3f} "
                  f"{k.R_m1.sum():+7.1f}")
        x = g[g.year != ""]
        k = x[x.real]
        print(f"{st:7s} pooled: always {len(x):4d} {x.R_m1.mean():+.3f} {x.R_m1.sum():+7.1f} | real {len(k):4d} "
              f"{k.R_m1.mean() if len(k) else np.nan:+.3f} {k.R_m1.sum():+7.1f}\n")
    a3 = E[E.year != ""]
    sums = {y: a3[(a3.year == y) & a3.real].R_m1.sum() for y, _, _ in YEARS}
    pooled = a3[a3.real].R_m1.mean()
    print("PASS LINE (three together, switched): summed R >= 0 in each year: "
          + ", ".join(f"{y} {v:+.1f}" for y, v in sums.items()) + f"; pooled R per traded trade {pooled:+.3f}")
    print("verdict:", "PASS" if all(v >= 0 for v in sums.values()) and pooled >= 0 else "FAIL",
          "(Y1 holds only 2021-09-01 .. 2021-10-17 of M1)")


if __name__ == "__main__":
    main()
