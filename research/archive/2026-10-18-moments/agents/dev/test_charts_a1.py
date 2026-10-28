"""charts_a1 by hand: which cases are drawn (pick), the variant line, the headline, the minutes axis, and a drawn
picture of the owner's example (the exam refused). Needs matplotlib:

    data/venv-research/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_charts_a1.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from charts_a1 import draw, headline, pick, variant_labels, xmin  # noqa: E402
from sweep_detector import NS_S, scan  # noqa: E402

U = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
OWNER, B, A1, C, K = U("2026-01-09 13:30"), U("2026-01-05 13:30"), U("2025-11-20 13:30"), U("2026-02-02 13:30"), U("2026-03-10 12:30")
D, E, F_, G, H, I_, J = (U("2026-02-03 15:00"), U("2026-02-04 15:00"), U("2026-02-05 15:00"), U("2025-11-03 13:30"),
                         U("2025-11-04 13:30"), U("2025-11-05 13:30"), U("2026-03-02 13:30"))


def frame() -> pd.DataFrame:
    """The detector's rows (larger / +3) and the three variants' rows, by hand.
    P1 08:30 faked: OWNER 18.6, A1 10, B 15 -> the median 15: B. P2 08:30 faked: C 30, K 25 -> the median 27.5, a tie:
    the earlier, C. P2 10:00 faked: D 12, E 14, F 20 -> the median 14: E. Continued at a release minute: P1 G (cont 2,
    CLM), H (6, RET) -> the median 4, a tie: the earlier, G (I_ has no release, not a candidate); P2 J. Not came down,
    not drawn yet: B and C are drawn, K (25) is left -> K. The side rules disagree on D (max move 8) and I_ (12) -> I_.
    The strict rule calls F continued -> F. Order: OWNER, B, C, E, G, J, K, I_, F."""
    rows = [  # t, part, ny, names, outcome, sweep, cont, came_down, up1, dn1
        (OWNER, "P1", "08:30", "NFP", "faked", 18.6, None, True, 1.0, 14.0),
        (A1, "P1", "08:30", "CLM+NFP", "faked", 10.0, None, True, 4.0, 18.0),
        (B, "P1", "08:30", "", "faked", 15.0, None, False, 3.3, 3.5),
        (C, "P2", "08:30", "", "faked", 30.0, None, False, 0.0, 5.0),
        (K, "P2", "08:30", "", "faked", 25.0, None, False, 0.0, 6.0),
        (D, "P2", "10:00", "", "faked", 12.0, None, True, 8.0, 4.0),
        (E, "P2", "10:00", "", "faked", 14.0, None, True, 0.0, 6.0),
        (F_, "P2", "10:00", "", "faked", 20.0, None, True, 0.0, 6.0),
        (G, "P1", "08:30", "CLM", "continued", None, 2.0, None, 5.0, 0.0),
        (H, "P1", "08:30", "RET", "continued", None, 6.0, None, 5.0, 0.0),
        (I_, "P1", "08:30", "", "continued", None, 10.0, None, 12.0, 3.5),
        (J, "P2", "08:30", "NFP", "continued", None, 5.0, None, 5.0, 0.0),
    ]
    other = {(D, "first", 3.0): "continued", (I_, "first", 3.0): "faked", (F_, "larger", 0.0): "continued"}
    out = []
    for t, p, ny, nm, oc, sw, co, cd, u, dn in rows:
        for rule, ex in (("larger", 3.0), ("first", 3.0), ("larger", 0.0), ("first", 0.0)):
            out.append(dict(t=t, set="fixed", side_rule=rule, cont_extra=ex, part=p, ny=ny, names=nm,
                            outcome=other.get((t, rule, ex), oc), sweep=sw, cont=co, came_down=cd, up1=u, dn1=dn))
    return pd.DataFrame(out)


def test_pick_by_the_written_rule():
    got = pick(frame())
    assert [r.name for r, _ in got] == [OWNER, B, C, E, G, J, K, I_, F_]
    why = [w for _, w in got]
    assert why[0].startswith("the owner's own example") and why[1] == "faked, P1 08:30 NY: the one nearest the median sweep"
    assert "researcher's first 3-USD move reads it: faked" in why[7] and "any new extreme" in why[8]


def test_variant_labels_put_the_detector_first():
    V = frame()
    s = variant_labels(V[V.t == F_])
    assert s == ("larger move / new extreme +3: faked; larger move / new extreme +0: continued; "
                 "first 3-USD move / new extreme +3: faked; first 3-USD move / new extreme +0: faked")


def test_headline_and_the_minutes_axis():
    r = pd.Series(dict(first=-1, outcome="faked", leg1=14.12, sweep=18.61, sweep_min=10.39, back=12.87,
                       came_down=True, third=False))
    assert headline(r) == "FAKED: first leg down 14.1, sweep up 18.6 past p0 at minute 10.4, back 12.9 (came down)"
    r3 = r.copy()
    r3["third"] = True
    assert headline(r3).endswith("back 12.9 (came down, through p0)")
    r2 = r.copy()
    r2["came_down"] = False
    assert headline(r2).endswith("back 12.9 (did not come down)")
    c = pd.Series(dict(first=1, outcome="continued", leg1=26.77, cont=4.3))
    assert headline(c) == "CONTINUED: first leg up 26.8, then 4.3 further up within 15 minutes"
    assert xmin(1_000 * NS_S + 90 * NS_S, 1_000 * NS_S) == pytest.approx(1.5)


def test_draw_the_owner_example_and_refuse_the_exam(tmp_path):
    ev = pd.DataFrame(dict(t=[OWNER], ny=["08:30"], names=["NFP"]))
    r = scan(ev).iloc[0].copy()
    r["part"] = "P1"
    r.name = OWNER
    title = draw(r, 1, "test", tmp_path / "x.png")
    assert title.startswith("#1 2026-01-09 20:30 Thai (08:30 NY, NFP) - P1 - FAKED: first leg down 14.1, sweep up 18.6")
    assert (tmp_path / "x.png").stat().st_size > 10_000
    r.name = U("2026-04-17 23:30")  # its 45 minutes after reach the exam
    with pytest.raises(RuntimeError, match="exam"):
        draw(r, 2, "test", tmp_path / "y.png")
