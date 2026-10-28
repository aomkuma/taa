"""Planted bugs for audit 7: the owner's windows (dev/p4_trades.window_of - mutated in memory only, the file is never
touched), the event minutes, the active hours, plib's NY windows and the parts, against audit2/test_windows.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_windows
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AG = ROOT / "research" / "2026-10-18-moments" / "agents"
TESTS = ["research/2026-10-18-moments/agents/audit2/test_windows.py"]

WINDOW_OF = [
    ("Asia's end included", "if 7 * 60 <= m < 9 * 60:", "if 7 * 60 <= m <= 9 * 60:"),
    ("Thai time as UTC+9", 'th = t.tz_convert("Asia/Bangkok")', 'th = t.tz_convert("Asia/Tokyo")'),
    ("London 06:00-07:00 on London's clock (= 13:00 Thai only in winter)", "if 13 * 60 - london_pad <= m < 14 * 60 + london_pad:",
     'if 6 * 60 - london_pad <= (lambda x: x.hour * 60 + x.minute)(t.tz_convert("Europe/London")) < 7 * 60 + london_pad:'),
    ("New York at a fixed UTC-5", 'ny = t.tz_convert("America/New_York")', 'ny = t.tz_convert("Etc/GMT+5")'),
    ("New York's window 1 hour", "if 9 * 60 + 30 <= mn < 11 * 60 + 30:", "if 9 * 60 + 30 <= mn < 10 * 60 + 30:"),
]
FOOTPRINTS = [
    ("the event clock in UTC", "    loc = t.tz_convert(zone)\n    mod = (loc.hour * 60 + loc.minute).to_numpy()\n    return np.clip",
     '    loc = t.tz_convert("UTC")\n    mod = (loc.hour * 60 + loc.minute).to_numpy()\n    return np.clip'),
]
PULLBACK15 = [
    ("the fix on GMT all year", '("Europe/London", 15 * 60)', '("Etc/GMT", 15 * 60)'),
    ("the NY open on EST all year", '(("America/New_York", 9 * 60 + 30),', '(("Etc/GMT+5", 9 * 60 + 30),'),
    ("the active edge exclusive", "out |= np.abs(mod - minute) <= minutes", "out |= np.abs(mod - minute) < minutes"),
]
PLIB = [
    ("the windows on the UTC clock", "        loc = idx.tz_convert(zone)\n", '        loc = idx.tz_convert("UTC")\n'),
]
M15 = [
    ("a part's end included", '(t >= pd.Timestamp(a, tz="UTC")) & (t < pd.Timestamp(b, tz="UTC"))',
     '(t >= pd.Timestamp(a, tz="UTC")) & (t <= pd.Timestamp(b, tz="UTC"))'),
    ("P2 starts a day late", '"P2": ("2026-01-16", "2026-04-18")', '"P2": ("2026-01-17", "2026-04-18")'),
]
TARGETS = [
    ("p4_trades", AG / "dev" / "p4_trades.py", TESTS, WINDOW_OF),
    ("footprints", AG / "precursors" / "footprints.py", TESTS, FOOTPRINTS),
    ("pullback15", AG / "precursors" / "pullback15.py", TESTS, PULLBACK15),
    ("plib", AG / "precursors" / "plib.py", TESTS, PLIB),
    ("m15_trades", AG / "precursors" / "m15_trades.py", TESTS, M15),
]
