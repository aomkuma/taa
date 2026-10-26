"""Which order kind fits which market condition (owner 2026-10-26: "in a sideways market the fades get many trades;
in a trend it needs stop orders"). For every scenario of the AI's day plans (data/replay/ai/store/plans.jsonl,
06-08 Jul), on the stored M1 bars of its window:

- the condition at the window's start, from the bot's own readers (knowledge.features): the D1 regime, the H1
  trend / rhythm / efficiency, the M15 range of 12 bars in ATRs - and the class: TREND (D1 and H1 the same way)
  or RANGE;
- the order's kind (a limit fades a level, a stop follows a break) read from its entry against the price then;
- the ways to fill it inside the window: at the touch; after the signal at the level (app/strategy/confirm.py,
  as the bot does now); and, for a stop, at the break without the retest and at the first M5 close through;
- each fill's result to the day's end (07:00 Thai) on bid bars, no spread: TP / SL / still open (marked at the
  last close), in R.

    .venv/Scripts/python research/2026-10-24-replay/regime_orders.py
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
from app.strategy import confirm as cf  # noqa: E402
from app.strategy import knowledge as kn  # noqa: E402

STORE = ROOT / "data/replay/ai/store"
TH = "Asia/Bangkok"


def outcome(
    m1: pd.DataFrame, t: pd.Timestamp, fill: float, stop: float, tp: float, sell: bool
) -> tuple[str, float]:
    """TP / SL / open at the day's end from the bar after ``t``, in R (a bar touching both: SL first)."""
    end = t.normalize() + pd.Timedelta(days=1)
    x = m1[(m1.index > t) & (m1.index < end)]
    risk = abs(stop - fill)
    for _, b in x.iterrows():
        hit_sl = b.high >= stop if sell else b.low <= stop
        hit_tp = b.low <= tp if sell else b.high >= tp
        if hit_sl:
            return "SL", -1.0
        if hit_tp:
            return "TP", abs(tp - fill) / risk
    last = float(x.close.iloc[-1]) if len(x) else fill
    return "open", ((fill - last) if sell else (last - fill)) / risk


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(ROOT / "data/history")
    tfs = (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1)
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in tfs}
    m1 = f[Timeframe.M1]
    plans = [json.loads(x) for x in (STORE / "plans.jsonl").read_text(encoding="utf-8").splitlines()]
    print(
        "| window (Thai) | condition | class | scenario | kind | touch fill -> result | signal fill -> result | "
        "stop at the touch -> result | stop at an M5 close through -> result |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for p in plans:
        if p.get("status") != "OK":
            continue
        a, until = pd.Timestamp(p["as_of"]), pd.Timestamp(p["valid_until"])
        fr = kn.Frames(
            m1[m1.index < a], f[Timeframe.M15], f[Timeframe.H1], f[Timeframe.H4], f[Timeframe.D1], ()
        )
        ft = kn.features(fr, a)
        cls = f"TREND {ft['d1_regime']}" if ft["d1_regime"] == ft["h1_trend"] != "none" else "RANGE"
        cond = (
            f"D1 {ft['d1_regime']}, H1 {ft['h1_trend']} / rhythm {ft['h1_rhythm']} / eff {ft['h1_eff12']:.2f}, "
            f"M15 12-bar range {ft['m15_range12_atr']:.1f} ATR"
        )
        price = ft["price"]
        win = m1[(m1.index >= a) & (m1.index < until)]
        for s in p["plan"]["scenarios"]:
            side, entry, stop, tp = s["side"], s.get("entry"), s.get("stop"), s.get("take_profit")
            if entry is None or stop is None or tp is None:
                continue
            sell = side == "SELL"
            ms = (p.get("map_stops") or {}).get(side)
            if ms is not None:  # out to the map's stop past the liquidate zone, as plan_orders does
                stop = max(stop, ms) if sell else min(stop, ms)
            kind = "limit" if ((entry >= price) if sell else (entry <= price)) else "stop"
            reach = (win.high >= entry) if (sell == (kind == "limit")) else (win.low <= entry)
            touched = win.index[reach]
            cells = []
            if not len(touched):
                cells = ["no touch", "-", "-", "-"]
            else:
                t0 = touched[0]
                cells.append(
                    f"{t0.tz_convert(TH):%H:%M} {entry:.2f} -> "
                    + "%s %+.2f" % outcome(m1, t0, entry, stop, tp, sell)
                )
                got = None
                for t in win.index[win.index >= t0]:
                    at = t + pd.Timedelta(minutes=1)
                    sig = cf.signal(m1[m1.index < at], at, t0, entry, sell, kind)
                    if sig:
                        got = (t, sig)
                        break
                if got:
                    t, sig = got
                    fill = float(m1.loc[t, "close"])
                    cells.append(
                        f"{sig} {t.tz_convert(TH):%H:%M} {fill:.2f} -> "
                        + "%s %+.2f" % outcome(m1, t, fill, stop, tp, sell)
                    )
                else:
                    cells.append("no signal in the window")
                if kind == "stop":
                    cells.append(
                        f"{t0.tz_convert(TH):%H:%M} {entry:.2f} -> "
                        + "%s %+.2f" % outcome(m1, t0, entry, stop, tp, sell)
                    )
                    m5 = cf.complete(
                        m1[m1.index < until + pd.Timedelta(minutes=5)], until + pd.Timedelta(minutes=5), 5
                    )
                    m5 = m5[(m5.index >= t0.floor("5min")) & (m5.index < until)]
                    through = m5.index[(m5.close < entry) if sell else (m5.close > entry)]
                    if len(through):
                        tc = through[0] + pd.Timedelta(minutes=4)  # the M5 bar's last M1 bar
                        fill = float(m5.loc[through[0], "close"])
                        cells.append(
                            f"{tc.tz_convert(TH):%H:%M} {fill:.2f} -> "
                            + "%s %+.2f" % outcome(m1, tc, fill, stop, tp, sell)
                        )
                    else:
                        cells.append("no M5 close through")
                else:
                    cells.append("-")
                    cells.append("-")
            print(
                f"| {a.tz_convert(TH):%m-%d %H:%M} {p['kind']} | {cond} | {cls} | {s['name']} {side} {entry} "
                f"(stop {stop:.2f}, tp {tp}) | {kind} | " + " | ".join(cells) + " |"
            )


if __name__ == "__main__":
    main()
