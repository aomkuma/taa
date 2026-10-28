"""charts_p by hand: the 12 slots and the written picking rule, the title and the agreement line, and one real picture
(the owner's 2026-01-09 W) drawn without error. Needs matplotlib:

    data/venv-research/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_charts_p.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import charts_p as CP  # noqa: E402
import patterns as P  # noqa: E402

MN = 60 * 10**9
M1, M2, OWN = CP.MID["P1"], CP.MID["P2"], CP.OWNER_NEWS


def row(key, tf, part, family, side, t, at_h1=True, at_news=False, other="", news_t=None):
    return dict(key=key, tf=tf, part=part, family=family, side=side, t_dec=int(t), at_h1=at_h1, at_news=at_news,
                other_pattern=other, news_t=news_t)


def frame() -> pd.DataFrame:
    """By hand. ihs P1 buy: a (-2 h), b (+1 h) -> b; p (at_h1 False, +10 min) is not an H1 catch. w P1 buy: d (+1 h)
    listed before c (-1 h), a tie -> the earlier, c. st P1 buy: e is at b's moment (taken) -> f (+5 h). base P1 buy:
    none. ihs P2 sell: g. w P2 sell: h (+2 min, its own moment) is a buy (excluded) -> i (+10 min). M5 P1 buy: j
    (+5 min) has no M1 pattern agreeing -> k. News P1: l2 (the owner's release + 2 min) before l (+3 min) and m
    (nearest the middle). News P2: o."""
    return pd.DataFrame([
        row("a", "M1", "P1", "ihs", 1, M1 - 120 * MN), row("b", "M1", "P1", "ihs", 1, M1 + 60 * MN),
        row("p", "M1", "P1", "ihs", 1, M1 + 10 * MN, at_h1=False),
        row("d", "M1", "P1", "w", 1, M1 + 60 * MN + 7), row("c", "M1", "P1", "w", 1, M1 - 60 * MN - 7),
        row("e", "M1", "P1", "st", 1, M1 + 60 * MN), row("f", "M1", "P1", "st", 1, M1 + 300 * MN),
        row("g", "M1", "P2", "ihs", -1, M2), row("h", "M1", "P2", "w", 1, M2 + 2 * MN), row("i", "M1", "P2", "w", -1, M2 + 10 * MN),
        row("j", "M5", "P1", "w", 1, M1 + 5 * MN), row("k", "M5", "P1", "ihs", 1, M1 + 50 * MN, other="inverse H&S"),
        row("l", "M1", "P1", "w", 1, OWN + 3 * MN, at_h1=False, at_news=True, news_t=OWN),
        row("l2", "M1", "P1", "st", 1, OWN + 2 * MN, at_h1=False, at_news=True, news_t=OWN),
        row("m", "M1", "P1", "w", 1, M1 + 30 * MN, at_h1=False, at_news=True, news_t=M1 + 25 * MN),
        row("o", "M1", "P2", "w", 1, M2 + 90 * MN, at_h1=False, at_news=True, news_t=M2 + 85 * MN),
    ])


def test_the_slots_in_order():
    s = CP.slots()
    assert [x["slot"] for x in s] == [
        "M1, ihs, P1 buy", "M1, w, P1 buy", "M1, st, P1 buy", "M1, base, P1 buy",
        "M1, ihs, P2 sell", "M1, w, P2 sell", "M1, st, P2 sell", "M1, base, P2 sell",
        "M5 entry, P1 buy", "M5 entry, P2 sell", "after the news first minute, P1", "after the news first minute, P2"]


def test_pick_by_the_written_rule():
    got = [None if r is None else r.key for _, r in CP.pick(frame())]
    assert got == ["b", "c", "f", None, "g", "i", None, None, "k", None, "l2", "o"]


def series(**kw) -> pd.Series:
    base = dict(t_dec=pd.Timestamp("2026-01-09 13:32", tz="UTC").value, part="P1", tf="M1", name="W",
                variant="W, the 2nd low swept the 1st", level=4459.43, level_kind="x3+ / flip", how="at", side=1,
                entry=4476.89, stop=4458.16, next_level=4479.41, news_ny=None, other_pattern="", other_structure="mixed")
    base.update(kw)
    return pd.Series(base)


def test_title_and_agreement():
    assert CP.title(11, series()) == (
        "#11 2026-01-09 20:32 Thai - P1 - M1 W (W, the 2nd low swept the 1st) at H1 level 4459.43 (x3+ / flip, at) - "
        "BUY entry 4476.89, stop 4458.16 (risk 18.73 USD), next level 4479.41")
    s = series(side=-1, name="M", variant="M", entry=100.0, stop=104.5, next_level=np.nan, level_kind="news leg",
               news_ny="10:00", level=104.0)
    assert CP.title(2, s).endswith("M1 M (M) after the 10:00 NY first minute (its extreme 104.00) - SELL entry 100.00, "
                                   "stop 104.50 (risk 4.50 USD), next level none")
    assert CP.agreement(series()) == "no M5 pattern in the last 30 min; M5 structure as it stands: mixed"
    assert CP.agreement(series(tf="M5", other_pattern="M", other_structure="down")) == (
        "M1 pattern: M; M1 structure as it stands: down")
    assert CP.thai(pd.Timestamp("2026-03-02 15:09", tz="UTC").value, "%Y-%m-%d %H:%M") == "2026-03-02 22:09"


def test_label_below():
    assert [CP.label_below(x, 1) for x in ("L1", "P", "L2", "LS", "N1", "Head", "S", "HL")] == [
        True, False, True, True, False, True, True, True]
    assert [CP.label_below(x, -1) for x in ("H1", "T", "H2", "LS", "N1", "Head", "S", "LH")] == [
        False, True, False, False, True, False, False, False]


def test_draw_the_owner_w(tmp_path):
    # the 2026-01-09 W from the scan (points from out_charts_p / the M1 bars): drawn on both panels without error
    import matplotlib.pyplot as plt

    m = P.load_m1(pd.Timestamp("2026-01-08", tz="UTC"), pd.Timestamp("2026-01-10", tz="UTC"))
    u = lambda s: pd.Timestamp(f"2026-01-09 {s}", tz="UTC").value  # noqa: E731
    r = series(family="w", start_t=u("13:20"), zone=1.114, trigger=4474.63, entry_t=u("13:32"),
               pts_t=[u("13:20"), u("13:25"), u("13:30")], pts_p=[4461.94, 4474.63, 4459.03], pts_lab=["L1", "P", "L2"],
               neck_t=None, neck_p=None, box_t=None, box_p=None)
    fig, (a1, a2) = plt.subplots(1, 2)
    CP.panel_main(a1, P.TF(m, 1), r)
    CP.panel_other(a2, P.TF(m, 5), r, pd.DataFrame())
    fig.savefig(tmp_path / "w.png")
    plt.close(fig)
    assert (tmp_path / "w.png").stat().st_size > 10_000
    assert a1.get_xticklabels()[0].get_text() == "20:10"  # Thai time on the axis: the first 10-minute tick after 20:05
