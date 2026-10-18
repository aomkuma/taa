"""Round 7 (docs/OWN_SETUP_ROUNDS.md): New York with the H1 trend on the M15 pullback, adjusted iteration by iteration
through the losers' three kinds. Development: four older half-years (price-scaled tools) and the earlier six
months; the latest six months only with --test.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ny_lab.py ITERATION [--test]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

SLIP, REF = 0.07, 4100.0
DEV = [
    ("2023-11 .. 2024-04", "2023-11-01", "2024-04-14", True),
    ("2024-04 .. 2024-10", "2024-04-14", "2024-10-14", True),
    ("2024-10 .. 2025-04", "2024-10-14", "2025-04-14", True),
    ("2025-04 .. 2025-10", "2025-04-14", "2025-10-14", True),
    ("earlier six months", "2025-10-14", "2026-04-14", False),
]
TEST = [("LATEST SIX MONTHS", "2026-04-14", "2026-10-14", False)]

# iteration -> (row filter, exit plan); each later iteration is written in docs/OWN_SETUP_ROUNDS.md before it is run
ITER = {
    "0": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=8, sl=6, be=None, hz=60),
    "1": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=8, sl=6, be=0.6, hz=60),
    "2": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=6, sl=6, be=None, hz=60),
    "3": dict(rule=lambda d: (d.h1_e20_slope > 0.3233) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=8, sl=6, be=0.6, hz=60),
    "5": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=8, sl=6, be=0.6, hz=60, phase=28),
    "7": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=None, sl=None, be=0.6, hz=60, pa=True),
    "9": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=8, sl=6, be=0.6, hz=60, quiet=True),
    "10": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=8, sl=6, be=0.6, hz=60, recheck=3),
    "11": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45), tp=8, sl=6, be=0.6, hz=60, quiet=True, recheck=3),
    "4": dict(rule=lambda d: (d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 45) & (d.ret1 > 0), tp=8, sl=6, be=0.6, hz=60),
}


class M1:
    def __init__(self) -> None:
        m = gold.bars("M1")
        m = m[(m.index >= pd.Timestamp("2023-09-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-15", tz="UTC"))]
        self.ot = m.index
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * 0.01

    def trade(self, e: int, side: int, tp: float, sl: float, be: float | None, hz: int) -> dict:
        """One trade: target tp, stop sl (USD from the fill); *be*: at that share of the target the stop moves to
        the entry. The kind of a stopped loser (the owner's three) from the path up to 120 minutes."""
        entry = self.o[e] + (self.sp[e] + SLIP if side > 0 else -SLIP)
        stop, armed, mfe = entry - side * sl, False, 0.0
        end = min(e + hz, len(self.o) - 1)
        res = None
        for j in range(e, end):
            adv = self.lo[j] if side > 0 else self.h[j] + self.sp[j]
            fav = self.h[j] if side > 0 else self.lo[j] + self.sp[j]
            if (adv - stop) * side <= 0:
                px = stop - side * SLIP
                res = ("stop" if not armed else "be", (px - entry) * side, j)
                break
            if (fav - entry) * side >= tp:
                res = ("win", tp, j)
                break
            mfe = max(mfe, (fav - entry) * side)
            if be is not None and not armed and mfe >= be * tp:
                armed, stop = True, entry
        if res is None:
            x = end - 1
            px = self.c[x] - (SLIP if side > 0 else -(self.sp[x] + SLIP))
            res = ("time", (px - entry) * side, x)
        kind = ""
        if res[0] == "stop":
            later = range(res[2] + 1, min(e + 120, len(self.o)))
            hit = any(((self.h[k] if side > 0 else self.lo[k] + self.sp[k]) - entry) * side >= tp for k in later)
            kind = "3" if hit else ("2" if mfe >= 0.5 * tp else "1")
        return dict(exit=res[0], usd=res[1], mins=res[2] - e + 1, kind=kind)


def select(x: pd.DataFrame, P: M1, plan: dict, scale: bool, coin: np.random.Generator | None = None) -> pd.DataFrame:
    x = x.sort_values("t").drop_duplicates("t")
    rows, free, count = [], pd.Timestamp(0, tz="UTC"), {}
    for r in x.itertuples():
        key = r.t.normalize()
        if r.t < free or count.get(key, 0) >= 2:
            continue
        k = P.c[r.e - 1] / REF if scale else 1.0
        side = int(r.side) if coin is None else int(coin.choice([-1, 1]))
        sl = getattr(r, "pa_sl", None) if plan.get("pa") else plan["sl"] * k
        tp = 1.5 * sl if plan.get("pa") else plan["tp"] * k
        out = P.trade(int(r.e), side, tp, sl, plan["be"], plan["hz"])
        out |= {"t": r.t, "sl": sl}
        rows.append(out)
        free, count[key] = r.t + pd.Timedelta(minutes=int(out["mins"])), count.get(key, 0) + 1
    return pd.DataFrame(rows)


def main() -> None:
    it, test = sys.argv[1], "--test" in sys.argv
    plan = ITER[it]
    d = pd.read_parquet("data/research/own_ml_long.parquet")
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[d.session == 2]
    tk = pd.read_parquet("data/research/own_ml_ticks.parquet")
    tk["t"] = pd.to_datetime(tk.t, utc=True)
    d = d.merge(tk, on="t", how="left")
    for col in ("tk_ret5", "tk_ret15", "tk_ret30", "tk_ret60", "tk_imb60"):
        d[col] = d[col] * d.side
    P = M1()
    assert (P.ot[d.e.to_numpy()] == d.t).all()
    rows = d[plan["rule"](d)]
    if plan.get("recheck"):  # the signal at t - k must have held too (same side): enter at t
        prev = set(zip(rows.t, rows.side))
        lag = pd.Timedelta(minutes=plan["recheck"])
        first = np.array([(t - lag, s_) in prev and (t - pd.Timedelta(minutes=plan["recheck"] + 1), s_) not in prev
                          for t, s_ in zip(rows.t, rows.side)])
        rows = rows[first]
    if plan.get("quiet"):  # no entries in the 30 minutes after 08:30 ET and 09:30 ET
        ny = rows.t.dt.tz_convert("America/New_York")
        mins = ny.dt.hour * 60 + ny.dt.minute
        rows = rows[~(((mins >= 510) & (mins < 540)) | ((mins >= 570) & (mins < 600)))]
    if plan.get("pa"):  # the stop hunt and the reclaim on M1; the stop beyond the swept extreme + 1 ATR
        p = rows.e.to_numpy() - 1
        side = rows.side.to_numpy()
        h, lo, c = P.h, P.lo, P.c
        atr = pd.Series(h - lo).rolling(14).mean().to_numpy()
        prior_lo = np.array([lo[i - 17 : i - 2].min() for i in p])
        prior_hi = np.array([h[i - 17 : i - 2].max() for i in p])
        last_lo = np.array([lo[i - 2 : i + 1].min() for i in p])
        last_hi = np.array([h[i - 2 : i + 1].max() for i in p])
        buy = (last_lo < prior_lo) & (c[p] > prior_lo)
        sell = (last_hi > prior_hi) & (c[p] < prior_hi)
        trig = np.where(side > 0, buy, sell)
        fill = P.o[p + 1] + np.where(side > 0, P.sp[p + 1] + SLIP, -SLIP)
        stop = np.where(side > 0, last_lo - atr[p], last_hi + atr[p])
        risk = (fill - stop) * side
        k = np.where(rows.t < pd.Timestamp("2025-10-14", tz="UTC"), c[p] / REF, 1.0)
        ok = trig & (risk >= 3 * k) & (risk <= 12 * k)
        rows = rows[ok].assign(pa_sl=risk[ok])
    print(f"iteration {it}: {plan['tp']}/{plan['sl']} USD (price action: {bool(plan.get('pa'))}), break-even {plan['be']}, {plan['hz']} min; New York rows {len(rows)}")
    print("  window                trades /day  win%  USD/trade    R    USD (0.01 lot) months+ | kinds ours (1/2/3) | coin")
    rng = np.random.default_rng(3)
    shadow = None
    if plan.get("phase"):  # the setup's own record: shadow trades over the whole timeline, price-scaled before 2025-10-14
        parts = []
        for _n, a, b, scale in DEV + TEST:
            x = rows[(rows.t >= pd.Timestamp(a, tz="UTC")) & (rows.t < pd.Timestamp(b, tz="UTC"))]
            parts.append(select(x, P, plan, scale))
        shadow = pd.concat(parts, ignore_index=True)
        shadow["closed"] = shadow.t + pd.to_timedelta(shadow.mins, unit="min")
    for name, a, b, scale in (TEST if test else DEV):
        x = rows[(rows.t >= pd.Timestamp(a, tz="UTC")) & (rows.t < pd.Timestamp(b, tz="UTC"))]
        r = select(x, P, plan, scale)
        cn = select(x, P, plan, scale, rng)
        if shadow is not None:
            lb = pd.Timedelta(days=plan["phase"])
            ok = [shadow.usd[(shadow.closed < t) & (shadow.closed >= t - lb)].sum() > 0 for t in r.t]
            r = r[np.array(ok, dtype=bool)]
            cn = cn[np.array(ok, dtype=bool)] if len(cn) == len(ok) else cn
        days = pd.bdate_range(a, b).size
        if not len(r):
            print(f"  {name}: 0 trades")
            continue
        by_m = r.usd.groupby(r.t.dt.strftime("%Y-%m")).sum()

        def kinds(z: pd.DataFrame) -> str:
            v = z.kind[z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
            return f"{100 * v['1']:3.0f}/{100 * v['2']:3.0f}/{100 * v['3']:3.0f}%"

        print(f"  {name:20} {len(r):5} {len(r) / days:4.2f} {100 * (r.exit == 'win').mean():4.0f}  {r.usd.mean():+8.2f}"
              f"  {(r.usd / (r.sl + SLIP)).mean():+.3f}  {r.usd.sum():+9.1f}   {(by_m > 0).sum()}/{len(by_m)}"
              f"   | {kinds(r)} | {kinds(cn)} (coin {cn.usd.sum():+.0f} USD)")
        print(f"  {'':20} exits: {r.exit.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
