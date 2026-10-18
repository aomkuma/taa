"""F1's entries split in two (turn_zone.py): ~40 % never get half way, ~40 % run far. What was different AT THE
ENTRY? (owner, 2026-10-18: "how do we use the results to improve the edge"). Population: every confluence entry (B0:
H1 tide + level + price action + 2 of 3 M5; one a minute, wide windows), followed 60 M1 bars with the F1 stop
(floored at 0.5 M15 ATR). dead = the best price before the stop < 0.25 x 8 U; runner = >= 8 U (the target).
For each feature at the decision bar (the journal's candidate table): the median among runners vs dead, per
design half-year and on the window; a feature counts only if the sign holds in >= 4 of 5 halves AND the window.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/dead_vs_runner.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
import rules  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)
FEATS = ["ret5", "ret15", "ret30", "ret60", "rng5", "rng15", "rng60", "rng240", "pos5", "pos15", "pos60", "pos240",
         "atr_ratio", "vol5", "day_rng_adr", "day_pos", "h1_c_e20", "h1_c_e50", "h1_e20_slope", "m15_c_e20",
         "m15_c_e50", "m15_e20_slope", "cr_M15_struct", "cr_H1_struct", "cr_M15_now", "cr_H1_now", "cr_H1_leg_dir",
         "cr_H1_leg_atr", "dist_atr", "cluster", "room_atr", "m5_rsi", "m5_c_e20", "m5_e20_d", "min_in", "spread_atr",
         "since_rel", "front72_u", "a15_atr", "sl_u"]


def reach(S):
    out = np.empty(len(S))
    for i, r in enumerate(S.itertuples()):
        e, s = int(r.e), int(r.side)
        entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
        j = np.arange(e, min(e + 60, len(P.o)))
        fav = (P.h[j] - entry) if s > 0 else (entry - P.lo[j] - P.sp[j])
        adv = (entry - P.lo[j]) if s > 0 else (P.h[j] + P.sp[j] - entry)
        hit = np.flatnonzero(adv >= r.sl)
        k = hit[0] if len(hit) else len(j)
        out[i] = fav[:k].max() if k else 0.0
    return out


res = {}
for part in ("wdesign", "wtest"):
    _, D = plib.load(part)
    D = D.reset_index(drop=True)
    S = rules.signals(D, rules.RULES["B0"], P).drop_duplicates("t").reset_index(drop=True)
    t = pd.to_datetime(S.t, utc=True)
    S["a15"] = a15.reindex(t, method="ffill").to_numpy()
    S["sl"] = np.maximum(S.sl, 0.5 * S.a15)
    S["room_atr"] = S.room / S.atr1
    S["spread_atr"] = S.spread / S.atr1
    S["front72_u"] = (S.front72 - S.c_dec) * S.side / S.unit
    S["a15_atr"] = S.a15 / S.atr1
    S["sl_u"] = S.sl / S.unit
    S["reach_u"] = reach(S) / S.unit
    S["grp"] = np.where(S.reach_u >= 8, "run", np.where(S.reach_u < 2, "dead", "mid"))
    S["half"] = plib.half_of(t) if part == "wdesign" else "window"
    S["F1"] = (plib.MENU["C4 72-h extreme near/behind"](S) & plib.MENU["C5 not a fast tape"](S)).to_numpy()
    res[part] = S
    print(f"{part}: {len(S)} entries, dead {np.mean(S.grp == 'dead'):.0%}, runners {np.mean(S.grp == 'run'):.0%};"
          f" F1 subset {S.F1.sum()}: dead {np.mean(S.grp[S.F1] == 'dead'):.0%}, runners {np.mean(S.grp[S.F1] == 'run'):.0%}")

X = pd.concat(res.values(), ignore_index=True)
rows = []
for f in FEATS:
    g = X[X.grp != "mid"].groupby(["half", "grp"])[f].median().unstack()
    diff = (g["run"] - g["dead"])
    halves = diff.drop("window", errors="ignore")
    sign = np.sign(halves.median())
    stable = (np.sign(halves) == sign).sum()
    win = diff.get("window", np.nan)
    rows.append(dict(feat=f, sign=int(sign), halves=f"{stable}/{halves.notna().sum()}", window_same=bool(np.sign(win) == sign),
                     run_med=X.loc[X.grp == "run", f].median(), dead_med=X.loc[X.grp == "dead", f].median(),
                     design_diff=float(halves.median()), window_diff=float(win)))
R = pd.DataFrame(rows)
R["ok"] = (R.halves.str[0].astype(int) >= 4) & R.window_same
pd.set_option("display.width", 200)
print(R.sort_values(["ok", "halves"], ascending=False).round(3).to_string(index=False))
X.to_parquet("research/2026-10-18-moments/shadow/dead_vs_runner.parquet")
