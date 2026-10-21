"""Task B2-TF (DEV_LOG.md "Task B2-TF - written before computing"): PLAN-1's Asia B2 (variant W, 07:00-09:00 Thai) by
its entry TF (M1 / M5) over 2021-09 .. 2025-09 (whole-day ticks on D:) and P1 / P2, per year, inside / outside the
VOL-16 band; (a) the W stream split by entry TF, (b) "M5 only" (only M5 candidates enter the one-position stream).

Reads: M1 from gold.bars("M1", before=2026-04-18) (the old store joined to the main store); ticks from
D:/taa-data/ticks/XAUUSD before 2025-10-01 and data/ticks/XAUUSD from then on. Nothing at / after 2026-04-18 is read:
the M1 read is cut there and a tick day there is refused before any file is opened.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/b2_tf_history.py run YEAR [YEAR ...]   # one parquet a year
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/b2_tf_history.py selftest              # P1 + P2 = plan1's 79
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/b2_tf_history.py report
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan1 as L  # noqa: E402  (first: puts the dev, strategist and precursors folders on the path)
import plan1_forward as F  # noqa: E402
import p3_trades as T3  # noqa: E402
import patterns as P  # noqa: E402
from sweep_detector import EXAM_START, ExamPeriodError  # noqa: E402

ROOT = HERE.parents[3]
RESEARCH = HERE.parents[1]
OLD_TICKS = Path("D:/taa-data/ticks/XAUUSD")
NEW_TICKS = ROOT / "data/ticks/XAUUSD"
TICK_SWITCH = pd.Timestamp("2025-10-01", tz="UTC")  # D: before it, data/ticks from it
DAY = pd.Timedelta(days=1)
YEARS = {
    "2021-22": (pd.Timestamp("2021-09-01", tz="UTC"), pd.Timestamp("2022-09-01", tz="UTC")),
    "2022-23": (pd.Timestamp("2022-09-01", tz="UTC"), pd.Timestamp("2023-09-01", tz="UTC")),
    "2023-24": (pd.Timestamp("2023-09-01", tz="UTC"), pd.Timestamp("2024-09-01", tz="UTC")),
    "2024-25": (pd.Timestamp("2024-09-01", tz="UTC"), TICK_SWITCH),
    "P1+P2": (pd.Timestamp("2025-10-18", tz="UTC"), EXAM_START),
}
COLS = ["piece", "t_dec", "t_in", "t_out", "side", "entry", "stop", "risk", "pnl", "R", "exit"]


# ---------------------------------------------------------------- the readers
def tick_path(day: pd.Timestamp) -> Path:
    """The day's tick file: D: before 2025-10-01, data/ticks from then; a day at / after 2026-04-18 is refused."""
    day = pd.Timestamp(day)
    day = (day.tz_localize("UTC") if day.tzinfo is None else day.tz_convert("UTC")).normalize()
    if day >= EXAM_START:
        raise ExamPeriodError(f"{day:%Y-%m-%d} is at / after 2026-04-18")
    folder = OLD_TICKS if day < TICK_SWITCH else NEW_TICKS
    return folder / f"{day:%Y-%m-%d}.parquet"


def day_ticks(day: pd.Timestamp, read=pd.read_parquet) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """tick_straddle.day_ticks on tick_path: (t ns, bid, ask) in time order, None without a file."""
    f = tick_path(day)
    if not f.exists():
        return None
    x = read(f)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    o = np.argsort(t, kind="stable")
    return t[o], x.bid.to_numpy(float)[o], x.ask.to_numpy(float)[o]


def load_m1(before: pd.Timestamp = EXAM_START, bars=None) -> pd.DataFrame:
    """gold.bars('M1', before) in plan1's form (UTC open-time index, OHLC / tick_volume / spread, duplicates keep the
    last); `before` past 2026-04-18 is refused before reading, a row at / after `before` is an error."""
    if before > EXAM_START:
        raise ExamPeriodError("the M1 read may not pass 2026-04-18")
    if bars is None:
        sys.path.insert(0, str(RESEARCH))
        import gold  # noqa: PLC0415

        def bars(tf, before):
            old, new = gold.OLD, gold.NEW
            gold.OLD, gold.NEW = ROOT / old, ROOT / new  # gold's paths are relative to the repository root
            try:
                return gold.bars(tf, before=before)
            finally:
                gold.OLD, gold.NEW = old, new

    d = bars("M1", before=before)
    m = d[["open", "high", "low", "close", "tick_volume", "spread"]].copy()
    m.index = pd.DatetimeIndex(d.index).tz_convert("UTC")
    m = m[~m.index.duplicated(keep="last")].sort_index()
    m.index.name = None
    if len(m) and m.index.max() >= before:
        raise ExamPeriodError("a row at / after the cut was read")
    return m.astype(float)


# ---------------------------------------------------------------- B2 with its entry TF
def asia_b2_tf(m: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, ticks, tf_only: str | None = None,
               slip: float = 0.0) -> pd.DataFrame:
    """plan1.asia_b2 keeping each trade's entry TF; tf_only = 'M5' lets only that TF's candidates into the stream."""
    Y = P.level_inputs(m)
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    out = {}
    with L.located_in(start, end):
        for k, tf in tfs.items():
            a = int(np.searchsorted(tf.avail, start.value))
            out[k] = P.locate(tf.scan(a, len(tf.c)), tf, Y, L.EMPTY_NEWS)
    C = pd.concat([P.agree(out["M1"], out["M5"], tfs["M5"]), P.agree(out["M5"], out["M1"], tfs["M1"])], ignore_index=True)
    C = C[np.isfinite(C.entry)].reset_index(drop=True)
    cands = L.asia_candidates(T3.candidates3(C, tfs, T3.SETTINGS["B2"]))
    if tf_only is not None:
        cands = cands[cands.tf == tf_only].reset_index(drop=True)
    with L.entry_slippage(slip):
        T = T3.run_stream3(cands, tfs, ticks, np.empty(0, np.int64), 0.0, "structure")
    rows = [dict(t_dec=int(r.t_entry), t_in=int(r.entry_t), t_out=int(r.exit_t), side=int(r.side), entry=r.entry,
                 stop=r.stop, risk=r.risk, pnl=r.pnl, R=r.R, exit=r.exit, tf=r.tf) for r in T.itertuples(index=False)
            if start.value <= r.t_entry < end.value]
    X = L.piece_rows("Asia B2", rows)
    X["tf"] = [r["tf"] for r in rows] if rows else pd.Series(dtype=object)
    return X


def tiles(a: pd.Timestamp, b: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """[a, b) cut on Saturdays every four weeks (the first Saturday after a, then + 28 days)."""
    cuts = [a]
    s = a + pd.Timedelta(days=(5 - a.dayofweek) % 7 or 7)
    while s < b:
        if s > a:
            cuts.append(s)
        s += pd.Timedelta(days=28)
    return list(zip(cuts, [*cuts[1:], b], strict=True))


def run_period(m_all: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp, locate_first: pd.Timedelta = F.LOCATE_BACK,
               read=day_ticks) -> pd.DataFrame:
    """Each tile with 14 days of warm-up: (a) the W stream and (b) M5 only, with the H1 ATR at the decision."""
    out = []
    for k, (s, e) in enumerate(tiles(a, b)):
        m = m_all[(m_all.index >= s - pd.Timedelta(days=F.WARM_DAYS)) & (m_all.index < e)]
        back = locate_first if k == 0 else F.LOCATE_BACK
        av, at = F.h1_atr(m)
        for name, only in (("W", None), ("M5 only", "M5")):
            X = asia_b2_tf(m, s - back, e, F.SpanTicks(s, e, read), only)
            X = X[X.t_dec.astype(np.int64) >= s.value].copy()
            X["stream"] = name
            X["atr_h1"] = F.atr_at(av, at, X.t_dec.to_numpy(np.int64))
            X["band"] = F.in_band(X.atr_h1)
            out.append(X)
        print(f"  {s:%Y-%m-%d} .. {e:%Y-%m-%d}: W {len(out[-2])}, M5 only {len(out[-1])}", flush=True)
    T = pd.concat(out, ignore_index=True)
    for c in ("t_dec", "t_in", "t_out"):
        T[c] = T[c].astype(np.int64)
    if len(T) and ((T.t_in < a.value) | (T.t_in >= b.value)).any():
        raise ExamPeriodError("a trade outside the period")
    return T


# ---------------------------------------------------------------- the report
def stats(R: np.ndarray, pnl: np.ndarray) -> dict:
    n = len(R)
    if not n:
        return dict(n=0, R=np.nan, lo=np.nan, hi=np.nan, win=np.nan, usd=0.0)
    mean = float(np.mean(R))
    half = 1.96 * float(np.std(R, ddof=1)) / np.sqrt(n) if n > 1 else np.nan
    return dict(n=n, R=mean, lo=mean - half, hi=mean + half, win=float(np.mean(pnl > 0)), usd=float(np.sum(pnl)))


def year_of(t_ns) -> np.ndarray:
    t = np.asarray(t_ns, np.int64)
    lab = np.full(len(t), "", dtype=object)
    for y, (a, b) in YEARS.items():
        lab[(t >= a.value) & (t < b.value)] = y
    return lab


def table(T: pd.DataFrame) -> pd.DataFrame:
    """Per reading (W split by TF; M5 only), year (and pooled) and band (all / in / out): trades, R, its range, win."""
    X = T.assign(year=year_of(T.t_in))
    rows = []
    groups = [("W: M1", X[(X.stream == "W") & (X.tf == "M1")]), ("W: M5", X[(X.stream == "W") & (X.tf == "M5")]),
              ("W: all", X[X.stream == "W"]), ("M5 only", X[X.stream == "M5 only"])]
    for name, G in groups:
        for y in [*YEARS, "pooled"]:
            Gy = G if y == "pooled" else G[G.year == y]
            for band, Gb in (("all", Gy), ("in", Gy[Gy.band]), ("out", Gy[~Gy.band])):
                rows.append(dict(reading=name, year=y, band=band, **stats(Gb.R.to_numpy(float), Gb.pnl.to_numpy(float))))
    return pd.DataFrame(rows)


def verdict(Tab: pd.DataFrame) -> dict:
    """The pre-registered pass: M5 only pooled R >= +0.15 on >= 40 trades with the range above 0, and M5 better than
    the W stream's M1 in >= 3 of the 5 years; the same read on the W stream's M5 split beside it."""
    A = Tab[Tab.band == "all"].set_index(["reading", "year"])
    out = {}
    for m5 in ("M5 only", "W: M5"):
        p = A.loc[(m5, "pooled")]
        better = sum(bool(A.loc[(m5, y), "R"] > A.loc[("W: M1", y), "R"]) for y in YEARS
                     if A.loc[(m5, y), "n"] and A.loc[("W: M1", y), "n"])
        ok = bool(p.R >= 0.15 and p.n >= 40 and p.lo > 0 and better >= 3)
        out[m5] = dict(R=float(p.R), n=int(p.n), lo=float(p.lo), better_years=better, passed=ok)
    return out


# ---------------------------------------------------------------- the commands
def run(years: list[str]) -> None:
    m_all = load_m1()
    print(f"M1 {m_all.index.min()} .. {m_all.index.max()}", flush=True)
    for y in years:
        a, b = YEARS[y]
        print(f"{y}:", flush=True)
        run_period(m_all, a, b, pd.Timedelta(0) if y == "P1+P2" else F.LOCATE_BACK).to_parquet(HERE / f"b2tf_{y}.parquet")


def selftest() -> None:
    """P1 + P2 through this pipeline (gold's M1, the tick switch, the tiles) against plan1's 79 learning Asia trades."""
    T = pd.read_parquet(HERE / "b2tf_P1+P2.parquet")
    ref = pd.read_parquet(HERE / "plan1_every_learn_s0_x0.parquet")
    ref = ref[ref.piece == "Asia B2"]
    W = T[T.stream == "W"]
    eq, diff, a, b = F.same_trades(W, ref)
    print(f"the W stream against plan1's Asia trades: {eq} equal on {COLS}, {diff} differ, {a} only here, {b} only in "
          f"plan1 ({len(ref)} in plan1)")
    m = W.assign(part=[L.part_of(t) for t in W.t_in])
    print("by entry TF (learning): " + "; ".join(f"{tf} {len(g)} {g.R.mean():+.3f}" for tf, g in m.groupby("tf")))
    print(f"SELF-TEST {'PASSED' if (diff, a, b) == (0, 0, 0) and eq == len(ref) else 'FAILED'}")


def report() -> None:
    T = pd.concat([pd.read_parquet(HERE / f"b2tf_{y}.parquet") for y in YEARS], ignore_index=True)
    T.to_parquet(HERE / "b2tf_all.parquet")
    Tab = table(T)
    with open(HERE / "out_b2tf.txt", "w", encoding="utf-8") as f:
        pr = lambda s="": print(s, file=f)  # noqa: E731
        pr("Asia B2 (W, 07:00-09:00 Thai) by entry TF, spread only, slippage 0; R a trade (95 % range), win = pnl > 0, "
           "USD at 0.01 lot")
        pr("readings: 'W: M1' / 'W: M5' = the W stream split by entry TF; 'M5 only' = only M5 candidates in the stream")
        for band in ("all", "in", "out"):
            pr(f"\nthe band: {band} (VOL-16: 12.0 <= the H1 ATR at the decision < 16.0)")
            S = Tab[Tab.band == band]
            for name in S.reading.unique():
                cells = []
                for r in S[S.reading == name].itertuples():
                    cells.append(f"{r.year} {r.n:3d} {r.R:+.3f} ({r.lo:+.2f}..{r.hi:+.2f}) w{r.win:.2f}" if r.n else f"{r.year}   0")
                pr(f"  {name:8s}| " + " | ".join(cells))
        pr("\nthe pass (pooled R >= +0.15 on >= 40 trades, range above 0; better than W's M1 in >= 3 of 5 years):")
        for k, v in verdict(Tab).items():
            pr(f"  {k}: R {v['R']:+.3f} on {v['n']} trades, lower end {v['lo']:+.3f}, better in {v['better_years']} of 5 "
               f"years -> {'PASS' if v['passed'] else 'FAIL'}")
        pr("\nexits: " + str(T.groupby(["stream", "tf", "exit"]).size().to_dict()))
    Tab.to_csv(HERE / "b2tf_table.csv", index=False)
    print((HERE / "out_b2tf.txt").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    a = sys.argv[1:] if argv is None else argv
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "run":
        bad = [y for y in a[1:] if y not in YEARS]
        if bad or len(a) < 2:
            raise SystemExit(f"years: {list(YEARS)}")
        run(a[1:])
    elif a[0] == "selftest":
        selftest()
    elif a[0] == "report":
        report()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
