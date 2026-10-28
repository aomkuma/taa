"""Round 2 frozen rules (notes.md, each written before its window run), one position at a time, real costs, against
the coin side on the same minutes (10 seeds) and before costs.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/rules2.py RULE [--window]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402
import simlib  # noqa: E402

REF = 4100.0
DESIGN = ("2023-11-01", "2026-03-01")
WINDOW = ("2026-03-01", "2026-10-17")
COLS = ["d", "e", "t", "side", "start", "ext", "run_t", "pl", "u", "size", "size_atr", "lvl_h72", "age", "atr15", "i_s",
        "xj", "lb"]

RULES2 = {
    # A9: RUN-A on strong runs (big, the 72-hour extreme broken, fresh), the stop beyond the run's start, 8 U, BE 0.6
    "A9": dict(kind="turn", big=3.7, brk72=True, fresh=120, exit="fixed", tp_u=8, be=0.6, hz=120),
    # A10: A9 with the trailing exit (armed at 0.5 x the run, trailing by 0.5 x the run, 240 min)
    "A10": dict(kind="turn", big=3.7, brk72=True, fresh=120, exit="trail", trail=0.5, hz=240),
    # A11 (window-informed, notes.md): A10 without the size condition
    "A11": dict(kind="turn", big=0.0, brk72=True, fresh=120, exit="trail", trail=0.5, hz=240),
    # D1: the deep limit at 61.8 % of a big R15 run, the stop beyond the start, the 1.618 extension, BE 0.6
    "D1": dict(kind="limit", f=0.618, big=3.7, tp_k=1.618, be=0.6, hz=120),
}


def turn_signals(P, cfg) -> pd.DataFrame:
    a = pd.read_parquet(HERE / "study_R15_design.parquet", columns=COLS)
    b = pd.read_parquet(HERE / "study_R15_window_feats.parquet", columns=COLS)
    S = pd.concat([a, b], ignore_index=True).sort_values("t")
    S = S[(S.size_atr >= cfg["big"]) & (S.age <= cfg["fresh"])]
    if cfg.get("brk72"):
        S = S[S.lvl_h72 > 0]
    return S.reset_index(drop=True)


def limit_signals(P, cfg) -> pd.DataFrame:
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[C.R == 15].sort_values("t")
    ot = P.ot
    rows = []
    for r in C.itertuples():
        s = int(r.side)
        i_s = ot.searchsorted(r.t)
        a = ot.searchsorted(r.t_tgt) + 1
        k0 = ot.searchsorted(r.t_end)
        b = min(i_s + 121, k0 + 60, len(ot) - 300)
        if a >= b:
            continue
        x0 = simlib.run_x0(P, i_s, a, s)  # fixed 2026-10-18: the start bar gives only its close
        got = simlib.limit_fill(P, a, b, s, r.start_px, cfg["f"], x0)
        if got is None:
            continue
        jf, entry, x = got
        t = ot[jf]
        if t.hour >= 20 or t.dayofweek >= 5:
            continue
        size = (x - r.start_px) * s
        if size / r.atr15 < cfg["big"]:
            continue
        rows.append(dict(t=t, e=jf, side=s, start=r.start_px, ext=x, run_t=r.t, entry=entry, u=P.o[jf] / REF, size=size,
                         a=a))
    return pd.DataFrame(rows).sort_values("t").reset_index(drop=True)


def one(P, r, cfg, AD, side=None):
    """One trade of signal *r*; *side* overrides the rule's side (the coin)."""
    s0 = int(r.side)
    s = s0 if side is None else side
    ss = P.stop_slip_ny if r.t.hour >= 12 else P.stop_slip
    if cfg["kind"] == "turn":
        e = int(r.e)
        entry = simlib.market_entry(P, e, s)
        ad = float(AD[int(r.d)])
        fill_bar = False
    else:
        e = int(r.e)
        entry = float(r.entry)
        ad = float(AD[e - 1])
        fill_bar = True
    # the stop beyond the run's start, measured from the rule's entry, also for the coin (same distance)
    entry0 = simlib.market_entry(P, e, s0) if cfg["kind"] == "turn" else entry
    sl = max((entry0 - (r.start - s0 * 0.3 * r.u)) * s0, 0.5 * ad, 3.0)
    if cfg.get("exit") == "trail":
        arm = cfg["trail"] * r.size
        x = simlib.trade_trail(P, e, s, entry, sl, arm, arm, cfg["hz"], ss, fill_bar=fill_bar)
        kind = simlib.kind_of(P, e, x["xj"], s, entry, arm, x["mfe"]) if x["exit"] == "stop" else ""
        tp = arm
        ex = "win" if (x["exit"] in ("trail", "time") and x["pnl"] > 0) else x["exit"]
    else:
        if cfg["kind"] == "turn":
            tp = cfg["tp_u"] * r.u
        else:
            tp = max((r.start + s0 * cfg["tp_k"] * r.size - entry0) * s0, 5.0)
        x = simlib.trade(P, e, s, entry, sl, tp, cfg["be"], cfg["hz"], ss, fill_bar=fill_bar)
        kind, ex = x["kind"], x["exit"]
    return dict(t=r.t, e=e, side=s, sl=sl, tp=tp, entry=entry, exit=ex, raw_exit=x["exit"], pnl=x["pnl"],
                R=x["pnl"] / (sl + ss), kind=kind, mins=x["mins"], session=0 if r.t.hour < 7 else (1 if r.t.hour < 12 else 2),
                start=r.start, run_t=r.run_t, size=r.size, ad_atr=ad, stop_ad=sl / ad, why=f"run {r.run_t:%H:%M} {r.size:.1f}",
                lvl=r.ext)


def simulate(P, S, cfg, AD, coin=None) -> pd.DataFrame:
    out, free = [], pd.Timestamp(0, tz="UTC")
    for r in S.itertuples():
        if r.t < free:
            continue
        side = None if coin is None else int(coin.choice([-1, 1]))
        x = one(P, r, cfg, AD, side)
        out.append(x)
        free = r.t + pd.Timedelta(minutes=int(x["mins"]))
    return pd.DataFrame(out)


def report(name, z, a, b, by) -> str:
    days = pd.bdate_range(a, b, inclusive="left").size
    eq = z.pnl.cumsum()
    streak = mx = 0
    for v in z.pnl:
        streak = streak + 1 if v < 0 else 0
        mx = max(mx, streak)
    key = z.t.dt.strftime("%Y-%m") if by == "month" else pd.cut(z.t, rules.HALVES, right=False)
    g = z.groupby(key, observed=True)
    per = " ".join(f"{(str(k)[2:7] if by == 'month' else str(k.left)[2:7])} {v.R.mean():+.2f}({len(v)},{v.pnl.sum():+.0f})"
                   for k, v in g)
    los = z[z.raw_exit == "stop"]
    kd = los.kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    return (f"  {name}: {len(z)} trades ({len(z) / days:.2f}/day), win {100 * (z.exit == 'win').mean():.0f}%, R {z.R.mean():+.3f},"
            f" {z.pnl.sum():+.1f} USD at 0.01 lot; worst {z.pnl.min():.2f}, streak {mx}, max DD {(eq.cummax() - eq).max():.1f},"
            f" 6 avg losses {-6 * los.pnl.mean() if len(los) else 0:.1f}; stop {z.sl.median():.2f} tp {z.tp.median():.2f}"
            f" (stop {z.stop_ad.median():.2f} x the trading-TF ATR); losers 1/2/3 {100 * kd['1']:.0f}/{100 * kd['2']:.0f}/{100 * kd['3']:.0f}%"
            f"; exits {dict(z.raw_exit.value_counts())}\n     {per}")


def main() -> None:
    rules.gold.below_normal_priority()
    name = sys.argv[1]
    cfg = RULES2[name]
    P = rules.jlib.Instr("XAUUSD")
    G = rules.jlib.Instr("XAUUSD")
    G.gross()
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_atr_usd"]).ad_atr_usd.reindex(P.ot).to_numpy()
    S = turn_signals(P, cfg) if cfg["kind"] == "turn" else limit_signals(P, cfg)
    parts = [("DESIGN", *DESIGN, "half")]
    if "--window" in sys.argv:
        parts.append(("WINDOW", *WINDOW, "month"))
    for part, a, b, by in parts:
        x = S[(S.t >= pd.Timestamp(a, tz="UTC")) & (S.t < pd.Timestamp(b, tz="UTC"))]
        z = simulate(P, x, cfg, AD)
        print(f"== {name} {part} {a} .. {b}: signals {len(x)}")
        print(report("rule", z, a, b, by))
        zg = simulate(G, x, cfg, AD)
        print(f"  before costs: R {zg.R.mean():+.3f}, {zg.pnl.sum():+.1f} USD")
        rs = [simulate(P, x, cfg, AD, np.random.default_rng(100 + k)) for k in range(10)]
        ck = pd.concat(rs)
        ck = ck[ck.raw_exit == "stop"].kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
        print(f"  coin (10 seeds, same minutes): R {np.mean([r.R.mean() for r in rs]):+.3f} (sd {np.std([r.R.mean() for r in rs]):.3f}),"
              f" USD {np.mean([r.pnl.sum() for r in rs]):+.1f}, losers 1/2/3 {100 * ck['1']:.0f}/{100 * ck['2']:.0f}/{100 * ck['3']:.0f}%")
        z.to_parquet(HERE / f"trades_{name}_{part.lower()}.parquet")


if __name__ == "__main__":
    main()
