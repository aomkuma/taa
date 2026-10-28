"""The candidate rule "RF" (release-day fade) and its variants; design by default, the one test with --test.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/cand.py [--test]

RF (frozen in notes.md before the test):
  days     US 08:30 ET release days in gold.releases() (CPI, NFP, PPI, PCE, GDP); the calendar is known in advance.
  pairs    EURUSD, GBPUSD, AUDUSD, USDCHF, USDCAD, NZDUSD (not USDJPY).
  window   move = bid close of the bar ending 10:00 ET - open of the 08:00 ET bar; range = its high/low.
  filters  |move| >= 1 x H1 ATR(24); stalled: the 10:00 close is more than 10 % of the range back from the move's
           extreme; a release move: the pre-release drift (08:00 -> 08:30 close) is <= 25 % of the move.
  side     against the move, decided at the 10:00 ET close, filled at the next bar's open.
  stop     beyond the 08-10 extreme + 1.0 x ATR (distance from the decision close; at least 1 ATR); skipped when
           the stop is worth more than 4 USD at 0.01 lot.
  exit     no target; time exit at the close of the bar ending 14:00 ET.
  account  at most 3 pairs a day, cheapest spread first: EURUSD, GBPUSD, AUDUSD, USDCHF, USDCAD, NZDUSD.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import fxlib as fx  # noqa: E402
import lab  # noqa: E402
import reltrades as rt  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]
PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]


def rule(Ps, period, pre_max=None, extra=0.5, usd_cap=None, cap=None, stall=0.10, coin_seed=None,
         pairs=PAIRS) -> pd.DataFrame:
    out = []
    for p in pairs:
        P = Ps[p]
        ev = rt.build(P, 10, 14)
        ev = ev[ev.half.isin(period) & ev.rel].reset_index(drop=True)
        atr = ev.h1_atr.to_numpy()
        mv = ev.move.to_numpy()
        q = np.abs(mv) / atr
        side = -np.sign(mv).astype(int)
        side[q < 1.0] = 0
        ext = np.where(side < 0, ev.whi.to_numpy(), ev.wlo.to_numpy())
        back = np.abs(ext - ev.px.to_numpy()) / (ev.whi - ev.wlo).to_numpy()
        side[back <= stall] = 0
        pre_share = (ev.pre.to_numpy() - P.o[ev.a.to_numpy()]) / np.where(mv == 0, np.nan, mv)
        if pre_max is not None:
            side[~(pre_share <= pre_max)] = 0
        sl = np.maximum(np.abs(ext - ev.px.to_numpy()) + extra * atr, atr)
        if usd_cap is not None:
            side[sl * P.usd_pip[ev.d.to_numpy()] > usd_cap] = 0
        z = lab.simulate(P, ev, side, sl, None)
        if coin_seed is not None:
            rng = np.random.default_rng(coin_seed)
            coin = np.where(side != 0, rng.choice([-1, 1], len(side)), 0)
            zc = lab.simulate(P, ev, coin, sl, None).set_index("ev")
        if not len(z):
            continue
        z["pair"] = p
        z["day"] = ev.day.to_numpy()[z.ev]
        z["q"] = q[z.ev]
        z["pre_share"] = pre_share[z.ev]
        z["back"] = back[z.ev]
        if coin_seed is not None:
            for k in ("R", "pips", "usd", "exit", "kind"):
                z["coin_" + k] = zc[k].reindex(z.ev).to_numpy()
        out.append(z)
    z = pd.concat(out, ignore_index=True)
    if cap:
        z["prio"] = z.pair.map({p: i for i, p in enumerate(PAIRS)})
        z = z.sort_values(["day", "prio"]).groupby("day").head(cap)
    return z.sort_values("t").reset_index(drop=True)


def risk(z: pd.DataFrame, col="usd", rcol="R") -> dict:
    z = z.sort_values("t")
    eq = z[col].cumsum()
    dd = float((np.maximum(eq.cummax(), 0) - eq).max())
    streak = mx = 0
    for v in (z[rcol] < 0):
        streak = streak + 1 if v else 0
        mx = max(mx, streak)
    avg_loss = float(-z[z[col] < 0][col].mean())
    return dict(worst=float(z[col].min()), worst_day=float(z.groupby("day")[col].sum().min()), streak=mx, maxdd=dd,
                six=6 * avg_loss)


def line(name, z, halves=H):
    nh = [z[z.half == h].R.mean() for h in halves]
    r = risk(z)
    print(f"  {name:34s} n={len(z):4d} win {100 * (z.pips > 0).mean():3.0f}% net {z.R.mean():+.3f} "
          f"pos {sum(np.array(nh) > 0)}/5 | {rt.f(nh)} | USD {z.usd.sum():+6.1f} | worst {r['worst']:+.2f} "
          f"day {r['worst_day']:+.2f} streak {r['streak']} maxDD {r['maxdd']:.1f} 6L {r['six']:.1f}")


def main() -> None:
    Ps = {p: fx.Pair(p) for p in PAIRS}
    if "--test" not in sys.argv:
        line("V7b (no JPY, extra 0.5)", rule(Ps, H))
        line("V9  + pre-release share <= 0.25", rule(Ps, H, pre_max=0.25))
        line("V10 + stop extra 1.0 ATR", rule(Ps, H, pre_max=0.25, extra=1.0))
        line("V11 + stop <= 4 USD", rule(Ps, H, pre_max=0.25, extra=1.0, usd_cap=4.0))
        z = rule(Ps, H, pre_max=0.25, extra=1.0, usd_cap=4.0, cap=3, coin_seed=3)
        line("RF  + max 3 pairs/day (cheapest)", z)
        print(f"  RF coin side: net {z.coin_R.mean():+.3f} win {100 * (z.coin_pips > 0).mean():.0f}% "
              f"USD {z.coin_usd.sum():+.1f}; kinds ours {fx.kinds(z)} coin "
              f"{fx.kinds(z.assign(exit=z.coin_exit, kind=z.coin_kind))}")
        z.to_parquet("research/2026-10-18-moments/agents/fx/rf_design.parquet")
        for p in PAIRS:
            y = z[z.pair == p]
            print(f"     {p} n={len(y):3d} net {y.R.mean():+.3f} | {rt.f([y[y.half == h].R.mean() for h in H])}")
        return
    # ---- the one test (2026-03-01 .. 2026-10-14) ----
    z = rule(Ps, ["TEST"], pre_max=0.25, extra=1.0, usd_cap=4.0, cap=3, coin_seed=3)
    z.to_parquet("research/2026-10-18-moments/agents/fx/rf_test.parquet")
    print("RF test 2026-03-01 .. 2026-10-14")
    z["m"] = z.t.dt.strftime("%Y-%m")
    g = z.groupby("m").agg(n=("R", "size"), days=("day", "nunique"), win=("pips", lambda s: 100 * (s > 0).mean()),
                           pips=("pips", "sum"), usd=("usd", "sum"), R=("R", "mean"), coinR=("coin_R", "mean"),
                           coin_usd=("coin_usd", "sum"))
    print(g.round(3).to_string())
    print(f"total n={len(z)} release days traded {z.day.nunique()} win {100 * (z.pips > 0).mean():.0f}% "
          f"pips {z.pips.sum():+.1f} USD {z.usd.sum():+.2f} R/trade {z.R.mean():+.3f} (gross not shown) | coin "
          f"R {z.coin_R.mean():+.3f} win {100 * (z.coin_pips > 0).mean():.0f}% USD {z.coin_usd.sum():+.2f}")
    bd = pd.bdate_range("2026-03-02", "2026-10-14")
    print(f"trades per weekday {len(z) / len(bd):.3f}")
    print("per pair:")
    print(z.groupby("pair").agg(n=("R", "size"), win=("pips", lambda s: 100 * (s > 0).mean()), pips=("pips", "sum"),
                                usd=("usd", "sum"), R=("R", "mean"), coinR=("coin_R", "mean")).round(3).to_string())
    print("exits:", z.exit.value_counts().to_dict(), "| kinds ours", fx.kinds(z), "coin",
          fx.kinds(z.assign(exit=z.coin_exit, kind=z.coin_kind)))
    print("risk:", {k: round(v, 2) for k, v in risk(z).items()})
    print(z[["t", "pair", "side", "exit", "pips", "usd", "R", "sl", "q", "pre_share", "back", "mins"]].round(2).to_string())


if __name__ == "__main__":
    main()
