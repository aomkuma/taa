"""Trade-by-trade audit of the journal (owner 2026-10-25: "if it all loses, the system thinks opposite to the
market - find where the error is: our understanding, or the understanding turned into code").

For every trade of the replay journal's days 2-4 (the run before the edge table, data/replay/ai/backup_before_edge),
from the M1 candles: the entry against the sweep's extreme, the best and the worst the trade saw in two hours (in
R), whether price reached the AI's target before / after the stop, and what the OPPOSITE trade (same entry, the
stop and target mirrored) would have done. Plus the condition the AI traded in.

    .venv/Scripts/python research/2026-10-24-replay/audit_trades.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.knowledge import d1_regime  # noqa: E402

BACKUP = ROOT / "data/replay/ai/backup_before_edge"
TH = "Asia/Bangkok"
ROW = re.compile(
    r"^\| (\d\d:\d\d):\d\d \| (\d\d:\d\d):\d\d \| (BUY|SELL) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| (\w+) \| ([+-][\d.]+) \|"
)


def trades() -> list[dict]:
    out = []
    for f in sorted(BACKUP.glob("day_2026-07-0*.md")):
        day = pd.Timestamp(f.stem.removeprefix("day_"))
        for line in f.read_text(encoding="utf-8").splitlines():
            m = ROW.match(line)
            if not m:
                continue
            t_in = pd.Timestamp(f"{day.date()} {m[1]}", tz=TH)
            if t_in.hour < 7:  # the Thai day runs 07:00 - 07:00
                t_in += pd.Timedelta(days=1)
            out.append(
                {
                    "in": t_in,
                    "side": m[3],
                    "entry": float(m[4]),
                    "stop": float(m[5]),
                    "exit": float(m[6]),
                    "why": m[7],
                    "r": float(m[8]),
                }
            )
    return out


def decision_at(rows: list[dict], t_in: pd.Timestamp, side: str) -> dict:
    """The AI's decision that opened the trade: the last BUY / SELL of that side at or before the fill."""
    best = None
    for r in rows:
        d = r.get("decision") or {}
        if d.get("decision") == side and pd.Timestamp(r["as_of"]) <= t_in.tz_convert("UTC") + pd.Timedelta(
            seconds=59
        ):
            best = r
    return best or {}


def readings(rec: dict, frames: dict[str, pd.DataFrame]) -> dict:
    """The readings the AI saw (its raw prompt) and the trends of D1 / H4 / H1 closed by then."""
    if not rec:
        return {}
    at = pd.Timestamp(rec["as_of"])
    stem = f"{at.tz_convert(TH):%Y-%m-%d_%H%M}"
    f: dict = {}
    raw = BACKUP / "store/raw" / f"{stem}_2_user.txt"
    if raw.exists():
        text = raw.read_text(encoding="utf-8")
        head = "READINGS (knowledge base features):\n"
        i = text.index(head) + len(head)
        f = json.loads(text[i : text.index("\n", i)])
    for name, df in frames.items():
        f[name] = d1_regime(df.close.to_numpy(float)[df.avail <= at]) or "?"
    return f


def main() -> None:
    raw = ParquetHistoryStore(ROOT / "data/history").load("FBS-Demo", "XAUUSD", Timeframe.M1, None, None)
    m1 = (
        raw.assign(t=pd.to_datetime(raw.open_time, utc=True)).drop_duplicates("t", keep="last").set_index("t")
    )
    m1 = m1.sort_index()
    store = ParquetHistoryStore(ROOT / "data/history")
    frames = {}
    for name, tf in (("d1_regime", Timeframe.D1), ("h4_trend", Timeframe.H4), ("h1_trend", Timeframe.H1)):
        df = store.load("FBS-Demo", "XAUUSD", tf, None, None)
        frames[name] = df.assign(avail=pd.to_datetime(df.close_time, utc=True)).sort_values("avail")
    rows = [
        json.loads(x) for x in (BACKUP / "store/decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    print(
        "| in (Thai) | side | weapon | entry | stop | target | risk | out | R | best R 2h | worst R 2h | "
        "target hit? | after the stop | opposite trade | D1 / H4 / H1 / M15 rhythm / session |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for t in trades():
        rec = decision_at(rows, t["in"], t["side"])
        d = rec.get("decision") or {}
        target = d.get("target")
        sell = t["side"] == "SELL"
        risk = abs(t["stop"] - t["entry"])
        t0 = t["in"].tz_convert("UTC").floor("min")
        w = m1[(m1.index >= t0) & (m1.index < t0 + pd.Timedelta(hours=2))]
        spr = w.spread.to_numpy(float) * 0.01
        fav = (t["entry"] - (w.low + spr)) if sell else (w.high - t["entry"])
        adv = ((w.high + spr) - t["entry"]) if sell else (t["entry"] - w.low)
        best, worst = fav.max() / risk, adv.max() / risk
        # the stop's and the target's first touch
        hit_stop = ((w.high + spr) >= t["stop"]) if sell else (w.low <= t["stop"])
        i_stop = hit_stop.to_numpy().argmax() if hit_stop.any() else None
        if target is not None:
            hit_tp = ((w.low + spr) <= target) if sell else (w.high >= target)
            i_tp = hit_tp.to_numpy().argmax() if hit_tp.any() else None
            if i_tp is None:
                tp_txt = "no"
            elif i_stop is None or i_tp < i_stop:
                tp_txt = f"yes, {i_tp} min"
            else:
                tp_txt = f"after the stop ({i_tp} min)"
        else:
            tp_txt = "-"
        after = "-"
        if i_stop is not None:
            rest = fav.iloc[i_stop:]
            after = f"then best {rest.max() / risk:+.2f} R"
        # the opposite: entry the same, stop where the target was, target where the stop was (mirrored R)
        opp = "-"
        if target is not None:
            o_stop, o_tp = target, t["stop"]
            o_hit_stop = ((w.low) <= o_stop) if sell else ((w.high + spr) >= o_stop)
            o_hit_tp = ((w.high) >= o_tp) if sell else ((w.low + spr) <= o_tp)
            a = o_hit_stop.to_numpy().argmax() if o_hit_stop.any() else None
            b = o_hit_tp.to_numpy().argmax() if o_hit_tp.any() else None
            o_r = abs(o_tp - t["entry"]) / abs(o_stop - t["entry"])
            opp = (
                f"won +{o_r:.2f} R"
                if b is not None and (a is None or b < a)
                else "lost -1 R"
                if a is not None
                else "open at 2h"
            )
        f = readings(rec, frames)
        cond = (
            f"{f.get('d1_regime', '?')} / {f.get('h4_trend', '?')} / {f.get('h1_trend', '?')} / "
            f"{f.get('m15_rhythm', '?')} / {f.get('session', '?')}"
        )
        print(
            f"| {t['in']:%m-%d %H:%M} | {t['side']} | {d.get('weapon', '-')} | {t['entry']:.2f} | {t['stop']:.2f} | "
            f"{target if target is not None else '-'} | {risk:.2f} | {t['why']} | {t['r']:+.2f} | {best:+.2f} | "
            f"{worst:+.2f} | {tp_txt} | {after} | {opp} | {cond} |"
        )


if __name__ == "__main__":
    main()
