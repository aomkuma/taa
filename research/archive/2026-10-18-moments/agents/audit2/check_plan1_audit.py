"""The auditor's real-data check of the PLAN-1 runner's learning trades (dev/plan1.py, read only; audit round 3).

Learning parts only (2025-10-18 .. 2026-04-17); every store is read with a row filter that stops before 2026-04-18 and
every tick day read is asserted to be before it. The runner's exam switch is never used.

0. (--rebuild) `plan1.build(False, 0.0, 0.0)` in memory (nothing written to dev/) against the stored
   `dev/plan1_every_learn_s0_x0.parquet` / `plan1_trades_learn_s0_x0.parquet`: the stored files are this code's output.
1. The D1 state from a second source: MT5's own D1 bars (`data/history/.../D1.parquet`, from 2025-01-01), the last
   bar whose close_time <= the fill, the 20-day efficiency by my own loop, P1's terciles 0.116 / 0.264 - against the
   runner's `trend` on every trade; and the measurer's regime path (`plib.load_learning(2025-01-01)` ->
   `indicators.bars` -> `regime.state_at`), whose history starts 8 months earlier than the runner's.
2. One position at a time by its definition, and the weights from the written tables.
3. The cost: every fill against the raw tick at the fill time (a buy at the ask, a sell at the bid, no slippage);
   every market exit against the tick at the exit time (a buy out at the bid, a sell at the ask); target exits at the
   target; no tick beyond the stop before a non-stop exit; London / NY re-derived by the measurer's independent
   `precursors/check_plan1.py` functions with slippage 0.
4. The printed plan lines of `dev/out_plan1_learn_s0_x0.txt` recomputed by separate code (n, win, R, USD, max DD).

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/check_plan1_audit.py [--rebuild]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENTS = HERE.parent
ROOT = HERE.parents[3]
DEV = AGENTS / "dev"
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
TICKS = ROOT / "data/ticks/XAUUSD"
D1_FILE = ROOT / "data/history/FBS-Demo/XAUUSD/D1.parquet"
W_MECH = {("Asia B2", "trend"): 0.5, ("London ORB", "trend"): 0.5, ("NY straddle", "sideways"): 0.5,
          ("NY straddle", "mixed"): 0.5}  # CHECKLIST row 37: range pieces halved in a trend, the breakout outside one


def ticks_of(day: pd.Timestamp) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    day = day.normalize()
    assert day < EXAM, day
    x = pd.read_parquet(TICKS / f"{day:%Y-%m-%d}.parquet")
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


def span(t_in: int, t_out: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a = pd.Timestamp(t_in, tz="UTC").normalize()
    b = pd.Timestamp(t_out, tz="UTC").normalize()
    parts = [ticks_of(d) for d in pd.date_range(a, b, freq="D")]
    return tuple(np.concatenate([p[i] for p in parts]) for i in range(3))


def efficiency_loop(c: np.ndarray, n: int = 20) -> np.ndarray:
    out = np.full(len(c), np.nan)
    for i in range(n, len(c)):
        path = sum(abs(c[j] - c[j - 1]) for j in range(i - n + 1, i + 1))
        out[i] = abs(c[i] - c[i - n]) / path if path > 0 else np.nan
    return out


def label(e: float) -> str:
    return "sideways" if e < 0.116 else ("trend" if e > 0.264 else "mixed")


def check_state(A: pd.DataFrame) -> None:
    d = pd.read_parquet(D1_FILE, filters=[("open_time", ">=", pd.Timestamp("2025-01-01", tz="UTC")), ("open_time", "<", EXAM)])
    d = d.drop_duplicates("open_time", keep="last").sort_values("open_time").reset_index(drop=True)
    assert d.close_time.max() <= EXAM
    er = efficiency_loop(d.close.to_numpy(float))
    ct = pd.DatetimeIndex(d.close_time).as_unit("ns").asi8
    k = np.searchsorted(ct, A.t_in.to_numpy(np.int64), side="right") - 1
    mine = np.array([label(er[i]) for i in k])
    same = mine == A.trend.to_numpy(str)
    gap_days = (A.t_in.to_numpy(np.int64) - ct[k]) / 86400e9
    print(f"1. the D1 state from MT5's own D1 bars (my efficiency loop): {same.sum()} of {len(A)} equal; "
          f"NaN efficiency used {int(np.isnan(er[k]).sum())}; the bar read closed {gap_days.min():.2f}..{gap_days.max():.2f} days before the fill "
          f"(none after: {(gap_days >= 0).all()})")
    for i in np.nonzero(~same)[0][:10]:
        print(f"   differs {pd.Timestamp(int(A.t_in.iloc[i]), tz='UTC')} {A.piece.iloc[i]}: runner {A.trend.iloc[i]}, "
              f"mine {mine[i]} (er {er[k[i]]:.4f})")
    sys.path.insert(0, str(AGENTS / "precursors"))
    import plib  # noqa: PLC0415
    import regime  # noqa: PLC0415
    from indicators import bars  # noqa: PLC0415

    m = plib.load_learning(start=pd.Timestamp("2025-01-01", tz="UTC"))
    st = regime.state_at(bars(m, "1D"), pd.DatetimeIndex(pd.to_datetime(A.t_in.to_numpy(np.int64), utc=True)))
    print(f"   the measurer's regime path (M1 from 2025-01-01): {(st.trend.to_numpy(str) == A.trend.to_numpy(str)).sum()} of "
          f"{len(A)} equal; |er - mine| max {np.nanmax(np.abs(st.er.to_numpy() - er[k])):.2e}")
    counts = A.groupby(["part", "trend"]).size().to_dict()
    print(f"   trades per part x state: {counts}")


def check_stream(every: pd.DataFrame, A: pd.DataFrame) -> None:
    key = ["piece", "t_in"]
    kept = A.sort_values("t_in")
    ok_order = bool((np.diff(kept.t_in.to_numpy(np.int64)) >= 0).all())
    ok_free = bool((kept.t_in.to_numpy(np.int64)[1:] >= kept.t_out.to_numpy(np.int64)[:-1]).all())
    ks = set(map(tuple, A[key].itertuples(index=False)))
    dropped = [r for r in every.itertuples(index=False) if (r.piece, r.t_in) not in ks]
    covered = all(((kept.t_in <= r.t_in) & (r.t_in < kept.t_out)).any() for r in dropped)
    print(f"2. one position at a time: {len(every)} trades, {len(A)} kept, {len(dropped)} dropped; fill order {ok_order}; "
          f"no fill before the open trade's exit {ok_free}; every dropped trade inside a kept one {covered}")
    gaps = (kept.t_in.to_numpy(np.int64)[1:] - kept.t_out.to_numpy(np.int64)[:-1]) / 60e9
    print(f"   the closest next fill after an exit: {gaps.min():.1f} min")
    wm = np.array([W_MECH.get((p, s), 1.0) for p, s in zip(A.piece, A.trend, strict=True)])
    P1 = A[A.part == "P1"]
    rule = {(p, s): 0.5 for (p, s), g in P1.groupby(["piece", "trend"]) if g.R.mean() < 0}
    wp = np.array([rule.get((p, s), 1.0) for p, s in zip(A.piece, A.trend, strict=True)])
    print(f"   weights: w_mech equal {np.array_equal(wm, A.w_mech.to_numpy())}; the P1 rule on these trades {rule}; "
          f"w_p1 equal {np.array_equal(wp, A.w_p1.to_numpy())}")


def check_costs(A: pd.DataFrame) -> None:
    bad, n_stop_cross, n = [], 0, 0
    same_ms_in = [0]
    for r in A.itertuples(index=False):
        t, bid, ask = span(int(r.t_in), int(r.t_out))
        # several ticks can share one millisecond: the fill / exit is the first of them that matches
        mk_in, mk_out = (ask if r.side > 0 else bid), (bid if r.side > 0 else ask)
        f0, f1 = int(np.searchsorted(t, r.t_in, side="left")), int(np.searchsorted(t, r.t_in, side="right"))
        x0, x1 = int(np.searchsorted(t, r.t_out, side="left")), int(np.searchsorted(t, r.t_out, side="right"))
        hit_in = [i for i in range(f0, f1) if abs(mk_in[i] - r.entry) <= 1e-9]
        want_out = r.entry + r.pnl * r.side
        hit_out = [i for i in range(x0, x1) if (abs(mk_out[i] - want_out) <= 1e-6 if r.exit != "target"
                                                 else (mk_out[i] - want_out) * r.side >= -1e-9)]
        same_ms_in[0] += f1 - f0 > 1
        f = hit_in[0] if hit_in else f0
        x = hit_out[0] if hit_out else x0
        why = []
        if f1 == f0:
            why.append("fill time is not a tick")
        elif not hit_in:
            why.append(f"fill {r.entry} vs tick {mk_in[f0]}")
        if x1 == x0:
            why.append("exit time is not a tick")
        elif not hit_out:
            why.append("the exit price is not at the tick (or the target not reached)")
        if abs(r.risk - (r.entry - r.stop) * r.side) > 1e-6 or abs(r.pnl / r.risk - r.R) > 1e-9:
            why.append("risk / R")
        far = (bid if r.side > 0 else ask)[f + 1:x]
        if r.exit != "stop" and len(far) and ((far - r.stop) * r.side <= 0).any():
            n_stop_cross += 1
            why.append("a tick beyond the stop before the exit")
        if r.piece == "London ORB" and r.exit == "target" and abs(r.R - 2.0) > 1e-9:
            why.append(f"London target R {r.R}")
        n += 1
        if why:
            bad.append((r.piece, pd.Timestamp(int(r.t_in), tz="UTC"), "; ".join(why)))
    print(f"3. the cost on the raw ticks: {n} trades, {n - len(bad)} with the fill = the tick's ask / bid exactly (no "
          f"slippage), the exit at the tick (or the target), risk / R consistent; faults {len(bad)}; fills on a "
          f"millisecond holding more than one tick {same_ms_in[0]}")
    for b in bad[:10]:
        print(f"   {b}")
    sys.path.insert(0, str(AGENTS / "precursors"))
    import check_plan1 as CP  # noqa: PLC0415  (the measurer's independent London / NY)

    for name, mine in (("London ORB", CP.london(0.0)), ("NY straddle", CP.ny(0.0))):
        CP.compare(mine, A[A.piece == name].assign(t_in=pd.to_datetime(A[A.piece == name].t_in, utc=True)), name)


def recompute(G: pd.DataFrame, w: np.ndarray | None) -> dict:
    o = np.argsort(G.t_in.to_numpy(np.int64), kind="stable")
    r, p = G.R.to_numpy(float)[o], G.pnl.to_numpy(float)[o]
    w = np.ones(len(G)) if w is None else np.asarray(w, float)[o]
    eq, peak, dd = 0.0, 0.0, 0.0
    for v in p * w:
        eq += v
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dict(n=len(G), win=round(float((p > 0).mean()), 3), R=round(float((r * w).sum() / w.sum()), 3),
                usd=round(float((p * w).sum()), 2), dd=round(dd, 2))


def check_report(A: pd.DataFrame) -> None:
    text = (DEV / "out_plan1_learn_s0_x0.txt").read_text(encoding="utf-8")
    pat = re.compile(r"  (P1|P2): (\d+) trades \([\d.]+ a weekday\), win ([\d.]+), R ([+-][\d.]+) \(.*?\), USD ([+-][\d.]+), "
                     r"max DD ([\d.]+)")
    blocks = re.split(r"\nthe plan, ", text)[1:]
    eq = tot = 0
    for blk, col in zip(blocks, (None, "w_mech", "w_p1"), strict=True):
        for mt in pat.finditer(blk.split("\n  pooled")[0]):
            p = mt.group(1)
            G = A[A.part == p]
            got = recompute(G, None if col is None else G[col].to_numpy())
            printed = dict(n=int(mt.group(2)), win=float(mt.group(3)), R=float(mt.group(4)), usd=float(mt.group(5)),
                           dd=float(mt.group(6)))
            tot += 1
            eq += got == printed
            print(f"4. {col or 'unweighted'} {p}: printed {printed} | recomputed {got} | {'equal' if got == printed else 'DIFFERENT'}")
    print(f"   {eq} of {tot} plan lines equal")


def main() -> None:
    every = pd.read_parquet(DEV / "plan1_every_learn_s0_x0.parquet")
    A = pd.read_parquet(DEV / "plan1_trades_learn_s0_x0.parquet")
    assert (A.t_out.max() < EXAM.value) and (every.t_out.max() < EXAM.value)
    if "--rebuild" in sys.argv:
        sys.path.insert(0, str(DEV))
        import plan1  # noqa: PLC0415

        e2, a2 = plan1.build(False, 0.0, 0.0)
        for name, x, y in (("every", every, e2), ("trades", A, a2)):
            try:
                pd.testing.assert_frame_equal(x.reset_index(drop=True), y.reset_index(drop=True), check_dtype=False)
                print(f"0. rebuilt in memory = the stored {name} file ({len(x)} rows)")
            except AssertionError as err:
                print(f"0. rebuilt in memory != the stored {name} file: {str(err)[:300]}")
    check_state(A)
    check_stream(every, A)
    check_costs(A)
    check_report(A)


if __name__ == "__main__":
    main()
