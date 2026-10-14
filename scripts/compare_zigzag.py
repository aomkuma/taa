r"""Compare the bot's ZigZag port with values exported from the MT5 terminal (TAA-L813, CHART_READ.md §4.1).

The terminal side is ``scripts/mt5/TAA_ExportZigZag.mq5``: it writes ``TAA_zigzag_<symbol>_<tf>.csv``
(OHLC plus the ZigZag buffer and its two candidate maps, closed bars only) into the terminal's
``MQL5\Files`` folder. This script runs the port on the same bars and reports, per file:

- **maps**: bars whose high/low candidate differs (the first ``2 × depth`` bars are skipped: the terminal
  computed them from older history; so are the last ``backstep`` bars, which the forming bar may still erase);
- **pivots**: the port's fixed pivots against the terminal's ZigZag points, skipping the first two (warm-up)
  and the terminal's last two points (its last leg, which it still redraws).

    .venv\Scripts\python scripts\compare_zigzag.py [FOLDER]   # default: the FBS terminal's MQL5\Files
"""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.indicators.chart_read import _zigzag_maps, zigzag_pivots


def default_folder() -> str:
    root = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal"
    hits = sorted(glob.glob(str(root / "*" / "MQL5" / "Files" / "TAA_zigzag_*.csv")))
    return str(Path(hits[0]).parent) if hits else "."


def compare(df: pd.DataFrame) -> dict[str, object]:
    depth, dev, back = (int(df[k].iloc[0]) for k in ("depth", "deviation", "backstep"))
    point = float(df["point"].iloc[0])
    hi, lo = df["high"].to_numpy(float), df["low"].to_numpy(float)
    n = len(df)
    hmap, lmap = _zigzag_maps(hi, lo, point, depth, dev, back)
    span = slice(2 * depth, n - back)
    map_diff = (
        np.flatnonzero(
            ~np.isclose(hmap[span], df["high_map"].to_numpy(float)[span])
            | ~np.isclose(lmap[span], df["low_map"].to_numpy(float)[span])
        )
        + 2 * depth
    )
    mine = zigzag_pivots(hi, lo, point, depth=depth, deviation=dev, backstep=back)
    theirs = np.flatnonzero(df["zigzag"].to_numpy(float) != 0)
    if len(mine) < 3 or len(theirs) < 3:
        return {"bars": n, "map_diff": len(map_diff), "pivots": 0, "pivot_diff": [], "note": "too few pivots"}
    lo_pos = mine[2].pivot_pos
    hi_pos = theirs[-3]
    a = {s.pivot_pos for s in mine if lo_pos <= s.pivot_pos <= hi_pos}
    b = {int(p) for p in theirs if lo_pos <= p <= hi_pos}
    diff = sorted(a ^ b)
    return {
        "bars": n,
        "map_diff": len(map_diff),
        "map_diff_first": [int(x) for x in map_diff[:5]],
        "pivots": len(b),
        "pivot_diff": [
            (int(p), pd.Timestamp(int(df["time"].iloc[p]), unit="s").isoformat(), "port" if p in a else "mt5")
            for p in diff[:8]
        ],
    }


def main() -> int:
    folder = sys.argv[1] if len(sys.argv) > 1 else default_folder()
    files = sorted(glob.glob(os.path.join(folder, "TAA_zigzag_*.csv")))
    if not files:
        print(f"no TAA_zigzag_*.csv in {folder}: run scripts/mt5/TAA_ExportZigZag.mq5 in the terminal first")
        return 1
    print(f"folder: {folder}\n")
    print(f"{'file':34} {'bars':>5} {'map diff':>8} {'pivots':>6} {'pivot diff':>10}")
    bad = 0
    for path in files:
        r = compare(pd.read_csv(path))
        d = r["pivot_diff"]
        bad += int(bool(d) or bool(r["map_diff"]))
        print(f"{Path(path).name:34} {r['bars']:>5} {r['map_diff']:>8} {r['pivots']:>6} {len(d):>10}")  # type: ignore[arg-type]
        for item in d:  # type: ignore[attr-defined]
            print(f"    only in {item[2]}: bar {item[0]} (open time {item[1]} server)")
        if r["map_diff"]:
            print(f"    first map differences at bars {r['map_diff_first']}")
    print(f"\n{len(files) - bad} of {len(files)} files match")
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
