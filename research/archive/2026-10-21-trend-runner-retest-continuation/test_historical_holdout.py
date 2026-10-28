"""The M1-bar eligibility of the 2021-2023 replay is retired (bug B8); its replacement is tested in
test_source_ticks.py (trailed stop before +1R is eligible; +1R before the stop is not)."""

from __future__ import annotations

import pandas as pd
import pytest
from run_historical_holdout import main, source_stopped_before_1r


def test_m1_eligibility_refuses_to_run():
    frame = pd.DataFrame(
        {"high": [100.5], "low": [99.0], "spread": [0.0]},
        index=pd.date_range("2022-01-03", periods=1, freq="min", tz="UTC"),
    )
    with pytest.raises(RuntimeError, match="bug B8"):
        source_stopped_before_1r(frame, frame.index[0], frame.index[0], 1, 100.0, 1.0)


def test_superseded_replay_refuses_to_run():
    with pytest.raises(SystemExit, match="Superseded"):
        main()
