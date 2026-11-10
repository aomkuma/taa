"""The runner's start checks on the stored bars of the pinned server (eye/ZONE_LIVE.md L2).

Pure functions over frames - no broker, no clock, no file access. The runner loads the stored frames of the
pinned server and reads the broker's closed bars; these functions judge them and say why a start is refused.

* ``check_stored_history``: the store exists, every frame the runner needs is there, and none starts later
  than the simulation's stored series of that frame (``REFERENCE_FIRST_BARS``, measured on ``FBS-Demo``,
  2026-11-04); a series that starts earlier is cut to the reference's first bar, so the steps, grids, pivots
  and arming are the simulation's.
* ``check_overlap``: the broker's closed bars reach back to the stored frame's last bar, and the bars they
  overlap agree (open time; open, high, low, close within one tick).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# The simulation's first stored bar (open time, UTC) of each frame (FBS-Demo) - L2: D1 2021-09-01, H4
# 2023-04-02, H1 and M15 2023-08-01, M5 2025-10-05. One constant; the live frames are cut to these.
REFERENCE_FIRST_BARS: dict[str, pd.Timestamp] = {
    "D1": pd.Timestamp("2021-09-01 21:00", tz="UTC"),
    "H4": pd.Timestamp("2023-04-02 21:00", tz="UTC"),
    "H1": pd.Timestamp("2023-08-01 00:00", tz="UTC"),
    "M15": pd.Timestamp("2023-08-01 00:00", tz="UTC"),
    "M5": pd.Timestamp("2025-10-05 22:05", tz="UTC"),
}

# D1, H4, H1, M15 are always needed (the state gate reads them); M5 only when it is the exec frame.
ALWAYS_FRAMES = ("D1", "H4", "H1", "M15")

_EPS = 1e-9


@dataclass(frozen=True)
class StartCheck:
    """``ok`` with the frames cut to the reference's first bar, or the refusal ``reasons`` (frames are then
    empty)."""

    ok: bool
    reasons: tuple[str, ...] = ()
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)


@dataclass(frozen=True)
class OverlapCheck:
    """``ok``, or the ``frame`` and the ``bar`` (open time; None when no bar is to blame), and why."""

    ok: bool
    frame: str = ""
    bar: pd.Timestamp | None = None
    reason: str = ""


def required_frames(exec_tf: str) -> tuple[str, ...]:
    if exec_tf not in ("M15", "M5"):
        raise ValueError(f"exec_tf must be M15 or M5, not {exec_tf!r}")
    return ALWAYS_FRAMES + (("M5",) if exec_tf == "M5" else ())


def _first_open(df: pd.DataFrame) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(df["open_time"], utc=True).min())


def check_stored_history(
    server: str,
    frames: Mapping[str, pd.DataFrame | None] | None,
    exec_tf: str,
    reference: Mapping[str, pd.Timestamp] | None = None,
) -> StartCheck:
    """L2's start checks on the stored frames of ``server``. ``frames`` is None (or empty) when the server
    has no store. Every refusal found is listed (a missing frame and a late one are reported together). A
    frame that is not required (M5 when the exec frame is M15) is cut when it reaches the reference and left
    out otherwise."""
    ref = REFERENCE_FIRST_BARS if reference is None else reference
    need = required_frames(exec_tf)
    if not frames:
        return StartCheck(False, (f"no stored bars for server {server}: fetch that server's history first",))
    reasons: list[str] = []
    for tf in need:
        df = frames.get(tf)
        if df is None or len(df) == 0:
            reasons.append(f"{tf}: the stored frame is missing for server {server}")
            continue
        first = _first_open(df)
        if first > ref[tf]:
            reasons.append(
                f"{tf}: the stored series starts {first} (UTC), later than the reference {ref[tf]}"
            )
    if reasons:
        return StartCheck(False, tuple(reasons))
    out: dict[str, pd.DataFrame] = {}
    for tf, df in frames.items():
        if df is None or tf not in ref:
            continue
        if tf in need or (len(df) > 0 and _first_open(df) <= ref[tf]):
            out[tf] = _cut(df, ref[tf])
    return StartCheck(True, (), out)


def _cut(df: pd.DataFrame, first: pd.Timestamp) -> pd.DataFrame:
    """The frame from the reference's first bar on (bars that start earlier are dropped)."""
    ot = pd.to_datetime(df["open_time"], utc=True)
    return df[ot >= first].reset_index(drop=True)


def check_overlap(frame: str, stored: pd.DataFrame, broker: pd.DataFrame, tick: float) -> OverlapCheck:
    """L2's overlap check of one frame: the broker's closed bars must reach back to the stored frame's last
    bar (their first bar opens at or before it) and, over the span both cover (from the broker's first bar to
    the stored last bar), have the same bars - the same open times - with open, high, low, close within one
    ``tick``. The refusal names the frame and the first bar that disagrees."""
    if len(stored) == 0:
        return OverlapCheck(False, frame, None, f"{frame}: the stored frame is empty")
    if len(broker) == 0:
        return OverlapCheck(False, frame, None, f"{frame}: the broker returned no closed bars")
    s = stored.assign(open_time=pd.to_datetime(stored["open_time"], utc=True)).set_index("open_time")
    b = broker.assign(open_time=pd.to_datetime(broker["open_time"], utc=True)).set_index("open_time")
    s_last = pd.Timestamp(s.index.max())
    b_first = pd.Timestamp(b.index.min())
    if b_first > s_last:
        return OverlapCheck(
            False,
            frame,
            s_last,
            f"{frame}: the broker's bars start {b_first}, after the stored last bar {s_last} (a gap)",
        )
    s_span = s[s.index >= b_first]
    b_span = b[b.index <= s_last]
    only_s = s_span.index.difference(b_span.index)
    only_b = b_span.index.difference(s_span.index)
    if len(only_s) or len(only_b):
        if len(only_b) and (not len(only_s) or only_b[0] < only_s[0]):
            t = pd.Timestamp(only_b[0])
            why = "the broker has a bar the stored frame lacks"
        else:
            t = pd.Timestamp(only_s[0])
            why = "the stored frame has a bar the broker lacks"
        return OverlapCheck(False, frame, t, f"{frame}: bar {t}: {why} (another time base or a gap)")
    common = s_span.index
    for col in ("open", "high", "low", "close"):
        diff = np.abs(
            s_span.loc[common, col].to_numpy(dtype=float) - b_span.loc[common, col].to_numpy(dtype=float)
        )
        bad = np.flatnonzero(~(diff <= tick + _EPS))
        if len(bad):
            t = pd.Timestamp(common[int(bad[0])])
            return OverlapCheck(
                False,
                frame,
                t,
                f"{frame}: bar {t}: {col} differs by {diff[int(bad[0])]:.5f}, more than one tick ({tick})",
            )
    return OverlapCheck(True)
