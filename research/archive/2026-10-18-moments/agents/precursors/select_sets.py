"""Choose the core-formation sets whose evidence is clear on design (chosen by the rules below, never by the window),
describe each set's formation in words, and draw up to 6 members (one per day) for the evidence page.

Rules (design snaps, sets seen on >= 30 days, outcomes against the members' snap times):
- runs more / less often: |z| >= 2.5 on a 10 U run within 30 minutes (each layer);
- once it starts it runs on one side: |z| >= 2.5 on "3 U then 10 U" signed by the start's side (trigger layer);
- moves farther / less far: |z| >= 3 on the largest move within 30 minutes (trigger layer).

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/select_sets.py
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import plib  # noqa: E402
import render  # noqa: E402
from plib import HERE  # noqa: E402

OUT = HERE / "png" / "evidence"
LAYER_TFS = {"context": ("H4", "H1"), "setup": ("M30", "M15"), "trigger": ("M5", "M1")}
TH = {
    "npiv": {0: "0-2 swings", 1: "3-5 swings", 2: "6-9 swings", 3: "10+ swings"},
    "leg": {0: "down leg (after a peak)", 1: "up leg (after a trough)", 2: "no swing"},
    "pk1": {0: "lower peak", 1: "equal peak", 2: "higher peak", 3: "-"},
    "tr1": {0: "lower trough", 1: "equal trough", 2: "higher trough", 3: "-"},
    "where": {0: "above the last peak", 1: "below the last trough", 2: "upper part of the swing", 3: "upper part of the swing",
              4: "lower part of the swing", 5: "-"},
    "rsi_up": {0: "RSI falling", 1: "RSI rising"},
    "macd_h": {0: "MACD hist < 0 falling", 1: "MACD hist < 0 rising", 2: "MACD hist > 0 falling", 3: "MACD hist > 0 rising"},
    "ema": {0: "EMA bull stack", 1: "EMA bear stack", 2: "EMA mixed"},
    "sr": {0: "between levels", 1: "at support", 2: "at resistance", 3: "just broke up through a level",
           4: "just broke down through a level"},
}


def zsets(sid, o, names, day, min_days=30):
    base = pd.Series(o).groupby(names).transform("mean").to_numpy()
    var = pd.Series(o).groupby(names).transform("var").to_numpy()
    x = pd.DataFrame({"set": sid, "o": o, "e": base, "v": var, "day": day})
    g = x.groupby("set")
    t = pd.DataFrame({"n": g.size(), "days": g.day.nunique(), "obs": g.o.mean(), "exp": g.e.mean(), "v": g.v.sum()})
    t = t[t.days >= min_days]
    t["z"] = (t.obs - t.exp) * t.n / np.sqrt(t.v)
    return t


def describe(F: pd.DataFrame, S: pd.DataFrame, i: int, tf: str) -> list[str]:
    r = F.iloc[i]
    parts = [TH["npiv"][int(r[f"{tf}_fp_npiv"])], TH["leg"][int(r[f"{tf}_fp_leg"])], TH["pk1"][int(r[f"{tf}_fp_pk1"])],
             TH["tr1"][int(r[f"{tf}_fp_tr1"])], TH["where"][int(r[f"{tf}_fp_where"])],
             TH["rsi_up"][int(r[f"{tf}_fp_rsi_up"])], TH["macd_h"][int(r[f"{tf}_fp_macd_h"])],
             TH["ema"][int(r[f"{tf}_fp_ema"]) // 2]]
    if f"{tf}_sr_loc" in S.columns:
        parts.append(TH["sr"][int(S.iloc[i][f"{tf}_sr_loc"])])
    return [p for p in parts if p != "-"]


def main() -> None:
    plib.gold.below_normal_priority()
    S = pd.read_parquet(HERE / "snaps.parquet")
    F = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    d = (S.half != "W").to_numpy()
    S, F = S[d].reset_index(drop=True), F[d].reset_index(drop=True)
    M = pd.read_parquet(HERE / "fpsets_core_members.parquet")
    names = S.name.to_numpy()
    day = S.S.dt.tz_convert("Asia/Bangkok").dt.normalize().to_numpy()
    ran = S.cls.isin(["ran_up", "ran_dn"]).to_numpy().astype(float)
    cont = np.where(S.cont10.to_numpy() == 1, S.start3.fillna(0).to_numpy(), 0.0)
    move = np.maximum(S.mfe_up30, S.mfe_dn30).to_numpy()
    chosen = []
    for layer in ("context", "setup", "trigger"):
        sid = M[f"set_{layer}"].to_numpy()
        t = zsets(sid, ran, names, day)
        for s, r in t[t.z.abs() >= 2.5].iterrows():
            chosen.append((layer, int(s), "runs more" if r.z > 0 else "runs less", float(r.z)))
        if layer == "trigger":
            x = pd.DataFrame({"set": sid, "c": cont, "day": day})
            g = x.groupby("set")
            tt = pd.DataFrame({"n": g.size(), "days": g.day.nunique(), "up": g.c.apply(lambda v: (v > 0).mean()),
                               "dn": g.c.apply(lambda v: (v < 0).mean())})
            tt = tt[tt.days >= 30]
            tt["z"] = (tt.up - tt.dn) / np.sqrt((tt.up + tt.dn).clip(lower=1e-9) / tt.n)
            for s, r in tt[tt.z.abs() >= 2.5].iterrows():
                chosen.append((layer, int(s), "starts then runs up" if r.z > 0 else "starts then runs down", float(r.z)))
            t2 = zsets(sid, move, names, day)
            for s, r in t2[t2.z.abs() >= 3].iterrows():
                chosen.append((layer, int(s), "moves farther" if r.z > 0 else "moves less far", float(r.z)))
    m = plib.load()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(21)
    cards = []
    for layer, s, kind, z in chosen:
        sid = M[f"set_{layer}"].to_numpy()
        mem = np.nonzero(sid == s)[0]
        g = S.iloc[mem]
        lead = mem[0]
        up = g.cls.isin(["ran_up", "slow_up"]).mean()
        dn = g.cls.isin(["ran_dn", "slow_dn"]).mean()
        exp_ran = pd.Series(ran).groupby(names).mean().reindex(g.name).mean()
        stats = dict(snaps=len(g), days=int(g.S.dt.tz_convert("Asia/Bangkok").dt.normalize().nunique()),
                     ran10=float(g.cls.isin(["ran_up", "ran_dn"]).mean()), ran10_expected=float(exp_ran),
                     up=float(up), down=float(dn), fake=float(g.cls.isin(["fake_up", "fake_dn"]).mean()),
                     flat=float((g.cls == "flat").mean()), cont_up=float((cont[mem] > 0).mean()),
                     cont_dn=float((cont[mem] < 0).mean()), move30=float(np.median(move[mem])),
                     first10_up=float((g.first10 > 0).mean()), first10_dn=float((g.first10 < 0).mean()),
                     times=g.name.value_counts().head(4).to_dict())
        desc = {tf: describe(F, S, lead, tf) for tf in LAYER_TFS[layer]}
        pick = g.assign(day=g.S.dt.tz_convert("Asia/Bangkok").dt.normalize()).groupby("day").head(1)
        pick = pick.sample(min(6, len(pick)), random_state=int(rng.integers(1e9))).sort_values("S")
        imgs = []
        for k, (_, r) in enumerate(pick.iterrows()):
            f = OUT / f"{layer}_{s}_{k}.png"
            th = r.S.tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %H:%M")
            title = f"{layer} set {s} | {th} TH ({r['name']}) | next 30 min: {r.cls}, max up {r.mfe_up30:.1f} U, max down {r.mfe_dn30:.1f} U"
            render.draw(m, r.S - pd.Timedelta(minutes=1), f, title)
            imgs.append(dict(file=f.name, when=th, name=r["name"], cls=r.cls, up30=round(float(r.mfe_up30), 1),
                             dn30=round(float(r.mfe_dn30), 1)))
        cards.append(dict(layer=layer, set=s, kind=kind, z=round(z, 2), stats=stats, desc=desc, images=imgs))
        print(layer, s, kind, round(z, 2), stats["days"], "days", flush=True)
    (OUT / "cards.json").write_text(json.dumps(cards, indent=1, default=str), encoding="utf-8")
    base = dict(ran10=float(ran.mean()), fake=float(S.cls.isin(["fake_up", "fake_dn"]).mean()),
                flat=float((S.cls == "flat").mean()), snaps=len(S), days=int(pd.Series(day).nunique()))
    (OUT / "base.json").write_text(json.dumps(base), encoding="utf-8")


if __name__ == "__main__":
    main()
