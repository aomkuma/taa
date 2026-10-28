"""Does picking the best variant on one year tell you anything about the next (owner 2026-10-27: "you read the
market well and predict it fairly accurately - why does it fall apart once it becomes code; which step is the
problem")?

Every variant of the round-1 sweep is run on the year its parameters were chosen on AND on the two earlier
years the parameters never saw. Then:

- the correlation between a variant's fitted score and its unseen score. Near zero means choosing by the
  fitted year is choosing noise;
- what the variant that looked best on the fitted year actually did on the unseen years;
- the best variant of the UNSEEN years, scored on the fitted year - the same test the other way round;
- the spread of all variants, which says how much a "best of N" pick is worth by chance alone.

    .venv/Scripts/python research/2026-10-26-three-bots/selection_bias.py
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bots  # noqa: E402

from app.core.enums import Timeframe  # noqa: E402
from app.engine.ai_trader import to_frame  # noqa: E402
from app.market_data.history_store import ParquetHistoryStore  # noqa: E402

FITTED = (pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-10-23", tz="UTC"))
UNSEEN = (pd.Timestamp("2023-09-05", tz="UTC"), pd.Timestamp("2025-10-19", tz="UTC"))
F: dict = {}


def load() -> None:
    hs = ParquetHistoryStore(HERE.parents[1] / "data/history")
    for tf in (Timeframe.M1, Timeframe.H1):
        F[tf] = to_frame(hs.load("FBS-Demo", "XAUUSD", tf, None, None))


def variants() -> list[tuple[str, bots.P]]:
    out = []
    for bot, boxes in (("DOWN", (0.2, 0.33)), ("UP", (0.2, 0.33))):
        for b in boxes:
            for r in ((0.382, 0.786), (0.236, 0.618), (0.236, 0.886), (0.5, 0.886)):
                for u in (0.2, 0.5):
                    for m in (0.8, 1.2):
                        name = f"{bot} box {b} retr {r[0]}-{r[1]} buf {u} minR {m}"
                        out.append(
                            (name, replace(bots.P(), bots=(bot,), box=b, retrace=r, buffer=u, min_r=m))
                        )
    for mode in ("fade", "break"):
        for tf in ("H4", "H1"):
            for tp in (0.3, 0.5, 0.8):
                for u in (0.2, 0.6):
                    name = f"RANGE {mode} {tf} tp {tp} buf {u}"
                    out.append((name, replace(bots.P(), bots=("RANGE",), range_mode=mode, range_tf=tf,
                                              tp_range=tp, buffer=u, min_r=0.8)))  # fmt: skip
    return out


def one(job: tuple[str, bots.P]) -> tuple[str, int, float, int, float]:
    if not F:
        load()
    name, p = job
    a = bots.run(F, p, *FITTED)
    b = bots.run(F, p, *UNSEEN)
    fr = sum(t.r for t in a) / len(a) if a else 0.0
    ur = sum(t.r for t in b) / len(b) if b else 0.0
    return name, len(a), fr, len(b), ur


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    jobs = variants()
    rows = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        for name, na, fr, nb, ur in ex.map(one, jobs):
            rows.append({"variant": name, "n_fit": na, "fitted": fr, "n_unseen": nb, "unseen": ur})
    d = pd.DataFrame(rows)
    d = d[(d.n_fit >= 15) & (d.n_unseen >= 15)]
    print(f"== {len(d)} variants with at least 15 trades in each period ==\n")
    print(f"- correlation between the fitted score and the unseen score: **{d.fitted.corr(d.unseen):+.2f}**")
    print(f"- all variants: fitted mean {d.fitted.mean():+.3f} (sd {d.fitted.std():.3f}); "
          f"unseen mean {d.unseen.mean():+.3f} (sd {d.unseen.std():.3f})")  # fmt: skip
    best = d.loc[d.fitted.idxmax()]
    print(f"\n- best on the FITTED year: {best.variant}")
    print(
        f"  fitted {best.fitted:+.3f} ({int(best.n_fit)} trades) -> unseen **{best.unseen:+.3f}** ({int(best.n_unseen)} trades)"
    )
    top5 = d.nlargest(5, "fitted")
    print(
        f"- the top 5 by fitted score averaged {top5.fitted.mean():+.3f} fitted -> {top5.unseen.mean():+.3f} unseen"
    )
    bu = d.loc[d.unseen.idxmax()]
    print(f"\n- best on the UNSEEN years: {bu.variant}")
    print(f"  unseen {bu.unseen:+.3f} -> fitted {bu.fitted:+.3f} (the same test the other way round)")
    print(f"\n- picking the best of {len(d)} variants is worth about {d.fitted.max() - d.fitted.mean():+.3f} R "
          f"over the average, by selection alone")  # fmt: skip
    print("\n| variant | fitted R | unseen R |")
    print("|---|---|---|")
    for _, r in d.nlargest(8, "fitted").iterrows():
        print(f"| {r.variant} | {r.fitted:+.3f} | {r.unseen:+.3f} |")


if __name__ == "__main__":
    main()
