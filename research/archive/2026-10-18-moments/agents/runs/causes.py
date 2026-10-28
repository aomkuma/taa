"""The losers' causes for a rule's design trades: every trade with its context at the decision bar (feats.parquet,
signed so that + = in the trade's favour) and its mirror (the other side, same minute, same stop / target / exits).
Per feature bin: the trades' R, the mirror's R, the share of the full losers, by design half-year.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/causes.py RULE
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402

SIGNED = ["ret5", "ret15", "ret30", "ret60", "ret120", "ema20_dist", "m15_e20_dist", "h1_e20_dist", "consec",
          "wick10", "m1f5_net", "m5_net", "slope60", "h1_tide", "m15_tide", "m5_tide", "usd_z30", "gold_z30",
          "spx_z30", "brk_p60", "brk_day", "brk_yday", "brk_asia", "sweep_day"]
PLAIN = ["atr15_u", "atr1_ratio", "bbw1", "rng60", "tv5_60", "tv60_1440", "sp_rel", "hour", "min_ny", "min_since_rel",
         "min_to_rel", "round50_dist"]
HL = ["H1", "H2", "H3", "H4", "H5"]


def main() -> None:
    name = sys.argv[1]
    cfg = rules.RULES[name]
    P = rules.jlib.Instr("XAUUSD")
    part = sys.argv[2] if len(sys.argv) > 2 else "design"
    z = pd.read_parquet(HERE / f"trades_{name}_{part}.parquet")
    mir = []
    for r in z.itertuples():
        ss = P.stop_slip_ny if r.session == 2 else P.stop_slip
        x = P.trade(int(r.e), -int(r.side), float(r.tp), float(r.sl), cfg["be"], cfg["hz"], ss)
        mir.append(x["pnl"] / (r.sl + ss))
    z["mR"] = mir
    z["edge"] = z.R - z.mR
    F = pd.read_parquet(HERE / "feats.parquet")
    dec = P.ot[z.e.to_numpy() - 1]
    X = F.reindex(dec).reset_index(drop=True)
    s = z.side.to_numpy()
    for f in SIGNED:
        z[f] = X[f].to_numpy() * s
    for f in PLAIN:
        z[f] = X[f].to_numpy()
    z["pos60"] = np.where(s > 0, X.pos60, 1 - X.pos60)
    z["d_day_ext"] = np.where(s > 0, X.d_dhi, -X.d_dlo)  # <= 0: below the day high for a buy (room to it)
    z["h1_struct"] = np.where(np.abs(X.h1_struct) == 1, X.h1_struct * s, X.h1_struct)
    z["m15_struct"] = np.where(np.abs(X.m15_struct) == 1, X.m15_struct * s, X.m15_struct)
    z["stop_atr1"] = z.sl / (X.atr1_ratio.to_numpy() * 0 + 1) / (X.atr15_u.to_numpy() * z.u.to_numpy())  # stop / M15 ATR
    z["tp_u"] = z.tp / z.u
    z["half"] = pd.cut(z.t, rules.HALVES, labels=HL, right=False)
    z.to_parquet(HERE / f"causes_{name}{'' if part == 'design' else '_' + part}.parquet")
    print(f"{name}: {len(z)} trades, R {z.R.mean():+.3f}, mirror {z.mR.mean():+.3f}, coin {(z.R.mean() + z.mR.mean()) / 2:+.3f};"
          f" full losers {(z.exit == 'stop').sum()}")
    rows = []
    for f in SIGNED + PLAIN + ["pos60", "d_day_ext", "h1_struct", "m15_struct", "stop_atr1", "tp_u"]:
        x = z[f].astype(float)
        vals = x.dropna().unique()
        if len(vals) <= 7:
            b, cats = x, sorted(vals)
        else:
            q = np.unique(np.nanquantile(x, [0.2, 0.4, 0.6, 0.8]))
            b, cats = pd.Series(np.digitize(x, q), index=x.index).where(x.notna()), list(range(len(q) + 1))
        for k in cats:
            sel = b == k
            if sel.sum() < max(30, 0.05 * len(z)):
                continue
            g = z[sel]
            per = [g[g.half == h].R.mean() - g[g.half == h].mR.mean() if (g.half == h).sum() >= 10 else np.nan for h in HL]
            perR = [g[g.half == h].R.mean() if (g.half == h).sum() >= 10 else np.nan for h in HL]
            rows.append(dict(feature=f, bin=k, lo=x[sel].min(), hi=x[sel].max(), n=int(sel.sum()),
                             loser_share=(g.exit == "stop").sum() / max((z.exit == "stop").sum(), 1),
                             R=g.R.mean(), mR=g.mR.mean(), edge=g.edge.mean(),
                             R_pos=int(np.nansum(np.array(perR) > 0)), edge_pos=int(np.nansum(np.array(per) > 0)),
                             **{f"R_{h}": v for h, v in zip(HL, perR, strict=True)}))
    T = pd.DataFrame(rows)
    T.to_csv(HERE / f"causes_{name}{'' if part == 'design' else '_' + part}.csv", index=False)
    pd.set_option("display.width", 250)
    print("\n== worst bins (R) ==")
    print(T.sort_values("R").head(25).round(3).to_string(index=False))
    print("\n== best bins (R) ==")
    print(T.sort_values("R", ascending=False).head(25).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
