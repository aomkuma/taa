"""PLAN-1 forward recorder (CHECKLIST rows 46 / 55; DEV_LOG.md "Task PLAN-1 forward recorder").

PLAN-1's three pieces exactly as `plan1.py` runs them (Asia B2, the London 13:00-Thai ORB, the NY 08:30 straddle; its
functions are imported, not copied), unweighted, one position at a time, slippage 0 (spread only), on the FORWARD
period 2026-10-18 00:00 UTC (a Sunday; the first trades are on Monday 2026-10-19) .. the newest data, three variants
side by side:

- unfiltered: every trade of the three pieces;
- VOL-16: a trade only while the MT5 ATR(14) of the last CLOSED H1 bar at the decision (t_dec) is 12.0 <= ATR < 16.0
  USD (a NaN ATR: no trade);
- VOL-16b: inside the band every piece, outside it only the NY straddle.

H1 bars: the M1 store on the UTC clock (patterns.tf_bars(m, 60): an hour's bar is complete at its open + 60 min);
ATR = the simple mean of the last 14 true ranges (foundation.atr). A filtered-out trade never holds the position: each
variant filters the pieces' trades first, then keeps one position at a time (plan1.stream).

What the forward run reads (`--forward`, THE MEASURER ONLY):
- M1 bars [2026-10-18 - WARM_DAYS, end): the warm-up, WARM_DAYS = 14 calendar days of the exam period
  (2026-10-04 00:00 .. 2026-10-17 23:59 UTC, about 10 trading days) - B2's M1 / M5 ZigZag and ATR, its H1 levels (the
  last 120 complete H1 bars, the H1 fractal swings, the H1 ATR, the previous server day's high / low), the ORB's H1
  ATR and the VOL-16 H1 ATR (15 H1 bars). B2's patterns are located from 2026-10-15 00:00 UTC (LOCATE_BACK = 3 days:
  a Friday pattern may confirm on Monday's Asia open, up to 30 entry-TF bars later); a trade counts only when its
  entry decision is at / after 2026-10-18. Nothing before 2026-10-04 is read. WARM_DAYS was fixed on the learning
  parts (the self-test: the tiled runs with this warm-up reproduce plan1.py's learning trades exactly).
- ticks: only UTC days in [2026-10-18, end); a day before the forward start is never opened.
- end: the day after the newest tick file, at most today's UTC date (a day still being fetched is never read), or
  `--end YYYY-MM-DD` (exclusive).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_forward.py             # self-test, learning parts
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_forward.py --forward   # THE MEASURER ONLY
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan1 as L  # noqa: E402  (first: puts the dev, strategist and precursors folders on the path)
import d1_orb as D1  # noqa: E402
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, ExamPeriodError  # noqa: E402

DAY = pd.Timedelta(days=1)
FWD_START = L.EXAM_END  # 2026-10-18 00:00 UTC: the day after the exam
WARM_DAYS = 14  # calendar days of M1 read before a period's start (fixed on the learning parts, see the module text)
LOCATE_BACK = pd.Timedelta(days=3)  # B2's patterns located this far before the start; trades only from the start
BAND_LO, BAND_HI = 12.0, 16.0  # VOL-16: 12.0 <= the H1 ATR < 16.0
VARIANTS = ("unfiltered", "VOL-16", "VOL-16b")
COLS = ["piece", "t_dec", "t_in", "t_out", "side", "entry", "stop", "risk", "pnl", "R", "exit"]
# the self-test's tiles: Saturdays 00:00 UTC (the market is closed), so no trade or entry decision crosses a boundary
DRY_RUN = (pd.Timestamp("2026-03-07", tz="UTC"), pd.Timestamp("2026-03-14", tz="UTC"))  # a learning week, Sat .. Sat
TILES = [pd.Timestamp(x, tz="UTC") for x in ("2025-10-18", "2025-11-15", "2025-12-13", "2026-01-10", "2026-02-07",
                                              "2026-03-07", "2026-04-04", "2026-04-18")]


# ---------------------------------------------------------------- the period and what is read
def forward_end(tick_days: list[pd.Timestamp], today: pd.Timestamp, end: pd.Timestamp | None = None) -> pd.Timestamp:
    """The forward period's end (exclusive): `end` if given, else the day after the newest tick day, at most today's
    UTC date (today's file may still be filling)."""
    if end is None:
        if not tick_days:
            raise ValueError("no tick day")
        end = min(max(tick_days) + DAY, today.normalize())
    if end <= FWD_START + DAY:
        raise ValueError("the forward period has no weekday yet")
    return end


def read_m1(start: pd.Timestamp, end: pd.Timestamp, reader=None, warm_days: int = WARM_DAYS) -> pd.DataFrame:
    """M1 bars [start - warm_days, end) straight from the parquet with a row filter; a row outside it read is an
    error. In the learning parts the end may not pass 2026-04-18; a forward read starts at FWD_START."""
    if start >= FWD_START:
        if start != FWD_START:
            raise ValueError("the forward period starts on 2026-10-18")
    elif end > EXAM_START:
        raise ExamPeriodError("a learning read reaching the exam")
    lo = start - pd.Timedelta(days=warm_days)
    if reader is None:
        import pyarrow.parquet as pq  # noqa: PLC0415

        reader = pq.read_table
    cols = ["open_time", "open", "high", "low", "close", "tick_volume", "spread"]
    t = reader(P.M1_FILE, columns=cols, filters=[("open_time", ">=", lo), ("open_time", "<", end)])
    m = t.to_pandas().drop_duplicates("open_time", keep="last").set_index("open_time").sort_index()
    m.index = pd.DatetimeIndex(m.index).tz_convert("UTC")
    m.index.name = None
    if len(m) and (m.index.min() < lo or m.index.max() >= end):
        raise ExamPeriodError("a row outside [start - warm-up, end) was read")
    return m.astype(float)


class SpanTicks(L.PlanTicks):
    """plan1's tick cache, reading a UTC day only inside [start, end): a day before the start or at / after the end is
    empty and its file is never opened."""

    def __init__(self, start: pd.Timestamp, end: pd.Timestamp, read=None) -> None:
        super().__init__(end, read)
        self.start = start

    def day(self, d):
        d = pd.Timestamp(d)
        d = (d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC")).normalize()
        if d < self.start:
            return np.empty(0, np.int64), np.empty(0), np.empty(0)
        return super().day(d)


def tick_days(folder: Path) -> list[pd.Timestamp]:
    """The UTC days with a tick file (from the names only; no file is opened)."""
    out = []
    for f in folder.glob("????-??-??.parquet"):
        with contextlib.suppress(ValueError):
            out.append(pd.Timestamp(f.stem, tz="UTC"))
    return sorted(out)


# ---------------------------------------------------------------- the H1 ATR and the band
def h1_atr(m: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """The H1 bars' avail (open + 60 min, ns) and their MT5 ATR(14)."""
    b = P.tf_bars(m, 60)
    return pd.DatetimeIndex(b["avail"]).as_unit("ns").asi8, P.atr14(b)


def atr_at(avail: np.ndarray, atr: np.ndarray, t_ns) -> np.ndarray:
    """The ATR of the last H1 bar complete by each time (avail <= t); NaN before the first."""
    t = np.asarray(t_ns, np.int64)
    k = np.searchsorted(avail, t, side="right") - 1
    return np.where(k >= 0, atr[np.maximum(k, 0)], np.nan)


def in_band(a) -> np.ndarray:
    """VOL-16's band: 12.0 <= ATR < 16.0; NaN is outside."""
    a = np.asarray(a, float)
    with np.errstate(invalid="ignore"):
        return (a >= BAND_LO) & (a < BAND_HI)


def masks(T: pd.DataFrame) -> dict[str, np.ndarray]:
    band = T.band.to_numpy(bool)
    return {"unfiltered": np.ones(len(T), bool), "VOL-16": band,
            "VOL-16b": band | (T.piece.to_numpy() == "NY straddle")}


# ---------------------------------------------------------------- the pieces and the variants
def pieces(m: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, ticks, locate_back: pd.Timedelta = LOCATE_BACK,
           slip: float = 0.0, extra: float = 0.0) -> pd.DataFrame:
    """plan1's three pieces with entry decisions in [start, end): B2's patterns located from start - locate_back (a
    candidate before the start has no ticks there, so it never trades), the ORB and the straddle on the weekdays."""
    days = pd.bdate_range(start.tz_localize(None), end.tz_localize(None), inclusive="left", tz="UTC")
    asia = L.asia_b2(m, start - locate_back, end, ticks, slip)
    asia = asia[asia.t_dec.astype(np.int64) >= start.value]
    london = L.london_orb(D1.Market(m), days, ticks, slip)
    ny = L.ny_straddle(days, ticks, slip, extra)
    every = pd.concat([asia, london, ny], ignore_index=True)
    for c in ("t_dec", "t_in", "t_out"):
        every[c] = every[c].astype(np.int64)
    if len(every) and ((every.t_in < start.value) | (every.t_in >= end.value) | (every.t_dec < start.value)).any():
        raise ExamPeriodError("a trade outside the period")
    return every


def tag(every: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """Each trade's H1 ATR at its decision, the band, and which variants take it (each variant: its filter, then one
    position at a time)."""
    av, a = h1_atr(m)
    T = every.copy()
    T["atr_h1"] = atr_at(av, a, T.t_dec.to_numpy(np.int64))
    T["band"] = in_band(T.atr_h1)
    return take_variants(T)


def take_variants(T: pd.DataFrame) -> pd.DataFrame:
    """take_<variant>: the variant's filter on the band, then one position at a time among the trades left."""
    T = T.reset_index(drop=True)
    for v, k in masks(T).items():
        kept = L.stream(T[k].assign(_row=np.flatnonzero(k)))
        T[f"take_{v}"] = np.isin(np.arange(len(T)), kept._row.to_numpy())
    return T


def variant(T: pd.DataFrame, v: str) -> pd.DataFrame:
    return T[T[f"take_{v}"]].sort_values("t_in", kind="stable").reset_index(drop=True)


# ---------------------------------------------------------------- the report
def weekdays(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return len(pd.bdate_range(start.tz_localize(None), end.tz_localize(None), inclusive="left"))


def summary(T: pd.DataFrame, n_days: int) -> dict:
    """plan1.summary (unweighted) with trades a weekday over n_days."""
    s = L.summary(T)
    if s.get("n"):
        s["per_day"] = s["n"] / n_days if n_days else np.nan
    return s


def thai_week(t_ns) -> np.ndarray:
    """The Monday (Thai date) of the Thai week (Monday 00:00 .. Sunday 24:00 Thai) of each time."""
    th = pd.DatetimeIndex(pd.to_datetime(np.asarray(t_ns, np.int64), utc=True)).tz_convert("Asia/Bangkok")
    return (th.normalize() - pd.to_timedelta(th.dayofweek, unit="D")).tz_localize(None).date


def weekly(T: pd.DataFrame) -> pd.DataFrame:
    """Week by week (Thai weeks, by the fill time), per variant: trades, win (pnl > 0), R a trade, USD, running USD."""
    parts = []
    for v in VARIANTS:
        X = variant(T, v)
        if X.empty:
            continue
        g = X.assign(week=thai_week(X.t_in)).groupby("week", sort=True)
        W = pd.DataFrame({"n": g.size(), "win": g.pnl.agg(lambda x: (x > 0).mean()), "R": g.R.mean(), "usd": g.pnl.sum()})
        W["run"] = W.usd.cumsum()
        W.columns = pd.MultiIndex.from_product([[v], W.columns])
        parts.append(W)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, axis=1).sort_index()
    for v in VARIANTS:
        if (v, "n") in out:
            out[(v, "n")] = out[(v, "n")].fillna(0).astype(int)
            out[(v, "usd")] = out[(v, "usd")].fillna(0.0)
            out[(v, "run")] = out[(v, "usd")].cumsum()
    return out.round(3)


def trade_table(T: pd.DataFrame) -> pd.DataFrame:
    """Every trade any variant takes: the piece, the times (UTC and Thai), side, entry, exit price and reason, R, pnl
    at 0.01 lot (1 oz: USD = the price move), the H1 ATR at the decision, the variants taking it."""
    X = T[T[[f"take_{v}" for v in VARIANTS]].any(axis=1)].sort_values("t_in", kind="stable")

    def th(c):
        return pd.to_datetime(X[c].to_numpy(np.int64), utc=True).tz_convert("Asia/Bangkok").strftime("%m-%d %H:%M:%S")

    return pd.DataFrame({
        "piece": X.piece.to_numpy(), "decision_utc": pd.to_datetime(X.t_dec.to_numpy(np.int64), utc=True).strftime("%Y-%m-%d %H:%M"),
        "in_thai": th("t_in"), "out_thai": th("t_out"), "side": np.where(X.side > 0, "buy", "sell"),
        "entry": X.entry.round(2).to_numpy(), "exit_px": (X.entry + X.side * X.pnl).round(2).to_numpy(),
        "exit": X.exit.to_numpy(), "R": X.R.round(3).to_numpy(), "pnl": X.pnl.round(2).to_numpy(),
        "atr_h1": X.atr_h1.round(2).to_numpy(),
        "variants": [",".join(v for v in VARIANTS if r[f"take_{v}"]) for _, r in X.iterrows()]})


def variant_lines(T: pd.DataFrame, n_days: int, pr) -> None:
    for v in VARIANTS:
        X = variant(T, v)
        pr(f"  {v:10s}: {L.line(summary(X, n_days))}")
        if len(X):
            pr(f"  {'':10s}  by piece (trades, R): " + "; ".join(f"{pc} {len(g)} {g.R.mean():+.3f}"
                                                              for pc, g in X.groupby("piece")))


# ---------------------------------------------------------------- the self-test (learning parts only)
def independent_atr(m: pd.DataFrame, t_ns: np.ndarray) -> np.ndarray:
    """The H1 ATR re-derived another way (precursors/atr_winners.py's: pandas resample, the true range's three terms,
    a rolling mean), at each time from the last bar whose close <= t."""
    b = m.resample("1h", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pc = b.close.shift(1)
    tr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1)
    a = tr.rolling(14).mean()
    close_t = (b.index + pd.Timedelta(hours=1)).as_unit("ns").asi8
    i = np.searchsorted(close_t, np.asarray(t_ns, np.int64), side="right") - 1
    return np.where(i >= 0, a.to_numpy()[np.maximum(i, 0)], np.nan)


def same_trades(A: pd.DataFrame, B: pd.DataFrame) -> tuple[int, int, int, int]:
    """(in both and equal on every column, in both but different, only in A, only in B), keyed by (piece, t_in)."""
    ka = {(r.piece, int(r.t_in)): r for r in A[COLS].itertuples(index=False)}
    kb = {(r.piece, int(r.t_in)): r for r in B[COLS].itertuples(index=False)}
    both = set(ka) & set(kb)
    eq = sum(tuple(ka[k]) == tuple(kb[k]) for k in both)
    return eq, len(both) - eq, len(set(ka) - set(kb)), len(set(kb) - set(ka))


def self_test(warm_days: int = WARM_DAYS) -> None:
    m_all = L.load_m1(EXAM_START, False)  # 2025-09-01 .. 2026-04-17: the learning parts and plan1's warm-up
    out = open(HERE / f"out_plan1_forward_selftest_w{warm_days}.txt", "w", encoding="utf-8")  # noqa: SIM115
    pr = lambda s="": (print(s, file=out), print(s, flush=True))  # noqa: E731
    pr(f"PLAN-1 forward recorder, the self-test on the learning parts (warm-up {warm_days} days, locate back "
       f"{LOCATE_BACK.days} days, slippage 0)")
    tiles = []
    for k, (s, e) in enumerate(zip(TILES[:-1], TILES[1:], strict=True)):
        lo = s - pd.Timedelta(days=warm_days)
        m = m_all[(m_all.index >= lo) & (m_all.index < e)]
        back = pd.Timedelta(0) if k == 0 else LOCATE_BACK  # plan1 located from 2025-10-18 itself
        E = pieces(m, s, e, SpanTicks(s, e), back)
        E = tag(E, m)
        pr(f"  tile {s:%Y-%m-%d} .. {e:%Y-%m-%d}: M1 from {m.index.min():%Y-%m-%d %H:%M}, {len(E)} trades")
        tiles.append(E)
    T = pd.concat(tiles, ignore_index=True)
    T["part"] = [L.part_of(t) for t in T.t_in]
    ref_every = pd.read_parquet(HERE / "plan1_every_learn_s0_x0.parquet")
    ref_plan = pd.read_parquet(HERE / "plan1_trades_learn_s0_x0.parquet")
    eq, diff, only_t, only_r = same_trades(T, ref_every)
    pr(f"\n(1) every piece's trades against plan1_every_learn_s0_x0.parquet: {eq} equal on {COLS}, {diff} differ, "
       f"{only_t} only here, {only_r} only in plan1 ({len(ref_every)} in plan1)")
    U = variant(T, "unfiltered")
    eq, diff, only_t, only_r = same_trades(U, ref_plan)
    pr(f"(2) the unfiltered plan (one position at a time) against plan1_trades_learn_s0_x0.parquet: {eq} equal, {diff} "
       f"differ, {only_t} only here, {only_r} only in plan1 ({len(ref_plan)} in plan1)")
    # the ATR: the short warm-up against the full series, and against the independent re-derivation
    av, a = h1_atr(m_all)
    full = atr_at(av, a, T.t_dec.to_numpy(np.int64))
    ind = independent_atr(m_all, T.t_dec.to_numpy(np.int64))
    pr(f"(3) the H1 ATR at the decisions: the tiles' (short warm-up) equal to the full series on "
       f"{int(np.sum(np.isclose(T.atr_h1, full, rtol=0, atol=1e-9)))} of {len(T)}; to the re-derivation (resample) on "
       f"{int(np.sum(np.isclose(T.atr_h1, ind, rtol=0, atol=1e-9)))} of {len(T)}; NaN {int(np.isnan(T.atr_h1).sum())}")
    V = variant(T, "VOL-16")
    kept_band = bool(V.band.all())
    want = L.stream(T[T.band])
    eq, diff, only_t, only_r = same_trades(V, want)
    inter = U[U.band]
    eq2, diff2, only_v, only_u = same_trades(V, inter)
    pr(f"(4) VOL-16: {len(V)} trades, all in the band: {kept_band}; equal to the in-band trades streamed: {eq} equal, "
       f"{diff} differ, {only_t} / {only_r} on one side only; against the unfiltered plan's in-band trades "
       f"({len(inter)}): {eq2} equal, {only_v} only in VOL-16, {only_u} only in the plan")
    Vb = variant(T, "VOL-16b")
    nb = Vb[~Vb.band]
    pr(f"(5) VOL-16b: {len(Vb)} trades; outside the band {len(nb)}, all the NY straddle: {bool((nb.piece == 'NY straddle').all())}; "
       f"in the band {int(Vb.band.sum())}")
    t_in_band = in_band(atr_at(av, a, T.t_in.to_numpy(np.int64)))
    pr(f"(6) the band read at the fill (t_in) instead of the decision differs on {int(np.sum(t_in_band != T.band))} of "
       f"{len(T)} trades (the measurer's atr_winners.py reads at t_in)")
    for p in ("P1", "P2"):
        X = U[U.part == p]
        pr(f"    {p}: the unfiltered plan's trades in the band, read at the decision {int(X.band.sum())}, at the fill "
           f"{int(in_band(atr_at(av, a, X.t_in.to_numpy(np.int64))).sum())}")
    pr("\nthe variants per part (seen data: the band was chosen after these parts; not evidence):")
    for p in ("P1", "P2"):
        pr(f" {p}:")
        variant_lines(T[T.part == p], L.weekdays(p), pr)
    T.to_parquet(HERE / f"plan1_forward_selftest_w{warm_days}.parquet")
    # the dry run: forward() itself (its reader, tick cache, warm-up check, report) on one learning week
    a, b = DRY_RUN
    D = forward(b, a, tag_name="plan1_forward_dryrun")
    W = T[(T.t_in >= a.value) & (T.t_in < b.value)]
    dry = same_trades(D, W)
    takes = all(sorted(D[D[f"take_{v}"]].t_in) == sorted(W[W[f"take_{v}"]].t_in) for v in VARIANTS)
    pr(f"\n(7) the dry run of forward() on {a:%Y-%m-%d} .. {b:%Y-%m-%d} (out_plan1_forward_dryrun.txt): {dry[0]} trades "
       f"equal to the tiles', {dry[1]} differ, {dry[2]} / {dry[3]} on one side only; the variants take the same trades: {takes}")
    ok = (same_trades(T, ref_every)[1:] == (0, 0, 0) and same_trades(U, ref_plan)[1:] == (0, 0, 0) and kept_band
          and same_trades(V, want)[1:] == (0, 0, 0) and dry[1:] == (0, 0, 0) and dry[0] == len(W) > 0 and takes)
    pr(f"\nSELF-TEST {'PASSED' if ok else 'FAILED'}")
    out.close()


# ---------------------------------------------------------------- the forward run (the measurer only)
def forward(end: pd.Timestamp | None = None, start: pd.Timestamp = FWD_START, today: pd.Timestamp | None = None,
            out_dir: Path = HERE, tag_name: str = "plan1_forward", reader=None, read_ticks=None) -> pd.DataFrame:
    """The forward record: the three pieces in [start, end), the variants, the report (out_<tag_name>.txt) and every
    trade (<tag_name>_trades.parquet). The measurer's run uses the defaults; the self-test's dry run passes a
    learning week (read_m1 then refuses anything past 2026-04-18)."""
    from tick_straddle import TICKS  # noqa: PLC0415

    if start != FWD_START and end is None:
        raise ValueError("a dry run needs its end")
    names = tick_days(TICKS)
    if end is None:
        if today is None:
            import datetime as dt  # noqa: PLC0415

            today = pd.Timestamp(dt.datetime.now(dt.UTC))
        end = forward_end(names, today)
    elif start == FWD_START:
        end = forward_end([], start, end)
    m = read_m1(start, end, reader)
    T = tag(pieces(m, start, end, SpanTicks(start, end, read_ticks)), m)
    T["part"] = tag_name
    # the warm-up check on the same read: 3 days less warm-up must give the same trades
    m3 = m[m.index >= start - pd.Timedelta(days=WARM_DAYS - 3)]
    conv = same_trades(T, tag(pieces(m3, start, end, SpanTicks(start, end, read_ticks)), m3))
    n_days = weekdays(start, end)
    T.to_parquet(out_dir / f"{tag_name}_trades.parquet")
    with open(out_dir / f"out_{tag_name}.txt", "w", encoding="utf-8") as f:
        pr = lambda s="": print(s, file=f)  # noqa: E731
        pr(f"PLAN-1 forward recorder ({tag_name}), {start:%Y-%m-%d} .. {end - DAY:%Y-%m-%d} ({n_days} weekdays), "
           f"spread only, slippage 0, unweighted, one position at a time")
        wd = pd.bdate_range(start.tz_localize(None), (end - DAY).tz_localize(None), tz="UTC")  # end excluded
        missing = [f"{d:%m-%d}" for d in wd if d not in set(names)]
        pr(f"tick files for {len(wd) - len(missing)} of {len(wd)} weekdays" + (f"; missing {missing}" if missing else ""))
        if len(m):
            pr(f"read: M1 {m.index.min():%Y-%m-%d %H:%M} .. {m.index.max():%Y-%m-%d %H:%M} UTC (asked from "
               f"{start - pd.Timedelta(days=WARM_DAYS):%Y-%m-%d}); tick days only in {start:%Y-%m-%d} .. {end - DAY:%Y-%m-%d}")
            if m.index.max() < end - DAY:
                pr(f"NOTE: the M1 store ends at {m.index.max():%Y-%m-%d %H:%M} UTC, more than a day before the period's end")
        pr(f"the warm-up check ({WARM_DAYS - 3} instead of {WARM_DAYS} days): {conv[0]} trades equal, {conv[1]} differ, "
           f"{conv[2]} / {conv[3]} on one side only")
        pr("\nthe variants (the judge: after >= 60 trades, >= +0.15 R a trade and VOL-16 better than unfiltered on the "
           "same days):")
        variant_lines(T, n_days, pr)
        with pd.option_context("display.width", 250, "display.max_rows", 2000, "display.max_columns", 40):
            pr("\nweek by week (Thai weeks, by the fill time; n, win, R a trade, USD, running USD):")
            pr(weekly(T).to_string())
            pr("\nevery trade any variant takes (in / out in Thai time, the decision in UTC; pnl in USD at 0.01 lot):")
            pr(trade_table(T).to_string(index=False))
    print((out_dir / f"out_{tag_name}.txt").read_text(encoding="utf-8"))
    return T


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--forward", action="store_true", help="THE MEASURER ONLY: the forward period from 2026-10-18")
    ap.add_argument("--end", type=str, default=None, help="the forward period's end, YYYY-MM-DD, exclusive")
    ap.add_argument("--warm-days", type=int, default=WARM_DAYS, help="the self-test's warm-up (the forward run's is fixed)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    a = parse(argv)
    if a.forward:
        if a.warm_days != WARM_DAYS:
            raise SystemExit("the forward run's warm-up is fixed")
        forward(None if a.end is None else pd.Timestamp(a.end, tz="UTC"))
        return
    if a.end is not None:
        raise SystemExit("--end is for --forward only")
    self_test(a.warm_days)


if __name__ == "__main__":
    main()
