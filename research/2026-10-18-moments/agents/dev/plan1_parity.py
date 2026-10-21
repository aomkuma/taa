"""PLAN-1 lane parity (checkpoint A, owner 2026-10-21 "the bot must learn with it"): the bot's backtest of lane
`plan1` (app/strategy/plan1.py: the London ORB on closed M1 bars, the NY straddle on quotes; the broker on the
stored ticks wherever a position, an order or the straddle's window is open) against the research's trades
(dev/plan1_trades_learn_s0_x0.parquet; the ORB re-simulated with the journal's 1.5 R target as
journal/rules_week.py does: the same entry, stop and 60-minute exit).

Learning parts only: P1 2025-10-18 .. 2026-01-15, P2 2026-01-16 .. 2026-04-17. Nothing at / after 2026-04-18 is
read: the history load ends there, the tick store never opens a day at / after it.

The bot's run: slippage 0 (the research's s0), risk 0.25 % a trade with the loss breakers out of the way (50
losses in a row, no pause), so that the account rules never skip a trade the research takes (one position at a
time stays: risk.max_positions_per_symbol 1).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_parity.py           # run + compare
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_parity.py --compare # compare the saved run
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_parity.py --h4      # the week-10 rule on:
        the ORB days it skips against the rule-off run (weeks 1-9 must be the journal's 12 days)

The rule-off run is the parity with the research trades (they have no week-10 rule).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENTS = HERE.parent
ROOT = AGENTS.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(AGENTS / "precursors"))

START = pd.Timestamp("2025-10-18", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
P1_END = pd.Timestamp("2026-01-16", tz="UTC")
ORB_TP = 1.5
NS_MIN = 60 * 10**9
H4 = "--h4" in sys.argv
APP_TRADES = HERE / f"plan1_app_trades_learn{'_h4' if H4 else ''}.parquet"
APP_JOURNAL = HERE / f"plan1_app_journal_learn{'_h4' if H4 else ''}.jsonl"
JOURNAL_SKIPS = ["2025-11-03", "2025-11-04", "2025-11-05", "2025-11-11", "2025-11-18", "2025-11-19", "2025-11-28",
                 "2025-12-05", "2025-12-09", "2025-12-16", "2025-12-18", "2025-12-19"]  # the measurer, 9c74c7c
PIECE = {"setup_plan1_orb": "London ORB", "setup_plan1_ny": "NY straddle"}


def run_app() -> None:
    from app.backtest.runner import load_history, run_backtest
    from app.config import load_settings
    from app.market_data.history_store import ParquetHistoryStore
    from app.market_data.tick_store import TickStore
    from app.news.releases import load_releases

    settings = load_settings()
    full = settings.config
    cfg = full.for_lane(full.lane("plan1"))
    items = [
        i.model_copy(update={"params": {**i.params, "pool_break_when_h4_contracting": H4}})
        if i.name == "setup_plan1_orb" else i
        for i in cfg.strategies.items
    ]
    cfg = cfg.model_copy(update={"strategies": cfg.strategies.model_copy(update={"items": items})})
    cfg = cfg.model_copy(
        update={
            "backtest": cfg.backtest.model_copy(update={"slippage_model": "none", "slippage_points": 0.0}),
            "risk": cfg.risk.model_copy(
                update={"max_risk_per_trade_percent": 0.25, "max_consecutive_losses": 50, "consecutive_loss_pause_hours": 0.0}
            ),
        }
    )
    end = EXAM_START.to_pydatetime()
    loaded = load_history(
        ParquetHistoryStore(settings.path("data/history")),
        "FBS-Demo",
        ["XAUUSD"],
        cfg.timeframes.enabled,
        account_currency=cfg.backtest.account_currency,
        start=None,
        end=end,
    )
    for d in loaded.data.values():
        for tf, df in d.frames.items():
            if len(df) and pd.Timestamp(df["open_time"].max()) >= EXAM_START:
                raise SystemExit(f"{tf}: a bar at / after 2026-04-18 was loaded")
    result, prov = run_backtest(
        cfg,
        loaded,
        config_hash="plan1-parity",
        strategy_names=list(PIECE),
        start=START.to_pydatetime(),
        end=(EXAM_START - pd.Timedelta(minutes=1)).to_pydatetime(),
        quotes=TickStore(settings.path("data/ticks"), end=end),
        calendar=lambda name: load_releases(settings.path(name)),
    )
    rows = [
        dict(
            piece=PIECE[t.strategy],
            t_in=pd.Timestamp(t.entry_time).value,
            t_out=pd.Timestamp(t.exit_time).value,
            side=1 if t.side.value == "BUY" else -1,
            entry=t.entry_price,
            stop=t.sl_initial,
            exit_px=t.exit_price,
            exit=t.exit_reason.value,
            signal_id=t.signal_id,
        )
        for t in result.trades
    ]
    A = pd.DataFrame(rows)
    A["risk"] = (A.entry - A.stop) * A.side
    A["R"] = (A.exit_px - A.entry) * A.side / A.risk
    if len(A) and (A.t_in >= EXAM_START.value).any():
        raise SystemExit("a trade at / after 2026-04-18")
    A.to_parquet(APP_TRADES)
    with APP_JOURNAL.open("w", encoding="utf-8", newline="\n") as fh:
        for sid, rec in result.journal.items():
            fh.write(json.dumps({"signal_id": sid, **rec}, sort_keys=True) + "\n")
    print(f"app run: {len(A)} trades, decisions {dict(result.decisions)}, rejections {dict(result.rejections)}, "
          f"tick minutes {result.tick_minutes}, data hash {prov.data_hash}")


def research_trades() -> pd.DataFrame:
    import check_plan1 as C

    R = pd.read_parquet(HERE / "plan1_trades_learn_s0_x0.parquet")
    R = R[R.piece.isin(PIECE.values())].copy()
    out = []
    for r in R.itertuples():
        d = r._asdict()
        if r.piece == "London ORB":
            t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
            f = int(np.searchsorted(t, int(r.t_in)))
            px, t_x, kind = C.manage(t, bid, ask, f, r.entry, r.side, r.stop, r.entry + r.side * ORB_TP * r.risk,
                                     int(t[f]) + 60 * NS_MIN)
            d.update(t_out=int(t_x), exit=kind, R=(px - r.entry) * r.side / r.risk, pnl=(px - r.entry) * r.side)
        out.append(d)
    X = pd.DataFrame(out).drop(columns=["Index"])
    return X


def th(ns: int) -> str:
    return pd.Timestamp(int(ns), tz="UTC").tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %a %H:%M:%S")


def part(ns: int) -> str:
    return "P1" if ns < P1_END.value else "P2"


def compare() -> None:
    A = pd.read_parquet(APP_TRADES)
    R = research_trades()
    for X in (A, R):
        X["day"] = pd.to_datetime(X.t_in, utc=True).dt.normalize()
        X["part"] = [part(t) for t in X.t_in]
    M = R.merge(A, on=["piece", "day"], how="outer", suffixes=("_r", "_a"), indicator=True)
    both = M[M._merge == "both"].copy()
    both["d_in"] = (both.t_in_a - both.t_in_r) / 1e9
    both["d_out"] = (both.t_out_a - both.t_out_r) / 1e9
    both["dR"] = both.R_a - both.R_r
    both["d_entry"] = both.entry_a - both.entry_r
    print("=== parity table (research = dev/plan1_trades_learn_s0_x0.parquet, ORB at 1.5 R; app = lane plan1 backtest)")
    print(f"{'piece':12s} {'part':4s} {'res n':>5s} {'app n':>5s} {'both':>5s} {'side=':>5s} {'exit=':>5s} "
          f"{'|d in| s':>8s} {'|d out| s':>9s} {'|dR|<0.05':>9s} {'res R':>8s} {'app R':>8s} {'res R/t':>8s} {'app R/t':>8s}")
    for pc in PIECE.values():
        for p in ("P1", "P2"):
            r, a = R[(R.piece == pc) & (R.part == p)], A[(A.piece == pc) & (A.part == p)]
            b = both[(both.piece == pc) & (both.part_r == p)]
            print(f"{pc:12s} {p:4s} {len(r):5d} {len(a):5d} {len(b):5d} {int((b.side_r == b.side_a).sum()):5d} "
                  f"{int((b.exit_r.str.lower().str[:4] == b.exit_a.map(EXIT).str[:4]).sum()):5d} "
                  f"{b.d_in.abs().median():8.2f} {b.d_out.abs().median():9.2f} {int((b.dR.abs() < 0.05).sum()):9d} "
                  f"{r.R.sum():+8.2f} {a.R.sum():+8.2f} {r.R.mean():+8.3f} {a.R.mean():+8.3f}")
    print("\n=== days in one only")
    for r in M[M._merge != "both"].sort_values("day").itertuples():
        src = "research only" if r._merge == "left_only" else "app only"
        t_in = r.t_in_r if r._merge == "left_only" else r.t_in_a
        R_ = r.R_r if r._merge == "left_only" else r.R_a
        print(f"  {src:13s} {r.piece:11s} {th(t_in)} Thai R {R_:+.2f}")
    print("\n=== trades in both that differ (side, exit kind, or |dR| >= 0.05)")
    diff = both[(both.side_r != both.side_a) | (both.dR.abs() >= 0.05)
                | (both.exit_r.str.lower().str[:4] != both.exit_a.map(EXIT).str[:4])]
    for r in diff.sort_values("day").itertuples():
        print(f"  {r.piece:11s} {th(r.t_in_r)} Thai | research {'BUY' if r.side_r > 0 else 'SELL'} {r.entry_r:.2f} "
              f"stop {r.stop_r:.2f} out {th(r.t_out_r)[-8:]} {r.exit_r} R {r.R_r:+.3f} | app {'BUY' if r.side_a > 0 else 'SELL'} "
              f"{r.entry_a:.2f} in {th(r.t_in_a)[-8:]} stop {r.stop_a:.2f} out {th(r.t_out_a)[-8:]} {r.exit_a} R {r.R_a:+.3f} "
              f"| dR {r.dR:+.3f}")
    print(f"\n=== in both: {len(both)}; median |d entry price| {both.d_entry.abs().median():.3f}, max {both.d_entry.abs().max():.3f}; "
          f"mean dR {both.dR.mean():+.4f}; trades with |dR| < 0.05: {int((both.dR.abs() < 0.05).sum())}")


EXIT = {"SL": "stop", "TP": "target", "TIME": "time", "TIME_STOP": "time", "SIGNAL": "signal", "END_OF_DATA": "end"}


def h4_skips() -> None:
    """The ORB days the week-10 rule skips: in the rule-off run and not in the rule-on run."""
    off = pd.read_parquet(HERE / "plan1_app_trades_learn.parquet")
    on = pd.read_parquet(HERE / "plan1_app_trades_learn_h4.parquet")
    day = lambda X: set(pd.to_datetime(X[X.piece == "London ORB"].t_in, utc=True).dt.strftime("%Y-%m-%d"))  # noqa: E731
    skipped = sorted(day(off) - day(on))
    added = sorted(day(on) - day(off))
    w19 = [d for d in skipped if d < "2025-12-20"]
    print(f"=== the week-10 rule (H4 ATR contracting over 24 h -> the ORB needs a pool break): skipped {len(skipped)} ORB days "
          f"of {len(day(off))}, added {added or 'none'}")
    print(f"  weeks 1-9 (to 2025-12-19): {len(w19)} skipped: {w19}")
    print(f"  the journal's 12: {JOURNAL_SKIPS}")
    print(f"  only here: {sorted(set(w19) - set(JOURNAL_SKIPS)) or 'none'}; only in the journal: "
          f"{sorted(set(JOURNAL_SKIPS) - set(w19)) or 'none'}")
    o = off[off.piece == "London ORB"].assign(day=lambda X: pd.to_datetime(X.t_in, utc=True).dt.strftime("%Y-%m-%d"))
    for p, (a, b) in {"P1": ("", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}.items():
        g = o[(o.day >= a) & (o.day < b)]
        k = g[~g.day.isin(skipped)]
        print(f"  {p}: ORB rule off {len(g)} trades {g.R.sum():+.2f} R ({g.R.mean():+.3f}); rule on {len(k)} trades "
              f"{k.R.sum():+.2f} R ({k.R.mean():+.3f}); the skipped {len(g) - len(k)} summed {g.R.sum() - k.R.sum():+.2f} R")


if __name__ == "__main__":
    if "--compare" not in sys.argv:
        run_app()
    if H4:
        h4_skips()
    else:
        compare()
