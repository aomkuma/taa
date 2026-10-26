"""Why the losing trades lost (owner 2026-10-26: "find the reasons for the losing trades - why still so many").
For every closed trade with R < 0 in data/replay/ai/store/trades_live.jsonl, from the stored M1 bars and the bot's
own readers at the entry:

- the move into the entry: how far price had run TOWARD the trade's stop in the 60 minutes before it (a sell
  entered after a rise), in USD and in H1 ATRs, and what share of the stop distance that is;
- the M15 leg / rhythm, the H1 rhythm and the D1 regime then;
- after the entry: the best price before the exit (MFE, in R) and the worst (MAE);
- after the exit: did price reach the take-profit later that day (the side was right) and how far it went.

    .venv/Scripts/python research/2026-10-24-replay/losers.py
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

STORE = ROOT / "data/replay/ai/store"
TH = "Asia/Bangkok"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(ROOT / "data/history")
    tfs = (Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1)
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in tfs}
    m1 = f[Timeframe.M1]
    rows = [json.loads(x) for x in (STORE / "trades_live.jsonl").read_text(encoding="utf-8").splitlines()]
    opens = {(r["side"], r["entry"]): r for r in rows if r["event"] == "OPEN"}
    print("| in (Thai) | side | entry / stop / tp | out | R | run into the entry (60 min) | M15 leg / rhythm, H1, D1 | "
          "MFE / MAE before the exit (R) | after the exit (same day) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for c in rows:
        if c["event"] != "CLOSE" or c["r"] >= 0 or (c["side"], c["entry"]) not in opens:
            continue
        o = opens[(c["side"], c["entry"])]
        t_in, t_out = pd.Timestamp(o["at"]), pd.Timestamp(c["at"])
        sell, entry, stop, tp = o["side"] == "SELL", float(o["entry"]), float(o["sl"]), float(o["tp"])
        risk = abs(stop - entry)
        a = t_in.floor("1min")
        before = m1[(m1.index >= a - pd.Timedelta(minutes=60)) & (m1.index < a)]
        run = (entry - float(before.low.min())) if sell else (float(before.high.max()) - entry)
        fr = kn.Frames(m1[m1.index < a], f[Timeframe.M15], f[Timeframe.H1], f[Timeframe.H4], f[Timeframe.D1], ())
        ft = kn.features(fr, a)
        held = m1[(m1.index >= a) & (m1.index <= t_out)]
        best = (entry - float(held.low.min())) if sell else (float(held.high.max()) - entry)
        worst = (float(held.high.max()) - entry) if sell else (entry - float(held.low.min()))
        end = t_in.normalize() + pd.Timedelta(days=1)
        after = m1[(m1.index > t_out) & (m1.index < end)]
        far = (entry - float(after.low.min())) if sell else (float(after.high.max()) - entry)
        hit = after.index[(after.low <= tp) if sell else (after.high >= tp)]
        later = f"TP reached {hit[0].tz_convert(TH):%H:%M}" if len(hit) else "TP not reached"
        print(
            f"| {t_in.tz_convert(TH):%m-%d %H:%M} | {o['side']} | {entry:.2f} / {stop:.2f} / {tp:.2f} | "
            f"{c['reason']} {t_out.tz_convert(TH):%H:%M} | {c['r']:+.2f} | {run:+.1f} USD toward the stop "
            f"({run / ft['h1_atr']:.2f} H1 ATR, {run / risk:.1f}x the stop distance) | {ft['m15_leg']} / "
            f"{ft['m15_rhythm']}, H1 {ft['h1_rhythm']}, D1 {ft['d1_regime']} | {best / risk:+.2f} / {-worst / risk:+.2f} | "
            f"{later}; best {far:+.1f} USD from the entry |"
        )


if __name__ == "__main__":
    main()
