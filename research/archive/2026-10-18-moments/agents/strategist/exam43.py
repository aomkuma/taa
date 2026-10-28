"""The exam runner of two FROZEN leads (the owner's top-5 step 1, 2026-10-20/21). Written by the strategist; the
--exam switch is for THE MEASURER ONLY, once. The strategist never runs it.

THE FROZEN DEFINITIONS (exactly the row-39 / row-45 cells; the code is streams.py's event loops = states_events.py's):

Shared:
- M1 bid bars (data/history/FBS-Demo/XAUUSD/M1.parquet); M5 bars and H1 bars built from M1; H = the MT5 ATR(14) of
  the last H1 bar complete at the decision (H1 bar available one minute after its last M1 bar).
- The levels everyone sees, per server day (Europe/Athens): the previous server day's high (PDH) and low (PDL), known
  from the day's start; the Asian range high (ASH) / low (ASL) of the M5 bars 00:00-06:00 UTC, known from 06:00 UTC
  (only when >= 60 such bars). A day needs >= 50 M5 bars.
- The break of a level: the first M5 close beyond it by 0.1 H with the previous M5 close on the other side (a top
  breaks up, a low breaks down); one break per level per day.
- The entry: at the first tick at / after the decision M5 bar's close (tick bid / ask; slippage 0). The costs: the
  tick spread only. Each trade alone (no one-position filter). R = pnl / the trade's own risk.

#23 RC_win - the reclaim of a level everyone sees, in the owner's windows:
- after the break, within the next 24 M5 bars, the first M5 close back inside by 0.1 H -> trade back into the range
  (a buy for a broken low, a sell for a broken top);
- stop = the break's extreme since the break bar (included) up to the bar before the reclaim, 0.25 H beyond it;
  target 2 R (from the tick fill); out at the first tick at / after 120 minutes;
- kept only when the entry minute is in the owner's windows: Asia 07:00-09:00 Thai, London 13:00-14:00 Thai, New York
  09:30-11:30 New York time.

#43 RT_opp - the break-and-retest taken the other way, back into the range, 1 R target:
- after the break (the side = the break's way), the retest: within the next 36 M5 bars the first bar touching back to
  the level by 0.15 H (cancelled by an M5 close 0.75 H back through the level first);
- the turn: within 12 M5 bars after the retest bar, the first M5 close beyond the extreme of bars retest .. k-1 the
  break's way, with that close no more than 0.5 H back inside the level (cancelled by a close 0.75 H back through);
- the rule's own stop = the retest-side extreme since the retest bar + 0.25 H; its distance d is measured from the rule
  side's tick fill (ask for a buy, bid for a sell);
- the trade is the OTHER side at the same tick: stop at d from its own fill, target at 1 x d, out at the first tick at
  / after 120 minutes. All hours.

Learning reproduction (switch off): the tick results of P1 / P2 equal states_events.parquet trade for trade
(RT_opp 41 / 46, RC_win 19 / 22).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/exam43.py            # learning parts (default)
    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/exam43.py --exam     # THE MEASURER ONLY, once

Without --exam nothing at / after 2026-04-18 is read: the M1 reader is called with a filter that stops before the exam
and its result is asserted; the tick reader refuses exam days. With --exam the period is 2026-04-18 .. 2026-10-17 only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
M1_PATH = ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet"
TICKS = ROOT / "data/ticks/XAUUSD"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
EXAM_END = pd.Timestamp("2026-10-18", tz="UTC")  # the exam is 2026-04-18 .. 2026-10-17
PERIODS = {"P1": (pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-01-16", tz="UTC")),
           "P2": (pd.Timestamp("2026-01-16", tz="UTC"), EXAM_START), "exam": (EXAM_START, EXAM_END)}
WARMUP = pd.Timedelta(days=30)
MIN = 60 * 10**9
TH = "Asia/Bangkok"


class ExamPeriodError(RuntimeError):
    """Exam data requested without the --exam switch."""


def parts_for(exam: bool) -> list[str]:
    return ["exam"] if exam else ["P1", "P2"]


def window(exam: bool) -> tuple[pd.Timestamp, pd.Timestamp]:
    ps = [PERIODS[p] for p in parts_for(exam)]
    return ps[0][0], ps[-1][1]


def _parquet_reader(path, filters):
    return pd.read_parquet(path, filters=filters)


def load_m1(exam: bool, reader=_parquet_reader) -> pd.DataFrame:
    """M1 bars (ns UTC index) from the period's start - 30 days up to the period's end; the learning read never reaches
    the exam (the filter stops before it, and the result is checked before it is returned)."""
    start, end = window(exam)
    if not exam and end > EXAM_START:
        raise ExamPeriodError("the learning read reaches the exam")
    d = reader(M1_PATH, [("open_time", ">=", start - WARMUP), ("open_time", "<", end)])
    d.index = pd.DatetimeIndex(pd.to_datetime(d["open_time"], utc=True)).as_unit("ns")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if not exam and len(d) and d.index.max() >= EXAM_START:
        raise ExamPeriodError("the reader returned exam rows without --exam")
    return d[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


def _tick_file_reader(day: pd.Timestamp):
    f = TICKS / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return None
    x = pd.read_parquet(f, columns=["time_utc", "bid", "ask"])
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


def day_ticks(day: pd.Timestamp, exam: bool, reader=_tick_file_reader):
    """One UTC day's ticks; a day at / after the exam start is refused without --exam (before the reader is called),
    and with --exam nothing at / after the exam's end is read."""
    d = pd.Timestamp(day)
    d = (d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")).normalize()
    if d >= EXAM_START and not exam:
        raise ExamPeriodError(f"{d:%Y-%m-%d} is in the exam period")
    if d >= EXAM_END:
        return None
    return reader(d)


def span(t_ns: int, exam: bool, reader=_tick_file_reader):
    """The entry day's ticks joined to the next day's (a learning day is never joined to an exam day)."""
    d = pd.Timestamp(int(t_ns), tz="UTC").normalize()
    a = day_ticks(d, exam, reader)
    if a is None:
        return None
    nxt = d + pd.Timedelta(days=1)
    if not exam and nxt >= EXAM_START:
        return a
    b = day_ticks(nxt, exam, reader)
    return a if b is None else tuple(np.concatenate([x, y]) for x, y in zip(a, b, strict=True))


def label(t_ns: int) -> str:
    for k, (a, b) in PERIODS.items():
        if a.value <= t_ns < b.value:
            return k
    return ""


def trades(m: pd.DataFrame, exam: bool, reader=_tick_file_reader) -> pd.DataFrame:
    """The frozen events (streams.build) and their tick trades, for the switch's parts only."""
    import streams
    import tsim

    start, end = window(exam)
    E = streams.build(m, f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}")
    E = E[E.stream.isin(["RC", "RT_opp"])].copy()
    E = E[(E.stream == "RT_opp") | (E.win != "other")]
    E["stream"] = E.stream.replace({"RC": "RC_win"})
    E["part"] = [label(int(t)) for t in E.t_in]
    E = E[E.part.isin(parts_for(exam))].sort_values("t_in").reset_index(drop=True)
    rows = []
    cache: dict = {}
    for r in E.itertuples():
        d = pd.Timestamp(int(r.t_in), tz="UTC").normalize()
        if d not in cache:
            cache.clear()
            cache[d] = span(int(r.t_in), exam, reader)
        sp = cache[d]
        if sp is None:
            continue
        g = tsim.grid(*sp, int(r.t_in), int(r.side), float(r.stop), np.nan, int(r.t_in + r.X * MIN),
                      sides=("opp" if r.opp else "same",), stops=(1.0,), targets=(0.5 if r.opp else "orig",), tgt_r=2.0)
        if g:
            x = g[0]
            rows.append(dict(stream=r.stream, part=r.part, kind=r.kind, win=r.win, t_in=int(r.t_in), side=x["side"],
                             entry=x["entry"], risk=x["risk"], exit=x["exit"], t_exit=x["exit_t"], pnl=x["pnl"], R=x["R"]))
    return pd.DataFrame(rows)


def summary(T: pd.DataFrame) -> dict:
    """Trades, R, win (pnl > 0), the worst loss (USD at 0.01 lot = 1 oz), the longest losing streak, and the max
    drawdown of the cumulative USD from 0, in exit order."""
    if not len(T):
        return dict(n=0, R=np.nan, win=np.nan, usd=0.0, worst=0.0, streak=0, dd=0.0)
    x = T.sort_values("t_exit")
    pnl = x.pnl.to_numpy(float)
    eq = np.r_[0.0, np.cumsum(pnl)]
    dd = float(np.max(np.maximum.accumulate(eq) - eq))
    streak = run = 0
    for p in pnl:
        run = run + 1 if p <= 0 else 0
        streak = max(streak, run)
    return dict(n=len(x), R=float(x.R.mean()), win=float((x.pnl > 0).mean()), usd=float(pnl.sum()),
                worst=float(pnl.min()), streak=streak, dd=dd)


def thai_week(t_ns: pd.Series) -> pd.Series:
    th = pd.to_datetime(t_ns, utc=True).dt.tz_convert(TH).dt.tz_localize(None)
    return (th.dt.normalize() - pd.to_timedelta(th.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")


def report(T: pd.DataFrame, exam: bool) -> str:
    out = [f"exam43 - #43 RT_opp and #23 RC_win, FROZEN; {'THE EXAM 2026-04-18 .. 2026-10-17' if exam else 'learning parts'}",
           "costs: the tick spread only, slippage 0; each trade alone; USD at 0.01 lot", ""]
    for st in ("RT_opp", "RC_win"):
        for p in parts_for(exam):
            s = summary(T[(T.stream == st) & (T.part == p)])
            out.append(f"{st:7s} {p:4s} trades {s['n']:3d}  R {s['R']:+.3f}  win {s['win']:.2f}  USD {s['usd']:+8.2f}  "
                       f"worst {s['worst']:+7.2f}  losing streak {s['streak']}  max DD {s['dd']:7.2f}")
    out.append("\nweek by week (Thai weeks, Monday; by the entry): trades / R / USD")
    W = T.assign(week=thai_week(T.t_in))
    for st in ("RT_opp", "RC_win"):
        out.append(f"-- {st}")
        g = W[W.stream == st].groupby(["part", "week"])
        for (p, w), x in g:
            out.append(f"   {p:4s} {w}  {len(x):3d}  {x.R.mean():+.3f}  {x.pnl.sum():+8.2f}")
    return "\n".join(out)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument("--exam", action="store_true", help="THE MEASURER ONLY: the exam period 2026-04-18 .. 2026-10-17, once")
    return ap


def main(argv: list[str] | None = None) -> None:
    import tsim

    a = parser().parse_args(argv)
    tsim.idle()
    m = load_m1(a.exam)
    T = trades(m, a.exam)
    tag = "exam" if a.exam else "learn"
    T.to_parquet(HERE / f"exam43_trades_{tag}.parquet")
    txt = report(T, a.exam)
    if not a.exam:  # the reproduction check against the row-45 tick trades
        S = pd.read_parquet(HERE / "states_events.parquet")
        S = S[S.part.isin(["P1", "P2"]) & S.R_tk.notna()]
        S = S[(S.stream == "RT_opp") | ((S.stream == "RC") & (S.win != "other"))].copy()
        S["stream"] = S.stream.replace({"RC": "RC_win"})
        lines = ["", "reproduction against states_events.parquet (row 45, ticks):"]
        for st in ("RT_opp", "RC_win"):
            for p in ("P1", "P2"):
                a1 = T[(T.stream == st) & (T.part == p)].sort_values(["t_in", "kind"])
                b1 = S[(S.stream == st) & (S.part == p)].sort_values(["t_in", "kind"])
                same = len(a1) == len(b1) and bool((a1.t_in.to_numpy() == b1.t_in.to_numpy()).all())
                dR = float(np.max(np.abs(a1.R.to_numpy() - b1.R_tk.to_numpy()))) if same and len(a1) else np.nan
                lines.append(f"  {st:7s} {p}: {len(a1)} vs {len(b1)} trades; same entries {same}; max |dR| {dR:.2e}")
        txt += "\n" + "\n".join(lines)
    (HERE / f"out_exam43_{tag}.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
