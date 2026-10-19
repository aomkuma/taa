"""Task P: 12 of the pattern detector's catches drawn for the owner to confirm, chosen by the rule written in DEV_LOG.md
before drawing (not by eye): M1 entries at the owner's H1 levels - one per family in P1 on the buy side and in P2 on
the sell side; M5 entries at the H1 levels (with an M1 pattern agreeing), P1 buy and P2 sell; after a news first
minute, one per part (2026-01-09 13:30 first if it has a catch). In each slot the catch nearest the part's middle; an
empty slot stays empty. Each picture: the entry TF with the level's zone, the pattern's points, the neckline / trigger,
the entry, the stop and the next level; beside it the other TF (M5 for an M1 entry, M1 for an M5 entry). Thai time.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/dev/charts_p.py
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
import patterns as P  # noqa: E402

MID = {"P1": pd.Timestamp("2025-12-02 12:00", tz="UTC").value, "P2": pd.Timestamp("2026-03-02 12:00", tz="UTC").value}
OWNER_NEWS = pd.Timestamp("2026-01-09 13:30", tz="UTC").value
FAMILIES = ("ihs", "w", "st", "base")
UP, DOWN = "#1a9b77", "#d6492f"
LEVEL, PAT, ENTRY, STOP, NEXT, INK, MUTED = "#6250d6", "#eb6834", "#2a78d6", "#d6492f", "#1a9b77", "#1d2127", "#52514e"
NS_MIN = 60 * 10**9


def slots() -> list[dict]:
    """The 12 slots in drawing order: (what, the filter's keys)."""
    out = [dict(slot=f"M1, {fam}, P1 buy", tf="M1", family=fam, part="P1", side=1, where="h1") for fam in FAMILIES]
    out += [dict(slot=f"M1, {fam}, P2 sell", tf="M1", family=fam, part="P2", side=-1, where="h1") for fam in FAMILIES]
    out += [dict(slot="M5 entry, P1 buy", tf="M5", family=None, part="P1", side=1, where="h1"),
            dict(slot="M5 entry, P2 sell", tf="M5", family=None, part="P2", side=-1, where="h1"),
            dict(slot="after the news first minute, P1", tf="M1", family=None, part="P1", side=None, where="news"),
            dict(slot="after the news first minute, P2", tf="M1", family=None, part="P2", side=None, where="news")]
    return out


def pick(C: pd.DataFrame) -> list[tuple[dict, pd.Series | None]]:
    """Each slot's catch: the one nearest the part's middle (the earlier on a tie), never a decision moment (TF and
    time) drawn in an earlier slot; M5 entries need an M1 pattern agreeing; the P1 news slot takes 2026-01-09 13:30's
    earliest catch if any."""
    used: set = set()
    out = []
    for s in slots():
        q = C[(C.tf == s["tf"]) & (C.part == s["part"])]
        q = q[q.at_h1] if s["where"] == "h1" else q[q.at_news]
        if s["family"]:
            q = q[q.family == s["family"]]
        if s["side"]:
            q = q[q.side == s["side"]]
        if s["tf"] == "M5":
            q = q[q.other_pattern != ""]
        q = q[np.array([(r.tf, r.t_dec) not in used for r in q.itertuples()], dtype=bool)]
        if s["where"] == "news" and s["part"] == "P1" and (q.news_t == OWNER_NEWS).any():
            q = q[q.news_t == OWNER_NEWS].sort_values("t_dec")
            r = q.iloc[0]
        elif len(q):
            q = q.assign(dist=(q.t_dec - MID[s["part"]]).abs()).sort_values(["dist", "t_dec"], kind="stable")
            r = q.iloc[0]
        else:
            r = None
        if r is not None:
            used.add((r.tf, r.t_dec))
        out.append((s, r))
    return out


def thai(t_ns: int, fmt: str = "%H:%M") -> str:
    return pd.Timestamp(int(t_ns), tz="UTC").tz_convert("Asia/Bangkok").strftime(fmt)


def title(k: int, r: pd.Series) -> str:
    side = "BUY" if r.side > 0 else "SELL"
    where = (f"after the {r.news_ny} NY first minute (its extreme {r.level:.2f})" if r.level_kind == "news leg"
             else f"at H1 level {r.level:.2f} ({r.level_kind}, {r['how']})")
    nxt = f"{r.next_level:.2f}" if np.isfinite(r.next_level) else "none"
    risk = abs(r.entry - r.stop)
    return (f"#{k} {thai(r.t_dec, '%Y-%m-%d %H:%M')} Thai - {r.part} - {r.tf} {r['name']} ({r.variant}) {where} - {side} "
            f"entry {r.entry:.2f}, stop {r.stop:.2f} (risk {risk:.2f} USD), next level {nxt}")


def agreement(r: pd.Series) -> str:
    other = "M5" if r.tf == "M1" else "M1"
    pat = f"{other} pattern: {r.other_pattern}" if r.other_pattern else f"no {other} pattern in the last 30 min"
    return f"{pat}; {other} structure as it stands: {r.other_structure}"


def label_below(lab: str, side: int) -> bool:
    """A point's label goes below it when the point is a low: a buy's lows (L1, L2, LS, Head, RS, S, HL) and a sell's
    troughs (T, N1, N2); above for the rest."""
    if side > 0:
        return lab in ("L1", "L2", "LS", "Head", "RS", "S", "HL")
    return lab in ("T", "N1", "N2")


def candles(ax, b: pd.DataFrame, x: np.ndarray, width: float) -> None:
    o, h, lo, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    upm = c >= o
    for mask, col in ((upm, UP), (~upm, DOWN)):
        ax.vlines(x[mask], lo[mask], h[mask], color=col, linewidth=0.7)
        ax.vlines(x[mask], np.minimum(o, c)[mask], np.maximum(o, c)[mask], color=col, linewidth=width)


def style(ax) -> None:
    ax.set_facecolor("#fcfcfb")
    ax.grid(color="#e4e2dc", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7.5, colors=MUTED)
    for sp in ax.spines.values():
        sp.set_color("#cfccc4")


def xaxis(ax, t0: int, t1: int, step_min: int) -> None:
    first = (t0 // (step_min * NS_MIN) + 1) * step_min * NS_MIN
    ticks = list(range(int(first), int(t1), step_min * NS_MIN))
    ax.set_xticks([(t - t0) / NS_MIN for t in ticks], [thai(t) for t in ticks])


def panel_main(ax, tf: P.TF, r: pd.Series) -> None:
    """The entry TF: from 15 bars before the pattern's first point to 30 bars after the decision."""
    mn = tf.minutes
    t0 = int(r.start_t) - 15 * mn * NS_MIN
    t1 = int(r.t_dec) + 30 * mn * NS_MIN
    sel = (tf.t_open >= t0) & (tf.t_open < t1)
    b = tf.b[sel]
    x = (tf.t_open[sel] - t0) / NS_MIN + mn / 2
    style(ax)
    candles(ax, b, x, 3.0 if mn == 1 else 4.0)
    X = lambda t: (int(t) - t0) / NS_MIN  # noqa: E731
    xr = X(t1)
    ax.axhspan(r.level - r.zone, r.level + r.zone, color=LEVEL, alpha=0.12, linewidth=0)
    ax.axhline(r.level, color=LEVEL, linewidth=1.2)
    ax.text(xr + 0.5, r.level, f"{'news leg' if r.level_kind == 'news leg' else r.level_kind} {r.level:.2f}",
            fontsize=7, color=INK, va="center")
    for t, p, lab in zip(r.pts_t, r.pts_p, r.pts_lab, strict=True) if r.family != "base" else ():
        ax.plot([X(t) + mn / 2], [p], marker="o", markersize=7, color=PAT, markeredgecolor="white", markeredgewidth=1.2, zorder=5)
        below = label_below(lab, int(r.side))
        ax.annotate(lab, (X(t) + mn / 2, p), xytext=(0, -11 if below else 6), textcoords="offset points", ha="center",
                    fontsize=7, color=INK, zorder=6)
    if r.neck_t is not None:
        (ta, tb), (pa, pb) = r.neck_t, r.neck_p
        slope = (pb - pa) / ((tb - ta) / NS_MIN)
        xs = np.array([X(ta), X(r.t_dec)]) + np.array([mn / 2, 0])
        ax.plot(xs, pa + slope * (xs - X(ta) - mn / 2), color=PAT, linewidth=1.2, linestyle="--")
        ax.text(xs[1], pa + slope * (xs[1] - X(ta) - mn / 2), " neckline", fontsize=7, color=INK, va="bottom")
    elif r.box_t is not None:
        (ta, tb), (lo_b, hi_b) = r.box_t, r.box_p
        ax.add_patch(plt.Rectangle((X(ta), lo_b), X(tb) + mn - X(ta), hi_b - lo_b, fill=False, edgecolor=PAT, linewidth=1.2))
        ax.text(X(ta), hi_b, "base", fontsize=7, color=INK, va="bottom")
    else:
        ax.hlines(r.trigger, X(r.pts_t[1]) + mn / 2, X(r.t_dec), color=PAT, linewidth=1.2, linestyle="--")
        ax.text(X(r.t_dec), r.trigger, " trigger", fontsize=7, color=INK, va="bottom")
    ax.axvline(X(r.t_dec), color=ENTRY, linewidth=0.8, alpha=0.7)
    ax.plot([X(r.entry_t) + 0.2], [r.entry], marker=">" if r.side > 0 else "<", markersize=9, color=ENTRY, zorder=6)
    ax.hlines(r.stop, X(r.t_dec), xr, color=STOP, linewidth=1.1, linestyle="--")
    ax.text(xr + 0.5, r.stop, f"stop {r.stop:.2f}", fontsize=7, color=INK, va="center")
    ax.text(xr + 0.5, r.entry, f"entry {r.entry:.2f}", fontsize=7, color=INK, va="center")
    lo_y, hi_y = b.low.min(), b.high.max()
    if np.isfinite(r.next_level):
        ax.hlines(r.next_level, X(r.t_dec), xr, color=NEXT, linewidth=1.1, linestyle="--")
        ax.text(xr + 0.5, r.next_level, f"next level {r.next_level:.2f}", fontsize=7, color=INK, va="center")
        lo_y, hi_y = min(lo_y, r.next_level), max(hi_y, r.next_level)
    pad = 0.06 * (hi_y - lo_y)
    ax.set_ylim(min(lo_y, r.stop, r.level - r.zone) - pad, max(hi_y, r.stop, r.level + r.zone) + pad)
    ax.set_xlim(-0.5, xr + 0.12 * xr)
    xaxis(ax, t0, t1, 10 if mn == 1 else 30)
    ax.set_title(f"{r.tf} - the entry TF; blue line = the decision (the breakout bar's close)", fontsize=8, color=INK)


def panel_other(ax, tf: P.TF, r: pd.Series, C: pd.DataFrame) -> None:
    """The other TF: M5 from 6 hours before to 1 hour after an M1 decision, with its confirmed swings; or M1 from 60
    minutes before to 30 after an M5 decision, with the agreeing M1 pattern's points."""
    if tf.minutes == 5:
        t0, t1 = int(r.t_dec) - 360 * NS_MIN, int(r.t_dec) + 60 * NS_MIN
    else:
        t0, t1 = int(r.t_dec) - 60 * NS_MIN, int(r.t_dec) + 30 * NS_MIN
    sel = (tf.t_open >= t0) & (tf.t_open < t1)
    b = tf.b[sel]
    x = (tf.t_open[sel] - t0) / NS_MIN + tf.minutes / 2
    style(ax)
    candles(ax, b, x, 2.2)
    X = lambda t: (int(t) - t0) / NS_MIN  # noqa: E731
    ax.axhspan(r.level - r.zone, r.level + r.zone, color=LEVEL, alpha=0.12, linewidth=0)
    ax.axhline(r.level, color=LEVEL, linewidth=1.0)
    ax.axvline(X(r.t_dec), color=ENTRY, linewidth=0.8, alpha=0.7)
    if tf.minutes == 5:
        d = tf.last_complete(int(r.t_dec))
        pb, pp, pk, pc = tf.piv
        k = (pc <= d) & (tf.t_open[pb] >= t0)
        ax.plot((tf.t_open[pb[k]] - t0) / NS_MIN + 2.5, pp[k], linestyle="none", marker="D", markersize=4,
                color=MUTED, zorder=5)
        ax.set_title(f"M5 (6 h before, 1 h after; grey = its swings confirmed by the decision) - {r.other_structure}",
                     fontsize=8, color=INK)
    else:
        m1 = C[(C.tf == "M1") & (C.side == r.side) & ((C.level - r.level).abs() <= r.zone) & (C.t_dec <= r.t_dec)
               & (C.t_dec >= r.t_dec - P.AGREE_MIN * NS_MIN)]
        for q in m1.itertuples():
            ax.plot([X(t) + 0.5 for t in q.pts_t], q.pts_p, marker="o", markersize=5, color=PAT, linewidth=0.8, zorder=5)
            ax.axvline(X(q.t_dec), color=PAT, linewidth=0.6, alpha=0.6)
        ax.set_title(f"M1 (60 min before, 30 after) - the agreeing M1 pattern(s): {r.other_pattern}", fontsize=8, color=INK)
    xaxis(ax, t0, t1, 60 if tf.minutes == 5 else 15)


def main() -> None:
    C = pd.read_parquet(HERE / "p_catches.parquet")
    if (C.t_dec >= P.EXAM_START.value).any():
        raise P.ExamPeriodError("an exam decision in the catches")
    m = P.load_m1()
    tfs = {"M1": P.TF(m, 1), "M5": P.TF(m, 5)}
    outdir = HERE / "charts" / "p_patterns"
    outdir.mkdir(parents=True, exist_ok=True)
    cards, rows = [], []
    for k, (s, r) in enumerate(pick(C), 1):
        if r is None:
            rows.append(f"<tr><td>{k}</td><td>{html.escape(s['slot'])}</td><td colspan=4>empty - no catch for this slot</td></tr>")
            print(f"#{k} {s['slot']}: EMPTY", flush=True)
            continue
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.0), gridspec_kw={"width_ratios": [1.8, 1]})
        fig.patch.set_facecolor("#fcfcfb")
        panel_main(a1, tfs[r.tf], r)
        panel_other(a2, tfs["M5" if r.tf == "M1" else "M1"], r, C)
        t = title(k, r)
        fig.suptitle(t, fontsize=8.5, color=INK, x=0.01, ha="left")
        fig.text(0.01, 0.005, f"Slot: {s['slot']}. {agreement(r)}.", fontsize=7.5, color=MUTED)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        f = outdir / f"{k:02d}.png"
        fig.savefig(f, dpi=90, facecolor=fig.get_facecolor())
        plt.close(fig)
        cards.append((t, s["slot"], agreement(r), base64.b64encode(f.read_bytes()).decode()))
        rows.append(f"<tr><td>{k}</td><td>{html.escape(s['slot'])}</td><td>{thai(r.t_dec, '%Y-%m-%d %H:%M')}</td>"
                    f"<td>{html.escape(r['name'])}</td><td>{html.escape(r.level_kind)}</td><td>{html.escape(agreement(r))}</td></tr>")
        print(f"#{k} {s['slot']}: {t}", flush=True)
    body = "\n".join(f'<figure><figcaption><b>{html.escape(t)}</b><br><span class="why">Slot: {html.escape(s)}. '
                     f'{html.escape(a)}.</span></figcaption><img alt="{html.escape(t)}" src="data:image/png;base64,{b64}"></figure>'
                     for t, s, a, b64 in cards)
    (HERE / "charts" / "p_patterns.html").write_text(PAGE.format(n=len(cards), table="\n".join(rows), body=body), encoding="utf-8")
    print(f"{len(cards)} drawn -> {outdir}, page {HERE / 'charts' / 'p_patterns.html'}")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chart Pattern Catches</title>
<style>
:root {{ --bg: #f6f5f2; --fg: #1d2127; --muted: #52514e; --card: #ffffff; --line: #dcd9d2; color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }} }}
:root[data-theme="dark"] {{ --bg: #15171b; --fg: #e8e6e1; --muted: #b9bec8; --card: #fcfcfb; --line: #30343b; }}
body {{ background: var(--bg); color: var(--fg); font-family: system-ui, sans-serif; margin: 0; padding: 20px 16px; }}
main {{ max-width: 1240px; margin: 0 auto; display: grid; gap: 18px; }}
h1 {{ font-size: 1.3rem; margin: 0; text-wrap: balance; }}
p {{ color: var(--muted); margin: 0; max-width: 80ch; line-height: 1.5; }}
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
<h1>Chart patterns at the level - the detector's catches</h1>
<p>{n} catches from the learning parts (P1 2025-10-18 .. 2026-01-16, P2 2026-01-16 .. 2026-04-18), chosen by a rule
written before drawing (one per slot, the one nearest the middle of its part), for the owner to confirm that the code
finds the patterns meant: inverse head and shoulders / head and shoulders, W / M (also a second low that sweeps the
first), a sweep past the level then the higher low (lower high), a base then its break. Left: the entry TF - the
purple band is the owner's H1 level (or the news first minute's extreme) with its zone, orange points the pattern
(LS / Head / RS, L1 / P / L2, S / P / HL, the base box), the dashed orange line the neckline or trigger, the blue line
the decision (the first close beyond it), the blue arrow the entry (the next bar's open), the red dashed line the
stop, the green dashed line the next level. Right: the other TF. Thai time. Nothing is counted here: no outcomes.
Research charts only.</p>
<div class="wrap"><table>
<tr><th>#</th><th>slot</th><th>Thai time</th><th>pattern</th><th>level</th><th>the other TF</th></tr>
{table}
</table></div>
{body}
</main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
