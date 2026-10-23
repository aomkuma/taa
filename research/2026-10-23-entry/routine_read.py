"""The trader's routine, step 1 - read the forest (owner 2026-10-23: "imagine you sit at the computer this morning,
open the chart, see the price structure, open the checklist and have enough to say which setups it fits; every
trade picks the most suitable one; after it closes, journal it, find the mistakes, learn why it won or lost - all
without bias").

Only the bot's code (app/strategy/*) and only bars closed by ``AS_OF``. Writes the read to live/<as-of>.md BEFORE
anything after it is known (committed at once, so the review can never bend the read), and prints it.

Draft situation names (the owner's hunting picture, docs/OWNER_GOALS.md) - definitions to be confirmed by the owner:
  elephant  extreme volatility (H1 vol > 1.4 x usual, or today's range > 2 steps) -> step back
  tiger     a scheduled US release within 60 minutes -> only the news weapon
  boar      a one-way market (the last 3 D1 closes the same way, or yesterday a strong D1 bar)
  deer      price sitting at a zone line (8+ M15 bars in its band)
  rabbit    a quiet range (vol < 0.9, no one-way run)
  (none)    nothing clear

    .venv/Scripts/python research/2026-10-23-entry/routine_read.py [AS_OF_UTC, default: the last closed M15 bar]
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from candidates import FRAMES, frame, window  # noqa: E402

from app.news.releases import load_releases  # noqa: E402
from app.strategy import context_read as cr  # noqa: E402
from app.strategy import level_momentum as lm  # noqa: E402
from app.strategy import strong_levels as sl  # noqa: E402
from app.strategy import structure_read as sr  # noqa: E402
from app.strategy import zone_break as zb  # noqa: E402
from app.strategy import zone_grid as zg  # noqa: E402
from app.strategy import zone_reject as zj  # noqa: E402
from app.strategy import zone_retest as zr  # noqa: E402

TH = "Asia/Bangkok"
WEAPONS = [  # (weapon, its animal, status, when)
    ("PLAN-1 Asia B2 (M1/M5 pattern at the owner's H1 level)", "rabbit / any", "REAL - passed its frozen exam (+0.140)", "07:00-09:00 Thai"),
    ("PLAN-1 London ORB (13:00 Thai opening range)", "any", "REAL - in PLAN-1 (exam -0.006)", "13:00-15:00 Thai"),
    ("PLAN-1 NY straddle (08:30 New York, +-2 USD, stop 8, out +30 min)", "tiger / every weekday", "REAL - passed (+0.285)", "19:30 Thai (EDT)"),
    ("T4 consolidation at a line, then THROUGH", "deer", "SHADOW - raw +0.083, not through the journal yet", "any session"),
    ("T1 re-test of a broken line", "boar", "SHADOW - raw -0.074", "any session"),
    ("T2 rejection at a line (bounce)", "rabbit", "SHADOW - raw -0.024; bounces lost in every form", "any session"),
    ("Stand aside", "elephant", "RULE - held in learning and exam", "-"),
]


def fmt_sign(v: int) -> str:
    return {1: "up (HH/HL)", -1: "down (LH/LL)", 0: "mixed"}[int(v)]


def main() -> None:
    data = {tf: frame(tf) for tf in FRAMES}
    m15df, M15 = data["M15"]
    as_of = pd.Timestamp(sys.argv[1], tz="UTC") if len(sys.argv) > 1 else pd.Timestamp(int(M15.avail[-1]), tz="UTC")
    t = as_of.value
    w = {tf: window(data[tf][1], t, 700) for tf in FRAMES}
    D1 = data["D1"][1]
    G = zg.grid_rows(D1.t_open, D1.o, D1.h, D1.lo, D1.c)
    st = zg.grid_at(G, t)
    xm = sl.closed(w["M15"], t)
    price = float(xm.c[-1])
    out: list[str] = []
    say = out.append
    say(f"# The forest read - {as_of.tz_convert(TH):%a %d %b %Y %H:%M} Thai (bars closed by {as_of:%H:%M} UTC)\n")

    say("## 1. Health")
    for tf in FRAMES:
        last = pd.Timestamp(int(sl.closed(data[tf][1], t).avail[-1]), tz="UTC")
        say(f"- {tf}: last closed bar ends {last.tz_convert(TH):%a %d %H:%M} Thai")
    recent = m15df[(m15df.index > as_of - pd.Timedelta(days=7)) & (m15df.index < as_of)].index
    gaps = recent.to_series().diff().dt.total_seconds().div(60)
    big = gaps[(gaps > 90) & ~((recent.to_series().dt.dayofweek == 0) | (recent.to_series().dt.dayofweek == 6))]
    say(f"- M15 gaps over 90 min in the last 7 days (weekends aside): {len(big)}"
        + (f" - at {', '.join(f'{x:%d %H:%M}' for x in big.index[:3])} UTC" if len(big) else ""))
    rel = load_releases(ROOT / "app/news/us_releases.csv")
    today = as_of.tz_convert("America/New_York").date()
    today_rel = [r for r in rel if r.at.astimezone(pd.Timestamp(0).tz_localize("UTC").tzinfo).date() == as_of.date()]
    upcoming = [r for r in rel if r.at >= as_of.to_pydatetime()][:3]
    say(f"- US releases today on the bot's calendar: {', '.join(f'{r.event} {pd.Timestamp(r.at).tz_convert(TH):%H:%M} Thai' for r in today_rel) or 'none'}"
        f"; next: {', '.join(f'{r.event} {pd.Timestamp(r.at).tz_convert(TH):%d %b %H:%M}' for r in upcoming)}")
    say("- calendar coverage: CPI / NFP fetched to Dec 2026; FOMC / PCE / GDP / PPI after 2026-10-15 are NOT in the file (a gap to fix)")

    say("\n## 2. The plan - the zone grid and the far view")
    shifts = np.flatnonzero(G.shift[: st.row + 1])
    last_shift = shifts[-1]
    say(f"- grid: anchor {st.anchor:.2f}, step {st.step:.2f} USD; last zone shift {'down' if G.shift[last_shift] < 0 else 'up'} "
        f"(the D1 bar of {pd.Timestamp(int(D1.t_open[last_shift]), tz='UTC').tz_convert('Europe/Athens'):%a %d %b})")
    line, dist, share = zg.nearest_line(st, price)
    say(f"- price {price:.2f}: nearest line {line:.2f} ({dist:.1f} USD, {share:.2f} step)")
    lines = sl.zone_lines(w["H4"], w["D1"], t, st.anchor, st.step, price - 1.6 * st.step, price + 1.6 * st.step)
    say("- lines around price (strength = H4 / D1 swings that turned within 0.15 step):")
    for lv in sorted(lines, key=lambda x: -x.price):
        mark = " <- price" if abs(lv.price - price) < st.step / 4 else ""
        say(f"  - {lv.price:9.2f} {'MAIN' if lv.source == 'zone' else 'half'} ({lv.touches}){mark}")
    anchors = [float(G.anchor[i]) for i in shifts[-6:]]
    strong = sl.strong_levels(w["H4"], w["D1"], t, st.step, anchors)
    above = sorted([x for x in strong if x.price > price], key=lambda x: x.price)[:3]
    below = sorted([x for x in strong if x.price < price], key=lambda x: -x.price)[:3]
    say(f"- strong levels above: {', '.join(f'{x.price:.1f} ({x.source}, {x.touches})' for x in above)}")
    say(f"- strong levels below: {', '.join(f'{x.price:.1f} ({x.source}, {x.touches})' for x in below)}")

    say("\n## 3. Trend, phase, structure, volatility")
    day = cr.last_day(w["D1"], t)
    ph = sr.phase(w["D1"], t)
    say(f"- yesterday's D1: {'up' if day.direction > 0 else 'down' if day.direction < 0 else 'flat'}, body {day.body_atr:.2f} ATR, "
        f"close position {day.close_pos:.2f} -> {'STRONG' if day.strong else 'not strong'}")
    say(f"- phase (the last 3 D1 closes): {'one-way UP' if ph > 0 else 'one-way DOWN' if ph < 0 else 'not one-way'}")
    for tf in ("D1", "H4", "H1", "M15"):
        s = sr.structure(w[tf], t)
        say(f"- {tf} structure: {fmt_sign(s.sign)}, picture {'clear' if s.clear else 'not clear'}")
    vol = cr.vol_ratio(w["H1"], t)
    run, rng = cr.day_so_far(w["H1"], t, price, 1, st.step)
    say(f"- H1 volatility {vol:.2f} x usual; today so far: {run:+.2f} step from the open (up = +), range {rng:.2f} step")

    say("\n## 4. Momentum at the nearest lines")
    up_line = min((x.price for x in lines if x.price > price), default=math.nan)
    dn_line = max((x.price for x in lines if x.price < price), default=math.nan)
    for name, lvl, side in (("above (a resistance)", up_line, -1), ("below (a support)", dn_line, 1)):
        if not math.isfinite(lvl):
            continue
        mo = lm.level_momentum(w["H1"], t, lvl, 0.15 * st.step, side, t - 5 * 24 * 3600 * 10**9)
        me = lm.level_momentum(w["M15"], t, lvl, 0.15 * st.step, side, t - 24 * 3600 * 10**9)
        say(f"- {name} {lvl:.2f}: H1 visits in 5 days {mo.touches}, bounces {', '.join(f'{b:.1f}' for b in mo.bounces[-4:])} USD"
            f"{' (WORN)' if mo.worn else ''}; approach {mo.approach:+.2f} ATR; M15 bars at it now {me.bars_at_line}")

    say("\n## 5. The animal in front (draft rules)")
    near_rel = [r for r in rel if abs((pd.Timestamp(r.at) - as_of).total_seconds()) <= 3600]
    at_line = lm.level_momentum(w["M15"], t, line, 0.15 * st.step, 1, t - 24 * 3600 * 10**9).bars_at_line
    animals = []
    if vol > 1.4 or rng > 2:
        animals.append(f"ELEPHANT (vol {vol:.2f}, range {rng:.2f} step) -> step back")
    if near_rel:
        animals.append(f"TIGER ({', '.join(r.event for r in near_rel)})")
    if ph != 0 or day.strong:
        animals.append(f"BOAR ({'3-day one-way ' + ('up' if ph > 0 else 'down') if ph else ''}{' + ' if ph and day.strong else ''}"
                       f"{'yesterday strong ' + ('up' if day.direction > 0 else 'down') if day.strong else ''})")
    if at_line >= 8:
        animals.append(f"DEER (price {at_line} M15 bars at the line {line:.1f})")
    if vol < 0.9 and ph == 0:
        animals.append(f"RABBIT (quiet: vol {vol:.2f}, no one-way run)")
    say("- " + ("; ".join(animals) if animals else "nothing clear - no animal"))

    say("\n## 6. The shadow weapons' signals today (M15, the bot's code)")
    k = np.searchsorted(G.known, M15.avail, side="right") - 1
    sel = slice(max(0, len(M15.c) - 2000), int(np.searchsorted(M15.avail, t, side="right")))
    o, h, lo, c = (arr[sel] for arr in (M15.o, M15.h, M15.lo, M15.c))
    A, S = G.anchor[k][sel], G.step[k][sel]
    t0 = M15.t_open[sel]
    day_start = as_of.tz_convert("Europe/Athens").normalize().tz_convert("UTC").value
    sig = [("T1 re-test", e.entry_bar, e.side, e.entry, e.stop) for e in zr.zone_retests(h, lo, c, A, S)]
    sig += [("T2 rejection", e.entry_bar, e.side, e.entry, e.stop) for e in zj.zone_rejections(o, h, lo, c, A, S)]
    sig += [(f"T4 {'through' if e.through else 'bounce'}", e.entry_bar, e.side, e.entry, e.stop) for e in zb.zone_breaks(h, lo, c, A, S)]
    today_sig = sorted([x for x in sig if t0[x[1]] >= day_start], key=lambda x: x[1])
    for name, q, side, entry, stop in today_sig:
        say(f"- {pd.Timestamp(int(t0[q]) + 15 * 60 * 10**9, tz='UTC').tz_convert(TH):%H:%M} {name} {'BUY' if side > 0 else 'SELL'} "
            f"{entry:.2f}, stop {stop:.2f} (risk {abs(entry - stop):.1f})")
    if not today_sig:
        say("- none so far today")

    say("\n## 7. The weapons and today's picture")
    say("| weapon | its animal | status | when |\n|---|---|---|---|")
    for wpn, animal, status, when in WEAPONS:
        say(f"| {wpn} | {animal} | {status} | {when} |")
    text = "\n".join(out) + "\n"
    live = HERE / "live"
    live.mkdir(exist_ok=True)
    path = live / f"{as_of.tz_convert(TH):%Y-%m-%d_%H%M}_read.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    print(path)


if __name__ == "__main__":
    main()
