"""LV3 walk-forward (notes.md "LV3 walk-forward"): every month the cell with the best mean R over the previous six
months' trades is used for that month; learning and testing in one run.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/precursors/wf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def walk_forward(cells: dict[str, pd.DataFrame], first_month: str, last_month: str, lookback: int = 6,
                 min_trades: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """cells: name -> trades with t (open, UTC), x_t (exit time), R, pnl. For each month from first_month to
    last_month: the cell with the best mean R over the trades OPENED in the previous `lookback` months AND already
    closed by the month's start (known to the bot); >= min_trades, else the previous choice stays. The month's trades
    = that cell's trades opening in the month, skipping any that opens before the previous taken trade has closed."""
    months = pd.period_range(first_month, last_month, freq="M")
    chosen, rows, taken = None, [], []
    last_exit = pd.Timestamp.min.tz_localize("UTC")
    for mo in months:
        start = mo.start_time.tz_localize("UTC")
        end = (mo + 1).start_time.tz_localize("UTC")
        lb = (mo - lookback).start_time.tz_localize("UTC")
        best, best_r = None, -np.inf
        for name, T in cells.items():
            past = T[(T.t >= lb) & (T.t < start) & (T.x_t <= start)]
            if len(past) >= min_trades and past.R.mean() > best_r:
                best, best_r = name, past.R.mean()
        if best is not None:
            chosen = best
        if chosen is None:
            rows.append(dict(month=str(mo), cell=None, past_R=np.nan, trades=0))
            continue
        T = cells[chosen]
        cur = T[(T.t >= start) & (T.t < end)].sort_values("t")
        keep = []
        for r in cur.itertuples():
            if r.t < last_exit:
                continue
            keep.append(r.Index)
            last_exit = r.x_t
        got = cur.loc[keep].assign(cell=chosen, month=str(mo))
        taken.append(got)
        rows.append(dict(month=str(mo), cell=chosen, past_R=round(best_r, 3) if best is not None else np.nan,
                         trades=len(got), win=round((got.pnl > 0).mean(), 3) if len(got) else np.nan,
                         R=round(got.R.mean(), 3) if len(got) else np.nan, usd=round(got.pnl.sum(), 1)))
    return (pd.concat(taken) if taken else pd.DataFrame()), pd.DataFrame(rows)


def weekly(T: pd.DataFrame) -> pd.DataFrame:
    """The owner's report (2026-10-18: "report it week by week"): trades grouped by the Thai week (Monday 00:00 ..
    Sunday 24:00 Thai, so a trading week - Monday morning to the Saturday-morning New York close - is one row):
    the settings used, trades, win %, R a trade, R, USD, running USD, the worst trade."""
    th = pd.DatetimeIndex(T.t).tz_convert("Asia/Bangkok")
    wk = (th.normalize() - pd.to_timedelta(th.dayofweek, unit="D")).tz_localize(None)
    g = T.assign(week=wk.date).groupby("week", sort=True)
    W = pd.DataFrame({"cell": g.cell.agg(lambda x: " ".join(dict.fromkeys(x))), "trades": g.size(),
                      "win": g.pnl.agg(lambda x: (x > 0).mean()).round(3), "R_trade": g.R.mean().round(3),
                      "R": g.R.sum().round(2), "usd": g.pnl.sum().round(2), "worst": g.pnl.min().round(2)})
    W.insert(W.columns.get_loc("worst"), "usd_total", W.usd.cumsum().round(2))
    return W.reset_index()


def longest_run(mask: np.ndarray) -> int:
    """The longest stretch of consecutive True (e.g. losing trades in a row)."""
    best = cur = 0
    for x in np.asarray(mask, bool):
        cur = cur + 1 if x else 0
        best = max(best, cur)
    return best


def exit_time(ot: pd.DatetimeIndex, xj: np.ndarray) -> pd.DatetimeIndex:
    """When a trade is over and known: the END of its exit bar (a target / stop fills inside bar xj; a close exit at
    xj's open, one minute earlier - the later time is the safe one for "known by the month's start")."""
    return ot[np.asarray(xj, int)] + pd.Timedelta(minutes=1)


def main() -> None:
    import lvl2  # noqa: PLC0415
    import lvl3  # noqa: PLC0415
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    learn = plib.LEARN_START_3Y if "3y" in sys.argv[1:] else plib.LEARN_START
    tag = "_3y" if "3y" in sys.argv[1:] else ""
    M = lvl3.Market()
    inwin = plib.window_mask(M.ot).any(axis=1).to_numpy()
    ny = plib.ny_mask(M.ot)
    # the learning: signals (so the learned stop), cells and choices only from `learn` on; older bars are chart history
    dec = np.nonzero(inwin & np.asarray(M.ot >= learn))[0]
    cells = {}
    for s in lvl3.SWINGS:
        for n in (3, 4, 5, 0):
            S = lvl3.signals(M, dec, lvl3.Params(k=0.5, s=s, n=n))
            S.to_parquet(HERE / f"lvl3_signals{tag}_s{s}_n{n}.parquet")
            for tg in ("T1", "T2"):
                for q in (80.0, 90.0):
                    T = lvl2.trades(M, S, lvl3.Params(k=0.5, s=s, n=n, target=tg, p=q), ny)
                    if T.empty:
                        continue
                    T["x_t"] = exit_time(M.ot, T.xj.to_numpy())
                    name = f"s{s}_n{n if n else 'ad'}_{tg}_p{int(q)}"
                    T.to_parquet(HERE / f"lvl3_cell{tag}_{name}.parquet")
                    cells[name] = T
            print(f"signals s {s} n {n}: {len(S)}", flush=True)
    WF, months = walk_forward(cells, str((learn + pd.offsets.MonthBegin(1)).to_period("M")), "2026-10")
    # R13: every trade records its library evidence (the pattern library as it stood before the trade's day)
    from evidence_journal import evidence_patterns  # noqa: PLC0415

    WF = WF.reset_index(drop=True)
    E, _libs = evidence_patterns(plib.load(), pd.DatetimeIndex(WF.t), WF.side.to_numpy())
    WF = pd.concat([WF, E.drop(columns=["t", "side"]).add_prefix("ev_")], axis=1)
    WF.to_parquet(HERE / f"lvl3_wf{tag}_trades.parquet")
    months.to_csv(HERE / f"lvl3_wf{tag}_months.csv", index=False)
    pd.set_option("display.width", 250)
    print(months.to_string(index=False))
    W = weekly(WF)
    W.to_csv(HERE / f"lvl3_wf{tag}_weeks.csv", index=False)
    print("\nweek by week (Thai weeks, Monday):")
    print(W.to_string(index=False))
    split, end = plib.EXAM_START, plib.EXAM_END
    d0, d1, d2 = (x.strftime("%Y-%m-%d") for x in (learn, split, end))
    for name, part, wd in ((f"{d0} .. {split - pd.Timedelta(days=1):%Y-%m-%d} (learning)", WF[WF.t < split],
                            np.busday_count(d0, d1)),
                           (f"{d1} .. {end - pd.Timedelta(days=1):%Y-%m-%d} (the exam)", WF[(WF.t >= split) & (WF.t < end)],
                            np.busday_count(d1, d2))):
        eq = part.pnl.cumsum()
        print(f"{name}: {len(part)} trades ({len(part) / wd:.2f} a weekday), win {(part.pnl > 0).mean():.3f}, "
              f"R {part.R.mean():+.3f}, USD {part.pnl.sum():+.1f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}")
        if len(part):
            print(f"   worst trade {part.pnl.min():+.2f} USD, longest losing streak {longest_run(part.pnl.to_numpy() < 0)} "
                  "trades (0.01 lot)")
            print("   by the library evidence at entry:", part.groupby("ev_evidence").R.agg(["size", "mean"]).round(3)
                  .to_dict("index"))


if __name__ == "__main__":
    main()
