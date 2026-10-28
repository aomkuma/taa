"""Round 5b (docs/OWN_SETUP_ROUNDS.md): the deep pullback in the H1 trend (screen 1 A, M15 RSI below 40, screen 3 none or
the last bar) on the untouched older data (2023-11 .. 2025-10, by half-year) and the two recent windows, with the
tools in fixed USD and scaled by the price (x price / 4,100); then its losers in the owner's three kinds.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/deep_pullback.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as win

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
from exits import Path  # noqa: E402
from loser_kinds import classify  # noqa: E402

SLIP, REF = 0.07, 4100.0
TOOLS = [(10, 8), (8, 6)]
PERIODS = [
    ("2023-11 .. 2024-04", "2023-11-01", "2024-04-14"),
    ("2024-04 .. 2024-10", "2024-04-14", "2024-10-14"),
    ("2024-10 .. 2025-04", "2024-10-14", "2025-04-14"),
    ("2025-04 .. 2025-10", "2025-04-14", "2025-10-14"),
    ("earlier six (seen)", "2025-10-14", "2026-04-14"),
    ("latest six (seen)", "2026-04-14", "2026-10-14"),
]


def main() -> None:
    gold.below_normal_priority()
    lo_t, hi_t = pd.Timestamp("2023-09-01", tz="UTC"), pd.Timestamp("2026-10-14", tz="UTC")
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= lo_t) & (m1.index < hi_t + pd.Timedelta(days=1))]
    o, h, lo, c = (m1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m1["spread"].to_numpy(float) * 0.01
    n = len(o)
    d = pd.read_parquet("data/research/own_ml_long.parquet")
    d["t"] = pd.to_datetime(d.t, utc=True)
    fam = d[(d.h1_e20_slope > 0) & (d.h1_c_e50 > 0) & (d.m15_rsi < 40)].copy()
    print("family rows (minute x side):", len(fam))

    def label(rows: pd.DataFrame, tp: np.ndarray, sl: np.ndarray, hz: int = 60) -> pd.DataFrame:
        e, side = rows.e.to_numpy(), rows.side.to_numpy()
        ok = e + hz < n
        e = np.where(ok, e, 0)
        H, L, S = win(h, hz)[e], win(lo, hz)[e], win(sp, hz)[e]
        entry = o[e] + np.where(side > 0, sp[e] + SLIP, -SLIP)
        fav = np.where(side[:, None] > 0, H - entry[:, None], entry[:, None] - (L + S))
        adv = np.where(side[:, None] > 0, entry[:, None] - L, (H + S) - entry[:, None])
        ht = np.where((fav >= tp[:, None]).any(1), (fav >= tp[:, None]).argmax(1), 10**6)
        st = np.where((adv >= sl[:, None]).any(1), (adv >= sl[:, None]).argmax(1), 10**6)
        last = c[e + hz - 1] - np.where(side > 0, SLIP, -(sp[e + hz - 1] + SLIP))
        y = np.where(ht < st, 1, np.where(st < 10**6, 2, 0))
        usd = np.where(y == 1, tp, np.where(y == 2, -sl - SLIP, (last - entry) * side))
        out = rows[["t", "e", "side", "session", "ret1"]].copy()
        out["usd"], out["win"], out["mins"] = usd, y == 1, np.minimum(np.minimum(ht, st), hz - 1) + 1
        out["tp"], out["sl"], out["price"] = tp, sl, c[e]
        return out[ok]

    def run(x: pd.DataFrame, cap: int = 2) -> pd.DataFrame:
        x = x.sort_values("t").drop_duplicates("t")
        keep, free, count = [], pd.Timestamp(0, tz="UTC"), {}
        for t, s, mins in zip(x.t, x.session, x.mins, strict=True):
            key = (t.normalize(), s)
            ok = t >= free and count.get(key, 0) < cap
            keep.append(ok)
            if ok:
                free, count[key] = t + pd.Timedelta(minutes=int(mins)), count.get(key, 0) + 1
        return x[np.array(keep, dtype=bool)]

    scale = c[fam.e.to_numpy()] / REF
    results = {}
    print("\nUSD at 0.01 lot; win = target first; R = USD / stop")
    for s3 in ("none", "bar"):
        rows = fam if s3 == "none" else fam[fam.ret1 > 0]
        sc = scale if s3 == "none" else scale[(fam.ret1 > 0).to_numpy()]
        for tool in TOOLS:
            for mode in ("fixed", "scaled"):
                k = sc if mode == "scaled" else np.ones(len(rows))
                lab = label(rows, tool[0] * k, tool[1] * k)
                print(f"\n screen 3 {s3}, tool {tool[0]}/{tool[1]} {mode}:")
                for name, a, b in PERIODS:
                    x = run(lab[(lab.t >= pd.Timestamp(a, tz="UTC")) & (lab.t < pd.Timestamp(b, tz="UTC"))])
                    days = pd.bdate_range(a, b).size
                    r = (x.usd / (x.sl + SLIP)).mean() if len(x) else np.nan
                    by_m = x.usd.groupby(x.t.dt.strftime("%Y-%m")).sum()
                    print(f"   {name:20} {len(x):4} trades ({len(x) / days:.2f}/day) win {100 * x.win.mean():3.0f}%"
                          f"  {x.usd.mean():+.2f} USD/trade {r:+.3f} R  {x.usd.sum():+8.1f} USD  months+ {(by_m > 0).sum()}/{len(by_m)}")
                    results[(s3, tool, mode, name)] = x

    print("\nThe losers in three kinds (screen 3 none, tool 10/8 scaled), against a coin-flip side at the same minutes:")
    P = Path(pd.Timestamp("2023-11-01", tz="UTC"))
    rng = np.random.default_rng(5)
    for name, _a, _b in PERIODS:
        x = results[("none", (10, 8), "scaled", name)]
        if not len(x):
            continue
        ee = P.ot.searchsorted(x.t)
        for label_, sides in (("ours", x.side.to_numpy()), ("coin", rng.choice([-1, 1], len(x)))):
            kinds = []
            for e, s, tp, sl in zip(ee, sides, x.tp, x.sl, strict=True):
                k = classify(P, int(e), int(s), P.entry(int(e), int(s)) - s * sl, float(tp))
                if k:
                    kinds.append(k["kind"][0])
            v = pd.Series(kinds).value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
            print(f"   {name:20} {label_}: stopped {len(kinds):3}  wrong way {100 * v['1']:3.0f}%  fell short {100 * v['2']:3.0f}%"
                  f"  too early {100 * v['3']:3.0f}%")


if __name__ == "__main__":
    main()
