"""PLAN-1 runner (CHECKLIST row 38; DEV_LOG.md "Task PLAN-1 runner - written before computing").

The daily plan frozen for the one exam read: Asia B2 (p4_trades.py W, the Asia window 07:00-09:00 Thai), the London
13:00-Thai opening-range break (strategist/orb_ticks.py's rule), the NY 08:30 straddle held 30 minutes
(strategist/news_follow.py "STRADDLE 30m"), one position at a time, weighted by the D1 state before the entry
(precursors/regime.py: the 20-day efficiency, P1's terciles 0.116 / 0.264) - unweighted, by mechanism, from P1.

Costs: the tick bid / ask spread; the entry slippage is a parameter (default 0); the straddle's release slippage
`--extra` (default 0).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1.py                  # learning parts, slippage 0
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1.py --repro          # 0.07: out_combo / out_regime
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1.py --exam           # THE MEASURER ONLY, once

Without --exam nothing at / after 2026-04-18 is read (the M1 loader refuses before reading; the tick reader never opens
a day at / after the period's end).
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENTS = HERE.parent
sys.path.insert(0, str(HERE))
import p3_trades as T3  # noqa: E402  (first: puts the dev folder on the path)
import d1_orb as D1  # noqa: E402
import p2_trades as P2  # noqa: E402
import p4_trades as P4  # noqa: E402
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, LEARN_START, ExamPeriodError  # noqa: E402

sys.path.insert(0, str(AGENTS / "strategist"))
sys.path.insert(0, str(AGENTS / "precursors"))
import news_follow as NF  # noqa: E402  (the strategist's tick simulator, read-only)
import regime  # noqa: E402  (the D1 state, read-only)

NS_S = 10**9
NS_MIN = 60 * NS_S
EXAM_END = pd.Timestamp("2026-10-18", tz="UTC")  # the exam is 2026-04-18 .. 2026-10-17
WARM_START = P.WARM_START  # 2025-09-01: B2's swings and every bar series start here
PARTS = {"P1": (pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-01-16", tz="UTC")),
         "P2": (pd.Timestamp("2026-01-16", tz="UTC"), EXAM_START),
         "exam": (EXAM_START, EXAM_END)}
PIECES = ("Asia B2", "London ORB", "NY straddle")
ORB_MIN, ORB_K, ORB_X, ORB_FILL = 15, 2.0, 60, 5 * NS_MIN  # the range minutes, target R, minutes held, the fill's limit
STR_TRIG, STR_STOP, STR_HOLD = 2.0, 8.0, 30  # the straddle: trigger USD, stop USD, minutes
W_MECH = {("Asia B2", "trend"): 0.5, ("London ORB", "trend"): 0.5, ("NY straddle", "sideways"): 0.5,
          ("NY straddle", "mixed"): 0.5}
# The P1 rule (0.5 where the piece's mean P1 R in that state < 0) on this runner's own P1 trades at slippage 0, extra 0
# (DEV_LOG.md, read from out_plan1_learn_s0_x0.txt at 06:08 UTC: Asia B2 trend -0.070, NY straddle sideways -0.131, every
# other cell >= 0 - NY mixed +0.025); fixed here so that the exam uses the same table. The report prints the rule's
# result on each run beside it.
W_P1 = {("Asia B2", "trend"): 0.5, ("NY straddle", "sideways"): 0.5}
EMPTY_NEWS = pd.DataFrame({"t_rel": pd.Series(dtype=np.int64), "ny": pd.Series(dtype=object),
                           "first": pd.Series(dtype=np.int64), "leg1": pd.Series(dtype=float),
                           "level": pd.Series(dtype=float)})


# ---------------------------------------------------------------- the period and its guards
def period(exam: bool) -> tuple[pd.Timestamp, pd.Timestamp]:
    """The trades' period: the learning parts, or the exam only with the switch."""
    return (EXAM_START, EXAM_END) if exam else (LEARN_START, EXAM_START)


def check_period(start: pd.Timestamp, end: pd.Timestamp, exam: bool) -> None:
    """Refuse any period reaching the exam without the switch, and with the switch anything but the exam."""
    if end <= start:
        raise ValueError("an empty period")
    if not exam and end > EXAM_START:
        raise ExamPeriodError("the period reaches the exam without --exam")
    if exam and (start != EXAM_START or end != EXAM_END):
        raise ValueError("--exam reads the exam period 2026-04-18 .. 2026-10-17 and nothing else")


def load_m1(end: pd.Timestamp, exam: bool, reader=None) -> pd.DataFrame:
    """M1 bars [WARM_START, end) straight from the parquet with a row filter (patterns.load_m1's reading, its end set
    by the period); an end past 2026-04-18 without the switch is refused before anything is read."""
    if end > EXAM_START and not exam:
        raise ExamPeriodError("M1 may not be read into the exam period without --exam")
    if end > EXAM_END:
        raise ValueError("past the exam's end")
    if reader is None:
        import pyarrow.parquet as pq  # noqa: PLC0415

        reader = pq.read_table
    cols = ["open_time", "open", "high", "low", "close", "tick_volume", "spread"]
    t = reader(P.M1_FILE, columns=cols, filters=[("open_time", ">=", WARM_START), ("open_time", "<", end)])
    m = t.to_pandas().drop_duplicates("open_time", keep="last").set_index("open_time").sort_index()
    m.index = pd.DatetimeIndex(m.index).tz_convert("UTC")
    m.index.name = None
    if len(m) and m.index.max() >= end:
        raise ExamPeriodError("a row past the period's end was read")
    return m.astype(float)


class PlanTicks(P4.SmallTicks):
    """The day / span tick cache of B2 (last few days kept), reading a UTC day only when it is before `end`; a day at /
    after it is empty and its file is never opened."""

    def __init__(self, end: pd.Timestamp, read=None) -> None:
        super().__init__()
        self.end = end
        if read is None:
            from tick_straddle import day_ticks  # noqa: PLC0415

            read = day_ticks
        self.read = read

    def day(self, d):
        d = pd.Timestamp(d)
        d = (d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")).normalize()
        if d not in self.days:
            tk = self.read(d) if d < self.end else None
            self.days[d] = tk if tk is not None else (np.empty(0, np.int64), np.empty(0), np.empty(0))
        x = self.days[d]
        while len(self.days) > self.KEEP:
            self.days.pop(next(iter(self.days)))
        return x


@contextlib.contextmanager
def located_in(start: pd.Timestamp, end: pd.Timestamp):
    """patterns.locate keeps decisions in [LEARN_START, EXAM_START): set its bounds to the period while it runs."""
    old = P.LEARN_START, P.EXAM_START
    P.LEARN_START, P.EXAM_START = start, end
    try:
        yield
    finally:
        P.LEARN_START, P.EXAM_START = old


@contextlib.contextmanager
def entry_slippage(slip: float):
    """B2's simulator reads p2_trades.SLIP at each fill: set it to this run's slippage while it runs."""
    old = P2.SLIP
    P2.SLIP = float(slip)
    try:
        yield
    finally:
        P2.SLIP = old


def part_of(t_ns: int) -> str:
    t = pd.Timestamp(int(t_ns), tz="UTC")
    for name, (a, b) in PARTS.items():
        if a <= t < b:
            return name
    return ""


def weekdays(part: str) -> int:
    a, b = PARTS[part]
    return len(pd.bdate_range(a.tz_localize(None), b.tz_localize(None), inclusive="left"))


# ---------------------------------------------------------------- the pieces
def piece_rows(piece: str, rows: list[dict]) -> pd.DataFrame:
    cols = ["piece", "t_dec", "t_in", "t_out", "side", "entry", "stop", "risk", "pnl", "R", "exit", "part"]
    if not rows:
        return pd.DataFrame(columns=cols)
    T = pd.DataFrame(rows)
    T["piece"] = piece
    T["part"] = [part_of(t) for t in T.t_in]
    return T[cols]


def asia_candidates(base: pd.DataFrame) -> pd.DataFrame:
    """B2's candidates whose entry decision (t_entry) is in the Asia window, 07:00-09:00 Thai (p4_trades.window_of)."""
    cands = P4.in_windows(base, 0)
    return cands[cands.window == "Asia"].reset_index(drop=True)


def asia_b2(m: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, ticks, slip: float) -> pd.DataFrame:
    """B2 (P3's engine) with entry decisions in the Asia window, one position at a time, news cost 0."""
    Y = P.level_inputs(m)
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    out = {}
    with located_in(start, end):
        for k, tf in tfs.items():
            a = int(np.searchsorted(tf.avail, start.value))
            out[k] = P.locate(tf.scan(a, len(tf.c)), tf, Y, EMPTY_NEWS)
    C = pd.concat([P.agree(out["M1"], out["M5"], tfs["M5"]), P.agree(out["M5"], out["M1"], tfs["M1"])], ignore_index=True)
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    cands = asia_candidates(T3.candidates3(C, tfs, T3.SETTINGS["B2"]))
    with entry_slippage(slip):
        T = T3.run_stream3(cands, tfs, ticks, np.empty(0, np.int64), 0.0, "structure")
    rows = [dict(t_dec=int(r.t_entry), t_in=int(r.entry_t), t_out=int(r.exit_t), side=int(r.side), entry=r.entry,
                 stop=r.stop, risk=r.risk, pnl=r.pnl, R=r.R, exit=r.exit) for r in T.itertuples(index=False)
            if start.value <= r.t_entry < end.value]
    return piece_rows("Asia B2", rows)


def exit_tick(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, f: int, entry: float, side: int, stop: float,
              target: float | None, t_out: int) -> tuple[float, str, int] | None:
    """news_follow.run_trade's loop, also returning the exit tick: from tick f + 1 the time (first tick at / after
    t_out, at the market), the stop (gap included, at the market), the target (a limit, at the target)."""
    for k in range(f + 1, len(t)):
        px = bid[k] if side > 0 else ask[k]
        if t[k] >= t_out:
            return (px - entry) * side, "time", k
        if (px - stop) * side <= 0:
            return (px - entry) * side, "stop", k
        if target is not None and (px - target) * side >= 0:
            return (target - entry) * side, "target", k
    return None


def tick_run(t, bid, ask, f, entry, side, stop, target, t_out) -> tuple[float, str, int] | None:
    """The strategist's run_trade decides pnl and exit; exit_tick adds the exit tick and must agree with it."""
    r = NF.run_trade(t, bid, ask, f, entry, side, stop, target, t_out)
    x = exit_tick(t, bid, ask, f, entry, side, stop, target, t_out)
    if r is None or x is None:
        if (r is None) != (x is None):
            raise AssertionError("exit_tick disagrees with news_follow.run_trade")
        return None
    if r[1] != x[1] or r[0] != x[0]:
        raise AssertionError("exit_tick disagrees with news_follow.run_trade")
    return x


def orb_trade(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t_dec: int, side: int, stop: float, slip: float) -> dict | None:
    """orb_ticks.tick_trade: the fill at the first tick at / after the decision within 5 minutes (a buy at the ask +
    slip, a sell at the bid - slip), the stop at the range's other side, the target 2 R, out at the fill + 60 min."""
    f = int(np.searchsorted(t, t_dec, side="left"))
    if f >= len(t) or t[f] - t_dec > ORB_FILL:
        return None
    e = ask[f] + slip if side > 0 else bid[f] - slip
    risk = (e - stop) * side
    if risk <= 0:
        return None
    r = tick_run(t, bid, ask, f, e, side, stop, e + side * ORB_K * risk, int(t[f] + ORB_X * NS_MIN))
    if r is None:
        return None
    return dict(t_dec=int(t_dec), t_in=int(t[f]), t_out=int(t[r[2]]), side=side, entry=float(e), stop=float(stop),
                risk=float(risk), pnl=float(r[0]), R=float(r[0] / risk), exit=r[1], i_in=f, i_out=r[2])


def london_orb(mk, days, ticks, slip: float) -> pd.DataFrame:
    rows = []
    for day in days:
        t0 = int((day.normalize() + pd.Timedelta(hours=D1.OPEN_UTC)).value)
        dd = D1.decide(mk.t_open, mk.h, mk.lo, mk.c, t0, mk.H(t0), ORB_MIN)
        if dd["status"] != "trade":
            continue
        t, bid, ask = ticks.day(day)
        x = orb_trade(t, bid, ask, dd["t_dec"], dd["side"], dd["stop"], slip)
        if x is not None:
            rows.append(x)
    return piece_rows("London ORB", rows)


def ny_t0(day: pd.Timestamp) -> int:
    """08:30:00 New York on that date, in UTC ns (summer / winter time)."""
    return pd.Timestamp(f"{day:%Y-%m-%d} 08:30").tz_localize("America/New_York").tz_convert("UTC").value


def straddle(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, slip: float, extra: float = 0.0) -> dict | None:
    """news_follow.py's STRADDLE 30m at t0 on one UTC day's ticks: the day needs >= 1000 ticks, ticks from t0 - 10 min
    to t0 + 30 min; the reference = the last tick before t0; a buy stop at its ask + 2, a sell stop at its bid - 2,
    live [t0, t0 + 60 s), the buy first on one tick; the fill at max(trigger, ask) + slip + extra (a sell min(trigger,
    bid) - slip - extra); the stop 8 from the fill; out at the first tick at / after t0 + 30 min; R = pnl / 8."""
    if len(t) < 1000 or t0 < t[0] + 600 * NS_S or t0 + 1800 * NS_S > t[-1]:
        return None
    i0 = int(np.searchsorted(t, t0, side="left")) - 1
    up, dn = ask[i0] + STR_TRIG, bid[i0] - STR_TRIG
    k = int(np.searchsorted(t, t0, side="left"))
    k_end = int(np.searchsorted(t, t0 + 60 * NS_S, side="left"))
    hit = None
    for j in range(k, k_end):
        if ask[j] >= up:
            hit = (j, 1, max(up, ask[j]) + slip + extra)
            break
        if bid[j] <= dn:
            hit = (j, -1, min(dn, bid[j]) - slip - extra)
            break
    if hit is None:
        return None
    j, side, e = hit
    stop = e - side * STR_STOP
    r = tick_run(t, bid, ask, j, e, side, stop, None, t0 + STR_HOLD * NS_MIN)
    if r is None:
        return None
    return dict(t_dec=int(t0), t_in=int(t[j]), t_out=int(t[r[2]]), side=side, entry=float(e), stop=float(stop),
                risk=STR_STOP, pnl=float(r[0]), R=float(r[0] / STR_STOP), exit=r[1], i_in=j, i_out=r[2])


def ny_straddle(days, ticks, slip: float, extra: float) -> pd.DataFrame:
    rows = []
    for day in days:
        t, bid, ask = ticks.day(day)
        x = straddle(t, bid, ask, ny_t0(day), slip, extra)
        if x is not None:
            rows.append(x)
    return piece_rows("NY straddle", rows)


# ---------------------------------------------------------------- the combination
def stream(T: pd.DataFrame) -> pd.DataFrame:
    """One position at a time: in fill-time order, a trade filled before the kept trade's exit is dropped."""
    T = T.sort_values("t_in", kind="stable").reset_index(drop=True)
    keep, busy = [], -1
    for i, (a, b) in enumerate(zip(T.t_in.to_numpy(np.int64), T.t_out.to_numpy(np.int64), strict=True)):
        if a < busy:
            continue
        keep.append(i)
        busy = b
    return T.loc[keep].reset_index(drop=True)


def trend_state(d1: pd.DataFrame, t_ns) -> np.ndarray:
    """regime.state_at's trend label at each time, from the D1 bars complete by it."""
    return regime.state_at(d1, pd.DatetimeIndex(pd.to_datetime(np.asarray(t_ns, np.int64), utc=True))).trend.to_numpy()


def weights(T: pd.DataFrame, W: dict) -> np.ndarray:
    return np.array([W.get((p, s), 1.0) for p, s in zip(T.piece, T.trend, strict=True)], float)


def p1_weights(T: pd.DataFrame) -> dict:
    """The P1 rule: 0.5 where a piece's mean P1 R in that trend state is below 0."""
    G = T[T.part == "P1"]
    return {(p, s): 0.5 for (p, s), g in G.groupby(["piece", "trend"]) if g.R.mean() < 0}


def summary(T: pd.DataFrame, w: np.ndarray | None = None, part: str | None = None) -> dict:
    """Trades, a weekday, win % (pnl > 0), R per trade (weighted: sum R w / sum w) with its 95 % range, USD (pnl w),
    max DD from 0, the worst trade, the longest losing streak (count, USD)."""
    n = len(T)
    if not n:
        return dict(n=0)
    o = np.argsort(T.t_in.to_numpy(np.int64), kind="stable")  # time order; w is aligned with T's rows
    w = np.ones(n) if w is None else np.asarray(w, float)[o]
    r, raw = T.R.to_numpy(float)[o], T.pnl.to_numpy(float)[o]
    pnl = raw * w
    mean = float(np.sum(r * w) / np.sum(w))
    if n > 1:
        half = 1.96 * np.sqrt(np.sum(w**2 * (r - mean) ** 2) * n / (n - 1)) / np.sum(w)
    else:
        half = np.nan
    eq = np.r_[0.0, np.cumsum(pnl)]
    best_k, best_usd, k, usd = 0, 0.0, 0, 0.0
    for v in pnl:
        if v < 0:
            k, usd = k + 1, usd + v
            if k > best_k or (k == best_k and usd < best_usd):
                best_k, best_usd = k, usd
        else:
            k, usd = 0, 0.0
    return dict(n=n, per_day=n / weekdays(part) if part in PARTS else np.nan, win=float(np.mean(raw > 0)),
                R=mean, R_lo=mean - half, R_hi=mean + half, usd=float(pnl.sum()),
                dd=float(np.max(np.maximum.accumulate(eq) - eq)), worst=float(pnl.min()), streak=best_k, streak_usd=best_usd)


def line(s: dict) -> str:
    if not s.get("n"):
        return "n 0"
    pd_ = f" ({s['per_day']:.2f} a weekday)" if np.isfinite(s["per_day"]) else ""
    return (f"{s['n']} trades{pd_}, win {s['win']:.3f}, R {s['R']:+.3f} ({s['R_lo']:+.3f}..{s['R_hi']:+.3f}), "
            f"USD {s['usd']:+.2f}, max DD {s['dd']:.2f}, worst {s['worst']:+.2f}, streak {s['streak']} ({s['streak_usd']:+.2f})")


def weekly(T: pd.DataFrame) -> pd.DataFrame:
    """Week by week, Thai weeks (Monday 00:00 .. Sunday 24:00 Thai), by the fill time: trades, win, R a trade, USD,
    running USD, the worst trade - unweighted, then R a trade / USD by mechanism and from P1."""
    th = pd.DatetimeIndex(pd.to_datetime(T.t_in.to_numpy(np.int64), utc=True)).tz_convert("Asia/Bangkok")
    wk = (th.normalize() - pd.to_timedelta(th.dayofweek, unit="D")).tz_localize(None)
    X = T.assign(week=wk.date, rw_m=T.R * T.w_mech, pw_m=T.pnl * T.w_mech, rw_p=T.R * T.w_p1, pw_p=T.pnl * T.w_p1)
    g = X.groupby("week", sort=True)
    W = pd.DataFrame({"trades": g.size(), "win": g.pnl.agg(lambda x: (x > 0).mean()).round(2), "R_trade": g.R.mean().round(3),
                      "usd": g.pnl.sum().round(2), "worst": g.pnl.min().round(2),
                      "R_mech": (g.rw_m.sum() / g.w_mech.sum()).round(3), "usd_mech": g.pw_m.sum().round(2),
                      "R_p1": (g.rw_p.sum() / g.w_p1.sum()).round(3), "usd_p1": g.pw_p.sum().round(2)})
    W.insert(W.columns.get_loc("worst"), "usd_total", W.usd.cumsum().round(2))
    return W.reset_index()


# ---------------------------------------------------------------- the run
def build(exam: bool, slip: float, extra: float, m: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every piece's trades (all) and the plan (one position at a time, with the D1 state and the weights)."""
    start, end = period(exam)
    check_period(start, end, exam)
    if m is None:
        m = load_m1(end, exam)
    ticks = PlanTicks(end)
    days = pd.bdate_range(start.tz_localize(None), end.tz_localize(None), inclusive="left", tz="UTC")
    asia = asia_b2(m, start, end, ticks, slip)
    print(f"Asia B2: {len(asia)} trades", flush=True)
    london = london_orb(D1.Market(m), days, ticks, slip)
    print(f"London ORB: {len(london)} trades", flush=True)
    ny = ny_straddle(days, ticks, slip, extra)
    print(f"NY straddle: {len(ny)} trades", flush=True)
    every = pd.concat([asia, london, ny], ignore_index=True)
    for c in ("t_dec", "t_in", "t_out"):
        every[c] = every[c].astype(np.int64)
    if len(every) and ((every.t_in < start.value) | (every.t_in >= end.value)).any():
        raise ExamPeriodError("a trade outside the period")
    from indicators import bars  # noqa: PLC0415

    d1 = bars(m, "1D")
    every["trend"] = trend_state(d1, every.t_in)
    A = stream(every)
    A["w_mech"], A["w_p1"] = weights(A, W_MECH), weights(A, W_P1)
    return every, A


def report(every: pd.DataFrame, A: pd.DataFrame, parts: tuple[str, ...], out) -> None:
    pr = lambda s="": print(s, file=out)  # noqa: E731
    pr(f"dropped for overlap: {len(every) - len(A)}")
    pr("\nthe pieces alone (each piece's own trades):")
    for pc in PIECES:
        for p in parts:
            pr(f"  {pc:12s} {p}: {line(summary(every[(every.piece == pc) & (every.part == p)], part=p))}")
    for lab, col in (("unweighted", None), ("by mechanism", "w_mech"), ("from P1", "w_p1")):
        pr(f"\nthe plan, {lab}:")
        for p in parts:
            G = A[A.part == p]
            w = None if col is None else G[col].to_numpy()
            by = {pc: round(summary(g, None if col is None else g[col].to_numpy())["R"], 3) for pc, g in G.groupby("piece")}
            pr(f"  {p}: {line(summary(G, w, p))} | by piece R {by}")
        if parts == ("P1", "P2"):
            G = A[A.part.isin(parts)].reset_index(drop=True)
            s = summary(G, None if col is None else G[col].to_numpy())
            pr(f"  pooled P1 + P2: {line(s)}; {s['n'] / (weekdays('P1') + weekdays('P2')):.2f} a weekday")
    pr("\nR by piece x D1 state (mean, trades), per part:")
    pr(A.groupby(["piece", "trend", "part"]).R.agg(["mean", "size"]).round(3).unstack("part").to_string())
    if "P1" in parts:
        pr(f"\nthe P1 rule on these trades: {p1_weights(A)}; fixed table W_P1: {W_P1}")
    else:
        pr(f"\nthe fixed tables: W_MECH {W_MECH}; W_P1 {W_P1}")
    pr(f"exits: {A.groupby(['piece', 'exit']).size().to_dict()}")
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        for p in parts:
            pr(f"\nweek by week, {p} (Thai weeks; R / USD unweighted, by mechanism, from P1):")
            pr(weekly(A[A.part == p].reset_index(drop=True)).to_string(index=False))


def repro(m: pd.DataFrame) -> None:
    """Slippage 0.07: combo.stats lines against out_combo.txt, the trades against combo_trades_slip0 / slip1, the
    trend table and the weights against out_regime.txt / CHECKLIST row 37."""
    import combo  # noqa: PLC0415

    res = {}
    for extra in (0.0, 1.0):
        every, A = build(False, 0.07, extra, m)
        res[extra] = (every, A)
        every.to_parquet(HERE / f"plan1_repro_every_x{int(extra)}.parquet")
        A.to_parquet(HERE / f"plan1_repro_x{int(extra)}.parquet")
    lines = ["the pieces alone:"]
    for name, T in (("Asia B2", res[0.0][0][res[0.0][0].piece == "Asia B2"]), ("London ORB", res[0.0][0][res[0.0][0].piece == "London ORB"]),
                    ("NY straddle +0", res[0.0][0][res[0.0][0].piece == "NY straddle"]), ("NY straddle +1", res[1.0][0][res[1.0][0].piece == "NY straddle"])):
        for p in ("P1", "P2"):
            G = T[T.part == p]
            lines.append(f"  {name:16s} {p}: {combo.stats(G, combo.WEEKDAYS[p])}")
    for label, extra in (("the plan (NY slippage +0)", 0.0), ("the plan (NY slippage +1 USD)", 1.0)):
        every, A = res[extra]
        lines += ["", f"{label}: dropped for overlap {len(every) - len(A)}"]
        for p in ("P1", "P2"):
            G = A[A.part == p]
            lines.append(f"  {p}: {combo.stats(G, combo.WEEKDAYS[p])}  | by piece R: {G.groupby('piece').R.mean().round(3).to_dict()}")
        lines.append(f"  pooled P1 + P2: {combo.stats(A, combo.WEEKDAYS['P1'] + combo.WEEKDAYS['P2'])}")
    mine = "\n".join(lines)
    ref = (AGENTS / "precursors" / "out_combo.txt").read_text(encoding="utf-8").strip().splitlines()
    print("=== out_combo.txt against this runner (slippage 0.07); lines that differ:")
    for a, b in zip(ref, mine.splitlines(), strict=False):
        if a.strip() != b.strip():
            print(f"  out_combo: {a.strip()}\n  plan1    : {b.strip()}")
    print(f"  ({len(ref)} reference lines, {len(mine.splitlines())} lines here)")
    for extra in (0.0, 1.0):
        C = pd.read_parquet(AGENTS / "precursors" / f"combo_trades_slip{int(extra)}.parquet")
        A = res[extra][1]
        # the key: the piece and its fill time (combo's NY t_in is 08:30 NY = this runner's t_dec)
        key_c = [(r.piece, pd.Timestamp(r.t_in).value) for r in C.itertuples()]
        key_a = [(r.piece, int(r.t_dec if r.piece == "NY straddle" else r.t_in)) for r in A.itertuples()]
        assert len(set(key_c)) == len(key_c) and len(set(key_a)) == len(key_a)
        cm, am = dict(zip(key_c, zip(C.pnl, C.R, strict=True), strict=True)), dict(zip(key_a, zip(A.pnl, A.R, strict=True), strict=True))
        only_c, only_a = sorted(set(cm) - set(am)), sorted(set(am) - set(cm))
        diff = [(k, cm[k], am[k]) for k in sorted(set(cm) & set(am)) if abs(cm[k][0] - am[k][0]) > 1e-9]
        print(f"\n=== trade by trade against combo_trades_slip{int(extra)}.parquet (piece, fill time): {len(set(cm) & set(am))} in both, "
              f"only in combo {len(only_c)}, only here {len(only_a)}, pnl differs on {len(diff)}")
        for k in only_c:
            print(f"  only in combo: {k[0]} {pd.Timestamp(k[1], tz='UTC')} pnl {cm[k][0]:+.4f}")
        for k in only_a:
            print(f"  only here: {k[0]} {pd.Timestamp(k[1], tz='UTC')} pnl {am[k][0]:+.4f}")
        for k, c, a in diff:
            print(f"  differs: {k[0]} {pd.Timestamp(k[1], tz='UTC')}  combo pnl {c[0]:+.4f} R {c[1]:+.4f}  here pnl {a[0]:+.4f} R {a[1]:+.4f}")
    print("\n=== the D1 state (regime.py), R by piece x trend (mean, trades), NY + 1 USD (out_regime.txt's file):")
    A1 = res[1.0][1]
    print(A1.groupby(["piece", "trend", "part"]).R.agg(["mean", "size"]).round(3).unstack("part").to_string())
    for extra in (0.0, 1.0):
        A = res[extra][1]
        W = p1_weights(A)
        print(f"\nNY extra +{extra:.0f}: the weights from P1: {W}")
        for lab, WW in (("from P1", W), ("by mechanism", W_MECH)):
            out = []
            for p in ("P1", "P2"):
                G = A[A.part == p]
                w = weights(G, WW)
                out.append(f"{p} {np.sum(G.R * w) / np.sum(w):+.3f} (USD {G.pnl.sum():+.1f} -> {np.sum(G.pnl * w):+.1f})")
            print(f"  {lab}: weighted R " + "; ".join(out) + f"; unweighted {A[A.part == 'P1'].R.mean():+.3f} / {A[A.part == 'P2'].R.mean():+.3f}")


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slippage", type=float, default=0.0, help="entry slippage on every piece, USD (default 0)")
    ap.add_argument("--extra", type=float, default=0.0, help="the straddle's release slippage, USD (default 0)")
    ap.add_argument("--exam", action="store_true", help="THE MEASURER ONLY: the exam period, read once")
    ap.add_argument("--repro", action="store_true", help="slippage 0.07: reproduce out_combo.txt / out_regime.txt")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    a = parse(argv)
    if a.repro:
        if a.exam:
            raise SystemExit("--repro is for the learning parts only")
        repro(load_m1(EXAM_START, False))
        return
    every, A = build(a.exam, a.slippage, a.extra)
    tag = ("exam" if a.exam else "learn") + f"_s{a.slippage:g}_x{a.extra:g}"
    every.to_parquet(HERE / f"plan1_every_{tag}.parquet")
    A.to_parquet(HERE / f"plan1_trades_{tag}.parquet")
    parts = ("exam",) if a.exam else ("P1", "P2")
    with open(HERE / f"out_plan1_{tag}.txt", "w", encoding="utf-8") as f:
        print(f"PLAN-1 ({'EXAM' if a.exam else 'learning parts'}), entry slippage {a.slippage:g}, release extra {a.extra:g}", file=f)
        report(every, A, parts, f)
    print((HERE / f"out_plan1_{tag}.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
