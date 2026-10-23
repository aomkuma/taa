"""Planted bugs for app/strategy/readout.py against the byte-for-byte parity with the research scripts
(test_readout_parity.py; plant.main; TAA-1804).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_readout.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("the rhythm's name for a down rhythm without the big trend", [('name = "down (big trend not)" if down else', 'name = "down" if down else')]),
    ("the ATR to one decimal", [("f\"{tf:3s} ATR {atr:6.2f} | big trend", "f\"{tf:3s} ATR {atr:6.1f} | big trend")]),
    ("the push / pullback words swapped", [('with_rhythm = (sign < 0 and k == 1) or (sign > 0 and k == -1)', 'with_rhythm = (sign < 0 and k == -1) or (sign > 0 and k == 1)')]),
    ("the M5 scan from the stored M5 window", [("m1 = fr.m1[(fr.m1.index >= as_of - pd.Timedelta(minutes=5 * 1400)) & (fr.m1.index < as_of)]", "m1 = fr.m1[(fr.m1.index >= as_of - pd.Timedelta(minutes=5 * 300)) & (fr.m1.index < as_of)]")]),
    ("UP steps on 3 of 5", [('"UP steps" if hl >= last - 2 and hh >= last - 2 else', '"UP steps" if hl >= last - 3 and hh >= last - 3 else')]),
    ("a squeeze under 2.5 ATR", [("{' (a squeeze)' if rng < 3 else ''}", "{' (a squeeze)' if rng < 2.5 else ''}")]),
    ("two strong levels a side", [("key=lambda x: x.price)[:3]", "key=lambda x: x.price)[:2]")]),
    ("the elephant at 1.3", [("if vol > 1.4 or rng > 2:", "if vol > 1.3 or rng > 2:")]),
    ("the signals of the UTC day", [('day_start = as_of.tz_convert("Europe/Athens").normalize().tz_convert("UTC").value', 'day_start = as_of.normalize().value')]),
    ("the picture from 60 bars", [("PICTURE_N, PICTURE_SIZE = 72, 1.0", "PICTURE_N, PICTURE_SIZE = 60, 1.0")]),
]

if __name__ == "__main__":
    main("app.strategy.readout", ROOT / "research/2026-10-23-entry/test_readout_parity.py", BUGS)
