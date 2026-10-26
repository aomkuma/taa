"""Planted bugs in d1_regime / the brake's side: the tests must fail on each."""

import subprocess, sys
from pathlib import Path

ROOT = Path(r"C:\Users\korap\taa")
MUT = [
    ("app/strategy/knowledge.py", "    if last > mean > before:\n", "    if last > mean:\n"),
    ("app/strategy/knowledge.py", "    if last < mean < before:\n", "    if last < mean > before:\n"),
    (
        "app/strategy/knowledge.py",
        "    before = float(np.mean(closes[-n:-REGIME_SLOPE]))\n",
        "    before = float(np.mean(closes[-n:]))\n",
    ),
    ("app/strategy/knowledge.py", "    if len(closes) < n:\n", "    if len(closes) < REGIME_MEAN:\n"),
    ("app/ai/trader.py", '        and e.get("side") in (None, side)\n', ""),
    (
        "app/ai/trader.py",
        '        and e.get("side") in (None, side)\n',
        '        and e.get("side") in (None, "SELL")\n',
    ),
]
caught = 0
for f, old, new in MUT:
    p = ROOT / f
    src = p.read_text(encoding="utf-8")
    assert src.count(old) == 1, old
    p.write_text(src.replace(old, new), encoding="utf-8")
    try:
        r = subprocess.run(
            [
                str(ROOT / ".venv/Scripts/python"),
                "-m",
                "pytest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "tests/unit/test_ai_trader.py",
                "tests/unit/test_strategy_knowledge.py",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        ok = r.returncode != 0
    finally:
        p.write_text(src, encoding="utf-8")
    caught += ok
    print("caught" if ok else "MISSED", f, new.strip()[:60] or "(line removed)")
print(f"{caught}/{len(MUT)}")
