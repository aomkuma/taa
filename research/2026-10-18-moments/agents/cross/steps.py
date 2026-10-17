"""Agent "cross", step 6: the step table for the London rule (design data by default; --test for the one test of a
frozen rule, see notes.md). Every config: R a trade by half (or by month), trades, win %, the coin on the same
minutes (20 seeds), the losers' kinds, and the account view at 0.01 lot (worst loss USD, longest losing streak,
max drawdown USD, 6 average losses in USD).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/steps.py [--test CONFIG]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from design import fires, signals  # noqa: E402
from fxlab import PIP, Inst, kinds, run  # noqa: E402
from measure import HALVES, PANEL, scaled_returns  # noqa: E402
from measure2 import dollar_ex  # noqa: E402

DIRN = {"EURUSD": -1, "GBPUSD": -1, "USDCHF": 1, "USDCAD": 1, "USDJPY": 1}
DESIGN = (pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC"))
TEST = (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-10-15", tz="UTC"))
ALL5, FOUR = list(DIRN), ["EURUSD", "GBPUSD", "USDCHF", "USDCAD"]

# name -> config. plan: (tp, sl) in pips, or ("atr", k_tp, k_sl, floor_sl) in H1 ATR14 units
CONFIGS = {
    "s0 base: 5 pairs, |eq30|>=2.0, 20/15, 120m": dict(pairs=ALL5, sig="eq30", thr=2.0, plan=(20, 15), hz=120, usd=None),
    "s1 + the dollar not yet moved (usd30<=0)": dict(pairs=ALL5, sig="eq30", thr=2.0, plan=(20, 15), hz=120, usd=0.0),
    "s1b usd30<=0, 4 pairs (no USDJPY)": dict(pairs=FOUR, sig="eq30", thr=2.0, plan=(20, 15), hz=120, usd=0.0),
    "s1c usd30<=0, EURUSD only": dict(pairs=["EURUSD"], sig="eq30", thr=2.0, plan=(20, 15), hz=120, usd=0.0),
    "s2 4 pairs, target/stop 15/10": dict(pairs=FOUR, sig="eq30", thr=2.0, plan=(15, 10), hz=120, usd=0.0),
    "s2b 4 pairs, 15/15": dict(pairs=FOUR, sig="eq30", thr=2.0, plan=(15, 15), hz=120, usd=0.0),
    "s2c 4 pairs, ATR 1.5/1.0 (sl>=10)": dict(pairs=FOUR, sig="eq30", thr=2.0, plan=("atr", 1.5, 1.0, 10), hz=120, usd=0.0),
    "s2d 4 pairs, ATR 2.0/1.5 (sl>=12)": dict(pairs=FOUR, sig="eq30", thr=2.0, plan=("atr", 2.0, 1.5, 12), hz=120, usd=0.0),
    "s3 4 pairs, 15/10, 180m": dict(pairs=FOUR, sig="eq30", thr=2.0, plan=(15, 10), hz=180, usd=0.0),
    "s4 4 pairs, 15/10, |eq30|>=2.5": dict(pairs=FOUR, sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0),
    "s5 EURUSD only, 15/10": dict(pairs=["EURUSD"], sig="eq30", thr=2.0, plan=(15, 10), hz=120, usd=0.0),
    "s6 s4 + the pair not yet moved (own30<=0.5)": dict(pairs=FOUR, sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0, own=0.5),
    "s7 s6 + the pair not stretched (rng60<=1.5 ATR)": dict(pairs=FOUR, sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0, own=0.5, stretch=1.5),
    "s8 s7, EURUSD + GBPUSD only": dict(pairs=["EURUSD", "GBPUSD"], sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0, own=0.5, stretch=1.5),
    "s9 s7 at |eq30|>=2.0": dict(pairs=FOUR, sig="eq30", thr=2.0, plan=(15, 10), hz=120, usd=0.0, own=0.5, stretch=1.5),
    "s10 s7 with 20/15": dict(pairs=FOUR, sig="eq30", thr=2.5, plan=(20, 15), hz=120, usd=0.0, own=0.5, stretch=1.5),
    "s11 s7, all five pairs": dict(pairs=ALL5, sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0, own=0.5, stretch=1.5),
}


def usd_per_pip(sym: str, price_pips: np.ndarray) -> np.ndarray:
    if sym.endswith("USD"):
        return np.full(len(price_pips), 1000 * PIP[sym])
    return 1000 / price_pips  # USDxxx at 0.01 lot: 1,000 units x pip (quote) / price


def h1_atr(inst: Inst) -> pd.Series:
    m = pd.DataFrame({"h": inst.h, "l": inst.lo, "c": inst.c}, index=inst.ot)
    h1 = m.resample("1h", label="left", closed="left").agg({"h": "max", "l": "min", "c": "last"}).dropna()
    tr = pd.concat([h1.h - h1.l, (h1.h - h1.c.shift()).abs(), (h1.l - h1.c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(14).mean()


class Lab:
    def __init__(self) -> None:
        self.sig = signals()
        self.panel = pd.read_parquet(PANEL)
        self.t_ns = self.panel.index.as_unit("ns").asi8
        self.inst, self.usd, self.own, self.atr = {}, {}, {}, {}

    def pair(self, sym: str) -> None:
        if sym in self.inst:
            return
        self.inst[sym] = Inst(sym)
        q = self.panel.copy()
        q["USDx"] = dollar_ex(self.panel, sym)
        self.usd[sym] = pd.Series(scaled_returns(q, "USDx", 30, -1, self.t_ns), index=self.panel.index)
        self.own[sym] = pd.Series(scaled_returns(q, sym, 30, -1, self.t_ns), index=self.panel.index)
        self.atr[sym] = h1_atr(self.inst[sym])

    def trades(self, cfg: dict, lo: pd.Timestamp, hi: pd.Timestamp, coin: np.random.Generator | None = None) -> pd.DataFrame:
        f = fires(self.sig[cfg["sig"]], (7, 12), cfg["thr"], lo, hi)
        out = []
        for sym in cfg["pairs"]:
            self.pair(sym)
            inst = self.inst[sym]
            side = (np.sign(f.to_numpy()) * DIRN[sym]).astype(int)
            ff, ss = f, side
            if cfg["usd"] is not None:  # the dollar composite (without this pair) has not yet moved the trade's way
                usd_dir = side * (1 if sym.startswith("USD") else -1)  # +1 = the trade wants the dollar up
                ok = (self.usd[sym].reindex(f.index).to_numpy() * usd_dir) <= cfg["usd"]
                ff, ss = f[ok], side[ok]
            if cfg.get("own") is not None:  # the pair itself has not already moved the trade's way (vol-scaled 30 min)
                own = self.own[sym].reindex(ff.index).to_numpy() * ss
                ok = own <= cfg["own"]
                ff, ss = ff[ok], ss[ok]
            if cfg.get("stretch") is not None:  # the pair's last 60-minute range <= k x its H1 ATR14 (closed bars)
                di = inst.index_at(ff.index)
                a = self.atr[sym]
                k = a.index.searchsorted(ff.index + pd.Timedelta(minutes=1) - pd.Timedelta(hours=1), side="right") - 1
                rng = np.array([inst.h[i - 59:i + 1].max() - inst.lo[i - 59:i + 1].min() if i >= 60 else np.nan for i in di])
                ok = rng <= cfg["stretch"] * a.to_numpy()[k]
                ff, ss = ff[ok], ss[ok]
            if coin is not None:
                ss = coin.choice([-1, 1], len(ss))
            d = inst.index_at(ff.index)
            rows = []
            if cfg["plan"][0] == "atr":
                _, ktp, ksl, floor = cfg["plan"]
                a = self.atr[sym]
                k = a.index.searchsorted(ff.index + pd.Timedelta(minutes=1) - pd.Timedelta(hours=1), side="right") - 1
                av = a.to_numpy()[k]
                free = -1
                for di, s, t, at in zip(d, ss, ff.index, av):
                    if di < 0 or di + 1 <= free or not np.isfinite(at):
                        continue
                    sl = max(ksl * at, floor)
                    r = inst.trade(int(di), int(s), sl * ktp / ksl, sl, None, cfg["hz"])
                    if r is None:
                        continue
                    rows.append(r | {"t": t, "side": int(s), "sl": sl})
                    free = r["e"] + r["mins"]
                r = pd.DataFrame(rows)
            else:
                r = run(inst, d, ss, cfg["plan"][0], cfg["plan"][1], None, cfg["hz"], ff.index)
                r["sl"] = cfg["plan"][1]
            if not len(r):
                continue
            r["sym"] = sym
            r["usd"] = r.pnl * usd_per_pip(sym, inst.o[r.e.to_numpy()])
            r["usd_risk"] = (r.sl + 0.3) * usd_per_pip(sym, inst.o[r.e.to_numpy()])
            r["close_t"] = r.t + pd.to_timedelta(r.mins + 1, unit="min")
            out.append(r)
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def account(r: pd.DataFrame) -> dict:
    s = r.sort_values("close_t")
    eq = s.usd.cumsum().to_numpy()
    dd = float((np.maximum.accumulate(np.concatenate([[0.0], eq])) - np.concatenate([[0.0], eq])).max())
    streak = best = 0
    for v in s.usd.to_numpy():
        streak = streak + 1 if v < 0 else 0
        best = max(best, streak)
    losses = s.usd[s.usd < 0]
    return dict(worst=float(s.usd.min()), streak=best, maxdd=dd, six=6 * float(losses.mean()) if len(losses) else 0.0)


def row(lab: Lab, name: str, cfg: dict, lo: pd.Timestamp, hi: pd.Timestamp, periods: list) -> None:
    r = lab.trades(cfg, lo, hi)
    rng = np.random.default_rng(5)
    cs = [lab.trades(cfg, lo, hi, rng) for _ in range(20)]
    c = pd.concat(cs, ignore_index=True)
    days = pd.bdate_range(lo, min(hi, pd.Timestamp("2026-10-06", tz="UTC"))).size
    per = []
    for n, a, b in periods:
        m = (r.t >= a) & (r.t < b)
        per.append(f"{r.R[m].mean():+.2f}({m.sum()})" if m.any() else "   -   ")
    gross = (r.pnl + np.where(r.exit == "stop", 0.3, 0.2) + 0.2 + 0.25).mean()  # rough: costs added back, pips
    a = account(r)
    print(f"{name}\n   n {len(r)} ({len(r) / days:.2f}/day)  win {100 * (r.exit == 'win').mean():.0f}% "
          f"(coin {100 * (c.exit == 'win').mean():.0f}%)  R {r.R.mean():+.3f} (coin {c.R.mean():+.3f}, edge {r.R.mean() - c.R.mean():+.3f})"
          f"  pips/tr {r.pnl.mean():+.2f} (gross ~{gross:+.2f})  USD {r.usd.sum():+.1f}\n   periods: " + " ".join(per)
          + f"\n   exits {r.exit.value_counts().to_dict()}  kinds ours {kinds(r)} coin {kinds(c)}"
          + f"\n   account@0.01: worst {a['worst']:+.2f} USD, longest losing streak {a['streak']}, max DD {a['maxdd']:.2f} USD,"
          f" 6 avg losses {a['six']:+.2f} USD, avg risk/trade {r.usd_risk.mean():.2f} USD")
    return r


def main() -> None:
    gold.below_normal_priority()
    lab = Lab()
    if "--test" in sys.argv:
        name = sys.argv[sys.argv.index("--test") + 1]
        cfg = FROZEN[name]
        lo, hi = TEST
        months = [(m.strftime("%Y-%m"), m, m + pd.offsets.MonthBegin(1)) for m in pd.date_range("2026-03-01", "2026-10-01", freq="MS", tz="UTC")]
        r = row(lab, f"TEST {name}: {cfg}", cfg, lo, hi, months)
        r.to_csv(f"research/2026-10-18-moments/agents/cross/trades_test_{name}.csv", index=False)
        r["m"] = r.t.dt.strftime("%Y-%m")
        print(r.groupby("m").agg(n=("R", "size"), win=("exit", lambda e: (e == "win").mean()), R=("R", "mean"), usd=("usd", "sum")).round(3).to_string())
        print(r.groupby("sym").agg(n=("R", "size"), R=("R", "mean"), usd=("usd", "sum")).round(3).to_string())
        return
    halves = [(n, pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")) for n, a, b in HALVES]
    print("design halves: " + " ".join(n for n, _a, _b in halves))
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for name, cfg in CONFIGS.items():
        if only and not any(name.startswith(o) for o in only):
            continue
        r = row(lab, name, cfg, *DESIGN, halves)
        r.to_csv(f"research/2026-10-18-moments/agents/cross/trades_design_{name.split()[0]}.csv", index=False)


# frozen 2026-10-17 before the test (notes.md, "FROZEN RULES")
FROZEN: dict[str, dict] = {
    "X4": dict(pairs=FOUR, sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0),
    "X6": dict(pairs=FOUR, sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0, own=0.5),
    "X7": dict(pairs=FOUR, sig="eq30", thr=2.5, plan=(15, 10), hz=120, usd=0.0, own=0.5, stretch=1.5),
}

if __name__ == "__main__":
    main()
