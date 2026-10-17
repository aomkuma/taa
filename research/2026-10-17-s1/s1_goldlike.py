"""S1 with the spread floor on the 7 FX majors, three years of M1 (owner, 2026-10-17: every setup about two trades
a day; more markets first). Without the floor S1 found almost no trade on currencies: their M1 spread is
34-80 % of its stop (SETUP_REVIEW §19). The same event, plan and fills as ``s1_funnel.py``; slippage 2 points
a side (the account's spread is about 10 points, the history's 8-12).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/s1_fx.py
"""

from __future__ import annotations

import json
import sys

import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
sys.path.insert(0, ".")
import s1_funnel as f  # noqa: E402

SYMBOLS = ["XAUUSD", "US100", "JP225", "US30", "US500", "XAUAUD"]
FLOOR = 15
VARIANTS = {"time stop 240": 240, "time stop 60": 60}


def main() -> None:
    f.below_normal_priority()
    rows = []
    for sym in SYMBOLS:
        f.H = f"data/history/FBS-Demo/{sym}"  # the harness reads these module settings at call time
        f.SLIP = 7.0 if sym.startswith("XAU") else 0.0  # indices: the history spread is the account's
        point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
        m1 = f.load("M1")
        ev = f.events(m1, 20)
        for name, ts in VARIANTS.items():
            d = f.outcomes(m1, ev, point, FLOOR, spreads_only=True, time_stop=ts)
            ny = d["t"].dt.tz_convert(f.NY)
            nym = ny.dt.hour * 60 + ny.dt.minute
            utc = d["t"].dt.hour + d["t"].dt.minute / 60
            wd = d["t"].dt.weekday
            keep = (wd < 5) & ~((wd == 4) & (utc >= 16)) & (utc >= 7) & (utc < 20)
            keep &= ~((nym >= 8 * 60) & (nym < 12 * 60))
            t = f.one_at_a_time(d[keep], 60)
            row = {"symbol": sym, "variant": name}
            for y, (a, b) in f.YEARS.items():
                r = t.loc[(t.t >= a) & (t.t < b), "r"]
                row[f"{y}_n"], row[f"{y}_r"] = len(r), round(r.mean(), 3) if len(r) else float("nan")
            row["spread_a"] = round(float(d.spread_a.median()), 2)
            rows.append(row)
        print(f"{sym} done", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv("data/research/s1_goldlike.csv", index=False)
    pd.set_option("display.width", 200)
    for name in VARIANTS:
        v = out[out.variant == name]
        print(f"\n{name} (floor {FLOOR} spreads, Donchian 20, 07-20 UTC, skip 08-12 New York, cooldown 60):")
        print(v.drop(columns="variant").to_string(index=False))
        for y in ("C", "A", "B"):
            n = v[f"{y}_n"].sum()
            r = (v[f"{y}_n"] * v[f"{y}_r"].fillna(0)).sum() / n if n else float("nan")
            print(f"  all, year {y}: {n} trades ({n / 250:.1f} a day), {r:+.3f} R/trade")


if __name__ == "__main__":
    main()
