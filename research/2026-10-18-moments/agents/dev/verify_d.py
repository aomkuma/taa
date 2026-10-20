"""The second, separate computation of Task D (the owner's "right reading, wrong metric" rule). It imports none of
d1_orb / d2_straddle / d_report / p2_trades / p3_trades / patterns / sweep_detector: it reads the raw M1 file and the raw
tick files itself, builds its own H1 / D1 bars (precursors' foundation.atr; the owner's levels from precursors' zones
with its own inputs), makes its own decisions and runs its own tick / bar loops (plain Python). It

1. recomputes every metric cell of d_metrics.csv from the trade files with its own loops;
2. D1: re-derives every core day (the status, the side, the stop, the decision; H, ADR20 and the level ahead) and every
   core trade (P1 / P2 from the raw ticks, O1 / O2 and P1 / P2 from the M1 bars), and 20 trades of every other grid
   cell from the raw ticks;
3. D2: its own event list (weekdays 08:30 / 10:00 New York) and its own straddle on the raw ticks for every trade of the
   two core cells at the four costs, and 20 trades of every other grid cell at +0.5 USD; and the minutes with a trade.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/verify_d.py
"""

from __future__ import annotations

import bisect
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "precursors"))
ROOT = HERE.parents[3]
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
NS_MIN = 60 * 10**9
NS_S = 10**9
SLIP = 0.07
PARTS = {"O1": ("2023-10-18", "2024-10-18"), "O2": ("2024-10-18", "2025-10-18"), "P1": ("2025-10-18", "2026-01-16"),
         "P2": ("2026-01-16", "2026-04-18")}


def part_of(t_ns: int) -> str:
    for k, (a, b) in PARTS.items():
        if pd.Timestamp(a, tz="UTC").value <= t_ns < pd.Timestamp(b, tz="UTC").value:
            return k
    return ""


# --- the metrics -------------------------------------------------------------------------------------------------------


def metrics(rows: list[dict], part: str) -> dict:
    rows = sorted(rows, key=lambda r: r["entry_t"])
    n = len(rows)
    rs = [r["pnl"] / r["risk"] for r in rows]
    mean = sum(rs) / n
    var = sum((x - mean) ** 2 for x in rs) / (n - 1) if n > 1 else float("nan")
    half = 1.96 * math.sqrt(var / n) if n > 1 else float("nan")
    cum = peak = dd = 0.0
    for r in rows:
        cum += r["pnl"]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    best, best_usd, k, usd = 0, 0.0, 0, 0.0
    for r in rows:
        if r["pnl"] < 0:
            k, usd = k + 1, usd + r["pnl"]
            if k > best or (k == best and usd < best_usd):
                best, best_usd = k, usd
        else:
            k, usd = 0, 0.0
    return dict(n=n, win=sum(r["pnl"] > 0 for r in rows) / n, R=mean, R_lo=mean - half, R_hi=mean + half,
                usd=sum(r["pnl"] for r in rows), dd=dd, worst=min(r["pnl"] for r in rows), streak=best, streak_usd=best_usd)


def is_true(v) -> bool:
    return isinstance(v, (bool, np.bool_)) and bool(v)


def select(A: pd.DataFrame, B: pd.DataFrame, label: str) -> list[dict]:
    """The trades of one metric cell, picked by its label with plain comparisons."""
    f = label.split("|")
    if f[0] == "D1":
        name, src = f[1], f[2]
        rows = [r for r in A.to_dict("records") if r["src"] == src and r["L"] == 15 and r["k"] == 2.0 and r["X"] == 60
                and is_true(r.get("traded"))]
        lv = lambda r: r["level_ahead"] is None or (isinstance(r["level_ahead"], float) and math.isnan(r["level_ahead"]))  # noqa: E731
        if name.startswith("D1L"):
            rows = [r for r in rows if lv(r)]
        if "+ S" in name:
            rows = [r for r in rows if r["adr20"] >= 63.3]
        return rows
    if f[0] == "D1grid":
        L, k, X, src = int(f[1]), float(f[2]), int(f[3]), f[4]
        return [r for r in A.to_dict("records") if r["src"] == src and r["L"] == L and r["k"] == k and r["X"] == X
                and is_true(r.get("traded"))]
    tr, st, hold, extra = float(f[1]), float(f[2]), int(f[3]), float(f[4])
    return [r for r in B.to_dict("records") if r["trig"] == tr and r["stop_u"] == st and r["hold"] == hold and r["extra"] == extra]


def check_metrics(A: pd.DataFrame, B: pd.DataFrame, M: pd.DataFrame) -> tuple[int, int]:
    agree = total = 0
    for m in M.to_dict("records"):
        rows = [r for r in select(A, B, m["label"]) if part_of(int(r["entry_t"])) == m["part"]]
        mine = metrics(rows, m["part"]) if rows else dict(n=0)
        for k in ("n", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd"):
            total += 1
            a, b = mine.get(k, float("nan")), m[k]
            ok = (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1.0, abs(a))
            agree += ok
            if not ok:
                print(f"  DIFFERENT {m['label']} {m['part']} {k}: {a} vs {b}")
    return agree, total


# --- its own data --------------------------------------------------------------------------------------------------------


class Data:
    def __init__(self) -> None:
        import foundation as F  # noqa: PLC0415
        import pyarrow.parquet as pq  # noqa: PLC0415

        x = pq.read_table(ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet", columns=["open_time", "open", "high", "low", "close", "spread"],
                          filters=[("open_time", ">=", pd.Timestamp("2023-09-01", tz="UTC")), ("open_time", "<", EXAM)]).to_pandas()
        x = x.drop_duplicates("open_time", keep="last").sort_values("open_time").reset_index(drop=True)
        assert x.open_time.max() < EXAM
        self.t = pd.DatetimeIndex(x.open_time).as_unit("ns").asi8
        self.o, self.h, self.lo, self.c = (x[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.spr = x.spread.to_numpy(float) / 100.0
        hour = (self.t // (60 * NS_MIN)) * (60 * NS_MIN)
        g = pd.DataFrame(dict(k=hour, h=self.h, lo=self.lo, c=self.c)).groupby("k", sort=True)
        hh, hl, hc = g.h.max().to_numpy(), g.lo.min().to_numpy(), g.c.last().to_numpy()
        self.h1_av = g.h.max().index.to_numpy(np.int64) + 60 * NS_MIN
        self.h1_atr = F.atr(hh, hl, hc, 14)
        ath = pd.DatetimeIndex(self.t).tz_localize("UTC").tz_convert("Europe/Athens").date
        d = pd.DataFrame(dict(k=ath, h=self.h, lo=self.lo, t=self.t)).groupby("k", sort=True)
        rng = (d.h.max() - d.lo.min()).to_numpy()
        self.d_av = d.t.max().to_numpy(np.int64) + NS_MIN
        self.adr = np.array([rng[i - 19:i + 1].mean() if i >= 19 else np.nan for i in range(len(rng))])
        self.Y = None

    def last(self, avail: np.ndarray, values: np.ndarray, t: int) -> float:
        k = int(np.searchsorted(avail, t, side="right")) - 1
        return float(values[k]) if k >= 0 else float("nan")

    def levels(self, t: int, price: float) -> list[float]:
        import foundation as F  # noqa: PLC0415
        import indicators  # noqa: PLC0415
        from zones import levels_at, swings  # noqa: PLC0415

        if self.Y is None:
            m = pd.DataFrame(dict(open=self.o, high=self.h, low=self.lo, close=self.c),
                             index=pd.DatetimeIndex(self.t).tz_localize("UTC"))
            b1, d1 = indicators.bars(m, "1h"), indicators.bars(m, "1D")
            self.Y = dict(S=swings(b1), avail=pd.DatetimeIndex(b1["avail"]).as_unit("ns").asi8,
                          atr=F.atr(b1.high.to_numpy(), b1.low.to_numpy(), b1.close.to_numpy(), 14), h=b1.high.to_numpy(float),
                          lo=b1.low.to_numpy(float), d_avail=pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8,
                          d_high=d1.high.to_numpy(float), d_low=d1.low.to_numpy(float))
        L, _ = levels_at(self.Y, t, price)
        return [float(v) for v in L.price]


def raw_ticks(day: pd.Timestamp) -> tuple[list, list, list]:
    if day >= EXAM:
        return [], [], []
    f = ROOT / "data/ticks/XAUUSD" / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return [], [], []
    x = pd.read_parquet(f)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o].tolist(), x.bid.to_numpy(float)[o].tolist(), x.ask.to_numpy(float)[o].tolist()


def two_days(day: pd.Timestamp, cache: dict) -> tuple[list, list, list]:
    out: tuple[list, list, list] = ([], [], [])
    for d in (day, day + pd.Timedelta(days=1)):
        if d not in cache:
            cache[d] = raw_ticks(d)
        for a, b in zip(out, cache[d], strict=True):
            a.extend(b)
    return out


# --- D1, its own way -----------------------------------------------------------------------------------------------------


def decision(D: Data, t0: int, L: int) -> dict:
    i0 = int(np.searchsorted(D.t, t0))
    if i0 >= len(D.t) or D.t[i0] > t0 + 5 * NS_MIN:
        return dict(status="late open")
    hi, lo = -math.inf, math.inf
    i = i0
    while i < len(D.t) and D.t[i] < t0 + L * NS_MIN:
        hi, lo = max(hi, D.h[i]), min(lo, D.lo[i])
        i += 1
    H = D.last(D.h1_av, D.h1_atr, t0)
    if math.isnan(H) or hi - lo > 1.5 * H:
        return dict(status="wide")
    while i < len(D.t) and D.t[i] < t0 + (L + 60) * NS_MIN:
        if D.c[i] > hi:
            return dict(status="trade", side=1, stop=lo, i=i, t_dec=int(D.t[i]) + NS_MIN, close=float(D.c[i]))
        if D.c[i] < lo:
            return dict(status="trade", side=-1, stop=hi, i=i, t_dec=int(D.t[i]) + NS_MIN, close=float(D.c[i]))
        i += 1
    return dict(status="no break")


def walk(t: list, bid: list, ask: list, f: int, side: int, entry: float, stop: float, target: float | None,
         t_limit: int) -> tuple[float, str, int] | None:
    """From the tick after f: the stop (gap included), the target (a limit), the time; a gap > 30 min: out at the tick
    before it. Returns (exit price, reason, exit time)."""
    for k in range(f + 1, len(t)):
        if t[k] - t[k - 1] > 30 * NS_MIN:
            return (bid[k - 1] if side > 0 else ask[k - 1]), "break", t[k - 1]
        px = bid[k] if side > 0 else ask[k]
        if side * (px - stop) <= 0:
            return px, "stop", t[k]
        if target is not None and side * (px - target) >= 0:
            return target, "target", t[k]
        if t[k] >= t_limit:
            return px, "time", t[k]
    return (bid[-1] if side > 0 else ask[-1]), "break", t[-1]


def d1_tick(t: list, bid: list, ask: list, t_dec: int, side: int, stop: float, k_r: float, X: int) -> dict | None:
    f = bisect.bisect_left(t, t_dec)  # the first tick at / after the decision
    if f >= len(t) or t[f] - t_dec > 60 * NS_S:
        return None
    entry = ask[f] + SLIP if side > 0 else bid[f] - SLIP
    risk = side * (entry - stop)
    if risk <= 0:
        return None
    px, why, tx = walk(t, bid, ask, f, side, entry, stop, entry + side * k_r * risk, t[f] + X * NS_MIN)
    return dict(entry=entry, entry_t=t[f], exit=why, exit_t=tx, pnl=side * (px - entry), R=side * (px - entry) / risk)


def d1_m1(D: Data, i_dec: int, side: int, stop: float, k_r: float, X: int) -> dict | None:
    i = i_dec + 1
    if i >= len(D.t) or D.t[i] != D.t[i_dec] + NS_MIN:
        return None
    entry = D.o[i] + D.spr[i] + SLIP if side > 0 else D.o[i] - SLIP
    risk = side * (entry - stop)
    if risk <= 0:
        return None
    tgt = entry + side * k_r * risk
    j = i
    while j < len(D.t):
        if j > i and D.t[j] - D.t[j - 1] > 30 * NS_MIN:
            j -= 1
            px, why = (D.c[j] if side > 0 else D.c[j] + D.spr[j]), "break"
            break
        a = 0.0 if side > 0 else D.spr[j]
        if D.t[j] >= D.t[i] + X * NS_MIN:
            px, why = D.o[j] + a, "time"
            break
        if side > 0 and D.lo[j] <= stop:
            px, why = min(D.o[j], stop), "stop"
            break
        if side < 0 and D.h[j] + a >= stop:
            px, why = max(D.o[j] + a, stop), "stop"
            break
        if side > 0 and D.h[j] >= tgt:
            px, why = tgt, "target"
            break
        if side < 0 and D.lo[j] + a <= tgt:
            px, why = tgt, "target"
            break
        j += 1
    else:
        j = len(D.t) - 1
        px, why = (D.c[j] if side > 0 else D.c[j] + D.spr[j]), "break"
    return dict(entry=entry, entry_t=int(D.t[i]), exit=why, exit_t=int(D.t[j]), pnl=side * (px - entry), R=side * (px - entry) / risk)


def same(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a))


def check_d1(D: Data, A: pd.DataFrame, rng: random.Random) -> tuple[int, int]:
    good = n = 0
    cache: dict = {}
    core = A[(A.L == 15) & (A.k == 2.0) & (A.X == 60)]
    for r in core.to_dict("records"):
        n += 1
        t0 = int(pd.Timestamp(r["day"]).value) + 6 * 60 * NS_MIN
        d = decision(D, t0, 15)
        bad = []
        if d["status"] != r["status"]:
            bad.append(f"status {d['status']} vs {r['status']}")
        elif d["status"] == "trade":
            if (d["side"], d["t_dec"]) != (r["side"], r["t_dec"]) or not same(d["stop"], r["stop"]):
                bad.append("the decision")
            adr = D.last(D.d_av, D.adr, d["t_dec"])
            if not same(adr, r["adr20"]):
                bad.append(f"ADR20 {adr} vs {r['adr20']}")
            rd = d["side"] * (d["close"] - d["stop"])
            ahead = [v for v in D.levels(d["t_dec"], d["close"]) if 0 < d["side"] * (v - d["close"]) < 2 * rd]
            mine = min(ahead, key=lambda v: abs(v - d["close"])) if ahead else float("nan")
            theirs = r["level_ahead"]
            if not ((math.isnan(mine) and math.isnan(theirs)) or same(mine, theirs)):
                bad.append(f"the level ahead {mine} vs {theirs}")
            if r["src"] == "ticks":
                day = pd.Timestamp(r["day"])
                x = d1_tick(*two_days(day, cache), d["t_dec"], d["side"], d["stop"], 2.0, 60)
            else:
                x = d1_m1(D, d["i"], d["side"], d["stop"], 2.0, 60)
            traded = is_true(r.get("traded"))
            if (x is None) != (not traded):
                bad.append("traded or not")
            elif x is not None and not (x["exit"] == r["exit"] and x["exit_t"] == r["exit_t"] and x["entry_t"] == r["entry_t"]
                                        and same(x["entry"], r["entry"]) and same(x["pnl"], r["pnl"]) and same(x["R"], r["R"])):
                bad.append(f"the trade {x['exit']} {x['pnl']:.4f} vs {r['exit']} {r['pnl']:.4f}")
        good += not bad
        if bad:
            print(f"  D1 {r['src']} {pd.Timestamp(r['day']):%Y-%m-%d}: {bad}")
        if len(cache) > 4:
            cache.clear()
    print(f"2a. D1 core days re-derived (the status, decision, ADR20, the level ahead, the trade): {good} of {n} agree", flush=True)
    g2 = n2 = 0
    T = A[(A.src == "ticks") & A.traded.fillna(False).astype(bool) & ~((A.L == 15) & (A.k == 2.0) & (A.X == 60))]
    for (L, k_r, X), G in T.groupby(["L", "k", "X"]):
        for r in rng.sample(G.to_dict("records"), min(20, len(G))):
            n2 += 1
            t0 = int(pd.Timestamp(r["day"]).value) + 6 * 60 * NS_MIN
            d = decision(D, t0, int(L))
            x = d1_tick(*two_days(pd.Timestamp(r["day"]), cache), d["t_dec"], d["side"], d["stop"], float(k_r), int(X)) \
                if d["status"] == "trade" else None
            ok = x is not None and x["exit"] == r["exit"] and x["exit_t"] == r["exit_t"] and same(x["pnl"], r["pnl"]) and same(x["R"], r["R"])
            g2 += ok
            if not ok:
                print(f"  D1 grid L {L} k {k_r} X {X} {pd.Timestamp(r['day']):%Y-%m-%d}: {x} vs {r['exit']} {r['pnl']}")
            if len(cache) > 4:
                cache.clear()
    print(f"2b. D1 other grid cells, 20 trades each from the raw ticks: {g2} of {n2} agree", flush=True)
    return good + g2, n + n2


# --- D2, its own way -----------------------------------------------------------------------------------------------------


def events(minutes=((8, 30), (10, 0))) -> list[tuple[int, str]]:
    out = []
    for d in pd.date_range("2025-10-17", "2026-04-18", freq="D"):
        if d.weekday() >= 5:
            continue
        for hh, mm in minutes:
            t = pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hh, minute=mm, tz="America/New_York").tz_convert("UTC")
            if pd.Timestamp("2025-10-18", tz="UTC") <= t < EXAM:
                out.append((t.value, f"{hh:02d}:{mm:02d}"))
    return out


def straddle(t: list, bid: list, ask: list, t0: int, trig: float, stop_u: float, hold: int, extra: float) -> dict | None:
    k = bisect.bisect_left(t, t0) - 1  # the last tick before t0
    if k < 0 or t0 - t[k] > 30 * NS_S:
        return None
    u = bid[k] / 4000.0
    up, dn = ask[k] + trig * u, bid[k] - trig * u
    for j in range(k + 1, len(t)):
        if t[j] >= t0 + 60 * NS_S:
            return None
        if ask[j] >= up or bid[j] <= dn:
            side = 1 if ask[j] >= up else -1
            entry = ask[j] + SLIP + extra if side > 0 else bid[j] - SLIP - extra
            stop = entry - side * stop_u * u
            px, why, tx = walk(t, bid, ask, j, side, entry, stop, None, t0 + hold * NS_MIN)
            return dict(side=side, entry=entry, entry_t=t[j], exit=why, exit_t=tx, pnl=side * (px - entry),
                        R=side * (px - entry) / (stop_u * u))
    return None


def check_d2(B: pd.DataFrame, rng: random.Random) -> tuple[int, int]:
    ev = events()
    cache: dict = {}
    good = n = 0
    minutes_ok = True
    by = {(r["t0"], r["trig"], r["stop_u"], r["hold"], r["extra"]): r for r in B.to_dict("records")}
    other = [key for key in by if key[4] == 0.5 and (key[1], key[2]) != (2.0, 8.0)]
    pick = set(rng.sample(sorted(other), min(20 * 16, len(other))))
    for t0, _ny in ev:
        day = pd.Timestamp(t0, tz="UTC").normalize()
        span = two_days(day, cache)
        for trig, st, hold, extra in [(2.0, 8.0, h, e) for h in (15, 30) for e in (0.0, 0.5, 1.0, 2.0)]:
            x = straddle(*span, t0, trig, st, hold, extra)
            r = by.get((t0, trig, st, hold, extra))
            if (x is None) != (r is None):
                minutes_ok = False
                print(f"  D2 {pd.Timestamp(t0, tz='UTC')} {hold} +{extra}: a trade in one computation only")
                continue
            if x is None:
                continue
            n += 1
            ok = (x["side"] == r["side"] and x["entry_t"] == r["entry_t"] and x["exit"] == r["exit"] and x["exit_t"] == r["exit_t"]
                  and same(x["entry"], r["entry"]) and same(x["pnl"], r["pnl"]) and same(x["R"], r["R"]))
            good += ok
            if not ok:
                print(f"  D2 {pd.Timestamp(t0, tz='UTC')} {hold} +{extra}: {x} vs {r['exit']} {r['pnl']}")
        for key in [k for k in pick if k[0] == t0]:
            x = straddle(*span, t0, key[1], key[2], key[3], key[4])
            r = by[key]
            n += 1
            ok = x is not None and x["exit_t"] == r["exit_t"] and same(x["pnl"], r["pnl"]) and same(x["R"], r["R"])
            good += ok
            if not ok:
                print(f"  D2 grid {key}: {x} vs {r['exit']} {r['pnl']}")
        if len(cache) > 4:
            cache.clear()
    print(f"3. D2 trades re-derived from the raw ticks (every core trade at the four costs + {len(pick)} of the other "
          f"cells): {good} of {n} agree; the minutes with a trade agree: {minutes_ok}", flush=True)
    return good + (0 if minutes_ok else -1), n


def own_mid(t: list, bid: list, ask: list, at: int) -> float:
    k = bisect.bisect_right(t, at) - 1
    return (bid[k] + ask[k]) / 2 if k >= 0 else float("nan")


def own_gap(t: list, a: int, b: int) -> bool:
    i, j = bisect.bisect_right(t, a) - 1, bisect.bisect_left(t, b)
    if i < 0 or j >= len(t):
        return True
    return any(t[x + 1] - t[x] > 30 * NS_MIN for x in range(i, j))


def check_buckets(H: pd.DataFrame, M: pd.DataFrame) -> tuple[int, int]:
    """D2 by the clock: every held trade (+30 .. +240) and every bucket move, its own way."""
    held = {(r["t0"], r["hold"]): r for r in H.to_dict("records")}
    mv = {(r["t0"], r["bucket"]): r for r in M.to_dict("records")}
    cache: dict = {}
    good = n = 0
    for t0, ny in events(((8, 30), (9, 30), (10, 0))):
        span = two_days(pd.Timestamp(t0, tz="UTC").normalize(), cache)
        x0 = straddle(*span, t0, 2.0, 8.0, 30, 0.5)
        if (x0 is None) != ((t0, 30) not in held):
            n += 1
            print(f"  buckets {pd.Timestamp(t0, tz='UTC')}: a trade in one computation only")
            continue
        if x0 is None:
            continue
        for hold in range(30, 241, 30):
            x, r = straddle(*span, t0, 2.0, 8.0, hold, 0.5), held[(t0, hold)]
            n += 1
            ok = r["ny"] == ny and x["exit"] == r["exit"] and x["exit_t"] == r["exit_t"] and same(x["R"], r["R"])
            good += ok
            if not ok:
                print(f"  held {pd.Timestamp(t0, tz='UTC')} {hold}: {x['exit']} {x['R']} vs {r['exit']} {r['R']}")
        t, bid, ask = span
        risk = 8.0 * bid[bisect.bisect_left(t, t0) - 1] / 4000.0
        for b in range(1, 9):
            a_t = x0["entry_t"] if b == 1 else t0 + (b - 1) * 30 * NS_MIN
            e_t = t0 + b * 30 * NS_MIN
            r = mv[(t0, b)]
            n += 1
            if own_gap(t, a_t, e_t):
                ok = math.isnan(r["R_move"])
            else:
                d = own_mid(t, bid, ask, e_t) - own_mid(t, bid, ask, a_t)
                ok = same(x0["side"] * d / risk, r["R_move"]) and same(abs(d), r["usd_size"])
            good += ok
            if not ok:
                print(f"  bucket {pd.Timestamp(t0, tz='UTC')} b{b}: vs {r['R_move']}")
        if len(cache) > 4:
            cache.clear()
    print(f"4. D2 by the clock re-derived from the raw ticks (every held trade +30 .. +240 and every bucket move): {good} of {n} agree", flush=True)
    return good, n


def main() -> None:
    A = pd.read_parquet(HERE / "d1_trades.parquet")
    B = pd.read_parquet(HERE / "d2_trades.parquet")
    M = pd.read_csv(HERE / "d_metrics.csv")
    a, t = check_metrics(A, B, M)
    print(f"1. the metrics recomputed: {a} of {t} values agree ({len(M)} cells)", flush=True)
    rng = random.Random(20261019)
    g2, n2 = check_d2(B, rng)
    g4, n4 = check_buckets(pd.read_parquet(HERE / "d2_held.parquet"), pd.read_parquet(HERE / "d2_buckets.parquet"))
    D = Data()
    g1, n1 = check_d1(D, A, rng)
    if a != t or g1 != n1 or g2 != n2 or g4 != n4:
        raise SystemExit("VERIFICATION FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
