"""The app's reader lines (app/strategy/readout.py) against the research scripts' own filtered output, byte for
byte (TAA-1804; needs data/history). Also the planted-bug test for readout.py.

    .venv/Scripts/python -m pytest research/2026-10-23-entry/test_readout_parity.py -q
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "knowledge"))
import ai_trader  # noqa: E402
import kb  # noqa: E402
from observe import read_all  # noqa: E402

from app.strategy.readout import reader_lines  # noqa: E402

TIMES = ["2026-10-23T09:00", "2026-10-23T14:40", "2026-01-29T15:00", "2026-10-21T02:05", "2026-09-04T15:30"]  # the last: H1 vol 1.38


@pytest.fixture(scope="module")
def frames():
    return kb.frames()


@pytest.mark.parametrize("when", TIMES)
def test_the_same_lines_as_the_research_scripts(frames, when):
    t = pd.Timestamp(when, tz="UTC")
    assert reader_lines(frames, t) == ai_trader.trim_reads(read_all(t)).split("\n")
