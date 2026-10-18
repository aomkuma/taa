"""Experiment harness: a stretch-fade rule with a market or limit entry, run by half-year with a coin-flip side.

    from exp import Lab; L = Lab(); L.run(dict(...), test=False)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common import DEV, REF, SLIP, TEST, Bars, gold
from feats import build
from sim import one_at_a_time, simulate

gold.below_normal_priority()


class Lab:
    def __init__(self) -> None:
        self.B = Bars()
        self.F = build(self.B)
        days = (self.B.t64 // 86_400_000_000_000).astype(np.int64)
        self.day = days
        self.dkey = days * 10 + self.F.ses.to_numpy()

    def candidates(self, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
        F = self.F
        x = F[cfg["feat"]].to_numpy(float)
        thr = cfg["thr"]
        ok = np.isfinite(x) & (np.abs(x) >= thr) & F.ok60.to_numpy() & np.isfinite(F.atr.to_numpy())
        if cfg.get("thr_max"):
            ok &= np.abs(x) < cfg["thr_max"]
        side = -np.sign(x).astype(int)
        if cfg.get("follow"):
            side = -side
        ses = cfg.get("ses")
        if ses is not None:
            ok &= np.isin(F.ses.to_numpy(), ses)
        if cfg.get("win"):  # minutes-of-day windows, (clock, a, b) with clock utc/ldn/ny
            w = np.zeros(len(ok), bool)
            for clock, a, b in cfg["win"]:
                mm = {"utc": self.B.utc_min, "ldn": self.B.ldn_min, "ny": self.B.ny_min}[clock]
                w |= (mm >= a) & (mm < b)
            ok &= w
        tr = F.tr.to_numpy()
        if cfg.get("trend") == "with":
            ok &= side == tr
        elif cfg.get("trend") == "against":
            ok &= side == -tr
        elif cfg.get("trend") == "notagainst":
            ok &= side != -tr
        if cfg.get("extra") is not None:
            ok &= cfg["extra"](F, side)
        if cfg.get("sl_cap"):  # the account: skip a signal whose stop would exceed sl_cap USD at 0.01 lot
            ok &= cfg["sl"] * F.atr.to_numpy(float) <= cfg["sl_cap"]
        i = np.flatnonzero(ok)
        i = i[i < self.B.n - 400]
        return i, side[i]

    def sim(self, cfg: dict, i: np.ndarray, side: np.ndarray) -> pd.DataFrame:
        B, F = self.B, self.F
        atr = F.atr.to_numpy(float)[i]
        scale = B.c[i] / REF
        sl = cfg["sl"] * atr
        tp = cfg["tp"] * atr
        if cfg.get("tp_floor"):
            tp = np.maximum(tp, cfg["tp_floor"] * scale)
        if cfg.get("sl_floor"):
            sl = np.maximum(sl, cfg["sl_floor"] * scale)
        if cfg.get("rr"):
            sl = tp / cfg["rr"]
        lim = None
        if cfg.get("off") is not None:
            lim = cfg["off"] * atr
        d = simulate(B, i, side, sl, tp, cfg["hold"], lim, cfg.get("valid", 0), cfg.get("be"))
        return d

    def run(self, cfg: dict, test: bool = False, coin_seeds: int = 1, quiet: bool = False,
            months: bool = False) -> pd.DataFrame:
        i, side = self.candidates(cfg)
        res = []
        d = self.sim(cfg, i, side)
        coins = []
        for sd in range(coin_seeds):
            rng = np.random.default_rng(sd + 11)
            cs = rng.choice([-1, 1], size=len(i))
            coins.append(self.sim(cfg, i, cs))
        for name, a, b in (TEST if test else DEV):
            ia, ib = self.B.idx(a), self.B.idx(b)
            days = np.unique(self.day[ia:ib]).size
            sel = (d.i >= ia) & (d.i < ib)
            t = one_at_a_time(d[sel], cfg.get("cap"), self.B, self.dkey)
            row = self.stats(t, days) | {"half": name[:5]}
            cr = []
            for cd in coins:
                tc = one_at_a_time(cd[sel], cfg.get("cap"), self.B, self.dkey)
                cr.append(self.stats(tc, days))
            row |= {"cR": np.mean([c["R"] for c in cr]), "cUSD": np.mean([c["usd"] for c in cr]),
                    "ck": cr[0]["kinds"]}
            res.append(row)
            if months:
                f = t[t.filled].copy()
                f["m"] = self.B.ot[f.i.to_numpy()].strftime("%Y-%m")
                f["R"] = f.usd / (f.sl + SLIP)
                tc = one_at_a_time(coins[0][sel], cfg.get("cap"), self.B, self.dkey)
                tc = tc[tc.filled].copy()
                tc["m"] = self.B.ot[tc.i.to_numpy()].strftime("%Y-%m")
                tc["R"] = tc.usd / (tc.sl + SLIP)
                dd = self.B.ot[ia:ib].strftime("%Y-%m")
                mdays = pd.Series(self.day[ia:ib], index=dd).groupby(level=0).nunique()
                g = f.groupby("m").agg(n=("usd", "size"), win=("exit", lambda e: (e == "win").mean()),
                                       usd=("usd", "sum"), R=("R", "mean"))
                g["per_day"] = g.n / mdays.reindex(g.index)
                g["k123"] = f[f.kind > 0].groupby("m").kind.apply(
                    lambda k: "/".join(f"{100 * (k == j).mean():.0f}" for j in (1, 2, 3)))
                g["coin_usd"] = tc.groupby("m").usd.sum()
                g["coin_R"] = tc.groupby("m").R.mean()
                g["coin_k123"] = tc[tc.kind > 0].groupby("m").kind.apply(
                    lambda k: "/".join(f"{100 * (k == j).mean():.0f}" for j in (1, 2, 3)))
                self.last_months = g
                self.last_trades = f
        out = pd.DataFrame(res).set_index("half")
        if not quiet:
            print(out.round(3).to_string())
        return out

    def stats(self, t: pd.DataFrame, days: int) -> dict:
        f = t[t.filled]
        n = len(f)
        if not n:
            return dict(n=0, pd=0, fill=0, win=np.nan, usd=0.0, R=np.nan, kinds="")
        r = f.usd / (f.sl + SLIP)
        k = f.kind[f.kind > 0]
        kinds = "/".join(f"{100 * (k == j).mean():.0f}" for j in (1, 2, 3)) if len(k) else ""
        return dict(n=n, pd=n / days, fill=n / len(t), win=(f.exit == "win").mean(), usd=f.usd.sum(),
                    R=r.mean(), kinds=kinds)
