"""One trader, three bots (owner 2026-10-26: "the bots are like three traders, each trading its own setup at the
same time, one account - at one decision point they cannot all enter: at most two, a trend one way and sideways";
"make it profitable first - no before / after the exam").

Plain code, no AI, so it can be tuned fast. Each bot watches for its OWN structure at every M5 close inside the
owner's windows (Asia 07:00-09:00, London 13:00-15:00 Thai, New York 08:00-11:30 NY) and holds its own position;
a trend bot and the range bot can overlap, the two trend bots cannot (their conditions are opposites).

- DOWN: MetaTrader 5's ZigZag (12, 5, 3) on the H1 bars closed by then shows a lower high AND a lower low; its
  last leg A (high) -> B (low); price pulled back RETRACE of it; an M5 box (6-24 bars, at most BOX of the leg
  tall) - the quiet; an M5 close under the box = SELL; stop over the box by BUFFER of the box height;
  take-profit at B, at least MIN_TP USD and MIN_R x the risk. UP: the mirror;
- RANGE: the box comes from the BIG picture (owner 2026-10-26: "sideways has to be measured on H1-H4"):
  ``range_tf`` names the frame whose ZigZag gives the box - H4, H1, or 'both' (the H4 box, and the H1 swings
  must sit inside it). That frame must not be stepping (no lower-high-and-lower-low, no higher pair), and price
  must be inside the box. Then an M5 bar over the box top closing back under it = SELL (a sweep closed back),
  stop over that bar's high + BUFFER x its range, take-profit TP_RANGE of the way to the box low; the mirror at
  the bottom. ``range_mode`` 'opposite' takes the other side, 'break' trades an M5 close out of the box;
- shared by the account: no entry into a push still running toward the stop (the 60 minutes before ran more than
  RUN x the stop distance), and the windows;
- the exit, ``exit_mode``: 'tp' the stop and take-profit alone; 'be' the stop to break-even once the trade is
  BE_AT x risk ahead; 'trail' the same, then the stop follows the extreme of the last TRAIL_MIN minutes of M1
  bars; 'struct' out when STRUCT_BARS M5 bars close back across the entry. 'tp' leans on where the test stops
  (the Thai day's end carried 29-48 % of each bot's gross R), so it is a baseline, not a design;
- SL / TP on the M1 bars (bid), the spread SPREAD USD off every trade; a trade still open at the Thai day's end
  is closed there.

    .venv/Scripts/python research/2026-10-26-three-bots/bots.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402
from app.strategy.zigzag import zigzag  # noqa: E402

TH, NY = "Asia/Bangkok", "America/New_York"
START, END = pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-10-24", tz="UTC")


@dataclass
class P:
    retrace: tuple[float, float] = (0.382, 0.786)
    box: float = 0.25  # the box at most this share of the H1 leg tall
    buffer: float = 0.2  # the stop past the box by this share of the box height
    min_tp: float = 5.0
    min_r: float = 1.0
    tp_range: float = 0.5
    run: float = 1.2
    spread: float = 0.30
    exit_mode: str = "tp"  # tp | be | trail | struct (see the module docstring)
    be_at: float = 1.0  # the trade must be this many R ahead before the stop moves
    trail_min: int = 30  # 'trail': the stop follows the extreme of the last this many minutes of M1 bars
    struct_bars: int = 3  # 'struct': this many M5 closes back across the entry end the trade
    max_hours: float = 0  # the trade is closed at this bar's close after this many hours (0: at the day's end)
    bots: tuple[str, ...] = ("DOWN", "UP", "RANGE")
    d1: bool = False  # the trend bots only with the D1 regime (the close against its 50-day mean)
    range_mode: str = "fade"  # fade: sell a sweep closed back; opposite: the same trigger, the other side;
    # break: an M5 close out of the box, traded with the break
    range_tf: str = "H4"  # where the box comes from: "H4", "H1" or "both" (the H4 box with H1 inside it)
    range_flat: bool = True  # the box frame must not be stepping up or down


@dataclass
class Trade:
    bot: str
    side: str
    at: pd.Timestamp
    entry: float
    stop: float
    tp: float
    r: float = 0.0
    out: str = ""
    extra: dict = field(default_factory=dict)


def windows(day: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    th, ny = pd.Timestamp(day.date(), tz=TH), pd.Timestamp(day.date(), tz=NY)
    return [
        ((th + pd.Timedelta(hours=7)).tz_convert("UTC"), (th + pd.Timedelta(hours=9)).tz_convert("UTC")),
        ((th + pd.Timedelta(hours=13)).tz_convert("UTC"), (th + pd.Timedelta(hours=15)).tz_convert("UTC")),
        ((ny + pd.Timedelta(hours=8)).tz_convert("UTC"), (ny + pd.Timedelta(hours=11, minutes=30)).tz_convert("UTC")),
    ]


def market(h1: pd.DataFrame) -> tuple[str, list]:  # the census only: the bots no longer switch on it
    sw, _ = zigzag(h1.high.to_numpy(float), h1.low.to_numpy(float))
    highs = [s for s in sw if s.kind == 1]
    lows = [s for s in sw if s.kind == -1]
    if len(highs) < 2 or len(lows) < 2:
        return "NONE", sw
    if highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
        return "DOWN", sw
    if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
        return "UP", sw
    return "RANGE", sw


def settle(m1: pd.DataFrame, t: Trade, until: pd.Timestamp, p: P) -> Trade:
    """Walk the M1 bars from the entry to ``until``: the stop (moved by ``exit_mode``) and the take-profit, the
    worse of the two first when a bar holds both; else the last close. The spread is taken off once."""
    if p.max_hours:
        until = min(until, t.at + pd.Timedelta(hours=p.max_hours))
    x = m1[(m1.index >= t.at) & (m1.index < until)]
    sell = t.side == "SELL"
    risk = abs(t.stop - t.entry)
    hi = x.high.to_numpy()
    lo = x.low.to_numpy()
    cl = x.close.to_numpy()
    ix = x.index
    stop, best = t.stop, t.entry  # best: the furthest price reached in the trade's favour
    exit_px, out, when = None, ("time" if p.max_hours else "eod"), until
    back = 0  # 'struct': M5 closes in a row back across the entry
    for i in range(len(x)):
        if (hi[i] >= stop) if sell else (lo[i] <= stop):
            exit_px, out, when = stop, ("SL" if stop == t.stop else "trail"), ix[i]
            break
        if (lo[i] <= t.tp) if sell else (hi[i] >= t.tp):
            exit_px, out, when = t.tp, "TP", ix[i]
            break
        best = min(best, lo[i]) if sell else max(best, hi[i])
        ahead = (t.entry - best) if sell else (best - t.entry)
        if p.exit_mode in ("be", "trail") and ahead >= p.be_at * risk:
            moved = t.entry
            if p.exit_mode == "trail" and i >= 1:
                j = max(0, i - p.trail_min + 1)
                moved = float(hi[j : i + 1].max()) if sell else float(lo[j : i + 1].min())
            stop = min(stop, max(moved, t.entry)) if sell else max(stop, min(moved, t.entry))
        if p.exit_mode == "struct" and (i + 1) % 5 == 0:
            back = back + 1 if ((cl[i] > t.entry) if sell else (cl[i] < t.entry)) else 0
            if back >= p.struct_bars:
                exit_px, out, when = float(cl[i]), "struct", ix[i]
                break
    if exit_px is None:
        exit_px = float(cl[-1]) if len(x) else t.entry
    gain = (t.entry - exit_px) if sell else (exit_px - t.entry)
    t.r, t.out = (gain - p.spread) / risk, out
    t.extra["closed"] = when
    return t


def run(f: dict, params: P | dict[str, P], start: pd.Timestamp = START, end: pd.Timestamp = END) -> list[Trade]:
    """Every bot of ``params`` (one P for all its bots, or one P per bot) side by side, each with its own
    position, so a trend trade and a range trade can be open at once."""
    per: dict[str, P] = params if isinstance(params, dict) else {b: params for b in params.bots}
    m1, h1 = f[Timeframe.M1], f[Timeframe.H1]
    h4 = h1.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    m1 = m1[(m1.index >= start - pd.Timedelta(days=3)) & (m1.index < end + pd.Timedelta(days=2))]
    m5 = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    trades: list[Trade] = []
    busy = dict.fromkeys(per, start)  # each bot's own position: free again from this time
    for day in pd.date_range(start, end, freq="D"):
        if day.weekday() >= 5:
            continue
        day_end = (pd.Timestamp(day.date(), tz=TH) + pd.Timedelta(days=1, hours=7)).tz_convert("UTC")
        for w0, w1 in windows(day):
            bars = m5[(m5.index >= w0 - pd.Timedelta(hours=2)) & (m5.index < w1)]
            seen, sw, sw4 = None, [], []
            for i in range(len(bars)):
                t_close = bars.index[i] + pd.Timedelta(minutes=5)
                if t_close <= w0 or t_close > w1:
                    continue
                hx = h1[h1.index + pd.Timedelta(hours=1) <= t_close].iloc[-400:]
                if seen != len(hx):
                    seen = len(hx)
                    sw, _ = zigzag(hx.high.to_numpy(float), hx.low.to_numpy(float))
                    h4x = h4[h4.index + pd.Timedelta(hours=4) <= t_close].iloc[-300:]
                    sw4, _ = zigzag(h4x.high.to_numpy(float), h4x.low.to_numpy(float))
                if len(sw) < 3:
                    continue
                past = bars.iloc[: i + 1]
                for bot, p in per.items():
                    if t_close < busy[bot]:
                        continue  # this bot's own trade is still open
                    tr = signal(bot, sw, sw4, past, p, t_close)
                    if tr is None:
                        continue
                    before = m1[(m1.index >= t_close - pd.Timedelta(minutes=60)) & (m1.index < t_close)]
                    runup = (tr.entry - before.low.min()) if tr.side == "SELL" else (before.high.max() - tr.entry)
                    if p.run and runup > p.run * abs(tr.stop - tr.entry):
                        continue
                    tr = settle(m1, tr, day_end, p)
                    trades.append(tr)
                    busy[bot] = tr.extra["closed"]
    return sorted(trades, key=lambda x: x.at)


def stepping(sws: list) -> str:
    """'DOWN' (lower high and lower low), 'UP', or 'FLAT' - from the last two confirmed swings of each kind."""
    highs = [s for s in sws if s.kind == 1]
    lows = [s for s in sws if s.kind == -1]
    if len(highs) < 2 or len(lows) < 2:
        return "FLAT"
    if highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
        return "DOWN"
    if highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price:
        return "UP"
    return "FLAT"


def range_box(sw: list, sw4: list, p: P) -> tuple[float, float] | None:
    """(top, bottom) of the big-picture box, or None when that frame is not sideways."""
    big = sw4 if p.range_tf in ("H4", "both") else sw
    if len(big) < 2:
        return None
    if p.range_flat and stepping(big) != "FLAT":
        return None
    highs = [s.price for s in big if s.kind == 1]
    lows = [s.price for s in big if s.kind == -1]
    if not highs or not lows:
        return None
    top, floor = highs[-1], lows[-1]
    if top <= floor:
        return None
    if p.range_tf == "both":  # the H1 swings have to sit inside the H4 box
        h1h = [s.price for s in sw if s.kind == 1][-1:]
        h1l = [s.price for s in sw if s.kind == -1][-1:]
        if not h1h or not h1l or h1h[0] > top or h1l[0] < floor:
            return None
    return top, floor


def signal(bot: str, sw: list, sw4: list, past: pd.DataFrame, p: P, t: pd.Timestamp) -> Trade | None:
    """The bot's own setup on these bars, or None. Each bot tests its own structure, so a down leg and a range
    can hold at the same moment; the two trend bots cannot, their conditions being opposites."""
    price = float(past.close.iloc[-1])
    highs = [s for s in sw if s.kind == 1]
    lows = [s for s in sw if s.kind == -1]
    if len(highs) < 2 or len(lows) < 2:
        return None
    if bot in ("DOWN", "UP"):
        down = bot == "DOWN"
        stepping = (
            (highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price)
            if down
            else (highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price)
        )
        if not stepping:
            return None
        a, b = sw[-2], sw[-1]  # the last confirmed leg
        if (a.kind, b.kind) != ((1, -1) if down else (-1, 1)):
            return None
        leg = abs(a.price - b.price)
        if leg <= 0:
            return None
        for n in range(24, 5, -1):  # the longest box that still fits
            if len(past) < n + 1:
                continue
            box = past.iloc[-n - 1 : -1]
            top, floor = float(box.high.max()), float(box.low.min())
            if top - floor > p.box * leg:
                continue
            mid = (top + floor) / 2
            retr = (mid - b.price) / leg if down else (b.price - mid) / leg
            if not (p.retrace[0] <= retr <= p.retrace[1]):
                return None
            if down and price < floor:
                stop, tp = top + p.buffer * (top - floor), b.price
            elif not down and price > top:
                stop, tp = floor - p.buffer * (top - floor), b.price
            else:
                return None
            risk, reward = abs(stop - price), abs(price - tp)
            if reward < p.min_tp or reward < p.min_r * risk or (tp >= price if down else tp <= price):
                return None
            side = "SELL" if down else "BUY"
            return Trade(bot, side, t, price, stop, tp, extra={"retrace": round(retr, 2), "box": n})
        return None
    box = range_box(sw, sw4, p)
    if box is None:
        return None
    hh, ll = box
    bar = past.iloc[-1]
    rng = hh - ll
    if p.range_mode == "break":  # price leaves the box: the close through decides, no 'inside' gate
        prev = float(past.close.iloc[-2]) if len(past) > 1 else price
        if price > hh >= prev:
            stop, tp, side = hh - p.buffer * rng * 0.25, price + p.tp_range * rng, "BUY"
        elif price < ll <= prev:
            stop, tp, side = ll + p.buffer * rng * 0.25, price - p.tp_range * rng, "SELL"
        else:
            return None
        risk, reward = abs(stop - price), abs(tp - price)
        if risk <= 0 or reward < p.min_tp or reward < p.min_r * risk:
            return None
        return Trade("RANGE", side, t, price, stop, tp, extra={"range": round(rng, 1)})
    if not ll < price < hh:  # a fade is taken from inside the box only
        return None
    if bar.high > hh and bar.close < hh:
        stop = float(bar.high) + p.buffer * float(bar.high - bar.low)
        tp = price - p.tp_range * (price - ll)
        side = "SELL"
    elif bar.low < ll and bar.close > ll:
        stop = float(bar.low) - p.buffer * float(bar.high - bar.low)
        tp = price + p.tp_range * (hh - price)
        side = "BUY"
    else:
        return None
    if p.range_mode == "opposite":  # the same moment, the other side: stop and take-profit mirrored
        side = "BUY" if side == "SELL" else "SELL"
        stop, tp = 2 * price - stop, 2 * price - tp
    risk, reward = abs(stop - price), abs(tp - price)
    if reward < p.min_tp or reward < p.min_r * risk:
        return None
    return Trade("RANGE", side, t, price, stop, tp, extra={"range": round(rng, 1)})


def report(trades: list[Trade], title: str) -> None:
    df = pd.DataFrame([{"bot": t.bot, "side": t.side, "at": t.at, "r": t.r, "out": t.out} for t in trades])
    print(f"\n== {title}: {len(df)} trades ==")
    if not len(df):
        return
    print("| bot | trades | win % | R / trade (after spread) | total R | weeks + / - | worst streak |")
    print("|---|---|---|---|---|---|---|")
    for bot, g in [*df.groupby("bot"), ("ALL", df)]:
        wk = g.groupby(g["at"].dt.tz_convert(TH).dt.to_period("W")).r.sum()
        streak = cur = 0
        for r in g.r:
            cur = cur + 1 if r < 0 else 0
            streak = max(streak, cur)
        print(f"| {bot} | {len(g)} | {(g.r > 0).mean():.0%} | {g.r.mean():+.3f} | {g.r.sum():+.1f} | "
              f"{(wk > 0).sum()} / {(wk <= 0).sum()} | {streak} |")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    hs = ParquetHistoryStore(ROOT / "data/history")
    f = {t: to_frame(hs.load("FBS-Demo", "XAUUSD", t, None, None)) for t in (Timeframe.M1, Timeframe.H1)}
    report(run(f, P()), "three bots side by side, defaults, 2025-10-20 .. 2026-10-23")


if __name__ == "__main__":
    main()
