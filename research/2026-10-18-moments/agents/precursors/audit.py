"""Audit the matching (owner: "look again - what picture does the bot compare?"): for chosen V2 window trades, the
bot's snap and the library cases it matched (>= 0.80, earlier days) per layer, as pictures, with the attributes compared.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/audit.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import plib
import render
from cluster_fp import core_cols, onehot
from plib import HERE

LAYERS = {"context": ("H4", "H1"), "setup": ("M30", "M15"), "trigger": ("M5", "M1")}
NAMES = ["swings", "leg", "peak", "trough", "where", "rsi_up", "macd", "ema"]
OUT = HERE / "png" / "audit"


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    F = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    T = pd.read_parquet(HERE / "v2_window_B3.parquet")
    day = S.S.dt.tz_convert("Asia/Bangkok").dt.normalize().to_numpy()
    m = plib.load()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2)
    picks = pd.concat([T[T.exit == "stop"].sample(2, random_state=3), T[T.exit == "win"].sample(1, random_state=3)])
    layers = {}
    for layer, tfs in LAYERS.items():
        cols, labels = [], []
        for tf in tfs:
            cols += core_cols(F, tf)
            labels += [f"{tf}.{n}" for n in NAMES]
            if f"{tf}_sr_loc" in S.columns:
                cols.append(S[f"{tf}_sr_loc"].to_numpy())
                labels.append(f"{tf}.sr")
        layers[layer] = (onehot(cols), np.vstack(cols).T, labels)
    for q, tr in enumerate(picks.itertuples()):
        i = int(np.nonzero(S.S.to_numpy() == np.datetime64(tr.S.tz_convert(None)))[0][0]) if False else \
            int(S.index[S.S == tr.S][0])
        th = tr.S.tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %H:%M")
        render.draw(m, tr.S - pd.Timedelta(minutes=1), OUT / f"q{q}_query.png",
                    f"QUERY {th} TH {tr.name} | the bot traded {'BUY' if tr.side > 0 else 'SELL'} -> {tr.exit} {tr.pnl:+.1f} USD")
        print(f"\n=== query {q}: {th} TH {tr.name}, {('BUY' if tr.side > 0 else 'SELL')} -> {tr.exit} {tr.pnl:+.1f}")
        for layer, (V, codes, labels) in layers.items():
            sims = V @ V[i]
            ok = (sims >= 0.8 - 1e-6) & (day < day[i])
            idx = np.nonzero(ok)[0]
            print(f"  {layer}: {len(idx)} matches on {len(np.unique(day[idx]))} days; their outcomes: "
                  f"{S.cls.iloc[idx].value_counts(normalize=True).round(2).to_dict()}")
            print("    query  :", " ".join(f"{l}={c}" for l, c in zip(labels, codes[i])))
            top = idx[np.argsort(-sims[idx])][:30]
            show = rng.choice(top, size=min(3, len(top)), replace=False) if len(top) else []
            for k, j in enumerate(show):
                diff = [labels[a] for a in range(len(labels)) if codes[j, a] != codes[i, a]]
                print(f"    match {k}: {S.S.iloc[j].tz_convert('Asia/Bangkok'):%Y-%m-%d %H:%M} sim {sims[j]:.2f} "
                      f"differs in {diff} -> {S.cls.iloc[j]}")
                render.draw(m, S.S.iloc[j] - pd.Timedelta(minutes=1), OUT / f"q{q}_{layer}_{k}.png",
                            f"{layer.upper()} MATCH {k} for query {q} (sim {sims[j]:.2f}): "
                            f"{S.S.iloc[j].tz_convert('Asia/Bangkok'):%Y-%m-%d %H:%M} TH -> {S.cls.iloc[j]}")


if __name__ == "__main__":
    main()
