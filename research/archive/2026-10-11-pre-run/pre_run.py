"""Pre-run price behaviour, part 1: what happens before real runs (SETUP_REVIEW §12; owner, 2026-10-09).

Descriptive, independent of any setup. Pre-registered definitions (2026-10-11), per entry-timeframe bar t:

- **run up at t**: from close[t], within RUN_BARS bars the high reaches close + RUN_ATR x ATR before the low
  reaches close - STOP_ATR x ATR (a 1-ATR-stop trade entered at the close would make RUN_ATR R). Run down
  mirrored. A bar touching both levels counts as no run (conservative). ATR = 14-bar mean true range at t.
- **precursors** in the LOOK bars ending at t, against the REF bars before them (levels known at t):
  - ``sweep``: the window traded beyond the reference extreme on the side *against* the run, and close[t] is
    back inside (a sweep of the low before a run up);
  - ``false_break``: a close beyond the reference extreme on the run's side, then a close back inside
    (a break-and-shake before the run in the same direction);
  - ``compression``: the window's range in ATR is in the lowest fifth of the symbol's past 500 windows.
- **time buckets** in New York time (DST-aware): rollover (17:00-20:00, the illiquid early Asian morning),
  asia (20:00-02:00), london_open (02:00-04:00), london (04:00-08:00), pre_ny (08:00-09:30),
  ny_open (09:30-11:30), ny_late (11:30-17:00). ``pre_news``: the 60 minutes before 08:30 or 10:00 New York
  time on weekdays (a proxy: the scheduled US release slots; no historical calendar exists here).

Prints, per timeframe: run base rates; P(run | precursor) and its lift over the base per side, both halves;
the share of runs preceded by each precursor; false breaks (close back inside within 12 bars) per bucket;
depth and age of the sweeps before runs. Hypothetical, bar-based; no costs (no trades are simulated here).

    .venv/Scripts/python research/2026-10-11-pre-run/pre_run.py [M15 H1]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HIST = Path("data/history/FBS-Demo")
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD"]
START, END = pd.Timestamp("2025-10-15", tz="UTC"), pd.Timestamp("2026-10-05", tz="UTC")
SPLIT = pd.Timestamp("2026-04-01", tz="UTC")
ATR_BARS, RUN_BARS, RUN_ATR, STOP_ATR = 14, 16, 3.0, 1.0
LOOK, REF, FB_BARS = 8, 20, 12
BUCKETS = [  # New York minutes from midnight, [start, end)
    ("rollover", 17 * 60, 20 * 60),
    ("asia", 20 * 60, 26 * 60),
    ("london_open", 2 * 60, 4 * 60),
    ("london", 4 * 60, 8 * 60),
    ("pre_ny", 8 * 60, 9 * 60 + 30),
    ("ny_open", 9 * 60 + 30, 11 * 60 + 30),
    ("ny_late", 11 * 60 + 30, 17 * 60),
]
NEWS_SLOTS = (8 * 60 + 30, 10 * 60)


def bucket_of(ny_min: np.ndarray) -> np.ndarray:
    out = np.full(len(ny_min), "", dtype=object)
    for name, a, b in BUCKETS:
        if b > 24 * 60:
            m = (ny_min >= a) | (ny_min < b - 24 * 60)
        else:
            m = (ny_min >= a) & (ny_min < b)
        out[m] = name
    return out


def features(df: pd.DataFrame) -> pd.DataFrame:
    """One row per bar t (decided at close[t]); forward columns describe what came after t."""
    h, lo, c = (df[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    n = len(df)
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum.reduce([h - lo, np.abs(h - prev), np.abs(lo - prev)])
    atr = pd.Series(tr).rolling(ATR_BARS).mean().to_numpy()

    # forward: run up / down within RUN_BARS (first-touch order on the bars after t)
    run_up = np.zeros(n, dtype=bool)
    run_dn = np.zeros(n, dtype=bool)
    for i in range(n - RUN_BARS):
        a = atr[i]
        if not a > 0:
            continue
        up, dn = c[i] + RUN_ATR * a, c[i] - RUN_ATR * a
        su, sd = c[i] - STOP_ATR * a, c[i] + STOP_ATR * a
        hh, ll = h[i + 1 : i + 1 + RUN_BARS], lo[i + 1 : i + 1 + RUN_BARS]
        # up run: first bar with high >= up, no earlier (or same) bar with low <= su
        k_up = np.argmax(hh >= up) if (hh >= up).any() else -1
        k_su = np.argmax(ll <= su) if (ll <= su).any() else RUN_BARS
        run_up[i] = k_up >= 0 and k_up < k_su
        k_dn = np.argmax(ll <= dn) if (ll <= dn).any() else -1
        k_sd = np.argmax(hh >= sd) if (hh >= sd).any() else RUN_BARS
        run_dn[i] = k_dn >= 0 and k_dn < k_sd

    # backward: the LOOK window ending at t against the REF bars before it
    hs, ls, cs = pd.Series(h), pd.Series(lo), pd.Series(c)
    ref_hi = hs.shift(LOOK).rolling(REF).max().to_numpy()
    ref_lo = ls.shift(LOOK).rolling(REF).min().to_numpy()
    win_hi = hs.rolling(LOOK).max().to_numpy()
    win_lo = ls.rolling(LOOK).min().to_numpy()
    sweep_lo = (win_lo < ref_lo) & (c > ref_lo)  # took the lows, back above: precursor of a run UP
    sweep_hi = (win_hi > ref_hi) & (c < ref_hi)  # took the highs, back below: precursor of a run DOWN
    # false break in the run's direction: a close above ref_hi inside the window, then a close back below
    above = cs.gt(pd.Series(ref_hi)).astype(float)
    below = cs.lt(pd.Series(ref_lo)).astype(float)
    fb_up = (above.rolling(LOOK).max().to_numpy() > 0) & (c <= ref_hi)
    fb_dn = (below.rolling(LOOK).max().to_numpy() > 0) & (c >= ref_lo)
    win_rng = (win_hi - win_lo) / atr
    comp = pd.Series(win_rng).rolling(500, min_periods=200).rank(pct=True).to_numpy() <= 0.2
    # sweep depth (ATR beyond the reference) and age (bars since the sweep extreme) for sweeps before runs
    lo_arg = ls.rolling(LOOK).apply(lambda x: LOOK - 1 - int(np.argmin(x)), raw=True).to_numpy()
    hi_arg = hs.rolling(LOOK).apply(lambda x: LOOK - 1 - int(np.argmax(x)), raw=True).to_numpy()
    # false break after a break (close back inside within FB_BARS): every first close beyond the reference
    brk_up = (c > ref_hi) & ~(np.concatenate([[False], (c > ref_hi)[:-1]]))
    brk_dn = (c < ref_lo) & ~(np.concatenate([[False], (c < ref_lo)[:-1]]))
    back_up = np.zeros(n, dtype=bool)
    back_dn = np.zeros(n, dtype=bool)
    for i in np.nonzero(brk_up)[0]:
        back_up[i] = (c[i + 1 : i + 1 + FB_BARS] < ref_hi[i]).any()
    for i in np.nonzero(brk_dn)[0]:
        back_dn[i] = (c[i + 1 : i + 1 + FB_BARS] > ref_lo[i]).any()

    t = pd.DatetimeIndex(df["close_time"])
    ny = t.tz_convert("America/New_York")
    ny_min = (ny.hour * 60 + ny.minute).to_numpy()
    weekday = ny.weekday.to_numpy() < 5
    pre_news = np.zeros(n, dtype=bool)
    for slot in NEWS_SLOTS:
        pre_news |= weekday & (ny_min >= slot - 60) & (ny_min < slot)
    return pd.DataFrame(
        {
            "t": t,
            "atr": atr,
            "run_up": run_up,
            "run_dn": run_dn,
            "sweep_lo": sweep_lo,
            "sweep_hi": sweep_hi,
            "fb_up": fb_up,
            "fb_dn": fb_dn,
            "comp": comp,
            "depth_lo": (ref_lo - win_lo) / atr,
            "depth_hi": (win_hi - ref_hi) / atr,
            "age_lo": lo_arg,
            "age_hi": hi_arg,
            "brk_up": brk_up,
            "brk_dn": brk_dn,
            "back_up": back_up,
            "back_dn": back_dn,
            "bucket": bucket_of(ny_min),
            "pre_news": pre_news,
        }
    )


def shuffled(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """The random-walk baseline: the same bars in a random order (each bar's close-to-close return and its
    high/low/open offsets from the close kept), the timestamps unchanged. Destroys any sequence structure."""
    rng = np.random.default_rng(seed)
    c = df["close"].to_numpy(dtype=float)
    ret = np.diff(np.log(c), prepend=np.log(c[0]))
    off = {k: df[k].to_numpy(dtype=float) - c for k in ("open", "high", "low")}
    order = rng.permutation(len(df))
    close = c[0] * np.exp(np.cumsum(ret[order]))
    out = df.copy()
    out["close"] = close
    for k, v in off.items():
        out[k] = close + v[order]
    return out


def load(tf: str, baseline: bool = False) -> pd.DataFrame:
    frames = []
    for i, sym in enumerate(SYMBOLS):
        df = pd.read_parquet(HIST / sym / f"{tf}.parquet").sort_values("open_time").reset_index(drop=True)
        if baseline:
            df = shuffled(df, seed=i)
        f = features(df)
        f["symbol"] = sym
        frames.append(f[(f["t"] >= START) & (f["t"] < END) & f["atr"].gt(0)])
    return pd.concat(frames, ignore_index=True)


def pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def side_table(d: pd.DataFrame) -> None:
    """Both sides pooled: (run, precursor) pairs for up runs and down runs."""
    pairs = {
        "sweep of the other side": (("run_up", "sweep_lo"), ("run_dn", "sweep_hi")),
        "false break, same side": (("run_up", "fb_up"), ("run_dn", "fb_dn")),
        "compression": (("run_up", "comp"), ("run_dn", "comp")),
    }
    print(f"  {'precursor':26} {'P(pre)':>7} {'P(run|pre)':>10} {'base':>6} {'lift':>5} "
          f"{'H1 lift':>7} {'H2 lift':>7} {'runs w/ pre':>11}")
    for name, sides in pairs.items():
        runs = pre = both = 0
        halves = {True: [0, 0, 0, 0], False: [0, 0, 0, 0]}  # runs, pre, both, bars
        for run_col, pre_col in sides:
            r, p = d[run_col].to_numpy(), d[pre_col].to_numpy()
            runs += r.sum()
            pre += p.sum()
            both += (r & p).sum()
            first = (d["t"] < SPLIT).to_numpy()
            for flag in (True, False):
                m = first == flag
                halves[flag][0] += r[m].sum()
                halves[flag][1] += p[m].sum()
                halves[flag][2] += (r[m] & p[m]).sum()
                halves[flag][3] += m.sum()
        bars = 2 * len(d)
        base = runs / bars
        cond = both / pre if pre else float("nan")
        lifts = []
        for flag in (True, False):
            hr, hp, hb, hn = halves[flag]
            lifts.append((hb / hp) / (hr / hn) if hp and hr else float("nan"))  # hn counts both sides
        print(
            f"  {name:26} {pct(pre / bars):>7} {pct(cond):>10} {pct(base):>6} {cond / base:5.2f} "
            f"{lifts[0]:7.2f} {lifts[1]:7.2f} {pct(both / runs):>11}"
        )


def main(tfs: list[str]) -> None:
    for tf, baseline in [(tf, b) for tf in tfs for b in (False, True)]:
        d = load(tf, baseline)
        label = "RANDOM-WALK BASELINE (shuffled bars)" if baseline else "market"
        print(f"\n===== {tf} {label}: {len(d):,} bars, 8 symbols, {START.date()} .. {END.date()} =====")
        print(f"run = +{RUN_ATR:g} ATR within {RUN_BARS} bars before -{STOP_ATR:g} ATR; precursors over the last "
              f"{LOOK} bars vs the {REF} before them")
        base = (d["run_up"].mean() + d["run_dn"].mean()) / 2
        print(f"base: run up {pct(d['run_up'].mean())}, run down {pct(d['run_dn'].mean())} of bars")
        print("\nall hours")
        side_table(d)
        print("\nper time bucket (New York time): run rate, false breaks, and the precursor lifts")
        print(f"  {'bucket':12} {'bars':>7} {'run/bar':>7} {'breaks':>6} {'back in 12':>10} "
              f"{'sweep lift':>10} {'fb lift':>8} {'comp lift':>9} {'back H1/H2':>13}")
        groups = [(b, d[d["bucket"] == b]) for b, _, _ in BUCKETS] + [("pre_news", d[d["pre_news"]])]
        for name, g in groups:
            if g.empty:
                continue
            rate = (g["run_up"].mean() + g["run_dn"].mean()) / 2
            brk = g["brk_up"].sum() + g["brk_dn"].sum()
            back = (g["back_up"] & g["brk_up"]).sum() + (g["back_dn"] & g["brk_dn"]).sum()

            def lift(a: str, b: str, c_: str, e: str, g: pd.DataFrame = g, rate: float = rate) -> float:
                hit = (g[a] & g[b]).sum() + (g[c_] & g[e]).sum()
                n = g[b].sum() + g[e].sum()
                return (hit / n) / rate if n and rate else float("nan")

            print(
                f"  {name:12} {len(g):>7,} {pct(rate):>7} {brk:>6,} {pct(back / brk if brk else np.nan):>10} "
                f"{lift('run_up', 'sweep_lo', 'run_dn', 'sweep_hi'):10.2f} "
                f"{lift('run_up', 'fb_up', 'run_dn', 'fb_dn'):8.2f} "
                f"{lift('run_up', 'comp', 'run_dn', 'comp'):9.2f} "
                + "/".join(
                    pct(
                        ((h["back_up"] & h["brk_up"]).sum() + (h["back_dn"] & h["brk_dn"]).sum())
                        / max(1, h["brk_up"].sum() + h["brk_dn"].sum())
                    ).strip()
                    for h in (g[g["t"] < SPLIT], g[g["t"] >= SPLIT])
                )
            )
        up = d[d["run_up"] & d["sweep_lo"]]
        dn = d[d["run_dn"] & d["sweep_hi"]]
        depth = np.concatenate([up["depth_lo"].to_numpy(), dn["depth_hi"].to_numpy()])
        age = np.concatenate([up["age_lo"].to_numpy(), dn["age_hi"].to_numpy()])
        print(f"\nsweeps before runs: n={len(depth):,}; depth beyond the reference "
              f"median {np.nanmedian(depth):.2f} ATR (p75 {np.nanpercentile(depth, 75):.2f}); "
              f"bars since the sweep extreme median {np.nanmedian(age):.0f} (p75 {np.nanpercentile(age, 75):.0f})")
        print(f"base run rate both sides averaged: {pct(base)}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["M15", "H1"])
