"""Support / resistance from the larger timeframe - step 2, the touches counted (notes.md, written before it is computed;
owner, 2026-10-19: "does it usually go past the support / resistance with the wick, make the low / high, but not reach
the next level, when it reverses?"). Every touch of the owner's H1 levels (zones.levels_at) in the active hours of P1 /
P2, each once: reversed or broke (10 USD first), and for the reversed, how far the extreme went past the level and
whether it reached the next level beyond.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/touches.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from zones import TOUCH_ATR  # noqa: E402

AWAY_ATR, LOOKBACK, AHEAD, X = 0.5, 60, 60, 10.0


def outcome(h: np.ndarray, lo: np.ndarray, j: int, level: float, side: int, x: float = X, ahead: int = AHEAD) -> dict:
    """From the touch bar j (bars j .. j + ahead - 1). side +1: a support test (price came from above): reversed = a
    high >= level + x first, broke = a low <= level - x first; side -1 mirrored. The touch bar's own back side does not
    count (it is where price came from); a later bar reaching both is 'ambiguous'. For the reversed: over = how far the
    extreme went past the level up to the reversal bar (0 if it never did), and the extreme's price."""
    hh, ll = h[j:j + ahead], lo[j:j + ahead]
    back = (hh - level) if side > 0 else (level - ll)
    past = (level - ll) if side > 0 else (hh - level)
    back = back.astype(float).copy()
    back[0] = -np.inf
    r, b = np.nonzero(back >= x)[0], np.nonzero(past >= x)[0]
    ri, bi = (int(r[0]) if len(r) else len(hh)), (int(b[0]) if len(b) else len(hh))
    if ri == bi < len(hh):
        return dict(outcome="ambiguous")
    if ri < bi:
        over = max(float(past[:ri + 1].max()), 0.0)
        ext = float(ll[:ri + 1].min()) if side > 0 else float(hh[:ri + 1].max())
        return dict(outcome="reversed", over=over, extreme=ext, bars=ri)
    if bi < ri:
        return dict(outcome="broke", over=float(past.max()), extreme=float(ll.min() if side > 0 else hh.max()), bars=bi)
    return dict(outcome="neither", over=max(float(past.max()), 0.0))


def approach(c: np.ndarray, h: np.ndarray, lo: np.ndarray, j: int, level: float, atr: float) -> int:
    """The side price came from to the touch at bar j: the latest bar k in the LOOKBACK bars before j whose close was
    >= AWAY_ATR x atr from the level gives the side (+1 above, -1 below); 0 when there is none or a bar between k and
    j already touched the level (then j is not the first touch of that approach)."""
    a = max(j - LOOKBACK, 0)
    far = np.nonzero(np.abs(c[a:j] - level) >= AWAY_ATR * atr)[0]
    if not len(far):
        return 0
    k = a + int(far[-1])
    d = TOUCH_ATR * atr
    if np.any((lo[k + 1:j] <= level + d) & (h[k + 1:j] >= level - d)):
        return 0
    return 1 if c[k] > level else -1


def next_level(levels: np.ndarray, level: float, side: int, atr: float) -> float:
    """The next level past this one (below it for a support test, above for a resistance test), NaN if none."""
    gap = TOUCH_ATR * atr
    beyond = levels[levels < level - gap] if side > 0 else levels[levels > level + gap]
    return float(beyond.max() if side > 0 else beyond.min()) if len(beyond) else np.nan


def scan(m: pd.DataFrame, Y: dict, a: int, b: int, act: np.ndarray) -> pd.DataFrame:
    from zones import levels_at  # noqa: PLC0415

    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t_ns = m.index.as_unit("ns").asi8
    rows = []
    for j in range(a, b):
        if not act[j]:
            continue
        L, atr = levels_at(Y, int(t_ns[j]), float(o[j]))
        if L.empty:
            continue
        d = TOUCH_ATR * atr
        hit = L[(L.price >= lo[j] - d) & (L.price <= h[j] + d)]
        for z in hit.itertuples():
            s = approach(c, h, lo, j, z.price, atr)
            if s == 0:
                continue
            x = outcome(h, lo, j, z.price, s)
            nxt = next_level(L.price.to_numpy(float), z.price, s, atr)
            x.update(j=j, t=m.index[j], level=z.price, kind=z.kind, side=s, atr=atr, next=nxt,
                     next_dist=abs(z.price - nxt) if np.isfinite(nxt) else np.nan)
            if x["outcome"] in ("reversed", "broke"):
                x["reached_next"] = bool(np.isfinite(nxt) and (x["extreme"] <= nxt + d if s > 0 else x["extreme"] >= nxt - d))
            rows.append(x)
    return pd.DataFrame(rows)


def main() -> None:
    import foundation as F  # noqa: PLC0415
    import plib  # noqa: PLC0415

    from indicators import bars  # noqa: PLC0415
    from m15_trades import PARTS, part_of  # noqa: PLC0415
    from pullback15 import active  # noqa: PLC0415
    from zones import draw, swings  # noqa: PLC0415

    m = plib.load()
    m = m[(m.index >= pd.Timestamp("2025-09-01", tz="UTC")) & (m.index < pd.Timestamp(PARTS["P2"][1], tz="UTC"))]
    b1 = bars(m, "1h")
    d1 = bars(m, "1D")
    atr = F.atr(b1.high.to_numpy(), b1.low.to_numpy(), b1.close.to_numpy(), 14)
    Y = dict(S=swings(b1), avail=pd.DatetimeIndex(b1["avail"]).as_unit("ns").asi8, atr=atr, h=b1.high.to_numpy(float),
             lo=b1.low.to_numpy(float), d_avail=pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8,
             d_high=d1.high.to_numpy(float), d_low=d1.low.to_numpy(float))
    a = int(np.searchsorted(m.index, pd.Timestamp(PARTS["P1"][0], tz="UTC")))
    T = scan(m, Y, a, len(m) - AHEAD, active(m.index))
    T["part"] = part_of(pd.DatetimeIndex(T.t))
    T.drop(columns=["j"]).to_parquet(HERE / "touches.parquet")
    pd.set_option("display.width", 220)
    for p, D in T.groupby("part"):
        n = len(D)
        oc = D.outcome.value_counts()
        R = D[D.outcome == "reversed"]
        print(f"\n{p}: {n} touches on {D.t.dt.normalize().nunique()} days; " + ", ".join(f"{k} {oc.get(k, 0)} ({oc.get(k, 0) / n:.2f})" for k in ("reversed", "broke", "neither", "ambiguous")))
        if len(R):
            q = R.over.quantile([0.25, 0.5, 0.75, 0.9])
            print(f"  the reversed: turned short of the level (no pierce) {(R.over == 0).mean():.2f}; pierced {(R.over > 0).mean():.2f}; "
                  f"how far past (USD) 25/50/75/90 %: {q.iloc[0]:.1f} / {q.iloc[1]:.1f} / {q.iloc[2]:.1f} / {q.iloc[3]:.1f}; "
                  f"in H1 ATRs median {(R.over / R.atr).median():.2f}; the extreme reached the next level {R.reached_next.mean():.2f} "
                  f"(the next level a median {R.next_dist.median():.1f} USD away)")
        print("  by the level's kind (touches, reversed, broke):")
        print(D.groupby("kind").agg(n=("outcome", "size"), reversed=("outcome", lambda s: (s == "reversed").mean()),
                                    broke=("outcome", lambda s: (s == "broke").mean())).round(2).to_string())
    # the real candles behind the counts: the first two touches of each outcome in each part
    outdir = HERE / "charts" / "touches"
    outdir.mkdir(parents=True, exist_ok=True)
    cards = []
    from zones import levels_at  # noqa: PLC0415

    for (p, oc), G in T[T.outcome.isin(["reversed", "broke", "neither"])].groupby(["part", "outcome"]):
        for r in G.head(2).itertuples():
            L, at = levels_at(Y, int(pd.Timestamp(r.t).value), float(m.open.iloc[r.j]))
            th = pd.Timestamp(r.t).tz_convert("Asia/Bangkok")
            way = "support from above" if r.side > 0 else "resistance from below"
            past = f"past the level {r.over:.1f} USD" if np.isfinite(r.over) else ""
            title = (f"{p} {oc.upper()}: {th:%Y-%m-%d %H:%M} Thai - {r.kind} {r.level:.1f} as {way}; {past}; "
                     f"next level {r.next:.1f}" + (f", reached {r.reached_next}" if oc != "neither" else ""))
            f = outdir / f"{p}_{oc}_{len(cards) + 1:02d}.png"
            draw(m, b1, dict(j=r.j, zones=L, atr=at), title, f)
            cards.append((title, base64.b64encode(f.read_bytes()).decode()))
    body = "\n".join(f'<figure><figcaption>{t}</figcaption><img alt="{t}" src="data:image/png;base64,{b64}"></figure>' for t, b64 in cards)
    from zones import PAGE  # noqa: PLC0415

    page = PAGE.format(n=len(cards), body=body).replace("<title>H1 Zone Touches</title>", "<title>Level Touch Outcomes</title>")
    page = page.replace("<h1>The owner's H1 levels at the first touch after the New York open</h1>",
                        "<h1>Touches of the owner's H1 levels - reversed, broke, neither</h1>")
    page = page.split("<p>")[0] + ("<p>The first two touches of each outcome in each learning part (P1 2025-10-18 .. 2026-01-15, "
                                   "P2 2026-01-16 .. 2026-04-17), in the hours gold runs. Reversed = 10 USD back first; broke = 10 USD "
                                   "past the level first; within 60 minutes. Left: H1 with the levels known at the touch; right: M1 "
                                   "around it (blue line = the touch bar). Thai time. <strong>Not entry points:</strong> every touch of a level is drawn to count what price does there - the only rule is \"price reached the level after being away from it\"; no entry rule has been applied. Research charts only.</p>\n") + body + "\n</main>\n"
    (HERE / "charts" / "touches.html").write_text(page, encoding="utf-8")
    print(f"\n{len(cards)} touches drawn -> charts/touches.html")


if __name__ == "__main__":
    main()
