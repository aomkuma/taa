"""News agent: candidate rules, each traded on its side and on the opposite side with the same stop and target
(the coin's expectation is the average of the two). Design A / B only unless --test.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/candidates.py [--test] [NAME ...]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import Gold, events, summary  # noqa: E402

TEST = "--test" in sys.argv
ONLY = [a for a in sys.argv[1:] if not a.startswith("--")]


def presser(G, i, pre, k=40, m=2.0, hz=120, be=None):
    """i = the 14:30 ET press-conference bar."""
    e = i + k - 30
    mv = G.c[e - 1] - G.o[i]
    s = 1 if mv > 0 else -1
    sl = max(m * (G.h[e - 10 : e] - G.lo[e - 10 : e]).mean(), pre)
    return e, s, sl, None, hz, abs(mv) / pre


def fade(G, i, pre, k, xmin=0.0, tpm=1.0, hz=120, buf=1.0):
    e = i + k
    mv = G.c[e - 1] - G.o[i]
    if abs(mv) < xmin * pre:
        return None
    s = -1 if mv > 0 else 1
    fill = G.fill(e, s)
    ext = G.h[i:e].max() + G.sp[e - 1] if s < 0 else G.lo[i:e].min()
    sl = (ext - fill) * -s + buf * pre
    if sl <= 0:
        return None
    return e, s, sl, (tpm * sl if tpm else None), hz, abs(mv) / pre


def follow(G, i, pre, k, xmin=0.0, m=6.0, tpm=2.0, hz=120):
    e = i + k
    mv = G.c[e - 1] - G.o[i]
    if abs(mv) < xmin * pre:
        return None
    s = 1 if mv > 0 else -1
    return e, s, m * pre, (tpm * m * pre if tpm else None), hz, abs(mv) / pre


RULES = {
    "P1": ("PC", lambda G, i, pre: presser(G, i, pre)),
    "P1_t180": ("PC", lambda G, i, pre: presser(G, i, pre, hz=180)),
    "P1_k45": ("PC", lambda G, i, pre: presser(G, i, pre, k=45)),
    "P1_m3": ("PC", lambda G, i, pre: presser(G, i, pre, m=3.0)),
    "N1": ("NFP", lambda G, i, pre: fade(G, i, pre, 15, tpm=1.0)),
    "N1_x3": ("NFP", lambda G, i, pre: fade(G, i, pre, 15, xmin=3, tpm=1.0)),
    "F1": ("FOMC", lambda G, i, pre: follow(G, i, pre, 3, xmin=5, m=6, tpm=2, hz=27)),
    "F1_hz120": ("FOMC", lambda G, i, pre: follow(G, i, pre, 3, xmin=5, m=6, tpm=2, hz=120)),
    "Q1": ("PPI", lambda G, i, pre: fade(G, i, pre, 3, xmin=3, tpm=1.5)),
    "C1": ("CPI", lambda G, i, pre: follow(G, i, pre, 30, xmin=2, m=3, tpm=1.5)),
}


def run(G: Gold, ev: pd.DataFrame, name: str) -> pd.DataFrame:
    main_, fn = RULES[name]
    rng = G.h - G.lo
    rows = []
    for r in ev[ev.main == main_].itertuples():
        i = G.pos.get(r.t)
        if i is None:
            continue
        i = int(i)
        j = i - 30 if main_ == "PC" else i  # the presser's scale: the hour before the statement
        pre = rng[j - 60 : j].mean()
        spec = fn(G, i, pre)
        if spec is None:
            continue
        e, s, sl, tp, hz, x = spec
        ktp = tp if tp is not None else 2 * sl
        for who, side in (("rule", s), ("opp", -s)):
            out = G.trade(e, side, sl, tp, hz, kind_tp=ktp)
            rows.append(dict(rule=name, t=r.t, per=r.per, who=who, side=side, x=x, sl=sl, **out))
    return pd.DataFrame(rows)


def main() -> None:
    G = Gold()
    ev = events(extra=True)
    if not TEST:
        ev = ev[ev.per != "T"]
    else:
        ev = ev[ev.per == "T"]
    out = []
    for name in ONLY or RULES:
        d = run(G, ev, name)
        out.append(d)
        for per in sorted(d.per.unique()):
            x = d[d.per == per]
            r, o = x[x.who == "rule"], x[x.who == "opp"]
            coin = (r.R.mean() + o.R.mean()) / 2
            ok = o.kind[o.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
            print(summary(r, f"{name} {per}"), f"| coin R {coin:+.3f} (opp kinds {100 * ok['1']:.0f}/"
                  f"{100 * ok['2']:.0f}/{100 * ok['3']:.0f})")
    pd.concat(out).to_parquet(f"research/2026-10-18-moments/agents/news/cand_{'test' if TEST else 'design'}.parquet")


if __name__ == "__main__":
    main()
