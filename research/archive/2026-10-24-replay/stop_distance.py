"""How far the stop past the liquidation zone sits from price (the code's stops, app/strategy/liquidity.py), and
the risk percent a 0.01-lot trade needs to carry it (owner 2026-10-24: "raise the risk percent to cover the measured
distance"). Sampled at every M5 close inside the owner's windows (Asia 07-09, London 13-15, New York 08:00-11:30
NY), on the design months before the exam and on the replay month.

Gold: 0.01 lot = 1 USD per 1.00 of price, so a stop D away risks D USD at the minimum lot.

    .venv/Scripts/python research/2026-10-24-replay/stop_distance.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy import knowledge as kn  # noqa: E402
from app.strategy import liquidity as lq  # noqa: E402


def sample(f: dict, start: str, end: str, step: int = 3) -> pd.DataFrame:
    m1, m15, h1, d1 = (f[t] for t in (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.D1))
    times = pd.date_range(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"), freq=f"{5 * step}min")
    rows = []
    for at in times:
        if kn.session(at) == "none":
            continue
        x1 = m1[(m1.index >= at - pd.Timedelta(days=2)) & (m1.index < at)]
        if len(x1) < 600 or (at - x1.index[-1]) > pd.Timedelta(minutes=5):
            continue  # the market closed
        m5 = kn.m5_frame(x1, at)
        st = lq.structure_now(x1, m5, m15, d1, h1, at)
        if st is None:
            continue
        price = float(x1.close.iloc[-1])
        # the room: the nearest untaken pool (or round number / day level) in the trade's direction, at least
        # half an M5 ATR away - where the target stands before it (the geometry at the moment, no look ahead)
        xh = lq.closed(h1, 60, at)
        reach = 6 * lq.atr(xh.high.to_numpy(float), xh.low.to_numpy(float), xh.close.to_numpy(float))
        live = [p.price for p in lq.pools(m5, m15, d1, at) + lq.rounds(price) if not p.taken]
        ups = sorted(p - price for p in live if 0.5 * st.atr_m5 <= p - price <= reach)
        downs = sorted(price - p for p in live if 0.5 * st.atr_m5 <= price - p <= reach)
        rows.append(
            {
                "t": at,
                "sell": st.sell_stop - price,
                "buy": price - st.buy_stop,
                "room_buy": ups[0] if ups else np.nan,
                "room_sell": downs[0] if downs else np.nan,
                "room2_buy": ups[1]
                if len(ups) > 1
                else np.nan,  # the pool after the first: a runner's target
                "room2_sell": downs[1] if len(downs) > 1 else np.nan,
                "atr": st.atr_m5,
            }
        )
    return pd.DataFrame(rows)


def show(df: pd.DataFrame, title: str) -> None:
    d = pd.concat([df.sell, df.buy])
    q = d.quantile([0.25, 0.5, 0.75, 0.9]).round(2).tolist()
    print(f"\n== {title}: {len(df)} moments in the owner's windows ==")
    print(
        f"stop distance past the liquidation zone (USD, 25 / 50 / 75 / 90 %): {q}; median M5 ATR {df.atr.median():.2f}"
    )
    for bal in (100.0, 300.0):
        need = (np.array(q) / bal * 100).round(1).tolist()
        print(
            f"  {bal:.0f} USD account at 0.01 lot: risk % per trade {need} (25 / 50 / 75 / 90 % of the moments)"
        )
    for name, room in (
        ("the first pool", ("room_buy", "room_sell")),
        ("the second pool", ("room2_buy", "room2_sell")),
    ):
        r = pd.concat([df[room[0]] / df.buy, df[room[1]] / df.sell]).dropna()
        usd = pd.concat([df[room[0]], df[room[1]]]).dropna()
        print(
            f"target at {name}: USD (25 / 50 / 75 %) {usd.quantile([0.25, 0.5, 0.75]).round(2).tolist()}; "
            f"R = room / stop (25 / 50 / 75 / 90 %) {r.quantile([0.25, 0.5, 0.75, 0.9]).round(2).tolist()}"
        )
        for k in (0.5, 0.8, 1.0, 1.5):
            print(f"    R >= {k}: {(r >= k).mean():.0%} of the moments")


def main() -> None:
    st = ParquetHistoryStore(ROOT / "data/history")
    f = {
        t: to_frame(st.load("FBS-Demo", "XAUUSD", t, None, None))
        for t in (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.D1)
    }
    show(sample(f, "2026-03-02", "2026-04-17", step=6), "design: 2026-03-02 .. 2026-04-17 (before the exam)")
    show(sample(f, "2026-07-06", "2026-07-31"), "the replay month 2026-07-06 .. 07-31")


if __name__ == "__main__":
    main()
