"""Why do the losers lose? (owner, 2026-10-17: "never call it a coin flip; find why it loses".) The journal agent's
baseline B0 (H1 tide + at a level + price action + 2 of 3 M5 indicators; gold; design data 2023-11 .. 2026-02, five
half-years; `agents/journal/trades_all_XAUUSD_B0.parquet`). Each trade is checked against concrete situations a
trader would see at the entry; for each: the share of the stopped losers and of the winners in it, and R with /
without it in every half-year.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/why_losers.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SRC = "research/2026-10-18-moments/agents/journal/trades_all_XAUUSD_B0.parquet"


def main() -> None:
    d = pd.read_parquet(SRC)
    loser = (d.exit == "stop") & (d.pnl < 0)
    winner = d.exit == "win"
    risk_atr = d.risk / d.atr1
    situations = {
        "falling knife: 15-min move against >= 3 ATR": d.ret15 <= -3,
        "a long run against in the last hour (>= 5 ATR)": d.ret60 <= -5,
        "chasing: 1 h run with >= 4 ATR, near the 4-h extreme": (d.ret60 >= 4) & (d.pos240 >= 0.9),
        "flat H1 (close within 0.85 ATR of EMA50)": d.h1_c_e50.abs() < 0.85,
        "the H1 leg against the trade": d.cr_H1_leg_dir < 0,
        "the M15 leg against the trade": d.cr_M15_leg_dir < 0,
        "no room: next level < half the target": d.room < 0.5 * d.tp,
        "news within 15 minutes": (d.until_rel <= 15) | (d.since_rel <= 15),
        "stop inside the normal swing (< half the 15-min range)": risk_atr < 0.5 * d.rng15,
        "volatility spike (ATR >= 1.5x the day's median)": d.atr_ratio >= 1.5,
        "the first 15 minutes of the window": d.min_in < 15,
        "Asia session": d.session == 0,
        "far from the level (> 2 ATR)": d.dist_atr > 2,
        "price in the far half of the 4-h range (buying high)": d.pos240 >= 0.75,
    }
    halves = sorted(d.half.unique())
    rows = []
    for name, m in situations.items():
        m = m.fillna(False).to_numpy()
        worse = 0
        cells = []
        for h in halves:
            hh = (d.half == h).to_numpy()
            a, b = d.R[hh & m], d.R[hh & ~m]
            if len(a) >= 5 and len(b) >= 5:
                worse += int(a.mean() < b.mean())
                cells.append(f"{a.mean():+.2f}/{b.mean():+.2f}")
            else:
                cells.append("  -  ")
        rows.append(dict(
            situation=name, trades=int(m.sum()), losers_in=float(m[loser.to_numpy()].mean()),
            winners_in=float(m[winner.to_numpy()].mean()), R_in=float(d.R[m].mean()), R_out=float(d.R[~m].mean()),
            halves_worse=f"{worse}/{len(halves)}", by_half=" ".join(cells),
        ))
    t = pd.DataFrame(rows)
    t["lift"] = t.losers_in - t.winners_in
    t = t.sort_values("lift", ascending=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(f"B0 design trades {len(d)}: stopped losers {int(loser.sum())}, winners {int(winner.sum())}, R {d.R.mean():+.3f}")
    print("losers_in / winners_in = the share of stopped losers / winners in the situation; R_in / R_out = R a trade with / without;")
    print("halves_worse = half-years where trades in the situation did worse; by_half = R in/out per half-year\n")
    print(t.round(3).to_string(index=False))
    # the combination: drop the situations that are worse in at least 4 of 5 half-years
    bad = [r.situation for r in t.itertuples() if int(r.halves_worse.split("/")[0]) >= 4 and r.lift > 0]
    keep = np.ones(len(d), dtype=bool)
    for name in bad:
        keep &= ~situations[name].fillna(False).to_numpy()
    k = d[keep]
    print(f"\nWithout the situations worse in >= 4 of 5 half-years ({len(bad)}): {bad}")
    print(f"  kept {len(k)} of {len(d)} trades, R {k.R.mean():+.3f} (all {d.R.mean():+.3f}); by half-year: "
          + " ".join(f"{k.R[k.half == h].mean():+.3f}({int((k.half == h).sum())})" for h in halves))


if __name__ == "__main__":
    main()
