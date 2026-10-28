"""Checkpoint A1: the sweep detector's catches drawn for the owner to confirm (DEV_PROMPT.md Task A step 1). Each case:
M1 candles of the tick mid from 30 minutes before the release to 45 after, Thai time, with the release, p0, the
pre-release range, the first leg's extreme, the sweep's (or the continuation's) extreme and the third leg marked;
beside it the ticks of the first minutes, so the first minute's fake shows. One HTML page with every case, PNGs as
data URIs (as agents/precursors/loser_charts.py does). Learning parts only (the cases come from a1_detections.parquet).

The cases, chosen by a rule written before drawing (DEV_LOG.md): the owner's 2026-01-09; per part x minute the faked
one nearest its group's median sweep; per part the continued release minute nearest its part's median continuation;
the faked one that did not come down with the largest sweep; the largest first minute the two side rules read
differently; the largest sweep the researcher's 'any new extreme' rule calls continued.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/dev/charts_a1.py
"""

from __future__ import annotations

import base64
import html
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_detector import CONT_EXTRA, EXAM_START, NS_MIN, NS_S, WIN_MIN, learning_ticks, m1_from_ticks  # noqa: E402

UP, DOWN = "#1a9b77", "#d6492f"
P0, LEG1, SWEEP, BACK, GREY = "#2a78d6", "#eb6834", "#6250d6", "#008300", "#8a8986"
INK, MUTED = "#1d2127", "#52514e"
BEFORE, AFTER = 30, 45  # minutes drawn around the release
ZOOM = (-60, 180)  # seconds of ticks in the right panel


def pick(A: pd.DataFrame) -> list[tuple[pd.Series, str]]:
    """The cases (see the module's doc), each with why it was drawn; no case twice."""
    main_v = A[(A.side_rule == "larger") & (A.cont_extra == CONT_EXTRA)]
    fx = main_v[main_v.set == "fixed"].set_index("t")
    used: list[pd.Timestamp] = []
    out: list[tuple[pd.Series, str]] = []

    def take(t: pd.Timestamp, why: str) -> None:
        used.append(t)
        out.append((fx.loc[t], why))

    def largest(v: pd.Series) -> pd.Timestamp | None:
        """The case with the largest v not drawn yet (the earlier on a tie)."""
        v = v[~v.index.isin(used)].sort_index()
        return v.idxmax() if len(v) else None

    def nearest(v: pd.Series) -> pd.Timestamp | None:
        """The case nearest the median of all v (the earlier on a tie), skipping the ones already drawn."""
        dist = (v - v.median()).abs().sort_index().sort_values(kind="stable")
        free = [t for t in dist.index if t not in used]
        return free[0] if free else None

    take(pd.Timestamp("2026-01-09 13:30", tz="UTC"), "the owner's own example (US jobs report)")
    F = fx[fx.outcome == "faked"]
    for (p, ny), G in F.groupby(["part", "ny"]):
        if (t := nearest(G.sweep)) is not None:
            take(t, f"faked, {p} {ny} NY: the one nearest the median sweep")
    C = fx[(fx.outcome == "continued") & (fx.names != "")]
    for p, G in C.groupby("part"):
        if (t := nearest(G.cont)) is not None:
            take(t, f"continued, {p}, a release minute: nearest the median continuation")
    if (t := largest(F.sweep[~F.came_down.astype(bool)])) is not None:
        take(t, "faked but did not come down (the largest such sweep)")
    alt = (A[(A.set == "fixed") & (A.cont_extra == CONT_EXTRA)]
           .pivot_table(index="t", columns="side_rule", values="outcome", aggfunc="first"))
    d = alt.index[alt["first"] != alt["larger"]]
    if (t := largest(fx.loc[d, ["up1", "dn1"]].max(axis=1))) is not None:
        take(t, f"the two side rules disagree (the researcher's first 3-USD move reads it: {alt.loc[t, 'first']})")
    strict = A[(A.set == "fixed") & (A.side_rule == "larger") & (A.cont_extra == 0.0)].set_index("t")
    s = F[strict.reindex(F.index).outcome == "continued"]
    if (t := largest(s.sweep)) is not None:
        take(t, "the researcher's 'any new extreme' rule calls it continued (the largest such sweep)")
    return out


def variant_labels(V: pd.DataFrame) -> str:
    """One minute's label under each variant (the detector first), as one line."""
    V = V.assign(o=[(0 if (q.side_rule, q.cont_extra) == ("larger", CONT_EXTRA) else 1) for q in V.itertuples()])
    V = V.sort_values(["o", "side_rule", "cont_extra"], ascending=[True, False, False])
    return "; ".join(f"{'larger move' if q.side_rule == 'larger' else 'first 3-USD move'} / new extreme "
                     f"+{q.cont_extra:.0f}: {q.outcome}" for q in V.itertuples())


def xmin(t_ns: int, rel: int) -> float:
    return (t_ns - rel) / NS_MIN


def headline(r: pd.Series) -> str:
    side = "up" if r["first"] > 0 else "down"
    other = "down" if r["first"] > 0 else "up"
    if r.outcome == "faked":
        return (f"FAKED: first leg {side} {r.leg1:.1f}, sweep {other} {r.sweep:.1f} past p0 at minute {r.sweep_min:.1f}, "
                f"back {r.back:.1f}" + (" (came down" + (", through p0)" if r.third else ")") if r.came_down else " (did not come down)"))
    if r.outcome == "continued":
        return f"CONTINUED: first leg {side} {r.leg1:.1f}, then {r.cont:.1f} further {side} within 15 minutes"
    return f"{r.outcome.upper()}: first leg {side} {r.leg1:.1f}"


def draw(r: pd.Series, k: int, why: str, out: Path) -> str:
    rel = pd.Timestamp(r.name).value
    if rel + AFTER * NS_MIN >= EXAM_START.value:
        raise RuntimeError("a chart may not reach the exam period")
    t, bid, ask = learning_ticks(pd.Timestamp(r.name).normalize())
    mid = (bid + ask) / 2
    m = m1_from_ticks(t, mid, rel - BEFORE * NS_MIN, rel + AFTER * NS_MIN)
    x = np.array([xmin(v.value, rel) for v in m.index]) + 0.5
    s1, p0 = int(r["first"]), float(r.p0)
    fig, (ax, az) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [2.3, 1]})
    fig.patch.set_facecolor("#fcfcfb")
    for a_ in (ax, az):
        a_.set_facecolor("#fcfcfb")
        a_.grid(color="#e4e2dc", linewidth=0.6)
        a_.set_axisbelow(True)
        a_.tick_params(labelsize=7.5, colors=MUTED)
        for sp in a_.spines.values():
            sp.set_color("#cfccc4")
    o, h, lo, c = (m[q].to_numpy(float) for q in ("open", "high", "low", "close"))
    upm = c >= o
    for mask, col in ((upm, UP), (~upm, DOWN)):
        ax.vlines(x[mask], lo[mask], h[mask], color=col, linewidth=0.8)
        ax.vlines(x[mask], np.minimum(o, c)[mask], np.maximum(o, c)[mask], color=col, linewidth=3.0)
    ax.axvspan(0, 1, color="#f2d9c8", alpha=0.6, linewidth=0)  # the first minute
    ax.axvline(0, color=INK, linewidth=0.9, linestyle="--")
    ax.axvline(WIN_MIN, color=GREY, linewidth=0.8, linestyle=":")
    ax.hlines([r.pre_hi, r.pre_lo], -BEFORE, 0, color=GREY, linewidth=0.9, linestyle=":")
    ax.axhline(p0, color=P0, linewidth=1.1, linestyle="--")
    ax.text(AFTER + 0.5, p0, f"p0 {p0:.2f}", color=INK, fontsize=7.5, va="center")
    ax.text(-BEFORE + 0.3, r.pre_hi, "30-min pre-release high", color=MUTED, fontsize=6.5, va="bottom")
    ax.text(-BEFORE + 0.3, r.pre_lo, "30-min pre-release low", color=MUTED, fontsize=6.5, va="top")
    ax.text(0.2, 1.0, "release", transform=ax.get_xaxis_transform(), fontsize=7, color=INK, va="top")
    ax.text(WIN_MIN + 0.2, 1.0, "+15 min", transform=ax.get_xaxis_transform(), fontsize=7, color=MUTED, va="top")

    def mark(a_, tx: float, py: float, col: str, label: str, dy: int) -> None:
        a_.plot([tx], [py], marker="o", markersize=8, color=col, markeredgecolor="white", markeredgewidth=1.5, zorder=5)
        a_.annotate(label, (tx, py), xytext=(6, dy), textcoords="offset points", fontsize=7.5, color=INK, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col, lw=0.9))

    y1 = p0 + s1 * r.leg1
    mark(ax, xmin(int(r.t_ext), rel), y1, LEG1, f"1 first leg {'+' if s1 > 0 else '-'}{r.leg1:.1f}", 10 * s1)
    if r.outcome == "faked":
        ys = p0 - s1 * r.sweep
        mark(ax, xmin(int(r.t_sweep), rel), ys, SWEEP, f"2 sweep {'-' if s1 > 0 else '+'}{r.sweep:.1f} (min {r.sweep_min:.1f})", -12 * s1)
        yb = ys + s1 * r.back
        mark(ax, xmin(int(r.t_back), rel), yb, BACK, f"3 back {r.back:.1f}", 10 * s1)
    elif r.outcome == "continued":
        yc = p0 + s1 * (r.leg1 + r.cont)
        mark(ax, xmin(int(r.t_cont), rel), yc, SWEEP, f"2 continued {'+' if s1 > 0 else '-'}{r.leg1 + r.cont:.1f}", 10 * s1)
    ticks = list(range(-BEFORE, AFTER + 1, 10))
    ax.set_xticks(ticks, [pd.Timestamp(rel + v * NS_MIN, tz="UTC").tz_convert("Asia/Bangkok").strftime("%H:%M") for v in ticks])
    ax.set_xlim(-BEFORE - 0.5, AFTER + 6)
    ax.set_xlabel("Thai time (UTC+7); M1 candles of the tick mid", fontsize=7.5, color=MUTED)
    ax.set_ylabel("XAUUSD mid (USD)", fontsize=7.5, color=MUTED)
    # the first minutes, tick by tick
    za, zb = int(np.searchsorted(t, rel + ZOOM[0] * NS_S)), int(np.searchsorted(t, rel + ZOOM[1] * NS_S))
    az.plot((t[za:zb] - rel) / NS_S, mid[za:zb], color=INK, linewidth=0.8)
    az.axvspan(0, 60, color="#f2d9c8", alpha=0.6, linewidth=0)
    az.axvline(0, color=INK, linewidth=0.9, linestyle="--")
    az.axhline(p0, color=P0, linewidth=1.1, linestyle="--")
    mark(az, (int(r.t_ext) - rel) / NS_S, y1, LEG1, f"1 {(int(r.t_ext) - rel) / NS_S:.0f} s", 10 * s1)
    az.plot([60], [r.c1], marker="s", markersize=7, color=MUTED, markeredgecolor="white", zorder=5)
    az.annotate(f"close of minute 1: {r.c1 - p0:+.1f}", (60, r.c1), xytext=(6, -12 * s1), textcoords="offset points",
                fontsize=7, color=INK)
    az.set_xlabel("seconds from the release (tick mid; shaded = the first minute)", fontsize=7.5, color=MUTED)
    az.set_xlim(*ZOOM)
    th = pd.Timestamp(rel, tz="UTC").tz_convert("Asia/Bangkok")
    names = f", {r.names}" if r.names else ""
    title = f"#{k} {th:%Y-%m-%d %H:%M} Thai ({r.ny} NY{names}) - {r.part} - {headline(r)}"
    fig.suptitle(title, fontsize=9, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, f"Drawn because: {why}.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out, dpi=90, facecolor=fig.get_facecolor())
    plt.close(fig)
    return title


def main() -> None:
    A = pd.read_parquet(HERE / "a1_detections.parquet")
    if not (pd.DatetimeIndex(A.t) < EXAM_START).all():
        raise RuntimeError("an exam minute in the detections")
    cases = pick(A)
    outdir = HERE / "charts" / "a1_sweeps"
    outdir.mkdir(parents=True, exist_ok=True)
    fixed = A[A.set == "fixed"]
    cards, rows = [], []
    for k, (r, why) in enumerate(cases, 1):
        variants = variant_labels(fixed[fixed.t == r.name])
        f = outdir / f"{k:02d}.png"
        title = draw(r, k, why, f)
        cards.append((title, why, variants, base64.b64encode(f.read_bytes()).decode()))
        rows.append(dict(k=k, thai=pd.Timestamp(r.name).tz_convert("Asia/Bangkok").strftime("%Y-%m-%d %H:%M"), ny=r.ny,
                         names=r.names, part=r.part, outcome=r.outcome, why=why))
        print(f"#{k} {title}  <- {why}", flush=True)
    body = "\n".join(
        f'<figure><figcaption><b>{html.escape(t)}</b><br><span class="why">Drawn because: {html.escape(w)}. '
        f"Labels by the variants: {html.escape(v)}</span></figcaption>"
        f'<img alt="{html.escape(t)}" src="data:image/png;base64,{b64}"></figure>'
        for t, w, v, b64 in cards)
    table = "\n".join(f"<tr><td>{q['k']}</td><td>{q['thai']}</td><td>{q['ny']}</td><td>{html.escape(q['names'])}</td>"
                      f"<td>{q['part']}</td><td>{q['outcome']}</td><td>{html.escape(q['why'])}</td></tr>" for q in rows)
    (HERE / "charts" / "a1_sweeps.html").write_text(PAGE.format(n=len(cards), table=table, body=body), encoding="utf-8")
    print(f"{len(cards)} cases drawn -> {outdir}, page {HERE / 'charts' / 'a1_sweeps.html'}")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>News Sweep Catches</title>
<style>
:root {{ --bg: #f6f5f2; --fg: #1d2127; --muted: #52514e; --card: #ffffff; --line: #dcd9d2; color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }} }}
:root[data-theme="dark"] {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }}
body {{ background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; margin: 0; padding: 20px 16px; }}
main {{ max-width: 1180px; margin: 0 auto; display: grid; gap: 18px; }}
h1 {{ font-size: 1.3rem; margin: 0; text-wrap: balance; }}
p {{ color: var(--muted); margin: 0; max-width: 75ch; line-height: 1.5; }}
.wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; font-size: 0.85rem; font-variant-numeric: tabular-nums; }}
td, th {{ border-bottom: 1px solid var(--line); padding: 4px 8px; text-align: left; vertical-align: top; }}
figure {{ margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 8px; display: grid; gap: 6px; }}
figcaption {{ font-size: 0.85rem; color: #1d2127; line-height: 1.4; }}
figcaption .why {{ color: #52514e; }}
img {{ width: 100%; height: auto; display: block; }}
</style>
</head>
<body>
<main>
<h1>The two-way sweep at the news - the detector's catches</h1>
<p>{n} release minutes from the learning parts (P1 2025-10-18 .. 2026-01-16, P2 2026-01-16 .. 2026-04-18), drawn so the
owner can confirm that the code finds the pattern the owner means: "to really buy, wait for the fake drop in the first
minute - then it sweeps up, and then it comes down". Left: M1 candles of the tick mid, Thai time; the dashed black line
is the release, the shaded band the first minute, the dashed blue line p0 (the last price before the release), the
dotted grey lines the 30-minute pre-release high / low, the dotted line at +15 min the end of the detector's window.
Markers: 1 the first leg's extreme, 2 the sweep's extreme (or the continuation's), 3 how far it came back within 15
minutes of the sweep. Right: the ticks from 1 minute before to 3 after the release. The detector: the first leg = the
first minute's larger move (3 USD or more); FAKED = 10 USD past p0 the other way before a new extreme 3 USD beyond the
first minute's; CONTINUED = that new extreme first; within 15 minutes of the release. Research charts only.</p>
<div class="wrap"><table>
<tr><th>#</th><th>Thai time</th><th>NY</th><th>release</th><th>part</th><th>label</th><th>why drawn</th></tr>
{table}
</table></div>
{body}
</main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
