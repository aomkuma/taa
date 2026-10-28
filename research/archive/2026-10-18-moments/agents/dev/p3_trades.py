"""Task P3: changes to B2, one at a time (DEV_LOG.md "Task P3 - written before computing"): L (refuse a late entry),
Xa (out on the pattern's own invalidation), Xb (break-even at +1 risk, then trail the entry TF's confirmed swings), Xab
(both), ST (the sweep then the turn only with the M5 agreeing), LEAD (written after the leads' paths). The base B2 is
P2's exactly (checked: the same trades).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p3_trades.py [SETTING ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p2_trades as P2  # noqa: E402
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, ExamPeriodError  # noqa: E402

NS_MIN = 60 * 10**9
TRAIL_ATR = 0.2  # the trailing stop sits 0.2 x the pattern's ATR past the confirmed swing
MAX_LAG_NS = 60 * 10**9  # no tick within 60 s of the entry decision: no trade (the tick files have no Sunday evening)
ORDER = {"stop": 0, "trail": 0, "target": 1, "structure": 2, "invalid": 2, "time": 3, "break": 4}
SETTINGS = {
    "B2": dict(exit="structure"),
    "L": dict(exit="structure", late=True),
    "Xa": dict(exit="invalid"),
    "Xb": dict(exit="trail"),
    "Xab": dict(exit="invalid+trail"),
    "ST": dict(exit="structure", st_m5=True),
    "LEAD": dict(exit="structure", lead=True),  # written after the leads' paths (DEV_LOG.md), before it was run
}


def invalidation(family: str, side: int, pts_p, box_p) -> float:
    """The pattern's own invalidation: its last point on the extreme's side (the right shoulder, the second low / high,
    the higher low / lower high) - the base's far edge (the box's low for a break up, its high for a break down)."""
    if family == "base":
        return float(box_p[0] if side > 0 else box_p[1])
    return float(pts_p[-1])


def close_exit_time(t_open: np.ndarray, avail: np.ndarray, c: np.ndarray, price: float, side: int, t_entry: int,
                    t_limit: int) -> int | None:
    """The close of the first entry-TF bar opening at / after t_entry and closing by t_limit whose close is past price
    (a buy: below it; a sell: above it); None if none."""
    b0 = int(np.searchsorted(t_open, t_entry, side="left"))
    b1 = int(np.searchsorted(avail, t_limit, side="right"))
    if b1 <= b0:
        return None
    hit = np.nonzero(side * (c[b0:b1] - price) < 0)[0]
    return int(avail[b0 + hit[0]]) if len(hit) else None


def trail_schedule(t_open: np.ndarray, avail: np.ndarray, lt: np.ndarray, lp: np.ndarray, side: int, t_entry: int,
                   t_limit: int, buffer: float) -> tuple[np.ndarray, np.ndarray]:
    """At each entry-TF bar close (bars opening at / after t_entry, closing by t_limit): the trailing candidate - a buy
    the last confirmed trough - buffer, a sell the last confirmed peak + buffer (NaN where there is none yet)."""
    b0 = int(np.searchsorted(t_open, t_entry, side="left"))
    b1 = int(np.searchsorted(avail, t_limit, side="right"))
    v = lt[b0:b1] - buffer if side > 0 else lp[b0:b1] + buffer
    return np.asarray(avail[b0:b1], np.int64), np.asarray(v, float)


def simulate3(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t_entry: int, side: int, stop: float, target: float,
              t_close: int | None, t_limit: int, extra: float = 0.0, trail: tuple | None = None,
              close_name: str = "structure") -> dict | None:
    """P2's simulate with a stop that can move: with trail = (times, values), once a tick is one risk our way the stop
    goes to the fill (break-even), then from each bar close after that tick to the best of the break-even and the
    candidates so far (a buy: the highest; never back); a moved stop's exit is 'trail'. t_close: a close-based exit
    (named close_name) at the first tick at / after it."""
    f = int(np.searchsorted(t, t_entry, side="left"))
    if f >= len(t) or t[f] - t_entry > MAX_LAG_NS:
        return None
    entry = ask[f] + P2.SLIP + extra if side > 0 else bid[f] - P2.SLIP - extra
    risk = side * (entry - stop)
    if not risk > 0:
        return None
    end = min(int(np.searchsorted(t, t_limit, side="left")), len(t) - 1)
    ev = []
    gaps = np.nonzero(np.diff(t[f:end + 1]) > P2.GAP_NS)[0]
    if len(gaps):
        ev.append((f + int(gaps[0]), "break"))
        end = f + int(gaps[0])
    elif t[end] >= t_limit:
        ev.append((end, "time"))
    else:
        ev.append((end, "break"))
    seg = slice(f + 1, end + 1)
    mkt = bid if side > 0 else ask
    ms, ts = mkt[seg], t[seg]
    lv = np.full(len(ms), side * stop)  # the stop level at each tick, in the trade's direction (higher = tighter)
    t_be = None
    if trail is not None and len(ms):
        up = np.nonzero(side * (ms - entry) >= risk)[0]
        if len(up):
            i1 = int(up[0])
            t_be = int(ts[i1])
            tt, vv = trail
            sel = tt > t_be
            steps_t = tt[sel]
            steps = np.maximum.accumulate(np.where(np.isnan(vv[sel]), -np.inf, side * vv[sel])) if sel.any() else np.empty(0)
            k = np.searchsorted(steps_t, ts[i1:], side="right") - 1
            best = np.where(k >= 0, steps[np.maximum(k, 0)] if len(steps) else -np.inf, -np.inf)
            lv[i1:] = np.maximum(side * entry, best)
    s = np.nonzero(side * ms <= lv)[0]
    stop_exit = np.nan
    if len(s):
        moved = lv[s[0]] != side * stop
        ev.append((f + 1 + int(s[0]), "trail" if moved else "stop"))
        stop_exit = float(side * lv[s[0]])
    if np.isfinite(target):
        g = np.nonzero(side * (ms - target) >= 0)[0]
        if len(g):
            ev.append((f + 1 + int(g[0]), "target"))
    if t_close is not None:
        k = int(np.searchsorted(t, t_close, side="left"))
        if f < k <= end:
            ev.append((k, close_name))
    i, why = min(ev, key=lambda e: (e[0], ORDER[e[1]]))
    if t_be is not None and t_be > int(t[i]):
        t_be = None  # one risk our way only after the exit: not part of this trade (the look-ahead check found it)
    px = target if why == "target" else float(mkt[i])
    pnl = side * (px - entry)
    return dict(side=side, entry=float(entry), entry_t=int(t[f]), stop=float(stop), risk=float(risk), exit=why,
                exit_px=float(px), exit_t=int(t[i]), pnl=float(pnl), R=float(pnl / risk), t_be=t_be,
                stop_exit=stop_exit if why in ("stop", "trail") else np.nan)


def m5_turned(piv5: tuple[np.ndarray, ...], b: int, side: int) -> bool:
    """At M5 bar b: a buy - the last confirmed trough above the one before it (a higher low); a sell - the last
    confirmed peak below the one before it."""
    pb, pp, pk, pc = piv5
    n = int(np.searchsorted(pc, b, side="right"))
    x = pp[:n][pk[:n] == (-1 if side > 0 else 1)][-2:]
    return bool(len(x) == 2 and side * (x[1] - x[0]) > 0)


def candidates3(C: pd.DataFrame, tfs: dict, setting: dict) -> pd.DataFrame:
    """B2's candidates (the confirmation, the pattern's stop) with the pattern's fields for the changes; L refuses a
    confirming close that covered the measured move; ST keeps a turn only with the M5 agreeing."""
    m5 = tfs["M5"]
    rows = []
    for r in C.itertuples(index=False):
        tf = tfs[r.tf]
        d = int(np.searchsorted(tf.avail, int(r.t_dec)))
        conf = P2.confirm_b(tf.h, tf.lo, tf.c, d, float(r.extreme), float(r.atr), int(r.side))
        if conf is None:
            continue
        k = conf["k"]
        t_entry, close = int(tf.avail[k]), float(tf.c[k])
        if setting.get("late") and r.side * (close - r.trigger) >= r.height:
            continue
        if setting.get("lead") and not (r.family == "ihs" or r.tf == "M5"):
            continue
        if setting.get("st_m5") and r.family == "st":
            agree5 = m5_turned(m5.piv, m5.last_complete(t_entry), int(r.side)) or (r.tf == "M1" and bool(r.other_pattern))
            if not agree5:
                continue
        rows.append(dict(t_entry=t_entry, side=int(r.side), stop=float(r.stop), risk_dec=abs(close - float(r.stop)),
                         tf=r.tf, family=r.family, name=r.name, level_kind=r.level_kind, level=float(r.level),
                         height=float(r.height), trigger=float(r.trigger), close_k=close, atr=float(r.atr),
                         next_level=float(r.next_level), t_dec=int(r.t_dec),
                         invalid=invalidation(r.family, int(r.side), r.pts_p, r.box_p),
                         agree=P2.agreement_group(r.other_pattern, r.other_structure, int(r.side)),
                         at_news=bool(r.at_news), conf_t=t_entry, pull=conf["pull"]))
    if not rows:
        return pd.DataFrame(columns=["t_entry", "side", "stop", "risk_dec", "tf"])
    return pd.DataFrame(rows).sort_values(["t_entry", "risk_dec"], kind="stable").reset_index(drop=True)


def one_trade3(r, tf, lt: np.ndarray, lp: np.ndarray, t: np.ndarray, bid: np.ndarray, ask: np.ndarray, extra: float,
               exit_mode: str) -> dict | None:
    """One candidate on its entry TF with the setting's exit: 'structure' (B2), 'invalid', 'trail', 'invalid+trail'."""
    t_limit = int(r.t_entry + P2.HOLD * tf.minutes * NS_MIN)
    if exit_mode == "structure":
        t_close, name = P2.structure_exit_time(tf.t_open, tf.avail, tf.c, lt, lp, r.side, r.t_entry, t_limit), "structure"
    elif "invalid" in exit_mode:
        t_close, name = close_exit_time(tf.t_open, tf.avail, tf.c, r.invalid, r.side, r.t_entry, t_limit), "invalid"
    else:
        t_close, name = None, "structure"
    trail = (trail_schedule(tf.t_open, tf.avail, lt, lp, r.side, r.t_entry, t_limit, TRAIL_ATR * r.atr)
             if "trail" in exit_mode else None)
    x = simulate3(t, bid, ask, r.t_entry, r.side, r.stop, np.nan, t_close, t_limit, extra, trail, name)
    if x is None:
        return None
    tgt = r.next_level if np.isfinite(r.next_level) and r.side * (r.next_level - x["entry"]) > x["risk"] else np.nan
    if np.isfinite(tgt):
        x = simulate3(t, bid, ask, r.t_entry, r.side, r.stop, tgt, t_close, t_limit, extra, trail, name)
    x.update(target=tgt, t_limit=t_limit, t_struct=t_close,
             trail_t=None if trail is None else trail[0].tolist(), trail_v=None if trail is None else trail[1].tolist())
    return x


def run_stream3(cands: pd.DataFrame, tfs: dict, ticks, news: np.ndarray, news_cost: float, exit_mode: str) -> pd.DataFrame:
    """One position at a time, as P2's run_stream, with the setting's exit."""
    pivs = {k: P2.last_pivot_prices(tf.piv, len(tf.c)) for k, tf in tfs.items()}
    rows, busy = [], -1
    for r in cands.itertuples(index=False):
        if r.t_entry < busy:
            continue
        t, bid, ask = ticks.span(r.t_entry)
        news_trade = P2.is_news(r.t_entry, news)
        x = one_trade3(r, tfs[r.tf], *pivs[r.tf], t, bid, ask, news_cost if news_trade else 0.0, exit_mode)
        if x is None:
            continue
        rows.append({**r._asdict(), **x, "news": news_trade})
        busy = x["exit_t"]
    out = pd.DataFrame(rows)
    for k in ("t_be", "t_struct"):  # ns times with gaps: integers with a missing value, never floats (rounding)
        if k in out:
            out[k] = pd.array([None if v is None or (isinstance(v, float) and np.isnan(v)) else int(v) for v in rows_of(rows, k)],
                              dtype="Int64")
    return out


def rows_of(rows: list[dict], k: str) -> list:
    return [r[k] for r in rows]


def run(settings: list[str]) -> pd.DataFrame:
    from m15_trades import part_of  # noqa: PLC0415

    C = pd.read_parquet(HERE / "p_catches.parquet")
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    m = P.load_m1()
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    ticks, news = P2.Ticks(), P2.news_times()
    out = []
    for name in settings:
        s = SETTINGS[name]
        cands = candidates3(C, tfs, s)
        for cost in P2.NEWS_COSTS:
            T = run_stream3(cands, tfs, ticks, news, cost, s["exit"])
            T["variant"], T["news_cost"] = name, cost
            T["part"] = part_of(pd.to_datetime(T.entry_t, utc=True))
            if (T.exit_t >= EXAM_START.value).any():
                raise ExamPeriodError("a trade reached the exam")
            out.append(T)
        print(f"{name}: {len(cands)} candidates", flush=True)
    A = pd.concat(out, ignore_index=True)
    A["big"] = (A.height > P2.BIG) | (A.risk > P2.BIG)
    M = A[A.news_cost == 0.0]
    why = []
    for r in M.itertuples(index=False):
        if r.pnl < 0:
            t, bid, ask = ticks.span(r.t_entry)
            why.append(f"{P2.reason(t, bid, ask, r._asdict())} x other TF {r.agree}")
        else:
            why.append("")
    A.loc[M.index, "reason"] = why
    return A


def metrics_table(A: pd.DataFrame, cost: float = 0.0) -> pd.DataFrame:
    rows = []
    for (v, p), G in A[A.news_cost == cost].groupby(["variant", "part"], sort=False):
        s = P2.stats(G, p)
        for e in ORDER:
            s[f"x_{e}"] = int((G.exit == e).sum())
        rows.append(dict(variant=v, part=p, **s))
    return pd.DataFrame(rows)


def main() -> None:
    names = sys.argv[1:] or list(SETTINGS)
    A = run(names)
    tag = "_".join(names) if sys.argv[1:] else "all"
    A.to_parquet(HERE / f"p3_trades_{tag}.parquet")
    M = pd.concat([metrics_table(A, c).assign(news_cost=c) for c in P2.NEWS_COSTS])
    M.to_csv(HERE / f"p3_metrics_{tag}.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    cols = ["variant", "part", "n", "per_day", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd",
            "x_stop", "x_trail", "x_target", "x_structure", "x_invalid", "x_time", "x_break"]
    print(M[M.news_cost == 0.0][cols].round(3).to_string(index=False))
    for c in P2.NEWS_COSTS[1:]:
        t = M[M.news_cost == c]
        print(f"  news +{c:.1f}: " + "; ".join(f"{r.variant} {r.part} R {r.R:+.3f}" for r in t.itertuples()))
    t = M[M.news_cost == 0.0]
    print("the smaller part's R: " + "; ".join(f"{v} {g.R.min():+.3f}" for v, g in t.groupby("variant", sort=False)))


if __name__ == "__main__":
    main()
