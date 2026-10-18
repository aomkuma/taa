"""Round 6 (docs/OWN_SETUP_ROUNDS.md): a weighted indicator score - MACD, RSI, Stochastic, Bollinger, EMA, ADX/DI, CCI,
ROC votes on M1 / M5 / M15 / H1, weights from an L2 logistic regression fitted on 2025-10-14 .. 2026-02-14, the tool
and the cut chosen on 2026-02-14 .. 04-14, tested once on 2026-04-14 .. 10-14. Runs in data/venv-research:

    data/venv-research/Scripts/python research/2026-10-18-moments/indicator_score.py
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

TOOLS = [(5, 4), (5, 6), (8, 6), (10, 8)]
FIT, VAL, TEST, END = "2025-10-14", "2026-02-14", "2026-04-14", "2026-10-14"
TFS = {"M1": 1, "M5": 5, "M15": 15, "H1": 60}


def votes(b: pd.DataFrame, name: str) -> pd.DataFrame:
    """Votes for a BUY (+1 / -1 / 0) per closed bar of *b* (OHLC, index = the bar's open time)."""
    c, h, lo = b.close, b.high, b.low
    out = pd.DataFrame(index=b.index)
    ema = lambda x, n: x.ewm(span=n, adjust=False).mean()  # noqa: E731
    macd = ema(c, 12) - ema(c, 26)
    hist = macd - ema(macd, 9)
    out[f"{name}_macd"] = np.sign(hist)
    out[f"{name}_macd_slope"] = np.sign(hist.diff())
    d = c.diff()
    rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14).mean())
    out[f"{name}_rsi50"] = np.sign(rsi - 50)
    out[f"{name}_rsi_turn"] = ((rsi.shift(1) < 30) & (rsi >= 30)).astype(int) - ((rsi.shift(1) > 70) & (rsi <= 70)).astype(int)
    k = 100 * (c - lo.rolling(14).min()) / (h.rolling(14).max() - lo.rolling(14).min())
    k = k.rolling(3).mean()
    dd = k.rolling(3).mean()
    out[f"{name}_stoch50"] = np.sign(k - 50)
    out[f"{name}_stoch_cross"] = ((k > dd) & (k.shift(1) <= dd.shift(1))).astype(int) - ((k < dd) & (k.shift(1) >= dd.shift(1))).astype(int)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    pb = (c - (mid - 2 * sd)) / (4 * sd)
    out[f"{name}_bb_half"] = np.sign(pb - 0.5)
    out[f"{name}_bb_out"] = (pb > 1).astype(int) - (pb < 0).astype(int)
    out[f"{name}_ema_cross"] = np.sign(ema(c, 20) - ema(c, 50))
    out[f"{name}_close_ema"] = np.sign(c - ema(c, 20))
    up, dn = h.diff(), -lo.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14).mean()
    pdi = 100 * pd.Series(pdm, index=b.index).ewm(alpha=1 / 14).mean() / atr
    ndi = 100 * pd.Series(ndm, index=b.index).ewm(alpha=1 / 14).mean() / atr
    adx = (100 * (pdi - ndi).abs() / (pdi + ndi)).ewm(alpha=1 / 14).mean()
    out[f"{name}_adx_di"] = np.where(adx > 20, np.sign(pdi - ndi), 0)
    tp = (h + lo + c) / 3
    cci = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True))
    out[f"{name}_cci"] = np.sign(cci)
    out[f"{name}_roc"] = np.sign(c - c.shift(10))
    return out


def run(x: pd.DataFrame, tool: tuple[int, int], cap: int = 2) -> pd.DataFrame:
    t_, sl = tool
    x = x[x[f"y_{t_}_{sl}"] >= 0].sort_values(["t", "score"], ascending=[True, False]).drop_duplicates("t")
    keep, free, count = [], pd.Timestamp(0, tz="UTC"), {}
    for t, s, mins in zip(x.t, x.session, x[f"min_{t_}_{sl}"], strict=True):
        key = (t.normalize(), s)
        ok = t >= free and count.get(key, 0) < cap
        keep.append(ok)
        if ok:
            free, count[key] = t + pd.Timedelta(minutes=int(mins)), count.get(key, 0) + 1
    out = x[np.array(keep, dtype=bool)].copy()
    out["usd"], out["win"] = out[f"usd_{t_}_{sl}"], out[f"y_{t_}_{sl}"] == 1
    return out


def summary(r: pd.DataFrame, days: int) -> str:
    if not len(r):
        return "0 trades"
    by_m = r.usd.groupby(r.t.dt.strftime("%Y-%m")).sum()
    return (f"{len(r):4} trades ({len(r) / days:.2f}/day) win {100 * r.win.mean():3.0f}%  {r.usd.mean():+.2f} USD/trade"
            f"  {r.usd.sum():+8.1f} USD  months+ {(by_m > 0).sum()}/{len(by_m)}")


def main() -> None:
    from sklearn.linear_model import LogisticRegression

    warnings.filterwarnings("ignore")
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= pd.Timestamp("2025-07-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    d = pd.read_parquet("data/research/own_ml_long.parquet", columns=["t", "e", "side", "session"])
    lab = pd.read_parquet("data/research/own_ml_arsenal_labels.parquet")
    d = pd.concat([d, lab.drop(columns=["t", "e", "side"])], axis=1)
    d["t"] = pd.to_datetime(d.t, utc=True)
    d = d[(d.t >= pd.Timestamp(FIT, tz="UTC")) & (d.t < pd.Timestamp(END, tz="UTC"))].reset_index(drop=True)
    times = pd.DatetimeIndex(d.t.drop_duplicates().sort_values())
    V = pd.DataFrame(index=times)
    ohlc = {"open": "first", "high": "max", "low": "min", "close": "last"}
    for name, mins in TFS.items():
        b = m1[["open", "high", "low", "close"]] if mins == 1 else m1.resample(f"{mins}min", label="left", closed="left").agg(ohlc).dropna()
        v = votes(b, name)
        ends = b.index + pd.Timedelta(minutes=mins)
        k = ends.searchsorted(times, side="right") - 1
        part = v.iloc[np.clip(k, 0, None)].set_axis(times)
        part[k < 0] = 0
        V = V.join(part)
    V = V.fillna(0)
    cols = list(V.columns)
    X = V.reindex(d.t).to_numpy() * d.side.to_numpy()[:, None]
    print(f"rows {len(d)}, votes {len(cols)}")
    T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    fit = (d.t < T(VAL)).to_numpy()
    val = ((d.t >= T(VAL)) & (d.t < T(TEST))).to_numpy()
    test = (d.t >= T(TEST)).to_numpy()
    days = {k: d.t[m].dt.normalize().nunique() for k, m in (("val", val), ("test", test))}
    best = (-np.inf,)
    models = {}
    for tool in TOOLS:
        y = d[f"y_{tool[0]}_{tool[1]}"].to_numpy()
        ok = fit & (y >= 0)
        m = LogisticRegression(C=0.1, max_iter=500).fit(X[ok], (y[ok] == 1).astype(int))
        models[tool] = m
        score = m.decision_function(X)
        for q in (0.9, 0.95, 0.98, 0.99, 0.995):
            cut = float(np.quantile(score[val], q))
            r = run(d[val].assign(score=score[val])[score[val] >= cut], tool)
            if len(r) >= days["val"] and r.usd.sum() > best[0]:
                best = (r.usd.sum(), tool, cut, q, summary(r, days["val"]))
    _, tool, cut, q, note = best
    m = models[tool]
    print(f"chosen on validation: tool {tool[0]}/{tool[1]}, the top {100 * (1 - q):.1f}% scores: {note}")
    w = pd.Series(m.coef_[0], index=cols).sort_values()
    print("weights (most against .. most for):")
    print("  against:", ", ".join(f"{k} {v:+.3f}" for k, v in w.head(8).items()))
    print("  for:    ", ", ".join(f"{k} {v:+.3f}" for k, v in w.tail(10).items()))
    score = m.decision_function(X)
    r = run(d[test].assign(score=score[test])[score[test] >= cut], tool)
    print(f"\nTEST latest six months (weighted): {summary(r, days['test'])}")
    for s, g in r.groupby("session"):
        print(f"   {['Asia', 'London', 'New York'][int(s)]:8}: {summary(g, days['test'])}")
    for mo, g in r.groupby(r.t.dt.strftime("%Y-%m")):
        print(f"   {mo}: {len(g):3} trades, win {100 * g.win.mean():3.0f}%, {g.usd.sum():+7.1f} USD")
    eq = X.sum(1)
    cut_eq = float(np.quantile(eq[val], q))
    r_eq = run(d[test].assign(score=eq[test])[eq[test] >= cut_eq], tool)
    print(f"TEST equal weights (the vote sum >= {cut_eq:.0f} of {len(cols)}): {summary(r_eq, days['test'])}")
    y = d[f"y_{tool[0]}_{tool[1]}"].to_numpy()
    base = (y[test] == 1).mean()
    print(f"base rate of the tool on the test rows: {100 * base:.1f}%")
    r.to_parquet("data/research/own_indicator_score_test.parquet")


if __name__ == "__main__":
    main()
