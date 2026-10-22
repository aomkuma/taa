"""PLAN-1 checkpoint B parity: Asia B2 in the bot (app/strategy/plan1_b2.py) against the research, and the whole lane
`plan1` with the journal's rules in force against the research plan with the same rules.

Learning parts only (P1 2025-10-18 .. 2026-01-15, P2 2026-01-16 .. 2026-04-17): the history load ends at 2026-04-18 and
the tick store never opens a day at / after it.

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_b2_parity.py readings   # ZigZag + levels, window vs full
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_b2_parity.py b2         # B2 alone, week-6 rule off
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_b2_parity.py lane       # all four pieces, rules on
    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plan1_b2_parity.py compare-b2 | compare-lane

`b2`: the research reference is plan1_every_learn_s0_x0.parquet's Asia B2 rows (B2's own one-at-a-time stream).
`lane`: the reference is plan1_trades_learn_s0_x0.parquet with the rules of journal/rules_week.py applied from the start:
the ORB at 1.5 R (re-simulated on the ticks), the ORB skipped where the H4 ATR contracted (< +0.5 %, the journal's
whole-percent reading) and its 15 minutes broke no pool (liq_journal), a B2 flip against the morning's first B2 skipped;
the straddle as it is (its wider stop was deleted after week 16).
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
sys.path.insert(0, str(HERE))

START = pd.Timestamp("2025-10-18", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
P1_END = pd.Timestamp("2026-01-16", tz="UTC")
NS_MIN = 60 * 10**9
PIECE = {"setup_plan1_orb": "London ORB", "setup_plan1_ny": "NY straddle", "setup_plan1_b2": "Asia B2",
         "setup_plan1_b2m5": "Asia B2"}
B2 = ["setup_plan1_b2", "setup_plan1_b2m5"]


def out(name: str) -> Path:
    return HERE / name


# ---------------------------------------------------------------- the bot's runs
def run_app(names: list[str], tag: str, b2_rule: bool) -> None:
    from app.backtest.runner import load_history, run_backtest
    from app.config import load_settings
    from app.market_data.history_store import ParquetHistoryStore
    from app.market_data.tick_store import TickStore
    from app.news.releases import load_releases

    settings = load_settings()
    full = settings.config
    cfg = full.for_lane(full.lane("plan1"))
    items = [
        i.model_copy(update={"params": {**i.params, "second_same_side": b2_rule}}) if i.name in B2 else i
        for i in cfg.strategies.items
    ]
    cfg = cfg.model_copy(update={
        "strategies": cfg.strategies.model_copy(update={"items": items}),
        "backtest": cfg.backtest.model_copy(update={"slippage_model": "none", "slippage_points": 0.0}),
        "risk": cfg.risk.model_copy(update={"max_risk_per_trade_percent": 0.25, "max_consecutive_losses": 50,
                                            "consecutive_loss_pause_hours": 0.0}),
    })
    end = EXAM_START.to_pydatetime()
    loaded = load_history(ParquetHistoryStore(settings.path("data/history")), "FBS-Demo", ["XAUUSD"],
                          cfg.timeframes.enabled, account_currency=cfg.backtest.account_currency, start=None, end=end)
    for d in loaded.data.values():
        for tf, df in d.frames.items():
            if len(df) and pd.Timestamp(df["open_time"].max()) >= EXAM_START:
                raise SystemExit(f"{tf}: a bar at / after 2026-04-18 was loaded")
    result, prov = run_backtest(cfg, loaded, config_hash="plan1-b2-parity", strategy_names=names,
                                start=START.to_pydatetime(), end=(EXAM_START - pd.Timedelta(minutes=1)).to_pydatetime(),
                                quotes=TickStore(settings.path("data/ticks"), end=end),
                                calendar=lambda name: load_releases(settings.path(name)))
    rows = [dict(piece=PIECE[t.strategy], strategy=t.strategy, t_in=pd.Timestamp(t.entry_time).value,
                 t_out=pd.Timestamp(t.exit_time).value, side=1 if t.side.value == "BUY" else -1, entry=t.entry_price,
                 stop=t.sl_initial, tp=t.tp_initial, exit_px=t.exit_price, exit=t.exit_reason.value, signal_id=t.signal_id)
            for t in result.trades]
    A = pd.DataFrame(rows)
    A["risk"] = (A.entry - A.stop) * A.side
    A["R"] = (A.exit_px - A.entry) * A.side / A.risk
    if len(A) and (A.t_in >= EXAM_START.value).any():
        raise SystemExit("a trade at / after 2026-04-18")
    A.to_parquet(out(f"plan1_app_trades_{tag}.parquet"))
    with out(f"plan1_app_journal_{tag}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for sid, rec in result.journal.items():
            fh.write(json.dumps({"signal_id": sid, **rec}, sort_keys=True) + "\n")
    print(f"app run {tag}: {len(A)} trades, decisions {dict(result.decisions)}, rejections {dict(result.rejections)}, "
          f"tick minutes {result.tick_minutes}, data hash {prov.data_hash}", flush=True)


# ---------------------------------------------------------------- the research references
def research_b2() -> pd.DataFrame:
    E = pd.read_parquet(HERE / "plan1_every_learn_s0_x0.parquet")
    return E[E.piece == "Asia B2"].reset_index(drop=True)


def research_lane() -> pd.DataFrame:
    """plan1_trades_learn_s0_x0 with the rules in force from the start (rules_week.py's, the deleted ones left out)."""
    sys.path.insert(0, str(AGENTS / "journal"))
    import liq_journal as L  # noqa: PLC0415

    C = L.C
    A = pd.read_parquet(HERE / "plan1_trades_learn_s0_x0.parquet").sort_values("t_in").reset_index(drop=True)
    J = pd.concat([L.journal(f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}") for a, b in
                   ((START, P1_END), (P1_END, EXAM_START))], ignore_index=True)
    if len(J) != len(A):
        raise SystemExit("liq_journal rows do not line up with the trades")
    keep, first_b2 = [], {}
    for r, j in zip(A.itertuples(index=False), J.itertuples(index=False), strict=True):
        d = r._asdict()
        day = pd.Timestamp(int(r.t_in), tz="UTC").tz_convert("Asia/Bangkok").date()
        note = ""
        if r.piece == "Asia B2":
            if day in first_b2 and r.side != first_b2[day]:
                note = "skipped: B2 flip"
            first_b2.setdefault(day, r.side)
        elif r.piece == "London ORB":
            if j.H4chg <= 0 and j.broke == "-":
                note = f"skipped: H4 {j.H4chg:+d} % and no pool"
            else:
                t, bid, ask = C.day_ticks(pd.Timestamp(int(r.t_in), tz="UTC").normalize())
                f = int(np.searchsorted(t, int(r.t_in)))
                px, t_x, kind = C.manage(t, bid, ask, f, r.entry, r.side, r.stop, r.entry + r.side * 1.5 * r.risk,
                                         int(t[f]) + 60 * NS_MIN)
                d.update(t_out=int(t_x), exit=kind, R=(px - r.entry) * r.side / r.risk)
        d["note"] = note
        keep.append(d)
    X = pd.DataFrame(keep)
    X.to_parquet(out("plan1_research_rules_learn.parquet"))
    return X


# ---------------------------------------------------------------- the comparison
EXIT = {"SL": "stop", "TP": "target", "TIME": "time", "SIGNAL": "structure", "END_OF_DATA": "end"}


def th(ns: int) -> str:
    return pd.Timestamp(int(ns), tz="UTC").tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %a %H:%M:%S")


def part(ns: int) -> str:
    return "P1" if ns < P1_END.value else "P2"


def compare(A: pd.DataFrame, R: pd.DataFrame, title: str) -> None:
    """Trades matched by piece and fill time within 2 minutes (several B2 trades a morning)."""
    A, R = A.copy(), R.copy()
    for X in (A, R):
        X["part"] = [part(t) for t in X.t_in]
    used, pairs = set(), []
    for i, r in R.iterrows():
        cand = A[(A.piece == r.piece) & ((A.t_in - r.t_in).abs() <= 2 * NS_MIN)]
        cand = cand[~cand.index.isin(used)]
        if len(cand):
            j = (cand.t_in - r.t_in).abs().idxmin()
            used.add(j)
            pairs.append((i, j))
    M = pd.DataFrame([dict(piece=R.at[i, "piece"], part=R.at[i, "part"], side_r=R.at[i, "side"], side_a=A.at[j, "side"],
                           t_in_r=R.at[i, "t_in"], t_in_a=A.at[j, "t_in"], t_out_r=R.at[i, "t_out"], t_out_a=A.at[j, "t_out"],
                           entry_r=R.at[i, "entry"], entry_a=A.at[j, "entry"], stop_r=R.at[i, "stop"], stop_a=A.at[j, "stop"],
                           exit_r=str(R.at[i, "exit"]), exit_a=EXIT.get(str(A.at[j, "exit"]), str(A.at[j, "exit"])),
                           R_r=R.at[i, "R"], R_a=A.at[j, "R"]) for i, j in pairs])
    only_r = R[~R.index.isin([i for i, _ in pairs])]
    only_a = A[~A.index.isin(used)]
    print(f"=== {title}")
    print(f"{'piece':12s} {'part':4s} {'res n':>5s} {'app n':>5s} {'both':>5s} {'side=':>5s} {'exit=':>5s} {'|dR|<0.05':>9s} "
          f"{'res R':>8s} {'app R':>8s} {'res R/t':>8s} {'app R/t':>8s}")
    for pc in sorted(set(R.piece) | set(A.piece)):
        for p in ("P1", "P2"):
            r, a = R[(R.piece == pc) & (R.part == p)], A[(A.piece == pc) & (A.part == p)]
            b = M[(M.piece == pc) & (M.part == p)] if len(M) else M
            print(f"{pc:12s} {p:4s} {len(r):5d} {len(a):5d} {len(b):5d} {int((b.side_r == b.side_a).sum()):5d} "
                  f"{int((b.exit_r.str[:4] == b.exit_a.str[:4]).sum()):5d} {int(((b.R_a - b.R_r).abs() < 0.05).sum()):9d} "
                  f"{r.R.sum():+8.2f} {a.R.sum():+8.2f} {r.R.mean() if len(r) else np.nan:+8.3f} "
                  f"{a.R.mean() if len(a) else np.nan:+8.3f}")
    print("\n--- in the research only")
    for r in only_r.sort_values("t_in").itertuples():
        print(f"  {r.piece:11s} {th(r.t_in)} Thai {'BUY' if r.side > 0 else 'SELL'} {r.entry:.2f} stop {r.stop:.2f} "
              f"{r.exit} R {r.R:+.3f}")
    print("--- in the bot only")
    for r in only_a.sort_values("t_in").itertuples():
        print(f"  {r.piece:11s} {th(r.t_in)} Thai {'BUY' if r.side > 0 else 'SELL'} {r.entry:.2f} stop {r.stop:.2f} "
              f"{r.exit} R {r.R:+.3f} ({r.strategy})")
    if len(M):
        diff = M[(M.side_r != M.side_a) | ((M.R_a - M.R_r).abs() >= 0.05) | (M.exit_r.str[:4] != M.exit_a.str[:4])]
        print("--- in both, differing (side, exit kind or |dR| >= 0.05)")
        for r in diff.sort_values("t_in_r").itertuples():
            print(f"  {r.piece:11s} {th(r.t_in_r)} | research {r.entry_r:.2f} stop {r.stop_r:.2f} out {th(r.t_out_r)[-8:]} "
                  f"{r.exit_r} R {r.R_r:+.3f} | bot {r.entry_a:.2f} stop {r.stop_a:.2f} out {th(r.t_out_a)[-8:]} "
                  f"{r.exit_a} R {r.R_a:+.3f} | dR {r.R_a - r.R_r:+.3f}")
        print(f"in both: {len(M)}; |dR| < 0.05: {int(((M.R_a - M.R_r).abs() < 0.05).sum())}; mean dR {(M.R_a - M.R_r).mean():+.4f}")


# ---------------------------------------------------------------- the readings, window against full history
def readings(n: int = 300) -> None:
    import patterns as P  # noqa: PLC0415
    from zones import levels_at as r_levels_at  # noqa: PLC0415

    from app.strategy import plan1_b2 as B  # noqa: PLC0415

    m = P.load_m1()
    Y = P.level_inputs(m)
    rng = np.random.default_rng(7)
    a0 = int(np.searchsorted(m.index.as_unit("ns").asi8, START.value))
    picks = rng.integers(a0, len(m), n)
    bad_z, bad_l, tested = {1: 0, 5: 0}, 0, 0
    tfs = {1: P.TF(m, 1), 5: P.TF(m, 5)}
    for i in picks:
        t = m.index[i] + pd.Timedelta(minutes=1)
        w = m[m.index < t].iloc[-10_000:]
        opens = pd.DatetimeIndex(w.index)
        o, h, lo, c = (w[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        tested += 1
        for mins, tf in tfs.items():
            b = B.tf_bars(opens, o, h, lo, c, mins, t)
            if not len(b.c):
                continue
            atr = B.mt5_atr(b.h, b.lo, b.c)
            piv = B.zigzag(b.h, b.lo, atr)
            mine = [(int(b.t_open[x]), p, k, pr) for x, p, k, pr in B.structure(piv, b.h, b.lo, len(b.c) - 1)]
            d = int(np.searchsorted(tf.avail, t.value, side="right")) - 1
            ref = [(int(tf.t_open[x]), p, k, pr) for x, p, k, pr in P.structure(tf.piv, tf.h, tf.lo, d)]
            bad_z[mins] += mine != ref
        y = B.level_inputs(opens, h, lo, c, t)
        mine_l, a_m = B.levels_at(y, t.value, float(c[-1]))
        ref_l, a_r = r_levels_at(Y, t.value, float(c[-1]))
        same = (np.isclose(a_m, a_r, equal_nan=True) and len(mine_l) == len(ref_l)
                and all(np.isclose(x[0], y_) and x[1] == k for x, y_, k in zip(mine_l, ref_l.price, ref_l.kind, strict=False)))
        bad_l += not same
        if not same and bad_l <= 3:
            print(f"  levels differ at {t}: bot {mine_l} ATR {a_m:.3f} | research {list(zip(ref_l.price.round(2), ref_l.kind))} ATR {a_r:.3f}")
    print(f"readings at {tested} random M1 closes in P1 / P2 (a 10,000-bar window against the full history from 2025-09-01): "
          f"ZigZag structure differs M1 {bad_z[1]}, M5 {bad_z[5]}; the owner's H1 levels differ {bad_l}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "readings":
        readings()
    elif cmd == "b2":
        run_app(B2, "b2", b2_rule=False)
        compare(pd.read_parquet(out("plan1_app_trades_b2.parquet")), research_b2(), "Asia B2 alone, week-6 rule off")
    elif cmd == "compare-b2":
        compare(pd.read_parquet(out("plan1_app_trades_b2.parquet")), research_b2(), "Asia B2 alone, week-6 rule off")
    elif cmd == "lane":
        run_app(list(PIECE), "lane", b2_rule=True)
        R = research_lane()
        compare(pd.read_parquet(out("plan1_app_trades_lane.parquet")), R[R.note == ""].reset_index(drop=True),
                "the whole lane, the rules in force from the start")
    elif cmd == "compare-lane":
        R = research_lane()
        compare(pd.read_parquet(out("plan1_app_trades_lane.parquet")), R[R.note == ""].reset_index(drop=True),
                "the whole lane, the rules in force from the start")
