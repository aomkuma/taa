"""Run one exam week under the state in force (state.json) and append it to the append-only ledger.csv / weeks.csv.

Beside the realized line: the base (the bot as is) and the no-learning line (PROTOCOL.md's start state unchanged:
the realistic exit, the vol / near-line / 10:00 New York skips, the re-test piece).

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/solo/solo_week.py 1
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import solo_lib as S

COLS = ["week", "piece", "t", "thai", "side", "tf", "entry_price", "sl_initial", "risk", "r_base", "r_realized", "r_nolearn",
        "skipped_by", "shadow_hits", "exit_used", "r_cur", "r_real", "r_nobe", "r_noband", "r_hold90", "zone_line_dist",
        "zone_step_pos", "vol", "push3d", "min_to_10et", "score", "run3", "day_run", "day_rng", "touches", "worn",
        "h1_structure", "score_parts", "mfe_r", "mae_r", "exit_reason", "rule", "note"]
START_RULES = ("vol", "near", "news")


def b2_week(n: int, st: dict) -> pd.DataFrame:
    s, e = S.bounds(n)
    X = S.load_b2(S.EXAM_RAW, e)  # rows at / after the week's end are never read
    X = X[X.t >= s].reset_index(drop=True)
    if not len(X):
        return pd.DataFrame(columns=COLS)
    X = S.enrich(X)
    X["piece"], X["week"], X["r_base"] = "B2", n, X.r_multiple
    X["mfe_r"], X["mae_r"] = X.mfe / X.risk, -X.mae / X.risk
    hit = {k: S.RULES[k](X) for k in set(st["rules"]) | set(st["shadows"]) | set(START_RULES)}
    X["skipped_by"] = [" ".join(k for k in st["rules"] if hit[k][i]) for i in X.index]
    X["shadow_hits"] = [" ".join(k for k in st["shadows"] if hit[k][i]) for i in X.index]
    X["exit_used"] = st["exit"]
    X["r_cur"] = X[f"r_{st['exit']}"]
    on = "B2" in st["pieces"]
    X["r_realized"] = np.where((X.skipped_by == "") & on, X.r_cur, np.nan)
    if not on:  # the piece is stopped: its signals stay in the ledger as a record
        X["skipped_by"] = ("stopped " + X.skipped_by).str.strip()
    nl = np.zeros(len(X), bool)
    for k in START_RULES:
        nl |= hit[k].values
    X["r_nolearn"] = np.where(nl, np.nan, X.r_real)
    X["rule"] = X.rule.astype(str).str.split(": ", n=1).str[-1].str.replace(r" \(.*", "", regex=True)
    return X.reindex(columns=COLS)


def retest_week(n: int, st: dict) -> pd.DataFrame:
    s, e = S.bounds(n)
    R = S.RT.trades(s - pd.Timedelta(days=3), e)
    if not len(R):
        return pd.DataFrame(columns=COLS)
    R = R[(R.t >= s) & (R.t < e)].copy()
    R["piece"], R["week"], R["r_cur"], R["exit_used"] = "retest", n, R.r_real, "retest"
    R["r_realized"] = R.r_real if "retest" in st["pieces"] else np.nan
    R["r_nolearn"] = R.r_real
    R["skipped_by"] = "" if "retest" in st["pieces"] else "stopped"
    R["thai"] = R.t.dt.tz_convert("Asia/Bangkok").dt.strftime("%a %d %H:%M")
    R["risk"] = (R.entry_price - R.sl_initial).abs()
    R["note"] = [f"strong day {d} body {b:.2f} ATR ext {x:.2f} first exit {k}" for d, b, x, k in zip(R.strong_day, R.body, R.ext, R.exit1)]
    return R.reindex(columns=COLS)


def other_pieces(n: int, st: dict) -> list[pd.DataFrame]:
    """Pieces added through the gates (pieces.py), or stopped ones kept as a record."""
    out = []
    names = [p for p in list(st["pieces"]) + list(st["stopped"]) if p not in ("B2", "retest")]
    if not names:
        return out
    import pieces as P

    s, e = S.bounds(n)
    for p in names:
        R = P.PIECES[p](s, e)
        if not len(R):
            continue
        R = R[(R.t >= s) & (R.t < e)].copy()
        R["piece"], R["week"], R["r_cur"], R["exit_used"] = p, n, R.r_real, p
        R["r_realized"] = R.r_real if p in st["pieces"] else np.nan
        R["skipped_by"] = "" if p in st["pieces"] else "stopped"
        R["r_nolearn"] = np.nan
        R["thai"] = R.t.dt.tz_convert("Asia/Bangkok").dt.strftime("%a %d %H:%M")
        R["risk"] = (R.entry_price - R.sl_initial).abs()
        out.append(R.reindex(columns=COLS))
    return out


def d1_week(n: int) -> pd.DataFrame:
    s, e = S.bounds(n)
    d = S.W.Z.bars("D1")
    pc = d.close.shift(1)
    atr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1).rolling(20).mean().shift(1)
    d = d.assign(atr20=atr)
    d = d[(d.index >= s) & (d.index + pd.Timedelta(days=1) <= e)]
    d["day"] = d.index.tz_convert("Europe/Athens").strftime("%a %d %b")
    d["body_atr"] = (d.close - d.open) / d.atr20
    d["close_pos"] = (d.close - d.low) / (d.high - d.low)
    return d[["day", "open", "high", "low", "close", "atr20", "body_atr", "close_pos"]].round(2)


def main(n: int) -> None:
    st = S.load_state()
    L = S.ledger()
    wk = pd.read_csv(S.SOLO / "weeks.csv") if (S.SOLO / "weeks.csv").exists() else pd.DataFrame()
    assert not len(wk) or wk.week.max() == n - 1, f"week {n} out of order (done: {wk.week.max() if len(wk) else 0})"
    parts = [x for x in [b2_week(n, st), retest_week(n, st), *other_pieces(n, st)] if len(x)]
    Wk = pd.concat(parts).sort_values("t").reset_index(drop=True) if parts else pd.DataFrame(columns=COLS)
    Wk["t"] = pd.to_datetime(Wk.t, utc=True)
    L2 = pd.concat([L, Wk]) if len(L) else Wk
    Wk.to_csv(S.LEDGER, mode="a", header=not S.LEDGER.exists(), index=False)

    print(d1_week(n).to_string())
    pd.set_option("display.width", 250)
    show = ["thai", "piece", "side", "tf", "entry_price", "risk", "r_base", "r_cur", "r_realized", "r_nolearn", "skipped_by",
            "shadow_hits", "r_nobe", "r_noband", "r_hold90", "vol", "zone_line_dist", "min_to_10et", "push3d", "score", "run3", "day_run"]
    print(Wk[show].round(2).to_string() if len(Wk) else "no trades")
    for _, r in Wk.iterrows():
        print(f"  {r.thai} {r.piece} {r.rule if isinstance(r.rule, str) else ''} {r.score_parts if isinstance(r.score_parts, str) else ''} "
              f"{r.h1_structure if isinstance(r.h1_structure, str) else ''} {r.note if isinstance(r.note, str) else ''}")
    row = dict(week=n, trades=int(Wk.r_realized.notna().sum()), wins=int((Wk.r_realized > 0).sum()), losses=int((Wk.r_realized <= 0).sum()),
               r_realized=float(np.nansum(Wk.r_realized)), nl_trades=int(Wk.r_nolearn.notna().sum()),
               nl_wins=int((Wk.r_nolearn > 0).sum()), nl_losses=int((Wk.r_nolearn <= 0).sum()), r_nolearn=float(np.nansum(Wk.r_nolearn)),
               b2_signals=int((Wk.piece == "B2").sum()), r_base=float(np.nansum(Wk.r_base)))
    L2 = L2.reset_index(drop=True)
    for col, tag in (("r_realized", ""), ("r_nolearn", "nl_")):
        b100, b300, dd100, dd300 = S.balances(L2, col, n)
        row.update({f"{tag}acct100": b100, f"{tag}acct300": b300, f"{tag}dd100": dd100, f"{tag}dd300": dd300})
    b2 = L2[L2.piece == "B2"]
    b100, b300, dd100, dd300 = S.balances(b2, "r_base", n)
    row.update(base_acct100=b100, base_acct300=b300, base_dd100=dd100, base_dd300=dd300)
    row["state"] = f"exit={st['exit']} rules={','.join(st['rules'])} shadows={','.join(st['shadows'])} pieces={','.join(st['pieces'])}"
    pd.DataFrame([row]).to_csv(S.SOLO / "weeks.csv", mode="a", header=not len(wk), index=False)
    print(pd.Series(row).to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]))
