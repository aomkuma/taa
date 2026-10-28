"""The measurer's own planted bugs in dev2's swings.py (V3-1), run against dev2's test_swings.py on a copy in a sibling
folder (agents/_mut_v31, the same depth as dev2/, removed after), so dev2's files are never touched.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/plant_dev2_v31.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

AG = Path(__file__).resolve().parents[1]
SRC, MUT = AG / "dev2", AG / "_mut_v31"
BUGS = [
    ("S read 1 bar early (H1 complete by t: right -> left)",
     'k = np.searchsorted(_ns(m_h1["avail"]), t_ns, side="right") - 1', 'k = np.searchsorted(_ns(m_h1["avail"]), t_ns, side="left") - 1'),
    ("S factor 0.6 -> 0.5", "S_ATR = 0.6", "S_ATR = 0.5"),
    ("first pivot needs > thr", "if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr[i]:", "if hi_i != lo_i and h[hi_i] - lo[lo_i] > thr[i]:"),
    ("peak reversal: elif -> if (the new-high bar may also reverse)", "            elif h[ext] - lo[i] >= thr[i]:", "            if h[ext] - lo[i] >= thr[i]:"),
    ("trough reversal measured from the bar's low", "            elif h[i] - lo[ext] >= thr[i]:", "            elif lo[i] - lo[ext] >= thr[i]:"),
    ("running leg includes the pivot bar", "s = slice(int(pb[-1]) + 1, d + 1)", "s = slice(int(pb[-1]), d + 1)"),
    ("known_at counts pivots confirmed on the next bar", 'n = int(np.searchsorted(piv[3], d, side="right"))', 'n = int(np.searchsorted(piv[3], d + 1, side="right"))'),
    ("side buy allows H1 against", "buy = (d1 == 1) & (h4 == 1) & (h1 != -1)", "buy = (d1 == 1) & (h4 == 1)"),
    ("side sell needs H1 down", "sell = (d1 == -1) & (h4 == -1) & (h1 != 1)", "sell = (d1 == -1) & (h4 == -1) & (h1 == -1)"),
    ("trend down ignores the third TF", "dn = (a == -1) & (b == -1) & (c == -1)", "dn = (a == -1) & (b == -1)"),
    ("readings take the next bar (look-ahead)", 'out[f"{tf}_{what}"] = np.where(j >= 0, v[np.maximum(j, 0)], np.nan)',
     'out[f"{tf}_{what}"] = np.where(j >= 0, v[np.minimum(j + 1, len(v) - 1)], np.nan)'),
    ("TF threshold ignores the TF ATR", "return np.maximum(s, TF_ATR * a)", "return np.maximum(s, 0 * a)"),
]


def main() -> None:
    py = sys.executable
    base = SRC / "swings.py"
    text = base.read_text(encoding="utf-8")
    caught = 0
    try:
        for name, old, new in BUGS:
            assert text.count(old) == 1, f"not unique / not found: {name}"
            if MUT.exists():
                shutil.rmtree(MUT)
            MUT.mkdir()
            for f in ("swings.py", "test_swings.py"):
                shutil.copy(SRC / f, MUT / f)
            (MUT / "swings.py").write_text(text.replace(old, new), encoding="utf-8", newline="\n")
            r = subprocess.run([py, "-m", "pytest", str(MUT / "test_swings.py"), "-q", "-p", "no:cacheprovider", "-x"],
                               capture_output=True, text=True, env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
            last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
            ok = r.returncode != 0
            caught += ok
            print(f"{'CAUGHT' if ok else 'MISSED'}  {name}  | {last}")
    finally:
        if MUT.exists():
            shutil.rmtree(MUT)
    print(f"{caught} / {len(BUGS)} caught")


if __name__ == "__main__":
    main()
