"""Round 4 (docs/OWN_SETUP_ROUNDS.md): the arsenal - several tools (target / stop in USD) and, at each active minute, the
tool with the best expected USD after costs, per a LightGBM model per tool (win / stop / time-out). One trade at a
time; in each session the first minute whose best expected USD clears that session's cut (chosen on validation
for about one trade per session-day). Train 2023-11 .. 2026-02, validation 2026-02-14 .. 04-14, test the latest
six months (2026-04-14 .. 10-14) only.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ml_arsenal.py labels
    data/venv-research/Scripts/python research/2026-10-18-moments/ml_arsenal.py train
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

TOOLS = [(3, 3), (3, 5), (5, 4), (5, 6), (5, 8), (8, 6), (8, 8), (10, 8), (10, 12), (15, 10), (20, 12)]
SLIP = 0.07
SRC = "data/research/own_ml_long.parquet"
LAB = "data/research/own_ml_arsenal_labels.parquet"
T_VAL, T_TEST, T_END = "2026-02-14", "2026-04-14", "2026-10-14"


def horizon(t: int) -> int:
    return 120 if t >= 15 else 60


def labels() -> None:
    sys.path.insert(0, "research/2026-10-18-moments")
    import gold
    from numpy.lib.stride_tricks import sliding_window_view as win

    lo_t, hi_t = pd.Timestamp("2023-09-01", tz="UTC"), pd.Timestamp("2026-10-14", tz="UTC")
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= lo_t) & (m1.index < hi_t + pd.Timedelta(days=1))]
    o, h, lo, c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m1["spread"].to_numpy(float) * 0.01
    d = pd.read_parquet(SRC, columns=["t", "e", "side"])
    assert (m1.index[d.e.to_numpy()] == pd.to_datetime(d.t, utc=True)).all()
    out = d.copy()
    n = len(o)
    for side in (1, -1):
        rows = np.nonzero(d.side.to_numpy() == side)[0]
        e = d.e.to_numpy()[rows]
        entry = o[e] + (sp[e] + SLIP if side > 0 else -SLIP)
        for hz in sorted({horizon(t) for t, _ in TOOLS}):
            ok = e + hz < n
            ee = np.where(ok, e, 0)
            H, L, S = win(h, hz)[ee], win(lo, hz)[ee], win(sp, hz)[ee]
            fav = (H - entry[:, None]) if side > 0 else (entry[:, None] - (L + S))
            adv = (entry[:, None] - L) if side > 0 else ((H + S) - entry[:, None])
            xi = np.minimum(ee + hz - 1, n - 1)
            last = c[xi] - (SLIP if side > 0 else -(sp[xi] + SLIP))
            timeout = (last - entry) * side
            for t, sl in TOOLS:
                if horizon(t) != hz:
                    continue
                ht = np.where((fav >= t).any(1), (fav >= t).argmax(1), 10**6)
                st = np.where((adv >= sl).any(1), (adv >= sl).argmax(1), 10**6)
                y = np.where(ht < st, 1, np.where(st < 10**6, 2, 0))
                usd = np.where(y == 1, t, np.where(y == 2, -sl - SLIP, timeout))
                mins = np.minimum(np.minimum(ht, st), hz - 1) + 1
                y = np.where(ok, y, -1)
                for name, val in (("y", y), ("usd", usd), ("min", mins)):
                    col = f"{name}_{t}_{sl}"
                    if col not in out:
                        out[col] = np.zeros(len(out), dtype=np.float32)
                    out.loc[out.index[rows], col] = val.astype(np.float32)
    out.to_parquet(LAB)
    print(out.shape, {f"{t}/{sl}": round(float((out[f'y_{t}_{sl}'] == 1).mean()), 3) for t, sl in TOOLS})


def train() -> None:
    from lightgbm import LGBMClassifier

    warnings.filterwarnings("ignore", category=UserWarning)
    d = pd.read_parquet(SRC)
    lab = pd.read_parquet(LAB)
    d = pd.concat([d, lab.drop(columns=["t", "e", "side"])], axis=1)
    d["t"] = pd.to_datetime(d.t, utc=True)
    meta = {"t", "e", "mfe", "side"} | {c for c in d.columns if c[:2] in ("y4", "y6", "y8") or c.startswith(("y_", "usd", "min"))}
    feats = [c for c in d.columns if c not in meta and not c.startswith(("y4", "y6", "y8"))]
    feats = [c for c in feats if not (c.startswith("y") and c[1:].isdigit())]
    T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    tr = d[d.t < T(T_VAL)]
    va = d[(d.t >= T(T_VAL)) & (d.t < T(T_TEST))]
    te = d[(d.t >= T(T_TEST)) & (d.t < T(T_END))]
    print(f"features {len(feats)}; rows train {len(tr)}, validation {len(va)}, test {len(te)}")
    params = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=300, subsample=0.7,
                  subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0, random_state=7, verbose=-1)
    ev_va, ev_te = {}, {}
    for t, sl in TOOLS:
        y = tr[f"y_{t}_{sl}"]
        keep = y >= 0
        m = LGBMClassifier(objective="multiclass", **params)
        m.fit(tr.loc[keep, feats], y[keep].astype(int))
        to = tr.loc[keep & (y == 0), f"usd_{t}_{sl}"].mean()  # the mean time-out result
        for part, store in ((va, ev_va), (te, ev_te)):
            p = m.predict_proba(part[feats])
            store[(t, sl)] = p[:, 1] * t - p[:, 2] * (sl + SLIP) + p[:, 0] * (0.0 if np.isnan(to) else to)
        print(f"  tool {t}/{sl}: fitted (time-out mean {to:+.2f} USD)", flush=True)

    def best(part: pd.DataFrame, ev: dict) -> pd.DataFrame:
        mat = np.vstack([ev[k] for k in TOOLS]).T
        k = mat.argmax(1)
        out = part[["t", "side"]].copy()
        out["session"] = part.session.to_numpy()
        out["ev"] = mat.max(1)
        out["tool"] = [TOOLS[i] for i in k]
        out["usd"] = [part[f"usd_{a}_{b}"].iat[j] for j, (a, b) in enumerate(out.tool)]
        out["mins"] = [part[f"min_{a}_{b}"].iat[j] for j, (a, b) in enumerate(out.tool)]
        out["win"] = [part[f"y_{a}_{b}"].iat[j] == 1 for j, (a, b) in enumerate(out.tool)]
        return out.sort_values(["t", "ev"], ascending=[True, False]).drop_duplicates("t")

    def run(x: pd.DataFrame, cuts: dict, cap: int = 2) -> pd.DataFrame:
        keep, free, count = [], pd.Timestamp(0, tz="UTC"), {}
        for t, s, ev, mins in zip(x.t, x.session, x.ev, x.mins, strict=True):
            key = (t.normalize(), s)
            ok = ev >= cuts[s] and t >= free and count.get(key, 0) < cap
            keep.append(ok)
            if ok:
                free, count[key] = t + pd.Timedelta(minutes=int(mins)), count.get(key, 0) + 1
        return x[np.array(keep, dtype=bool)]

    bv, bt = best(va, ev_va), best(te, ev_te)
    cuts = {}
    for s in (0, 1, 2):
        xs = bv[bv.session == s]
        days = xs.t.dt.normalize().nunique()
        best_c = (-np.inf, np.inf)
        for q in (0.9, 0.95, 0.98, 0.99, 0.995, 0.998):
            c = float(np.quantile(xs.ev, q))
            r = run(xs, {s: c})
            if len(r) >= 0.7 * days and r.usd.sum() > best_c[0]:
                best_c = (r.usd.sum(), c)
        cuts[s] = best_c[1] if np.isfinite(best_c[1]) else float(np.quantile(xs.ev, 0.99))
        r = run(xs, {s: cuts[s]})
        print(f"  validation session {s}: cut EV {cuts[s]:+.2f} USD, {len(r)} trades ({len(r) / days:.2f}/day), {r.usd.sum():+.1f} USD")
    res = run(bt, cuts)
    days = bt.t.dt.normalize().nunique()
    names = {0: "Asia", 1: "London", 2: "New York"}
    print(f"\nTEST {T_TEST} .. {T_END} ({days} days): {len(res)} trades ({len(res) / days:.2f}/day), win {100 * res.win.mean():.0f}%,"
          f" {res.usd.mean():+.2f} USD/trade, {res.usd.sum():+.1f} USD at 0.01 lot")
    for s, g in res.groupby("session"):
        print(f"  {names[s]:8}: {len(g)} trades ({len(g) / days:.2f}/day), win {100 * g.win.mean():.0f}%, {g.usd.sum():+.1f} USD")
    for mo, g in res.groupby(res.t.dt.strftime("%Y-%m")):
        print(f"  {mo}: {len(g):3} trades, win {100 * g.win.mean():3.0f}%, {g.usd.sum():+7.1f} USD")
    print("  tools used:", res.tool.value_counts().to_dict())
    for tool, g in res.groupby("tool"):
        print(f"     {tool}: {len(g)} trades, win {100 * g.win.mean():.0f}%, {g.usd.mean():+.2f} USD/trade")
    print("  predicted EV of the trades taken (mean):", round(float(res.ev.mean()), 2), "USD; realized", round(float(res.usd.mean()), 2))
    res.to_parquet("data/research/own_ml_arsenal_test.parquet")


if __name__ == "__main__":
    labels() if sys.argv[1] == "labels" else train()
