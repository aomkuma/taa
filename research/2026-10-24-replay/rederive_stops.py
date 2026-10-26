"""An independent re-derivation of the code's stop past the liquidate zone (ISSUES 33, owner 2026-10-26: "is the
stop really past the liquidate zone - every trade"; "fix the calculation logic, then test it more thoroughly").

For every trade in data/replay/ai/store/trades_live.jsonl, at the last closed M1 bar before its fill:
- the structure's inputs (2 h of M5 and the closed M1 bars of the M5 bar still forming: top / bottom / ATR; the pools near price; the volume bands) from the
  tested helpers of app/strategy/liquidity.py;
- the stop past the zone written again here, apart from the app's code: the OLD rule (an unlimited jump at the
  edge, an unbounded chain) and the NEW rule (the jump within 1 ATR, the zone at most 2 ATR past the edge);
- the NEW rule must equal lq.structure_now to the cent (else the line says MISMATCH);
- the trade's own stop, and the worst price against it between the fill and its close (did the new stop hold).

    .venv/Scripts/python research/2026-10-24-replay/rederive_stops.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy import knowledge as kn  # noqa: E402
from app.strategy import liquidity as lq  # noqa: E402

STORE = ROOT / "data/replay/ai/store"
TH = "Asia/Bangkok"


def zone(edge: float, price: float, pools: list[float], bands: list[tuple[float, float]], a: float,
         up: bool, new: bool) -> tuple[float, float]:  # fmt: skip
    """(stop, zone end), written apart from lq.beyond_zone: distances measured outward from the edge."""
    out = (lambda x: x - edge) if up else (lambda x: edge - x)  # how far past the edge, outward
    dist = sorted(out(p) for p in pools if out(p) > 0)
    spans = [(out(lo), out(hi)) if up else (out(hi), out(lo)) for lo, hi in bands]  # (start, end) outward
    far = 0.0
    if abs(edge - price) <= 0.5 * a and dist and (not new or dist[0] <= 1.0 * a):
        far = dist[0]
    grew = True
    while grew:
        grew = False
        for d in dist:
            if far < d <= far + 0.5 * a:
                far, grew = d, True
        for s, e in spans:
            if s <= far + 0.5 * a and e > far:
                far, grew = e, True
    if new:
        far = min(far, 2.0 * a)
    sign = 1.0 if up else -1.0
    return round(edge + sign * (far + a), 2), round(edge + sign * far, 2)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(ROOT / "data/history")
    f = {
        t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None))
        for t in (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.D1)
    }
    m1, m15, h1, d1 = (f[t] for t in (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.D1))
    rows = [json.loads(x) for x in (STORE / "trades_live.jsonl").read_text(encoding="utf-8").splitlines()]
    closes = {(r["side"], r["entry"]): r for r in rows if r["event"] == "CLOSE"}
    print(
        "| opened (Thai) | side | entry | its stop | old code stop (dist) | new code stop (dist) | new zone | "
        "its stop past the new? | worst against, fill to close | result | app = rederived |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["event"] != "OPEN":
            continue
        fill = pd.Timestamp(r["at"])
        as_of = fill.floor("1min")
        x1 = m1[(m1.index >= as_of - pd.Timedelta(days=2)) & (m1.index < as_of)]
        m5 = kn.m5_frame(x1, as_of)
        x5 = lq.closed(m5, 5, as_of)
        xh = lq.closed(h1, 60, as_of)
        price = float(lq.closed(x1, 1, as_of).close.iloc[-1])
        a = lq.atr(x5.high.to_numpy(float), x5.low.to_numpy(float), x5.close.to_numpy(float))
        top, bottom = (
            float(x5.high.iloc[-lq.STRUCTURE_M5 :].max()),
            float(x5.low.iloc[-lq.STRUCTURE_M5 :].min()),
        )
        bar = x5.index[-1] + pd.Timedelta(minutes=5)  # the M5 bar still forming: its closed M1 bars count
        part = x1[(x1.index >= bar) & (x1.index + pd.Timedelta(minutes=1) <= as_of)]
        if len(part):
            top, bottom = max(top, float(part.high.max())), min(bottom, float(part.low.min()))
        reach = lq.NEAR_ATR * lq.atr(
            xh.high.to_numpy(float), xh.low.to_numpy(float), xh.close.to_numpy(float)
        )
        near = [p for p in lq.pools(m5, m15, d1, as_of) + lq.rounds(price) if abs(p.price - price) <= reach]
        live = [p.price for p in near if not p.taken]
        bands = [(s, s + lq.BUCKET) for s, _ in lq.volume_nodes(x1, as_of)]
        sell = r["side"] == "SELL"
        edge = top if sell else bottom
        old, _ = zone(edge, price, live, bands, a, sell, new=False)
        new, end = zone(edge, price, live, bands, a, sell, new=True)
        st = lq.structure_now(x1, m5, m15, d1, h1, as_of)
        app = None if st is None else (st.sell_stop, st.sell_zone) if sell else (st.buy_stop, st.buy_zone)
        same = "yes" if app == (new, end) else f"MISMATCH {app}"
        entry, sl = float(r["entry"]), float(r["sl"])
        past = sl >= new if sell else sl <= new
        c = closes.get((r["side"], r["entry"]))
        worst, result = "-", "open"
        if c is not None:
            span = m1[(m1.index >= as_of) & (m1.index < pd.Timestamp(c["at"]).ceil("1min"))]
            if len(span):
                w = float(span.high.max()) if sell else float(span.low.min())
                held = (w < new) if sell else (w > new)
                worst = f"{w:.2f} ({'held' if held else 'reached'} the new stop)"
            result = f"{c['reason']} {c['r']:+.2f} R"
        print(
            f"| {fill.tz_convert(TH):%m-%d %H:%M} | {r['side']} | {entry:.2f} | {sl:.2f} | "
            f"{old:.2f} ({abs(old - entry):.2f}) | {new:.2f} ({abs(new - entry):.2f}) | {end:.2f} | "
            f"{'yes' if past else f'no ({abs(new - sl):.2f} short)'} | {worst} | {result} | {same} |"
        )


if __name__ == "__main__":
    main()
