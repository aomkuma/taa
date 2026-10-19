"""Task P2: the pattern catches (p_catches.parquet) as trades on the real ticks, P1 / P2 only - entry A at the breakout,
entry B after the structure confirms (stop B1 past the pullback low, B2 the pattern's stop). The rules are in DEV_LOG.md
"Task P2 - written before computing"; in short: one position at a time per variant, the stop / the next level (when
more than one risk away) / the entry TF's structure turning / 60 entry-TF bars / the daily break, the bid / ask plus
0.07 entry slippage and 0 / 0.5 / 1 / 2 USD more for news entries.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/p2_trades.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, LEARN_START, ExamPeriodError  # noqa: E402

NS_S = 10**9
NS_MIN = 60 * NS_S
SLIP = 0.07  # entry slippage, USD
NEWS_COSTS = (0.0, 0.5, 1.0, 2.0)  # more at entry for a news trade
NEWS_MIN = 15  # a news trade: the entry within 15 minutes after a release minute / a news leg
PB_ATR = 1.0  # B: the pullback at least 1 x ATR below the post-breakout high
MAX_WAIT = 30  # B: the confirmation within 30 entry-TF bars after the breakout bar
STOP_ATR = 0.2  # B1: the stop 0.2 x ATR past the pullback low
HOLD = 60  # the time limit: 60 entry-TF bars after the entry
GAP_NS = 30 * NS_MIN  # the daily break / weekend: a gap in the ticks of more than 30 minutes
BIG = 20.0  # big: the pattern's height or the risk above 20 USD
ORDER = {"stop": 0, "target": 1, "structure": 2, "time": 3, "break": 4}
PARTS = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}


def confirm_b(h: np.ndarray, lo: np.ndarray, c: np.ndarray, d: int, extreme: float, atr: float, side: int,
              max_wait: int = MAX_WAIT, pb_atr: float = PB_ATR) -> dict | None:
    """Entry B on the entry TF's bars after the breakout bar d (a buy; a sell by the mirror): the post-breakout high
    (from bar d on, extended by any bar making a new high - such a bar is not also the pullback); the pullback = a bar
    whose low is >= pb_atr x atr below it (then the high is frozen, the pullback low = the lowest low since); the
    confirmation = the first close above the frozen high. None if a low reaches the pattern's extreme first, or no
    confirmation within max_wait bars after d. Returns dict(k = the confirming bar, hi, pull) in prices."""
    if side < 0:
        x = confirm_b(-lo, -h, -c, d, -extreme, atr, 1, max_wait, pb_atr)
        return None if x is None else dict(k=x["k"], hi=-x["hi"], pull=-x["pull"])
    hi, pulled, pull = h[d], False, np.inf
    for k in range(d + 1, min(d + max_wait, len(c) - 1) + 1):
        if lo[k] <= extreme:
            return None
        if not pulled:
            if h[k] > hi:
                hi = h[k]
            elif hi - lo[k] >= pb_atr * atr:
                pulled, pull = True, lo[k]
            continue
        pull = min(pull, lo[k])
        if c[k] > hi:
            return dict(k=k, hi=float(hi), pull=float(pull))
    return None


def last_pivot_prices(piv: tuple[np.ndarray, ...], n: int) -> tuple[np.ndarray, np.ndarray]:
    """For each bar b: the price of the last trough and of the last peak of the ZigZag confirmed by b (NaN before)."""
    pb, pp, pk, pc = piv
    lt, lp = np.full(n, np.nan), np.full(n, np.nan)
    lt[pc[pk == -1]] = pp[pk == -1]
    lp[pc[pk == 1]] = pp[pk == 1]
    return pd.Series(lt).ffill().to_numpy(), pd.Series(lp).ffill().to_numpy()


def structure_exit_time(t_open: np.ndarray, avail: np.ndarray, c: np.ndarray, lt: np.ndarray, lp: np.ndarray, side: int,
                        t_entry: int, t_limit: int) -> int | None:
    """The close of the first entry-TF bar that opens at / after t_entry and closes by t_limit where a buy closes
    below the last confirmed trough (a sell above the last confirmed peak); None if none."""
    b0 = int(np.searchsorted(t_open, t_entry, side="left"))
    b1 = int(np.searchsorted(avail, t_limit, side="right"))
    if b1 <= b0:
        return None
    cc = c[b0:b1]
    hit = np.nonzero(cc < lt[b0:b1])[0] if side > 0 else np.nonzero(cc > lp[b0:b1])[0]
    return int(avail[b0 + hit[0]]) if len(hit) else None


def simulate(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t_entry: int, side: int, stop: float, target: float,
             t_struct: int | None, t_limit: int, extra: float = 0.0) -> dict | None:
    """One trade on the ticks: in at the first tick at / after t_entry (a buy at ask + SLIP + extra, a sell at bid -
    SLIP - extra); None if no tick or the fill is already past the stop. Then the first of: the stop (the first tick at
    / beyond it, filled there), the target (a limit at its level; NaN = none), the structure exit (the first tick at /
    after t_struct), the time (the first tick at / after t_limit), the break (the last tick before a gap > GAP_NS).
    Market exits at the bid (buy) / ask (sell). One tick: stop, target, structure, time, break."""
    f = int(np.searchsorted(t, t_entry, side="left"))
    if f >= len(t):
        return None
    entry = ask[f] + SLIP + extra if side > 0 else bid[f] - SLIP - extra
    risk = side * (entry - stop)
    if not risk > 0:
        return None
    end = min(int(np.searchsorted(t, t_limit, side="left")), len(t) - 1)
    ev = []
    gaps = np.nonzero(np.diff(t[f:end + 1]) > GAP_NS)[0]
    if len(gaps):
        ev.append((f + int(gaps[0]), "break"))
        end = f + int(gaps[0])
    elif t[end] >= t_limit:
        ev.append((end, "time"))
    else:
        ev.append((end, "break"))  # the ticks end before the time limit
    seg = slice(f + 1, end + 1)
    mkt = bid if side > 0 else ask
    s = np.nonzero(side * (mkt[seg] - stop) <= 0)[0]
    if len(s):
        ev.append((f + 1 + int(s[0]), "stop"))
    if np.isfinite(target):
        g = np.nonzero(side * (mkt[seg] - target) >= 0)[0]
        if len(g):
            ev.append((f + 1 + int(g[0]), "target"))
    if t_struct is not None:
        k = int(np.searchsorted(t, t_struct, side="left"))
        if f < k <= end:
            ev.append((k, "structure"))
    i, why = min(ev, key=lambda e: (e[0], ORDER[e[1]]))
    px = target if why == "target" else float(mkt[i])
    pnl = side * (px - entry)
    return dict(side=side, entry=float(entry), entry_t=int(t[f]), stop=float(stop), risk=float(risk), exit=why,
                exit_px=float(px), exit_t=int(t[i]), pnl=float(pnl), R=float(pnl / risk))


def news_times() -> np.ndarray:
    """The release minutes of the calendar and the 08:30 / 10:00 NY news legs (p_news_levels.parquet), ns, sorted."""
    from sweep_detector import calendar_events  # noqa: PLC0415

    a = pd.DatetimeIndex(calendar_events().t).as_unit("ns").asi8
    b = pd.read_parquet(HERE / "p_news_levels.parquet").t_rel.to_numpy(np.int64)
    return np.unique(np.concatenate([a, b]))


def is_news(t_entry: int, news: np.ndarray) -> bool:
    """The entry within NEWS_MIN minutes after a release minute (release <= entry <= release + 15 min)."""
    k = int(np.searchsorted(news, t_entry, side="right")) - 1
    return bool(k >= 0 and t_entry - news[k] <= NEWS_MIN * NS_MIN)


def agreement_group(other_pattern: str, other_structure: str, side: int) -> str:
    """The other TF at the decision: 'with' (a same-side pattern, or its structure the trade's way), 'against', 'mixed
    / none'."""
    if other_pattern:
        return "with"
    if other_structure in ("up", "down"):
        return "with" if (other_structure == "up") == (side > 0) else "against"
    return "mixed / none"


def candidates(C: pd.DataFrame, tfs: dict, variant: str) -> pd.DataFrame:
    """The entry candidates of a variant: A at the decision with the pattern's stop; B1 / B2 at the confirmation with
    the stop past the pullback low (B1) or the pattern's (B2). risk_dec = |the deciding close - the stop|."""
    rows = []
    for r in C.itertuples(index=False):
        tf = tfs[r.tf]
        d = int(np.searchsorted(tf.avail, int(r.t_dec)))
        if variant == "A":
            t_entry, stop, close = int(r.t_dec), float(r.stop), float(r.close)
            conf = None
        else:
            conf = confirm_b(tf.h, tf.lo, tf.c, d, float(r.extreme), float(r.atr), int(r.side))
            if conf is None:
                continue
            t_entry, close = int(tf.avail[conf["k"]]), float(tf.c[conf["k"]])
            stop = conf["pull"] - r.side * STOP_ATR * float(r.atr) if variant == "B1" else float(r.stop)
        rows.append(dict(t_entry=t_entry, side=int(r.side), stop=stop, risk_dec=abs(close - stop), tf=r.tf,
                         family=r.family, name=r.name, level_kind=r.level_kind,
                         height=float(r.height), next_level=float(r.next_level), t_dec=int(r.t_dec),
                         agree=agreement_group(r.other_pattern, r.other_structure, int(r.side)),
                         at_news=bool(r.at_news), conf_t=None if conf is None else t_entry,
                         pull=None if conf is None else conf["pull"]))
    if not rows:
        return pd.DataFrame(columns=["t_entry", "side", "stop", "risk_dec", "tf"])
    return pd.DataFrame(rows).sort_values(["t_entry", "risk_dec"], kind="stable").reset_index(drop=True)


class Ticks:
    """The ticks of a UTC day joined to the next day's (never a day of the exam), cached."""

    def __init__(self) -> None:
        self.days: dict = {}
        self.spans: dict = {}

    def day(self, d: pd.Timestamp) -> tuple[np.ndarray, ...]:
        if d not in self.days:
            from sweep_detector import learning_ticks  # noqa: PLC0415

            tk = learning_ticks(d) if d < EXAM_START else None
            self.days[d] = tk if tk is not None else (np.empty(0, np.int64), np.empty(0), np.empty(0))
        return self.days[d]

    def span(self, t_ns: int) -> tuple[np.ndarray, ...]:
        d = pd.Timestamp(t_ns, tz="UTC").normalize()
        if d not in self.spans:
            a, b = self.day(d), self.day(d + pd.Timedelta(days=1))
            self.spans[d] = tuple(np.concatenate([x, y]) for x, y in zip(a, b, strict=True))
        return self.spans[d]


def one_trade(r, tf, lt: np.ndarray, lp: np.ndarray, t: np.ndarray, bid: np.ndarray, ask: np.ndarray,
              extra: float) -> dict | None:
    """A candidate r (t_entry, side, stop, next_level) traded on its entry TF: the time limit, the structure exit time,
    then the ticks; the target = the next level only when more than one risk (at the fill) beyond the entry."""
    t_limit = int(r.t_entry + HOLD * tf.minutes * NS_MIN)
    ts = structure_exit_time(tf.t_open, tf.avail, tf.c, lt, lp, r.side, r.t_entry, t_limit)
    x = simulate(t, bid, ask, r.t_entry, r.side, r.stop, np.nan, ts, t_limit, extra)
    if x is None:
        return None
    tgt = r.next_level if np.isfinite(r.next_level) and r.side * (r.next_level - x["entry"]) > x["risk"] else np.nan
    if np.isfinite(tgt):
        x = simulate(t, bid, ask, r.t_entry, r.side, r.stop, tgt, ts, t_limit, extra)
    x.update(target=tgt, t_limit=t_limit, t_struct=ts)
    return x


def run_stream(cands: pd.DataFrame, tfs: dict, ticks: Ticks, news: np.ndarray, news_cost: float) -> pd.DataFrame:
    """One position at a time: the candidates in time order (ties: the smaller decision risk); a candidate entering
    before the open trade's exit is skipped."""
    pivs = {k: last_pivot_prices(tf.piv, len(tf.c)) for k, tf in tfs.items()}
    rows, busy = [], -1
    for r in cands.itertuples(index=False):
        if r.t_entry < busy:
            continue
        t, bid, ask = ticks.span(r.t_entry)
        news_trade = is_news(r.t_entry, news)
        x = one_trade(r, tfs[r.tf], *pivs[r.tf], t, bid, ask, news_cost if news_trade else 0.0)
        if x is None:
            continue
        rows.append({**r._asdict(), **x, "news": news_trade})
        busy = x["exit_t"]
    return pd.DataFrame(rows)


def weekdays(part: str) -> int:
    a, b = PARTS[part]
    return len(pd.bdate_range(a, b, inclusive="left"))


def stats(T: pd.DataFrame, part: str | None = None) -> dict:
    """Trades, a weekday, win %, R mean and its 95 % range, USD, max drawdown, the worst trade, the longest losing
    streak (count and USD), the exits."""
    n = len(T)
    if not n:
        return dict(n=0)
    T = T.sort_values("entry_t")
    pnl, R = T.pnl.to_numpy(float), T.R.to_numpy(float)
    eq = np.cumsum(pnl)
    dd = float(np.max(np.maximum.accumulate(np.r_[0.0, eq]) - np.r_[0.0, eq]))
    best_k, best_usd, k, usd = 0, 0.0, 0, 0.0
    for v in pnl:
        if v < 0:
            k, usd = k + 1, usd + v
            if k > best_k or (k == best_k and usd < best_usd):
                best_k, best_usd = k, usd
        else:
            k, usd = 0, 0.0
    sd = float(R.std(ddof=1)) if n > 1 else np.nan
    half = 1.96 * sd / np.sqrt(n) if n > 1 else np.nan
    out = dict(n=n, per_day=n / weekdays(part) if part else np.nan, win=float((pnl > 0).mean()), R=float(R.mean()),
               R_lo=float(R.mean() - half), R_hi=float(R.mean() + half), usd=float(pnl.sum()), dd=dd, worst=float(pnl.min()),
               streak=best_k, streak_usd=best_usd)
    for e in ORDER:
        out[f"x_{e}"] = int((T.exit == e).sum())
    return out


def reason(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, x: dict) -> str:
    """What came after a trade's entry within its own time limit: 'wrong way' (1 risk against before 1 risk our way),
    'ran later' (1 risk our way first), 'no run' (neither) - on the ticks, a buy read on the bid, a sell on the ask."""
    f = int(np.searchsorted(t, x["entry_t"], side="left"))
    e = int(np.searchsorted(t, x["t_limit"], side="left"))
    side = x["side"]
    fav = side * ((bid if side > 0 else ask)[f + 1:e + 1] - x["entry"])
    up, dn = np.nonzero(fav >= x["risk"])[0], np.nonzero(fav <= -x["risk"])[0]
    iu, idn = (int(up[0]) if len(up) else len(fav)), (int(dn[0]) if len(dn) else len(fav))
    if idn < iu:
        return "wrong way"
    if iu < idn:
        return "ran later"
    return "no run"


def main() -> None:
    from m15_trades import part_of  # noqa: PLC0415

    C = pd.read_parquet(HERE / "p_catches.parquet")
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    if (C.t_dec >= EXAM_START.value).any() or (C.t_dec < LEARN_START.value).any():
        raise ExamPeriodError("a catch outside the learning parts")
    m = P.load_m1()
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    ticks, news = Ticks(), news_times()
    out = []
    for variant in ("A", "B1", "B2"):
        cands = candidates(C, tfs, variant)
        for cost in NEWS_COSTS:
            T = run_stream(cands, tfs, ticks, news, cost)
            T["variant"], T["news_cost"] = variant, cost
            T["part"] = part_of(pd.to_datetime(T.entry_t, utc=True))
            if (T.exit_t >= EXAM_START.value).any():
                raise ExamPeriodError("a trade reached the exam")
            out.append(T)
        print(f"{variant}: {len(cands)} candidates", flush=True)
    A = pd.concat(out, ignore_index=True)
    A["big"] = (A.height > BIG) | (A.risk > BIG)
    # the losers' reasons (the main cost run)
    M = A[A.news_cost == 0.0]
    why = []
    for r in M.itertuples(index=False):
        if r.pnl < 0:
            t, bid, ask = ticks.span(r.t_entry)
            why.append(f"{reason(t, bid, ask, r._asdict())} x other TF {r.agree}")
        else:
            why.append("")
    A.loc[M.index, "reason"] = why
    A.to_parquet(HERE / "p2_trades.parquet")
    pd.concat([table(A, None, c).assign(news_cost=c) for c in NEWS_COSTS]).to_csv(HERE / "p2_metrics.csv", index=False)
    report(A)


def table(A: pd.DataFrame, by: str | None, cost: float = 0.0) -> pd.DataFrame:
    rows = []
    D = A[A.news_cost == cost]
    for (v, p), G in D.groupby(["variant", "part"]):
        groups = [("all", G)] if by is None else list(G.groupby(by))
        for key, H in groups:
            rows.append(dict(variant=v, part=p, group=key, **stats(H, p)))
    return pd.DataFrame(rows)


def report(A: pd.DataFrame) -> None:
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    cols = ["variant", "part", "n", "per_day", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd",
            "x_stop", "x_target", "x_structure", "x_time", "x_break"]
    print("\n== all trades (news cost 0)")
    print(table(A, None)[cols].round(3).to_string(index=False))
    print("\n== the news costs (R / USD of all trades; news trades pay the extra at entry)")
    for cost in NEWS_COSTS:
        t = table(A, None, cost)
        print(f"  +{cost:.1f}: " + "; ".join(f"{r.variant} {r.part} n {r.n} R {r.R:+.3f} USD {r.usd:+.0f}" for r in t.itertuples()))
    small = ["variant", "part", "group", "n", "win", "R", "R_lo", "R_hi", "usd", "worst"]
    for by in ("family", "tf", "level_kind", "agree", "big", "news"):
        print(f"\n== by {by}")
        print(table(A, by)[small].round(3).to_string(index=False))
    print("\n== the smaller part's R (news cost 0 / +2)")
    for cost in (0.0, 2.0):
        t = table(A, None, cost)
        print(f"  +{cost:.0f}: " + "; ".join(f"{v}: {g.R.min():+.3f}" for v, g in t.groupby("variant")))
    print("\n== the losers by reason (news cost 0)")
    L = A[(A.news_cost == 0.0) & (A.pnl < 0)]
    print(L.groupby(["variant", "part", "reason"]).agg(n=("pnl", "size"), usd=("pnl", "sum"), R=("R", "mean"))
          .round(2).to_string())


if __name__ == "__main__":
    main()
