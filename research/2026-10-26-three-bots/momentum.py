"""The owner's hypothesis, 2026-10-27, measured rather than argued.

    "D1 should not be that rigid. The order of hardness is H1, H4, D1 - meaning the more momentum D1
    has, the more force that side has and the further it runs. Or not?"

Two claims live in that sentence, and they are measured separately:

A. **Direction is not a gate, it is a quantity.** A binary "the side must agree with the D1 regime" was
   already tested and is nearly worthless: aligned -0.112 R against counter -0.173 R over 220 trades.
   So the question is whether momentum *as a number* carries what the label does not.

B. **The further claim: more momentum on a side -> the trade on that side runs further.** The thing that
   "runs further" is the favourable excursion, so the test is MFE in R against momentum - not the win
   rate and not the final R, both of which the stop and the target cut off.

And the ordering H1 -> H4 -> D1: if the owner is right that D1 is the strongest, D1 momentum should
separate the outcomes more than H4's, and H4's more than H1's. That ordering is a prediction, so it can
fail: it is written here before the numbers are read.

Momentum of a frame, defined here (mine to define, the owner's idea): the close's distance from its own
50-bar mean, measured in that frame's own 14-bar Wilder ATR, signed - positive is up. Distance over a
mean says where price is; dividing by that frame's ATR makes H1, H4 and D1 comparable, which a raw USD
distance never is.

    .venv\\Scripts\\python research/2026-10-26-three-bots/momentum.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

MEAN_BARS, ATR_BARS = 50, 14
FRAMES = {"H1": 1, "H4": 4, "D1": 24}  # hours a bar covers


def atr(frame: pd.DataFrame, n: int = ATR_BARS) -> pd.Series:
    """Wilder's ATR, MetaTrader 5's own formula."""
    prev = frame.close.shift(1)
    tr = pd.concat([frame.high - frame.low, (frame.high - prev).abs(), (frame.low - prev).abs()], axis=1).max(
        axis=1
    )
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def momentum(h1: pd.DataFrame, hours: int) -> pd.DataFrame:
    """One row per CLOSED bar of the frame: its momentum, and the time it became readable."""
    opens = h1.copy()
    opens.index = pd.DatetimeIndex(opens.index) - pd.Timedelta(hours=1)  # frames are close-stamped
    rule = f"{hours}h" if hours < 24 else "1D"
    f = opens.resample(rule).agg({"high": "max", "low": "min", "close": "last"}).dropna()
    out = pd.DataFrame(index=f.index)
    out["mom"] = (f.close - f.close.rolling(MEAN_BARS).mean()) / atr(f)
    out["readable"] = f.index + pd.Timedelta(hours=hours)
    return out.dropna()


def read_at(table: pd.DataFrame, at: pd.Timestamp) -> float:
    usable = table[table.readable <= at]
    return float(usable.mom.iloc[-1]) if len(usable) else float("nan")


def bins(df: pd.DataFrame, col: str, name: str) -> None:
    """Outcomes by how much momentum there was ON THE TRADE'S OWN SIDE."""
    x = df.dropna(subset=[col])
    if x.empty:
        print(f"\n{name}: no data")
        return
    # signed momentum turned into "momentum behind this trade": +ve means the frame leans our way
    behind = np.where(x.side == "BUY", x[col], -x[col])
    x = x.assign(behind=behind)
    edges = [-np.inf, -2, -1, 0, 1, 2, np.inf]
    labels = ["<-2", "-2..-1", "-1..0", "0..1", "1..2", ">2"]
    x = x.assign(band=pd.cut(x.behind, edges, labels=labels))
    print(f"\n### {name}\n")
    print("| momentum behind the trade | trades | win | R a trade | **median MFE (R)** | fit / unseen R |")
    print("|---|---|---|---|---|---|")
    for lab in labels:
        g = x[x.band == lab]
        if len(g) < 8:
            continue
        fit, uns = g[g.fitted], g[~g.fitted]
        both = f"{fit.r.mean():+.2f} / {uns.r.mean():+.2f}" if len(fit) and len(uns) else "-"
        print(
            f"| {lab} | {len(g)} | {(g.r > 0).mean():.0%} | {g.r.mean():+.3f} | "
            f"**{g.mfe_r.median():.2f}** | {both} |"
        )
    c = x[["behind", "mfe_r"]].corr().iloc[0, 1]
    cr = x[["behind", "r"]].corr().iloc[0, 1]
    print(f"\ncorrelation with MFE **{c:+.3f}**, with the final R {cr:+.3f}  ({len(x)} trades)")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    d = pd.read_csv(HERE / "edge_trades.csv")
    d["at"] = pd.to_datetime(d["at"], utc=True)
    hs = ParquetHistoryStore(ROOT / "data/history")
    h1 = to_frame(hs.load("FBS-Demo", "XAUUSD", Timeframe.H1, None, None))
    for name, hours in FRAMES.items():
        table = momentum(h1, hours)
        d[f"mom_{name}"] = [read_at(table, t) for t in d["at"]]
    print("# The owner's momentum hypothesis (2026-10-27)\n")
    print(
        "Momentum = the close's distance from its own 50-bar mean in that frame's own 14-bar ATR, signed,\n"
        "read from the last bar of the frame CLOSED before the entry. 'Behind the trade' flips the sign\n"
        "for a sell, so a positive number always means the frame leans the way the trade is going.\n"
    )
    print(
        f"{len(d)} trades, 2023-09 .. 2026-10. The prediction written first: D1 separates most, then H4, then H1."
    )
    for name in FRAMES:
        bins(d, f"mom_{name}", f"{name} momentum behind the trade")
    print("\n## The ordering, in one line each\n")
    print("| frame | correlation with MFE | correlation with R |")
    print("|---|---|---|")
    for name in FRAMES:
        x = d.dropna(subset=[f"mom_{name}"])
        behind = np.where(x.side == "BUY", x[f"mom_{name}"], -x[f"mom_{name}"])
        print(
            f"| {name} | {np.corrcoef(behind, x.mfe_r)[0, 1]:+.3f} | {np.corrcoef(behind, x.r)[0, 1]:+.3f} |"
        )
    d.to_csv(HERE / "momentum_trades.csv", index=False)


if __name__ == "__main__":
    main()
