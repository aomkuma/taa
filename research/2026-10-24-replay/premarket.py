"""The morning plan before a trading day (owner 2026-10-25, rule P26: "before trading each day, look at the market:
yesterday's support / resistance and key levels, the likely trend today, the opportunities, the side with the
edge, where price may turn or go on - and summarise it to me; every time before trading").

This script gathers what the system reads at the start of the Thai day (07:00 Thai, bars closed by then only):
the readings, the readers' lines (rhythm, pictures, the zone plan, strong levels), yesterday's own levels (the M15
swings of the previous Thai day and its high / low) and the liquidity map. I write the plan from it (scenarios
with trigger / stop / take-profit point), into research/2026-10-24-replay/plan_<date>.md, and summarise it to the
owner before the day is replayed; the plan's summary is added to the AI's journal as the day's start.

    .venv/Scripts/python research/2026-10-24-replay/premarket.py 2026-07-06
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/2026-10-23-entry"))
sys.path.insert(0, str(ROOT / "research/2026-10-23-entry/knowledge"))

import kb  # noqa: E402  (the research door: the stored frames)

from app.strategy import behaviors as bh  # noqa: E402
from app.strategy import knowledge as kn  # noqa: E402
from app.strategy import liquidity as lq  # noqa: E402
from app.strategy.readout import reader_lines  # noqa: E402

TH = "Asia/Bangkok"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    day = pd.Timestamp(sys.argv[1])
    at = pd.Timestamp(f"{day.date()} 07:00", tz=TH).tz_convert("UTC")  # the Thai trading day starts
    fr = kb.frames()
    f = kn.features(fr, at)
    print(f"# The morning plan's inputs - {at.tz_convert(TH):%a %d %b %Y} 07:00 Thai (bars closed by then)\n")
    keys = ("price", "d1_big", "d1_regime", "d1_rhythm", "h4_trend", "h4_rhythm", "h1_trend", "h1_rhythm",
            "m15_rhythm", "phase", "yesterday", "h1_vol", "h1_atr", "d1_atr20", "release_min", "runaway")  # fmt: skip
    print("## Readings\n")
    print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in f.items() if k in keys}))
    print("\n## Yesterday's own levels (the previous Thai day, 05:00-05:00 Thai)\n")
    for line in bh.day_levels(fr.m15, fr.d1, at - pd.Timedelta(hours=2, minutes=1)):
        print(f"- {line}")
    print("\n## The readers (rhythm, pictures, the zone plan, strong levels, the clock)\n")
    for line in reader_lines(fr, at):
        print(f"- {line}")
    print("\n## The liquidity map (liquidate zones: the stop side)\n")
    m5 = kn.m5_frame(fr.m1, at)
    for line in lq.liquidity_lines(fr.m1, m5, fr.m15, fr.h1, fr.d1, at):
        print(f"- {line}")
    releases = [x for x in fr.releases if at <= pd.Timestamp(x.at) < at + pd.Timedelta(days=1)]
    print("\n## Today's scheduled US releases (Thai time)\n")
    for x in releases:
        print(f"- {pd.Timestamp(x.at).tz_convert(TH):%H:%M} {getattr(x, 'name', '')}")
    if not releases:
        print("- none")


if __name__ == "__main__":
    main()
