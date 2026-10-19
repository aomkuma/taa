"""A second, separate check of P2's numbers (owner, 13:37 Thai: "beware of interpreting correctly while the metric is
wrong"). It does NOT import p2_trades (nor sweep_detector / tick_straddle): it reads p2_trades.parquet, p2_metrics.csv
and the raw tick files, and

1. recomputes every reported metric per variant x part x news cost with its own plain loops and asserts it agrees with
   p2_metrics.csv: the count and trades a weekday, win %, R (from the fill's risk) and USD, the 95 % range, the max
   drawdown on the cumulative USD, the worst trade, the longest losing streak, the exit counts;
2. re-derives a seeded sample of 20 trades a variant (news cost 0) from the raw ticks: the fill tick and price with the
   0.07 slippage, no tick past the stop between the fill and the exit, the exit tick and price for its reason, the USD
   and the R;
3. checks one position at a time (no entry before the previous exit) in every variant x cost.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/verify_p2.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TICKS = HERE.parents[3] / "data/ticks/XAUUSD"
EXAM = pd.Timestamp("2026-04-18", tz="UTC")
SLIP = 0.07
GAP = 30 * 60 * 10**9
PART_DAYS = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}


def weekdays(a: str, b: str) -> int:
    """Mon-Fri days in [a, b), counted one by one."""
    d, end, n = pd.Timestamp(a), pd.Timestamp(b), 0
    while d < end:
        n += d.weekday() < 5
        d += pd.Timedelta(days=1)
    return n


def metrics(rows: list[dict], part: str) -> dict:
    """The metrics of one trade list, plain loops; rows need entry_t, side, entry, stop, pnl, exit."""
    rows = sorted(rows, key=lambda r: r["entry_t"])
    n = len(rows)
    rs = [r["pnl"] / (r["side"] * (r["entry"] - r["stop"])) for r in rows]
    mean = sum(rs) / n
    var = sum((x - mean) ** 2 for x in rs) / (n - 1) if n > 1 else float("nan")
    half = 1.96 * math.sqrt(var) / math.sqrt(n) if n > 1 else float("nan")
    cum, peak, dd = 0.0, 0.0, 0.0
    for r in rows:
        cum += r["pnl"]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    best, best_usd, run, run_usd = 0, 0.0, 0, 0.0
    for r in rows:
        if r["pnl"] < 0:
            run, run_usd = run + 1, run_usd + r["pnl"]
            if run > best or (run == best and run_usd < best_usd):
                best, best_usd = run, run_usd
        else:
            run, run_usd = 0, 0.0
    out = dict(n=n, per_day=n / weekdays(*PART_DAYS[part]), win=sum(r["pnl"] > 0 for r in rows) / n, R=mean,
               R_lo=mean - half, R_hi=mean + half, usd=sum(r["pnl"] for r in rows), dd=dd,
               worst=min(r["pnl"] for r in rows), streak=best, streak_usd=best_usd)
    for e in ("stop", "target", "structure", "time", "break"):
        out[f"x_{e}"] = sum(r["exit"] == e for r in rows)
    return out


def raw_ticks(day: pd.Timestamp) -> pd.DataFrame:
    if day >= EXAM:
        return pd.DataFrame(columns=["t", "bid", "ask"])
    f = TICKS / f"{day:%Y-%m-%d}.parquet"
    if not f.exists():
        return pd.DataFrame(columns=["t", "bid", "ask"])
    x = pd.read_parquet(f)
    t = pd.to_datetime(x.time_utc, utc=True).dt.as_unit("ns").astype("int64")  # the files hold milliseconds
    x = pd.DataFrame(dict(t=t, bid=x.bid, ask=x.ask))
    return x.sort_values("t", kind="stable").reset_index(drop=True)


def rederive(tr: dict, tk: pd.DataFrame) -> list[str]:
    """The problems found re-deriving one trade from the raw ticks (an empty list = it agrees)."""
    bad = []
    side, t, bid, ask = tr["side"], tk.t.tolist(), tk.bid.tolist(), tk.ask.tolist()
    f = next((i for i, v in enumerate(t) if v >= tr["t_entry"]), None)
    if f is None or t[f] != tr["entry_t"]:
        return ["the fill tick"]
    want = ask[f] + SLIP if side > 0 else bid[f] - SLIP
    if abs(want - tr["entry"]) > 1e-9:
        bad.append("the fill price")
    x = next((i for i in range(f, len(t)) if t[i] == tr["exit_t"]), None)
    if x is None:
        return [*bad, "the exit tick"]
    mkt = bid if side > 0 else ask
    past = [i for i in range(f + 1, x) if (mkt[i] <= tr["stop"] if side > 0 else mkt[i] >= tr["stop"])]
    if past:
        bad.append("a tick past the stop before the exit")
    why, px = tr["exit"], tr["exit_px"]
    if why == "stop":
        if not ((mkt[x] <= tr["stop"]) if side > 0 else (mkt[x] >= tr["stop"])) or abs(px - mkt[x]) > 1e-9:
            bad.append("the stop's tick / price")
    elif why == "target":
        tg = tr["target"]
        hit = [i for i in range(f + 1, x + 1) if (mkt[i] >= tg if side > 0 else mkt[i] <= tg)]
        if not hit or hit[0] != x or abs(px - tg) > 1e-9:
            bad.append("the target's tick / price")
    else:
        if abs(px - mkt[x]) > 1e-9:
            bad.append("the market exit price")
        if why == "time" and not (t[x] >= tr["t_limit"] and t[x - 1] < tr["t_limit"]):
            bad.append("the time exit tick")
        if why == "structure" and not (t[x] >= tr["t_struct"] and t[x - 1] < tr["t_struct"]):
            bad.append("the structure exit tick")
        if why == "break" and not (x == len(t) - 1 or t[x + 1] - t[x] > GAP):
            bad.append("the break tick")
    usd = side * (px - tr["entry"])
    if abs(usd - tr["pnl"]) > 1e-9 or abs(usd / (side * (tr["entry"] - tr["stop"])) - tr["R"]) > 1e-9:
        bad.append("the USD / R")
    return bad


def one_at_a_time(rows: list[dict]) -> int:
    """How many entries come before the previous trade's exit (0 = one position at a time holds)."""
    rows = sorted(rows, key=lambda r: r["entry_t"])
    return sum(rows[i]["entry_t"] < rows[i - 1]["exit_t"] for i in range(1, len(rows)))


def main() -> None:
    A = pd.read_parquet(HERE / "p2_trades.parquet")
    M = pd.read_csv(HERE / "p2_metrics.csv")
    keys = ["n", "per_day", "win", "R", "R_lo", "R_hi", "usd", "dd", "worst", "streak", "streak_usd", "x_stop", "x_target",
            "x_structure", "x_time", "x_break"]
    agree = total = 0
    for m in M.itertuples(index=False):
        rows = A[(A.variant == m.variant) & (A.part == m.part) & (A.news_cost == m.news_cost)].to_dict("records")
        mine = metrics(rows, m.part)
        for k in keys:
            total += 1
            a, b = mine[k], getattr(m, k)
            ok = (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1.0, abs(a))
            agree += ok
            if not ok:
                print(f"  DIFFERENT {m.variant} {m.part} +{m.news_cost} {k}: {a} vs {b}")
    print(f"1. the metrics recomputed: {agree} of {total} values agree ({len(M)} variant x part x cost rows x {len(keys)})")
    rng = random.Random(20261019)
    days: dict = {}
    good = n = 0
    for v in ("A", "B1", "B2"):
        rows = A[(A.variant == v) & (A.news_cost == 0.0)].to_dict("records")
        for tr in rng.sample(rows, 20):
            d = pd.Timestamp(tr["entry_t"], tz="UTC").normalize()
            for dd in (d, d + pd.Timedelta(days=1)):
                if dd not in days:
                    days[dd] = raw_ticks(dd)
            tk = pd.concat([days[d], days[d + pd.Timedelta(days=1)]], ignore_index=True)
            bad = rederive(tr, tk)
            n += 1
            good += not bad
            if bad:
                print(f"  {v} {pd.Timestamp(tr['entry_t'], tz='UTC')}: {bad}")
    print(f"2. trades re-derived from the raw ticks: {good} of {n} agree (20 a variant)")
    over = {(v, c): one_at_a_time(G.to_dict("records")) for (v, c), G in A.groupby(["variant", "news_cost"])}
    print(f"3. one position at a time: entries before the previous exit {sum(over.values())} in {len(over)} variant x cost "
          f"streams ({sum(len(G) for _, G in A.groupby(['variant', 'news_cost']))} trades)")
    if agree != total or good != n or sum(over.values()):
        raise SystemExit("VERIFICATION FAILED")
    print("PASSED")


if __name__ == "__main__":
    main()
