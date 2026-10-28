"""Owner 2026-10-22 after week 15: "the problem is you cannot read price momentum - and high volatility". Per NY-B2
entry of weeks 2-15 (everything before 2026-02-01, nothing after), from closed bars only:

- push30 / push60: the move of the last 30 / 60 minutes INTO the entry in the trade's direction, in H1 ATR(14)
  (negative = price was running against the trade into the entry, e.g. a sell into a rising market)
- push3d / push24h: the big push into the entry in the trade's direction, in D1 ATR(14): from the close 3 days ago
  and from the H4 close 24 hours ago (negative = the trade fades the big push)
- push240 / h1_with: the last 4 hours into the entry in the trade's direction (H1 ATR) and how many of the
  last 4 closed H1 bars closed in the trade's direction
- m15_with: how many of the last 4 closed M15 bars closed in the trade's direction (0-4)
- rng60: the high-low range of the last 60 minutes in H1 ATR (how fast the market is moving right now)
- vol: H1 ATR(14) at the entry over its median of the previous 20 days (above 1 = more volatile than usual)
Outcomes: the base R and the realistic variant without filters (r_real_all).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/momentum.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import week as W

END = pd.Timestamp("2026-02-01", tz="UTC")


def atr14(b: pd.DataFrame) -> pd.Series:
    pc = b.close.shift(1)
    return pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()


def main() -> None:
    X = W.load()
    X = X[X.t < END].sort_values("t").copy()
    X["r_real_all"] = W.realistic(X)
    m5, m15, h1, h4, d1 = (W.Z.bars(tf) for tf in ("M5", "M15", "H1", "H4", "D1"))
    d1a = atr14(d1).rename("a").to_frame().assign(a=lambda f: f.a)  # D1 ATR(14), closed days only below
    h1a = atr14(h1)
    h1med = h1a.rolling(20 * 24, min_periods=100).median()
    rows = []
    for r in X.itertuples():
        side = 1 if r.side == "BUY" else -1
        hc = h1a[h1a.index + pd.Timedelta(hours=1) <= r.t]
        a, med = float(hc.iloc[-1]), float(h1med[hc.index[-1]])
        c5 = m5[m5.index + pd.Timedelta(minutes=5) <= r.t]
        p30 = (r.entry_price - c5.close.iloc[-7]) * side / a  # close 30 min before the last closed M5 close
        p60 = (r.entry_price - c5.close.iloc[-13]) * side / a
        last12 = c5.iloc[-12:]
        rng60 = (last12.high.max() - last12.low.min()) / a
        c15 = m15[m15.index + pd.Timedelta(minutes=15) <= r.t].iloc[-4:]
        with_ = int(((c15.close - c15.open) * side > 0).sum())
        c1 = h1[h1.index + pd.Timedelta(hours=1) <= r.t]
        p240 = (r.entry_price - c1.close.iloc[-5]) * side / a  # the last 4 hours: the push the pattern fades
        h1_with = int(((c1.close - c1.open).iloc[-4:] * side > 0).sum())
        cd = d1[d1.index + pd.Timedelta(days=1) <= r.t]
        da = float(d1a.a[cd.index[-1]])
        p3d = (r.entry_price - cd.close.iloc[-4]) * side / da  # the big push: 3 closed days + today so far, D1 ATR
        c4 = h4[h4.index + pd.Timedelta(hours=4) <= r.t]
        p24 = (r.entry_price - c4.close.iloc[-7]) * side / da  # the last 24 hours (6 closed H4 bars), D1 ATR
        rows.append(dict(push3d=p3d, push24h=p24, push30=p30, push60=p60, push240=p240, h1_with=h1_with, m15_with=with_, rng60=rng60, vol=a / med, h1atr=a))
    X = X.join(pd.DataFrame(rows, index=X.index))
    pd.set_option("display.width", 220)
    for r in X.itertuples():
        print(f"{r.t.tz_convert('Asia/Bangkok'):%y-%m-%d %a %H:%M} {r.side:4s} base {r.r_multiple:+.2f} real {r.r_real_all:+.2f} | "
              f"push30 {r.push30:+.2f} push60 {r.push60:+.2f} 3d {r.push3d:+.2f} 24h {r.push24h:+.2f} D1ATR | push4h {r.push240:+.2f} H1 with {r.h1_with}/4 M15 with {r.m15_with}/4 rng60 {r.rng60:.2f} vol {r.vol:.2f} (H1 ATR {r.h1atr:.1f})")

    def split(col: str, edges: list[float]) -> None:
        b = pd.cut(X[col], [-np.inf, *edges, np.inf])
        g = X.groupby(b, observed=True).agg(n=("r_multiple", "size"), base=("r_multiple", "sum"), real=("r_real_all", "sum"),
                                            win=("r_real_all", lambda s: (s > 0).mean() * 100))
        print(f"\n{col}\n{g.round(2).to_string()}")

    split("push30", [-0.5, 0.0, 0.5])
    split("push60", [-0.5, 0.0, 0.5])
    split("push3d", [-1.0, 0.0, 1.0])
    split("push24h", [-0.5, 0.0, 0.5])
    split("push240", [-1.5, -0.5, 0.5])
    split("h1_with", [0.5, 1.5, 2.5])
    split("m15_with", [0.5, 1.5, 2.5])
    split("rng60", [0.75, 1.25, 2.0])
    split("vol", [0.9, 1.1, 1.4])
    print(f"\nall: {len(X)} trades base {X.r_multiple.sum():+.2f} real {X.r_real_all.sum():+.2f}")
    X.to_csv(W.HERE / "momentum.csv", index=False)


if __name__ == "__main__":
    main()
